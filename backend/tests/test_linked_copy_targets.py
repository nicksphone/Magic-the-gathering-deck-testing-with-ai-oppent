"""Independent choices for canonical controller-linked spell copies."""
import json
from pathlib import Path

import pytest

from effects.handlers import copy_spell, counter_spell
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_linked_damage_targets import position, raw_card
from tests.test_ai_recurring_engines import add


def copied_position(seat=1, primary='player', paid=False, extra_walker=False):
    state, spell, first, walker, targets = position(seat, primary)
    second = add(state, 'Torrential Gearhulk', seat)
    if extra_walker:
        raw = json.loads((Path(__file__).parent / 'fixtures/coupled_targets/ugin.json').read_text())
        raw_card(state, raw, seat, Zone.BATTLEFIELD)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    original = state.stack[-1].id
    copier = 3-seat
    if paid:
        raw = json.loads((Path(__file__).parent / 'fixtures/coupled_targets/twincast.json').read_text())
        twincast = raw_card(state, raw, copier, Zone.HAND)
        state.players[copier].mana_pool = {'U': 2}
        state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
        state = checked_action(state, RulesEngine(), copier,
                               {'type': 'cast_spell', 'card_id': twincast.id, 'targets': {'target_stack_id': original}})
        from tests.test_real_ordered_spell_copy import pass_twice
        state = pass_twice(state)
        assert state.pending_mechanic_choice is not None
        assert state.players[copier].mana_pool['U'] == 0
    else:
        copy_spell(state, copier, {'target_stack_id': original, 'may_choose_new_targets': True})
    return state, original, first.id, second.id, walker.id if walker else None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('primary', ['player', 'planeswalker'])
@pytest.mark.parametrize('paid', [False, True])
def test_linked_copy_independent_retarget_choices_survive_original_counter_and_reload(seat, primary, paid):
    state, original, first, second, _ = copied_position(seat, primary, paid)
    copier = 3-seat
    assert state.pending_mechanic_choice['linked_target_index'] == 0
    copied_id = state.stack[-1].id
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), copier,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_player:{seat}']})
    assert state.pending_mechanic_choice['linked_target_index'] == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), copier,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{second}']})
    assert state.pending_mechanic_choice is None
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.payload['__announced_targets'] == {'target_player': seat, 'target_card_id': second}
    assert next(item for item in state.stack if item.id == original).payload['target_instances'][1]['id'] == first
    state.land_entries_this_turn[copier] = 1
    counter_spell(state, copier, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert state.players[seat].life == 17
    assert state.cards[second].counters.get('__damage_marked') == 3
    assert state.cards[first].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_linked_copy_wrong_owner_or_wrong_dependency_preserves_snapshot(seat):
    state, _, first, second, _ = copied_position(seat)
    assert state.pending_mechanic_choice is not None
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_player:{seat}']})
    assert f'target_card_id:{first}' not in state.pending_mechanic_choice['options']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat,
                       {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{first}']})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_ai_redirects_harmful_linked_copy_for_each_style_and_seat(seat, style):
    from ai.agent import AIAgent
    state, original, _, second, _ = copied_position(seat)
    copier = 3-seat
    assert state.pending_mechanic_choice is not None
    ai = AIAgent(difficulty='master', archetype=style)
    for option in [f'target_player:{seat}', f'target_card_id:{second}']:
        before = serialize_match_snapshot(state)
        decision = ai.choose_action(state, RulesEngine().legal_moves(state, copier), copier)
        assert decision.action == {'type': 'choose_mechanic', 'card_ids': [option]}
        assert serialize_match_snapshot(state) == before
        state = checked_action(state, RulesEngine(), copier, decision.action)
    assert state.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['exile', 'return', 'hexproof'])
def test_linked_copy_keeps_old_illegal_secondary_without_recapturing_new_object(seat, change):
    state, original, first, _, _ = copied_position(seat)
    if change == 'hexproof':
        # The target becomes an opponent of the copy's controller before protection.
        resolve_effect(state, seat, 'change_control', {'target_card_id': first})
        resolve_effect(state, seat, 'grant_keyword', {'target_card_id': first, 'keyword': 'hexproof'})
    else:
        resolve_effect(state, seat, 'exile', {'target_card_id': first})
        if change == 'return':
            state.players[3-seat].exile.remove(first)
            state.cards[first].move_to_zone(Zone.BATTLEFIELD)
            state.players[3-seat].battlefield.append(first)
    for _ in range(2):
        if state.pending_mechanic_choice is None:
            break
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = checked_action(state, RulesEngine(), 3-seat,
                               {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert state.pending_mechanic_choice is None
    counter_spell(state, seat, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 19
    assert state.cards[first].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_can_switch_player_to_planeswalker_and_keep_now_invalid_creature(seat):
    state, original, first, _, _ = copied_position(seat, extra_walker=True)
    walker = next(card for card in state.cards.values() if card.name == 'Ugin, the Spirit Dragon' and card.controller == seat)
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{walker.id}']})
    assert state.pending_mechanic_choice['linked_target_index'] == 1
    state = checked_action(state, RulesEngine(), 3-seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert state.stack[-1].payload['__announced_targets'] == {'target_card_ids': [walker.id, first]}
    counter_spell(state, seat, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    assert state.cards[walker.id].loyalty == 6
    assert state.cards[first].counters.get('__damage_marked', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_new_secondary_ward_targets_only_copy_once(seat):
    state, original, _, second, _ = copied_position(seat)
    resolve_effect(state, seat, 'grant_keyword', {'target_card_id': second, 'keyword': 'ward {2}'})
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_player:{seat}']})
    copied_id = state.stack[-1].id
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_mechanic', 'card_ids': [f'target_card_id:{second}']})
    wards = [item for item in state.stack if item.effect_key == 'ward_payment']
    assert len(wards) == 1
    assert wards[0].payload['target_stack_id'] == copied_id
    assert wards[0].source_card_id == second
    assert next(item for item in state.stack if item.id == original).payload['target_instances'][1]['id'] != second
