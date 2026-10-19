"""Canonical +1 targets, incarnation receipts and next-controller untap."""
import pytest

from effects.registry import resolve_effect
from game_state.state import Zone
from rules_engine.named_counters import untap_permanent
from rules_engine.loyalty_instructions import begin_turn, timing
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_compleated_loyalty_full import (
    cast_walker, activate, settle, reject, raw_card, SEED, next_main)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shape', ['zero', 'empty_list', 'singular', 'list'])
def test_canonical_up_to_one_target_and_actual_next_untap(seat, shape):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    targets = {'zero': {}, 'empty_list': {'target_card_ids': []},
        'singular': {'target_card_id': target.id}, 'list': {'target_card_ids': [target.id]}}[shape]
    state = settle(activate(state, seat, cid, 0, targets))
    assert state.cards[cid].loyalty == 6
    target = state.cards[target.id]
    selected = shape in {'singular', 'list'}
    assert target.tapped == selected
    assert len([p for p in state.loyalty_permissions if p.get('kind') == 'next_untap_lock']) == int(selected)
    if selected:
        state.active_player = 3-seat
        state.turn += 1
        begin_turn(state)
        assert not untap_permanent(state, target.id, turn_based=True)
        assert target.tapped
        assert untap_permanent(state, target.id, turn_based=True)
        assert not target.tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['land', 'walker', 'hexproof', 'two', 'mixed', 'enemy_player'])
def test_freeze_target_boundaries_reject_before_positive_cost(seat, bad):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    other = raw_card(state, SEED['Forest'], seat, Zone.BATTLEFIELD)
    targets = {'target_card_id': target.id}
    if bad == 'land': targets = {'target_card_id': other.id}
    elif bad == 'walker': targets = {'target_card_id': cid}
    elif bad == 'hexproof': add_keyword_effect(state, target.id, ['hexproof'])
    elif bad == 'two': targets = {'target_card_ids': [target.id, target.id]}
    elif bad == 'mixed': targets['target_card_ids'] = [target.id]
    else: targets = {'target_player': 3-seat}
    reject(state, seat, {'type': 'activate_loyalty', 'card_id': cid, 'ability_index': 0, 'targets': targets})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('change', ['reentry', 'hexproof', 'type'])
def test_freeze_revalidates_target_at_resolution(seat, change):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    state = activate(state, seat, cid, 0, {'target_card_id': target.id})
    target = state.cards[target.id]
    if change == 'reentry':
        target.move_to_zone(Zone.EXILE)
        target.move_to_zone(Zone.BATTLEFIELD)
    elif change == 'hexproof': add_keyword_effect(state, target.id, ['hexproof'])
    else:
        # Controlled layer boundary, not a claimed naturally paid type-change spell.
        target.types = ['Land']
    state = settle(state)
    assert not state.cards[target.id].tapped
    assert not state.loyalty_permissions


@pytest.mark.parametrize('seat', [1, 2])
def test_freeze_follows_control_ordinary_untap_does_not_consume(seat):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    state = settle(activate(state, seat, cid, 0, {'target_card_ids': [target.id]}))
    resolve_effect(state, seat, 'change_control', {'target_card_id': target.id})
    resolve_effect(state, seat, 'exile', {'target_card_id': cid})
    assert untap_permanent(state, target.id)
    assert state.loyalty_permissions
    state.turn += 1
    state.active_player = seat
    begin_turn(state)
    assert not untap_permanent(state, target.id, turn_based=True)
    assert not state.loyalty_permissions
    state.cards[target.id].tapped = True
    assert untap_permanent(state, target.id, turn_based=True)


@pytest.mark.parametrize('seat', [1, 2])
def test_freeze_is_not_flash_permission_and_stale_lock_cannot_follow_reentry(seat):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], seat, Zone.BATTLEFIELD)
    state = settle(activate(state, seat, cid, 0, {'target_card_id': target.id}))
    sorcery = raw_card(state, SEED['Ponder'], seat, Zone.HAND)
    assert timing(state, sorcery, seat) == (True, False)
    target = state.cards[target.id]
    target.move_to_zone(Zone.EXILE)
    target.move_to_zone(Zone.BATTLEFIELD)
    target.tapped = True
    assert untap_permanent(state, target.id, turn_based=True)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_public_untap_step_skips_exactly_once_with_stun_preserved(seat):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    state = settle(activate(state, seat, cid, 0, {'target_card_id': target.id}))
    state.cards[target.id].counters['stun'] = 1
    state = next_main(state, 3-seat)
    assert state.cards[target.id].tapped
    assert state.cards[target.id].counters['stun'] == 1
    assert not state.loyalty_permissions
    state = next_main(state, 3-seat)
    assert state.cards[target.id].tapped and 'stun' not in state.cards[target.id].counters
    state = next_main(state, 3-seat)
    assert not state.cards[target.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_two_copied_locks_expire_together_at_one_real_untap(seat):
    state, cid = cast_walker(seat)
    target = raw_card(state, SEED['Llanowar Elves'], 3-seat, Zone.BATTLEFIELD)
    state = activate(state, seat, cid, 0, {'target_card_id': target.id})
    from tests.test_compleated_loyalty_full import FIX, act
    import json
    engine = raw_card(state, json.loads((FIX.parent / 'archangel_pair/lithoform-engine.json').read_bytes()), seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id, 'ability_index': 0,
        'targets': {'target_stack_id': state.stack[-1].id}})
    from rules_engine.stack_engine import resolve_top_of_stack
    assert not resolve_top_of_stack(state), 'Native copy resolution pauses for a deliberate keep choice'
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    state = settle(state)
    assert len(state.loyalty_permissions) == 2
    state = next_main(state, 3-seat)
    assert state.cards[target.id].tapped and not state.loyalty_permissions
    state = next_main(state, 3-seat)
    assert not state.cards[target.id].tapped
