"""Desired consumer REDs remain ordinary failures; canonical controls are separate."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ai.agent import _card_for_move
from ai.deck_analysis import analyze_deck
from ai.pending_effects import decision_projection_scope
from card_data.hydration import hydrate_deck_cards
from card_data.tactical import canonical_tactical_tags
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from knowledge.models import CardKnowledge
from persistence.repository import Repository
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_value
from tests.ai_knowledge_consumer_fixture import (actor, deck, emit, modal_case,
    position, receipt, reservation_case, take, view_and_moves)


@pytest.mark.parametrize('style,expected', [('Tempo', 'Tempo'), ('Dimir Control', 'Control'),
                                         ('Ramp', 'Ramp'), ('Tokens', 'Tokens')])
def test_actual_builtin_analysis_profile_fields_are_connected(style, expected):
    hydrated = deck(style)
    summary = analyze_deck(hydrated)
    assert summary['primary_archetype'] == expected
    ai = actor(expected, 'Control' if expected == 'Ramp' else 'Ramp')
    emit('deck-' + style, {'hydrated': hydrated, 'analysis': summary, 'profile': ai.matchup_profile})
    assert all(isinstance(ai.matchup_profile[key], float) for key in
               ('proactive_bias', 'holdup_bias', 'risk_tolerance'))
    assert analyze_deck(deepcopy(hydrated)) == summary


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Tempo', 'Control'])
def test_same_seed_private_legal_scoring_materializer_and_restart_controls(seat, style):
    state, draw, answer, _ = reservation_case(seat, style)
    replica, _, _, _ = reservation_case(seat, style)
    assert serialize_match_snapshot(state) == serialize_match_snapshot(replica)
    before = serialize_match_snapshot(state)
    ai = actor(style)
    row = receipt(state, seat, ai)
    restored = deserialize_match_snapshot(before)
    assert receipt(restored, seat, actor(style)) == row
    altered = deepcopy(state)
    for player in altered.players.values():
        player.library.reverse()
    enemy = altered.players[3-seat]
    held = enemy.hand[0]
    replacement = next(cid for cid in enemy.library if altered.cards[cid].name == 'Arboreal Grazer')
    enemy.hand[0] = replacement
    enemy.library[enemy.library.index(replacement)] = held
    altered.cards[held].move_to_zone(Zone.LIBRARY)
    altered.cards[replacement].move_to_zone(Zone.HAND)
    hidden_row = receipt(altered, seat, actor(style))
    for key in ['legal_moves', 'profile', 'board_role', 'ranked', 'cast_rows']:
        assert hidden_row[key] == row[key]
    draw_row = next(item for item in row['cast_rows'] if item['legal_move']['card_id'] == draw.id)
    announced = checked_action(state, RulesEngine(), seat, draw_row['materialized'])
    assert draw.id not in announced.players[seat].hand
    assert answer.id in announced.players[seat].hand
    assert serialize_match_snapshot(state) == before
    emit(f'controls-{style}-{seat}', row)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('role', ['race', 'convert'])
def test_selected_adventure_matchup_adjustment_matches_actual_face_desired(seat, role):
    state, source = modal_case(seat, role)
    before = serialize_match_snapshot(state)
    view, legal = view_and_moves(state, seat)
    move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == source.id
                and m.get('selected_face_index') == 1)
    ai = actor('Midrange', 'Tempo')
    surface = _card_for_move(view, move)
    assert surface.name == 'Stomp' and 'burn' in ai._spell_tags(surface)
    assert 'burn' not in ai._spell_tags(view.cards[source.id])
    assert ai._board_role(view, seat) == role
    actual = ai._matchup_move_adjustment(view, move, seat)
    face_context = deepcopy(view)
    face_context.cards[source.id] = _card_for_move(face_context, move)
    expected = ai._matchup_move_adjustment(face_context, move, seat)
    action = ai._materialize_action(view, move, seat)
    checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    emit(f'desired-face-{seat}-{role}', {'legal': move, 'actual': actual,
         'selected_face_reference': expected, 'materialized': action,
         'stored_tags': sorted(ai._spell_tags(view.cards[source.id])),
         'effective_tags': sorted(ai._spell_tags(surface)), 'snapshot': before})
    assert actual == expected, 'matchup adjustment reads stored front rather than offered cast face'


@pytest.mark.parametrize('seat', [1, 2])
def test_known_adventure_instant_lost_by_draw_has_reservation_desired(seat):
    state, draw, answer, _ = reservation_case(seat, 'Tempo')
    view, legal = view_and_moves(state, seat)
    ai = actor('Tempo')
    draw_move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == draw.id)
    answer_move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == answer.id
                       and m.get('selected_face_index') == 1)
    answer_action = ai._materialize_action(view, answer_move, seat)
    checked_action(state, RulesEngine(), seat, answer_action)
    draw_action = ai._materialize_action(view, draw_move, seat)
    spent = checked_action(state, RulesEngine(), seat, draw_action)
    answer_surface = _card_for_move(view, answer_move)
    spent_surface = _card_for_move(spent, answer_move)
    assert ai._can_pay_card_cost(view, seat, answer_surface)
    assert not ai._can_pay_card_cost(spent, seat, spent_surface)
    assert not any(m['type'] == 'cast_spell' and m.get('card_id') == answer.id
                   and m.get('selected_face_index') == 1 for m in RulesEngine().legal_moves(spent, seat))
    with decision_projection_scope(view, seat):
        value = ai._instant_value_reservation(view, draw_move, seat)
    emit(f'desired-reservation-{seat}', {'snapshot': serialize_match_snapshot(state),
         'draw_move': draw_move, 'answer_move': answer_move, 'reservation': value,
         'draw_action': draw_action, 'answer_action': answer_action,
         'payable_before': True, 'payable_after': False})
    assert value < 0, 'known legal Adventure instant is absent from stored-Instant response filter'


@pytest.mark.parametrize('seat', [1, 2])
def test_standard_counter_reservation_and_endstep_release_controls(seat):
    state, draw, answer, _ = reservation_case(seat, 'Control')
    view, legal = view_and_moves(state, seat)
    move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == draw.id)
    ai = actor('Control')
    with decision_projection_scope(view, seat):
        assert ai._instant_value_reservation(view, move, seat) == -6
    from game_state.state import Step
    view.step = Step.END_STEP
    assert ai._instant_value_reservation(view, move, seat) == 0
    assert answer.name == 'Counterspell'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Growth Spiral', 'Arboreal Grazer'])
def test_canonical_extra_land_deployment_is_a_ramp_role_desired(seat, name):
    state = position('Ramp', 'Tokens', seat)
    source = take(state, name, seat, Zone.HAND)
    take(state, 'Forest', seat, Zone.HAND)
    take(state, 'Forest', seat, Zone.BATTLEFIELD)
    take(state, 'Tropical Island', seat, Zone.BATTLEFIELD)
    view, legal = view_and_moves(state, seat)
    ai = actor('Ramp', 'Tokens')
    move = next(m for m in legal if m['type'] == 'cast_spell' and m.get('card_id') == source.id)
    action = ai._materialize_action(view, move, seat)
    announced = checked_action(state, RulesEngine(), seat, action)
    tags = ai._spell_tags(view.cards[source.id])
    emit(f'desired-ramp-{seat}-{name}', {'snapshot': serialize_match_snapshot(state),
         'tags': sorted(tags), 'oracle': source.oracle_text, 'legal': move,
         'materialized': action, 'announced_effect': announced.stack[-1].effect_key,
         'cast_bias': ai._cast_bias(view, move, seat),
         'matchup_adjustment': ai._matchup_move_adjustment(view, move, seat)})
    assert 'ramp' in tags, 'canonical extra-land deployment is absent from live role tags'


@pytest.mark.parametrize('seat', [1, 2])
def test_hybrid_tokens_real_offered_choices_and_checked_cast_control(seat):
    state = position('Tokens', 'Dimir Control', seat)
    source = take(state, 'Spectral Procession', seat, Zone.HAND)
    for _ in range(3):
        take(state, 'Plains', seat, Zone.BATTLEFIELD)
    view, legal = view_and_moves(state, seat)
    move = next(m for m in legal if m['type'] == 'cast_spell' and m.get('card_id') == source.id)
    ai = actor('Tokens', 'Control')
    assert mana_value(source.mana_cost) == 6
    assert 'token' in ai._spell_tags(source)
    action = ai._materialize_action(view, move, seat)
    result = checked_action(state, RulesEngine(), seat, action)
    assert result.stack[-1].source_card_id == source.id
    assert action['cost_choice']['id'] in {option['id'] for option in move['cost_options']}
    assert len(move['cost_options'][0]['hybrid_symbols']) == 3
    assert all(symbol['choices'] == ['2', 'W'] for symbol in move['cost_options'][0]['hybrid_symbols'])
    assert all(result.cards[cid].tapped for cid in state.players[seat].battlefield)
    emit(f'hybrid-{seat}', {'snapshot': serialize_match_snapshot(state), 'legal': move,
         'materialized': action, 'mana_value': 6, 'profile': ai.matchup_profile,
         'cast_bias': ai._cast_bias(view, move, seat)})


def test_real_persisted_canonical_facts_hydrate_but_optional_quality_is_not_a_live_input():
    raw = json.loads((Path(__file__).parent / 'fixtures/opaque_selection/memory-deluge.json').read_text())
    profile = {'card_data': raw, **canonical_tactical_tags(raw)}
    db = create_engine('sqlite://')
    SQLModel.metadata.create_all(db)
    with Session(db) as session:
        knowledge = CardKnowledge(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
                                  profiles_json=json.dumps(profile))
        session.add(knowledge)
        session.commit()
        repo = Repository(session)
        entries = [{'card_name': raw['name'], 'quantity': 1}]
        with patch.object(repo, 'get_card_knowledge_by_names', wraps=repo.get_card_knowledge_by_names) as fetch:
            original = hydrate_deck_cards(repo, entries)
            assert fetch.call_count == 1
        assert 'local_knowledge' in original[0]['card_data_sources']
        assert original[0]['oracle_text'] == raw['oracle_text']
        # Synthetic OPTIONAL quality annotations, not invented canonical card facts.
        knowledge.play_value = 9.0
        knowledge.threat_level = 9
        knowledge.cast_windows_json = '["end_step"]'
        session.add(knowledge)
        session.commit()
        changed = hydrate_deck_cards(repo, entries)
        assert changed == original
        state = __import__('game_state.state', fromlist=['MatchFactory']).MatchFactory.from_decks(original, original, seed=701)
        card = next(iter(state.cards.values()))
        assert not hasattr(card, 'play_value') and not hasattr(card, 'mechanic_metadata')
        assert actor('Control')._spell_tags(card) == set(profile['tactical_tags'])
        emit('persisted-canonical-versus-quality', {'raw_id': raw['id'], 'oracle_id': raw['oracle_id'],
             'hydration_uses_local_canonical': True, 'optional_quality_transfer': False,
             'runtime_tags': sorted(actor('Control')._spell_tags(card)), 'mechanic_surface': profile['mechanic_metadata']})
    db.dispose()
