"""Finite real-source controls and declared protocol mutations; no SQL/fake outcomes."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from ai import sideboard_facts as facts, sideboard_policy as policy
from ai.information import decision_view
from card_data.hydration import hydrate_deck_cards
from game_state.state import MatchFactory, draw_card
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from knowledge.profiles import _face
import main

from tests.test_sideboard_finished_transition import episode, metadata, MetadataRows, act, settle


@pytest.mark.parametrize('pid', [1, 2])
def test_actual_damage_source_and_terminal_witness_delivery(pid, metadata):
    calls = []
    original = facts.record_event
    def observe(state, event, payload):
        if event == 'damage_dealt':
            calls.append((payload['source_card_id'], payload['target_player'], payload['amount']))
        return original(state, event, payload)
    with patch.object(facts, 'record_event', side_effect=observe):
        match = episode(pid, 60, metadata)
    assert len(calls) == 1
    cid, victim, amount = calls[0]
    assert victim == 3-pid and amount == 3
    assert match.state.sideboard_facts['inventory'][cid]['stock_key'] == 'Lightning Bolt'
    assert cid in match.state.sideboard_facts['seats'][str(pid)]['protected']
    assert match.state.sideboard_facts['terminal_winner'] == pid


@pytest.mark.parametrize('pid', [1, 2])
def test_actual_cycling_hand_source_protects_whole_entry(pid, metadata):
    from game_state.state import Step, Zone
    from rules_engine.engine import RulesEngine
    deck = hydrate_deck_cards(metadata, [{'card_name': 'Forest', 'quantity': 56},
                                       {'card_name': 'Migration Path', 'quantity': 4}])
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=13)
    state.pregame_pending = False
    state.active_player = state.priority_player = pid
    state.step = Step.PRECOMBAT_MAIN
    state.players[pid].mana_pool = {'G': 2}
    for _ in range(len(state.players[pid].library)-1):
        draw_card(state, pid)
    offered = RulesEngine().legal_moves(state, pid)
    move = next(move for move in offered if move['type'] == 'cycle_card'
                and state.cards[move['card_id']].name == 'Migration Path')
    cid = move['card_id']
    # Materialize the actual offered cycling ability, not a guessed source ID.
    from ai.agent import AIAgent
    action = AIAgent()._materialize_action(state, move, pid)
    result = act(state, pid, action)
    assert result.cards[cid].zone == Zone.GRAVEYARD
    assert result.players[pid].mana_pool['G'] == 0
    assert cid in result.sideboard_facts['seats'][str(pid)]['protected']
    assert not any(result.sideboard_facts['inventory'][other]['stock_key'] == 'Migration Path'
                   for other in facts.held_unused_ids(result, pid))


@pytest.mark.parametrize('pid', [1, 2])
def test_real_printed_draw_trigger_source_delivered_without_fake_event(pid, metadata):
    from game_state.state import Step
    from rules_engine.engine import RulesEngine
    deck = hydrate_deck_cards(metadata, [{'card_name': 'Swamp', 'quantity': 56},
                                       {'card_name': 'Sheoldred, the Apocalypse', 'quantity': 4}])
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=13)
    state.pregame_pending = False
    state.active_player = state.priority_player = pid
    state.step = Step.PRECOMBAT_MAIN
    state.players[pid].mana_pool = {'B': 4}
    for _ in range(len(state.players[pid].library)-1):
        draw_card(state, pid)
    menu = RulesEngine().legal_moves(state, pid)
    source = next(move['card_id'] for move in menu if move['type'] == 'cast_spell')
    state = act(state, pid, {'type': 'cast_spell', 'card_id': source})
    state = settle(state)
    calls = []
    original = facts.protect_source
    def observe(game, cid):
        calls.append(cid)
        return original(game, cid)
    with patch.object(facts, 'protect_source', side_effect=observe):
        draw_card(state, pid)
    assert source in calls
    assert any(item.source_card_id == source for item in state.stack)
    state = settle(state)
    assert state.players[pid].life == 22


@pytest.mark.parametrize('pid', [1, 2])
def test_projection_terminal_and_old_foundation_schema_never_requalify(pid, metadata):
    match = episode(pid, 60, metadata)
    public, _ = decision_view(match.state, pid, [])
    assert not facts.seal_game(public)
    assert facts.summary_for(public, pid) == {'qualified': False}
    raw = serialize_match_snapshot(match.state)
    for field in ('capture_version', 'coverage_ok', 'terminal_winner'):
        del raw['sideboard_facts'][field]
    restored = deserialize_match_snapshot(raw)
    assert not facts.seal_game(restored)
    assert facts.summary_for(restored, pid) == {'qualified': False}


@pytest.mark.parametrize('mutation', ['bool_winner', 'unearned_complete', 'coverage_false'])
def test_protocol_malformed_completed_snapshot_is_rejected(mutation, metadata):
    # Explicit serialized-value negative, never evidence of an actual game result.
    match = episode(1, 60, metadata)
    main._post_step_finalize(match, None)
    raw = serialize_match_snapshot(match.state)
    if mutation == 'bool_winner':
        raw['sideboard_facts']['terminal_winner'] = True
    elif mutation == 'unearned_complete':
        raw['sideboard_facts']['terminal_winner'] = None
    else:
        raw['sideboard_facts']['coverage_ok'] = False
    original = deepcopy(raw)
    with pytest.raises(ValueError):
        deserialize_match_snapshot(raw)
    assert raw == original


def test_invalid_auto_flag_is_not_coerced():
    from pydantic import ValidationError
    payload = {'deck_a': [{'card_name': 'Forest', 'quantity': 60}],
               'deck_b': [{'card_name': 'Island', 'quantity': 60}]}
    assert main.StartMatchRequest(**payload).auto_sideboard is True
    assert main.StartMatchRequest(**payload, auto_sideboard=False).auto_sideboard is False
    for invalid in (1, 0, 'false', None):
        with pytest.raises(ValidationError):
            main.StartMatchRequest(**payload, auto_sideboard=invalid)


@pytest.mark.parametrize('pid', [1, 2])
def test_unavailable_source_context_stays_sticky_unknown_not_complete(pid, metadata):
    # Missing-source protocol negative on an actually earned completed position.
    match = episode(pid, 60, metadata)
    main._post_step_finalize(match, None)
    assert facts.summary_for(match.state, pid)['qualified'] is True
    facts.protect_source(match.state, None)
    assert match.state.sideboard_facts['coverage_ok'] is False
    assert match.state.sideboard_facts['complete'] is False
    assert not facts.seal_game(match.state)
    assert facts.summary_for(match.state, pid) == {'qualified': False}


def test_shared_target_reader_not_tags_alone_matches_artifact_role():
    # Pure profile protocol controls using existing closed grammar, NOT canonical
    # card admission or a claim of measured gameplay quality.
    creature = _face({'name': 'Diagnostic', 'type_line': 'Instant', 'mana_cost': '{1}{W}',
                      'oracle_text': 'Destroy target creature.'}, None, None)
    artifact = _face({'name': 'Diagnostic', 'type_line': 'Instant', 'mana_cost': '{1}{W}',
                      'oracle_text': 'Destroy target artifact.'}, None, None)
    observed = {'observed_types': ['Creature'], 'observed_creature_count': 6,
                'own_creature_count': 0, 'public_type_groups': [['Creature']]}
    assert policy._fit(creature, observed, 'Destroy target creature.') == 2
    assert policy._fit(artifact, observed, 'Destroy target artifact.') == 0
