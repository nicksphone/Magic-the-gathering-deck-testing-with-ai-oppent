"""Canonical independent target instances, real costs and partial resolution."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone, Step
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.continuous import effective_combat_stats
from effects.registry import resolve_effect
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_recurring_engines import add


RAW = json.loads((Path(__file__).parent / 'fixtures/coupled_targets/agony-warp.json').read_text())


def position(seat=1):
    state = bare_state(seat)
    sample = MatchFactory.from_decks([{**RAW, 'card_name': RAW['name'], 'quantity': 8}], [], seed=827)
    spell = deepcopy(next(iter(sample.cards.values())))
    spell.id = state.allocate_object_id()
    spell.owner = spell.controller = seat
    spell.move_to_zone(Zone.HAND)
    state.cards[spell.id] = spell
    state.players[seat].hand.append(spell.id)
    first = add(state, 'Sheoldred, the Apocalypse', 3-seat)
    second = add(state, 'Torrential Gearhulk', 3-seat)
    state.players[seat].mana_pool.update({'U': 1, 'B': 1})
    return state, spell.id, first.id, second.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shared', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_independent_modifiers_use_explicit_order_and_allow_shared_recipient(seat, shared, reverse):
    state, spell, first, second = position(seat)
    ids = [first, first] if shared else [first, second]
    if reverse:
        ids.reverse()
    base = {cid: effective_combat_stats(state, cid) for cid in set(ids)}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    assert state.players[seat].mana_pool['U'] == state.players[seat].mana_pool['B'] == 0
    from game_state.serializers import serialize_match
    public = serialize_match(state)['stack'][0]
    assert public['targets'] == ids
    assert 'payload' not in public
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    for cid in set(ids):
        power, toughness = base[cid]
        assert effective_combat_stats(state, cid) == (power-3*(cid == ids[0]), toughness-3*(cid == ids[1]))
    assert state.cards[spell].zone == Zone.GRAVEYARD
    state.step = Step.END_STEP
    RulesEngine().next_step(state)
    for cid in set(ids):
        assert effective_combat_stats(state, cid) == base[cid]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selection', ['missing', 'one', 'three', 'mixed'])
def test_incomplete_or_ambiguous_instance_announcements_reject_without_mutation(seat, selection):
    state, spell, first, second = position(seat)
    targets = {'missing': {}, 'one': {'target_card_ids': [first]},
               'three': {'target_card_ids': [first, second, first]},
               'mixed': {'target_card_ids': [first, second], 'target_card_id': first}}[selection]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell, 'targets': targets})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('departed_slot', [0, 1])
def test_only_the_illegal_target_instance_is_removed_at_resolution(seat, departed_slot):
    state, spell, first, second = position(seat)
    ids = [first, second]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    resolve_effect(state, seat, 'exile', {'target_card_id': ids[departed_slot]})
    survivor = ids[1-departed_slot]
    power, toughness = effective_combat_stats(state, survivor)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert effective_combat_stats(state, survivor) == (power-3*(departed_slot == 1), toughness-3*(departed_slot == 0))
    assert state.cards[ids[departed_slot]].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_one_creature_can_supply_both_instances_but_empty_board_has_no_cast(seat):
    state, spell, first, second = position(seat)
    resolve_effect(state, seat, 'exile', {'target_card_id': second})
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell)
    hints = move['target_hints']
    assert hints['required_target_instance_count'] == 2
    assert hints['choice_schema']['target_card_ids']['unique_items'] is False
    assert hints['choice_schema']['target_card_ids']['min_items'] == 2
    resolve_effect(state, seat, 'exile', {'target_card_id': first})
    assert not any(move.get('card_id') == spell for move in RulesEngine().legal_moves(state, seat))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('extra', ['target_player', 'target_distribution'])
def test_other_target_surfaces_cannot_be_smuggled_into_ordered_instances(seat, extra):
    state, spell, first, second = position(seat)
    targets = {'target_card_ids': [first, second], extra: seat if extra == 'target_player' else {first: 1}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell, 'targets': targets})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_ai_compares_real_modifier_assignments_without_mutating_the_board(seat, style):
    from ai.agent import AIAgent
    state, spell, first, second = position(seat)
    resolve_effect(state, seat, 'exile', {'target_card_id': first})
    small = add(state, 'Grizzly Bears', 3-seat)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell)
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty='master', archetype=style)._materialize_action(state, move, seat)
    assert action['targets']['target_card_ids'] == [second, small.id]
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), seat, action)
    assert resolve_top_of_stack(state)
    assert state.cards[small.id].zone == Zone.GRAVEYARD
    assert effective_combat_stats(state, second) == (2, 6)


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_projection_fallback_does_not_harm_a_friendly_creature(monkeypatch, seat):
    from ai.agent import AIAgent
    import ai.ordered_targets as targeting
    state, spell, first, second = position(seat)
    friendly = add(state, 'Torrential Gearhulk', seat)
    monkeypatch.setattr(targeting, '_settle_announced_stack', lambda projected: False)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell)
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty='master', archetype='Tempo')._materialize_action(state, move, seat)
    assert friendly.id not in action['targets']['target_card_ids']
    assert set(action['targets']['target_card_ids']) <= {first, second}
    assert serialize_match_snapshot(state) == before
    checked_action(state, RulesEngine(), seat, action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shared', [False, True])
def test_departure_and_return_does_not_reuse_old_target_incarnation(seat, shared):
    state, spell, first, second = position(seat)
    ids = [first, first] if shared else [first, second]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    resolve_effect(state, seat, 'exile', {'target_card_id': first})
    returned = state.cards[first]
    state.players[3-seat].exile.remove(first)
    returned.move_to_zone(Zone.BATTLEFIELD)
    state.players[3-seat].battlefield.append(first)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert effective_combat_stats(state, first) == (4, 5)
    assert effective_combat_stats(state, second) == ((5, 6) if shared else (5, 3))
    assert state.cards[spell].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shared', [False, True])
def test_all_target_instances_illegal_finish_without_any_modifier(seat, shared):
    state, spell, first, second = position(seat)
    ids = [first, first] if shared else [first, second]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    for cid in set(ids):
        resolve_effect(state, seat, 'exile', {'target_card_id': cid})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert not state.stack
    assert state.cards[spell].zone == Zone.GRAVEYARD
    if shared:
        assert effective_combat_stats(state, second) == (5, 6)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shared', [False, True])
def test_ward_triggers_per_targeted_object_not_target_instance(seat, shared):
    from tests.test_ward_resolution import add as add_ward
    state, spell, first, second = position(seat)
    for cid in [first, second]:
        resolve_effect(state, seat, 'exile', {'target_card_id': cid})
    one = add_ward(state, 'Tolarian Terror', 3-seat)
    two = add_ward(state, 'Tolarian Terror', 3-seat)
    ids = [one.id, one.id] if shared else [one.id, two.id]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    wards = [item for item in state.stack if item.effect_key == 'ward_payment']
    assert len(wards) == (1 if shared else 2)
    assert {item.source_card_id for item in wards} == set(ids)
    assert all(item.payload['ward_cost'] == '{2}' for item in wards)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('protected_slot', [0, 1])
def test_gaining_shroud_only_invalidates_its_own_instance(seat, protected_slot):
    state, spell, first, second = position(seat)
    ids = [first, second]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    # Constructed intervening keyword state; no invented printed card metadata.
    state.cards[ids[protected_slot]].keywords.append('shroud')
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert effective_combat_stats(state, first) == ((4, 5) if protected_slot == 0 else (1, 5))
    assert effective_combat_stats(state, second) == ((5, 6) if protected_slot == 1 else (5, 3))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shared', [False, True])
def test_copy_keeps_instances_and_resolves_after_original_is_countered(seat, shared):
    from effects.handlers import copy_spell, counter_spell
    state, spell, first, second = position(seat)
    ids = [first, first] if shared else [first, second]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    original = state.stack[-1].id
    copy_spell(state, seat, {'target_stack_id': original})
    copied = state.stack[-1]
    assert copied.id != original
    assert copied.payload['__announced_targets']['target_card_ids'] == ids
    counter_spell(state, 3-seat, {'target_stack_id': original})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert not state.stack
    assert effective_combat_stats(state, first) == ((1, 2) if shared else (1, 5))
    assert effective_combat_stats(state, second) == ((5, 6) if shared else (5, 3))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad_selection', ['missing', 'incomplete', 'mixed'])
def test_http_rejected_instances_preserve_complete_state_and_persisted_record(seat, bad_selection):
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from main import ACTIVE_MATCHES, MatchController, app, _persist_active_match
    from persistence.db import engine
    from persistence.repository import Repository
    state, spell, first, second = position(seat)
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    match = MatchController(state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'},
                            ai={}, mode='human_vs_human', deck_ids=(None, None),
                            mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []},
                            game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    targets = {'missing': {}, 'incomplete': {'target_card_ids': [first]},
               'mixed': {'target_card_ids': [first, second], 'target_card_id': first}}[bad_selection]
    with TestClient(app) as client:
        ACTIVE_MATCHES[state.id] = match
        try:
            with Session(engine) as session:
                repo = Repository(session)
                _persist_active_match(repo, match)
                saved = repo.get_active_match(state.id).model_dump()
            before = serialize_match_snapshot(match.state)
            rejected = client.post(f'/matches/{state.id}/action', json={
                'player_id': seat, 'action': {'type': 'cast_spell', 'card_id': spell, 'targets': targets}})
            assert rejected.status_code == 422
            assert serialize_match_snapshot(match.state) == before
            with Session(engine) as session:
                assert Repository(session).get_active_match(state.id).model_dump() == saved
            accepted = client.post(f'/matches/{state.id}/action', json={
                'player_id': seat, 'action': {'type': 'cast_spell', 'card_id': spell,
                                             'targets': {'target_card_ids': [first, second]}}})
            assert accepted.status_code == 200
            assert accepted.json()['stack'][-1]['targets'] == [first, second]
        finally:
            ACTIVE_MATCHES.pop(state.id, None)
