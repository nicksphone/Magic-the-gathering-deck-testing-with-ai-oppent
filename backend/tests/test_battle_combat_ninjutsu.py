"""Paid native ninjutsu after a real Battle attack in each seat."""
import pytest

from effects.handlers import prevent_damage
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.control_effects import transfer_controller
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.type_effects import add_type_effect
from tests.rings_activation_native_support_5763 import add, raw_card
from tests.test_battle_characteristics import mark
from tests.test_battle_combat import act, assert_life, attack, blocks, cold, place, position, reach


def ready(seat, *, blocked=False):
    state, battle, attacker = position(seat, ('Island',))
    place(state, seat, 'Island', Zone.BATTLEFIELD)
    name = 'Ninja of the Deep Hours'
    raw = raw_card(name)
    assert raw['object'] == 'card' and len(raw) >= 50
    assert all(raw.get(k) for k in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'layout'))
    ninja = add(state, name, state.allocate_object_id(), seat, Zone.HAND).id
    mark('Task5-native-Ninja-complete-printing-reader-returned')
    blocker = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD) if blocked else None
    state = attack(state, seat, attacker, 'battle:' + battle)
    state = blocks(state, seat, {attacker: [blocker]} if blocker else None)
    assert state.step == Step.DECLARE_BLOCKERS and state.blockers_declared
    return state, battle, attacker, ninja, blocker


def announce(state, seat, attacker, ninja):
    action = {'type': 'ninjutsu', 'card_id': ninja, 'return_card_id': attacker}
    before = sum(state.cards[cid].tapped for cid in state.players[seat].battlefield if cid != attacker)
    state = act(state, seat, action)
    assert state.cards[attacker].zone == Zone.HAND and state.cards[ninja].zone == Zone.HAND
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield) - before == 2
    assert state.stack[-1].effect_key == 'ninjutsu'
    assert not sum(state.players[seat].mana_pool.values())
    return state


def blink(state, seat, battle):
    card = state.cards[battle]
    incarnation = object_incarnation(card)
    resolve_effect(state, seat, 'exile_return_immediate', {'target_card_id': battle,
        '__announced_reference': {'incarnation': incarnation, 'zone_change_sequence': card.zone_change_sequence},
        'return_control': 'owner'})
    assert state.cards[battle].zone == Zone.BATTLEFIELD
    assert object_incarnation(state.cards[battle]) != incarnation
    for _ in range(4):
        assert state.stack
        if state.stack[-1].effect_key == 'ninjutsu':
            return state
        assert resolve_top_of_stack(state)
    raise AssertionError('Battle return trigger did not resolve above the paid activation')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_ninjutsu_cannot_rebind_to_blinked_battle(seat):
    state, battle, attacker, ninja, _ = ready(seat)
    state = cold(blink(announce(state, seat, attacker, ninja), seat, battle))
    assert resolve_top_of_stack(state)
    assert state.cards[ninja].zone == Zone.BATTLEFIELD and state.cards[ninja].tapped
    mark('Task5-native-ninjutsu-blink-no-rebind-assertion-reached')
    assert ninja not in state.attackers
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_ninjutsu_resumes_attacking_exact_same_battle(seat):
    state, battle, attacker, ninja, _ = ready(seat)
    state = cold(announce(state, seat, attacker, ninja))
    assert resolve_top_of_stack(state)
    assert state.cards[ninja].zone == Zone.BATTLEFIELD and state.cards[ninja].tapped
    assert state.attack_targets[ninja] == 'battle:' + battle and ninja in state.attackers
    state = reach(cold(state), Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters['defense'] == 1
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_ninjutsu_enters_tapped_when_current_battle_protector_is_attacker(seat):
    state, battle, attacker, ninja, _ = ready(seat)
    state = announce(state, seat, attacker, ninja)
    transfer_controller(state, state.cards[battle], 3-seat)
    apply_state_based_actions(state)
    assert state.cards[battle].battle_protector == seat
    state = cold(state)
    assert resolve_top_of_stack(state)
    assert state.cards[ninja].zone == Zone.BATTLEFIELD and state.cards[ninja].tapped
    assert ninja not in state.attackers
    state = reach(state, Step.COMBAT_DAMAGE)
    assert state.cards[battle].counters['defense'] == 3
    assert_life(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_ninjutsu_cannot_return_attacker_after_its_last_blocker_leaves_combat(seat):
    state, _, attacker, ninja, blocker = ready(seat, blocked=True)
    add_type_effect(state, blocker, ['Battle'])
    state.cards[blocker].counters['defense'] = 3
    state.cards[blocker].battle_protector = 3-seat
    apply_state_based_actions(state)
    assert state.blocks[attacker] == []
    state = cold(state)
    assert all(m['type'] != 'ninjutsu' for m in RulesEngine().legal_moves(state, seat))
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'ninjutsu', 'card_id': ninja, 'return_card_id': attacker})
    assert state.cards[attacker].zone == Zone.BATTLEFIELD and state.cards[ninja].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_planeswalker_combat_snapshot_preserves_its_ordinary_recipient(seat):
    state, _, attacker = position(seat)
    target = place(state, 3-seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    add_type_effect(state, target, ['Planeswalker'])
    state.cards[target].loyalty = 7
    prevent_damage(state, 3-seat, {'target_card_id': target, 'amount': 1})
    state = attack(state, seat, attacker, 'planeswalker:' + target)
    snapshot = serialize_match_snapshot(state)
    snapshot.pop('combat_target_context')
    state = reach(blocks(deserialize_match_snapshot(snapshot), seat), Step.COMBAT_DAMAGE)
    assert state.cards[target].loyalty == 6
    assert state.cards[target].counters['__damage_marked'] == 1
    assert_life(state)
