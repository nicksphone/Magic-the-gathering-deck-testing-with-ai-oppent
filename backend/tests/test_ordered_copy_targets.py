"""Ordered copy choices use canonical spells, real announcements and snapshots."""
import pytest

from effects.handlers import copy_spell, counter_spell
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.continuous import effective_combat_stats
from tests.test_ordered_creature_modifiers import position


def copied_position(seat, shared=False):
    state, spell, first, second = position(seat)
    ids = [first, first] if shared else [first, second]
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': ids}})
    original = state.stack[-1].id
    copy_spell(state, seat, {'target_stack_id': original, 'may_choose_new_targets': True})
    return state, original, first, second


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shared', [False, True])
def test_copy_allows_each_modifier_to_be_retargeted_and_resumed(seat, shared):
    state, original, first, second = copied_position(seat, shared)
    assert state.pending_mechanic_choice['ordered_target_index'] == 0
    copied_id = state.stack[-1].id
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{second}']})
    assert state.pending_mechanic_choice['ordered_target_index'] == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    selection = 'keep' if shared else f'target_card_id:{first}'
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': [selection]})
    assert state.pending_mechanic_choice is None
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.payload['__announced_targets']['target_card_ids'] == [second, first]
    assert serialize_match(state)['stack'][-1]['targets'] == [second, first]
    counter_spell(state, 3-seat, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert effective_combat_stats(state, first) == (4, 2)
    assert effective_combat_stats(state, second) == (2, 6)


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_wrong_owner_cannot_change_targets_or_pending_choice(seat):
    state, original, first, second = copied_position(seat)
    assert state.pending_mechanic_choice is not None
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat,
                       {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{second}']})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_ai_retargets_harmful_copied_modifiers_away_from_friendly_creatures(seat, style):
    from ai.agent import AIAgent
    from tests.test_ai_recurring_engines import add
    state, spell, first, second = position(seat)
    powerful = add(state, 'Torrential Gearhulk', seat)
    small = add(state, 'Grizzly Bears', seat)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': [first, second]}})
    original = state.stack[-1].id
    copier = 3-seat
    copy_spell(state, copier, {'target_stack_id': original, 'may_choose_new_targets': True})
    ai = AIAgent(difficulty='master', archetype=style)
    for target in [powerful.id, small.id]:
        before = serialize_match_snapshot(state)
        decision = ai.choose_action(state, RulesEngine().legal_moves(state, copier), copier)
        assert decision.action == {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{target}']}
        assert serialize_match_snapshot(state) == before
        state = checked_action(state, RulesEngine(), copier, decision.action)
    assert state.pending_mechanic_choice is None
    counter_spell(state, copier, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert effective_combat_stats(state, powerful.id) == (2, 6)
    from game_state.state import Zone
    assert state.cards[small.id].zone == Zone.GRAVEYARD
    assert effective_combat_stats(state, first) == (4, 5)
    assert effective_combat_stats(state, second) == (5, 6)


def distinct_copied_position(seat, departed=False):
    from game_state.state import Zone
    from tests.regression_agent_wave2.support import position as counter_position, add, cast
    from effects.registry import resolve_effect
    state = counter_position(seat)
    spell = add(state, 'Incremental Growth', seat)
    creatures = [add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD) for _ in range(3)]
    state.players[seat].mana_pool.update(G=2, U=3)
    state = cast(state, spell, {'target_card_ids': [card.id for card in creatures]})
    original = state.stack[-1].id
    if departed:
        resolve_effect(state, seat, 'exile', {'target_card_id': creatures[0].id})
    copy_spell(state, seat, {'target_stack_id': original, 'may_choose_new_targets': True})
    return state, original, [card.id for card in creatures]


@pytest.mark.parametrize('seat', [1, 2])
def test_distinct_copy_can_swap_targets_without_duplicating_final_assignment(seat):
    state, original, ids = distinct_copied_position(seat)
    for index, target in enumerate([ids[1], ids[2], ids[0]]):
        assert state.pending_mechanic_choice['ordered_target_index'] == index
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = checked_action(state, RulesEngine(), seat,
                               {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{target}']})
        if state.pending_mechanic_choice:
            assert 'keep' not in state.pending_mechanic_choice['options']
    assert state.pending_mechanic_choice is None
    counter_spell(state, 3-seat, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert [state.cards[cid].counters.get('+1/+1', 0) for cid in ids] == [3, 1, 2]


@pytest.mark.parametrize('seat', [1, 2])
def test_distinct_copy_does_not_offer_a_prefix_that_cannot_be_completed(seat):
    state, original, ids = distinct_copied_position(seat, departed=True)
    # Only two legal objects remain for three distinct instances. Keeping the old
    # illegal first target is permitted; changing to either remaining one traps
    # later instances, so those changes must not be offered.
    assert state.pending_mechanic_choice['ordered_target_index'] == 1
    assert f'target_card_id:{ids[0]}' not in state.pending_mechanic_choice['options']
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert state.pending_mechanic_choice is None
    counter_spell(state, 3-seat, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert [state.cards[cid].counters.get('+1/+1', 0) for cid in ids] == [0, 2, 3]


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_can_choose_returned_object_as_new_target_without_reusing_old_reference(seat):
    from effects.registry import resolve_effect
    from game_state.state import Zone
    state, spell, first, second = position(seat)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': [first, second]}})
    original = state.stack[-1].id
    resolve_effect(state, seat, 'exile', {'target_card_id': first})
    state.players[3-seat].exile.remove(first)
    state.cards[first].move_to_zone(Zone.BATTLEFIELD)
    state.players[3-seat].battlefield.append(first)
    copy_spell(state, seat, {'target_stack_id': original, 'may_choose_new_targets': True})
    assert f'target_card_id:{first}' in state.pending_mechanic_choice['options']
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{first}']})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    counter_spell(state, 3-seat, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert effective_combat_stats(state, first) == (1, 5)
    assert effective_combat_stats(state, second) == (5, 3)


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_shared_new_ward_target_triggers_once_after_complete_choice(seat):
    from tests.test_ward_resolution import add as add_ward
    state, spell, first, second = position(seat)
    warded = add_ward(state, 'Tolarian Terror', 3-seat)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell, 'targets': {'target_card_ids': [first, second]}})
    copy_spell(state, seat, {'target_stack_id': state.stack[-1].id, 'may_choose_new_targets': True})
    for slot in range(2):
        state = checked_action(state, RulesEngine(), seat,
                               {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{warded.id}']})
        if slot == 0:
            assert not any(item.effect_key == 'ward_payment' for item in state.stack)
            state = deserialize_match_snapshot(serialize_match_snapshot(state))
    wards = [item for item in state.stack if item.effect_key == 'ward_payment']
    assert len(wards) == 1
    assert wards[0].source_card_id == warded.id
    assert state.pending_mechanic_choice is None
