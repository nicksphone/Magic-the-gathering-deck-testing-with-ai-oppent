"""Canonical bounded Suspend; no altered Oracle, fake costs or targets."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from api_contracts import ActionRequest
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.suspend import instruction, remove_time_counters, suspended
from tests.test_ai_recurring_engines import add
from tests.test_variable_mana import clean

DIRECTORY = Path(__file__).parent / 'fixtures/suspend_canonical'
CARDS = {row['name']: {'power': None, 'toughness': None, **row} for row in
         [json.loads(p.read_text()) for p in DIRECTORY.glob('*.json') if p.name != 'provenance.json']}


def setup(seat=1, name='Rift Bolt'):
    state = clean()
    state.active_player = state.priority_player = seat
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    card = add(state, name, seat, Zone.HAND, cards=CARDS)
    state.players[seat].mana_pool = {'R': 1, 'U': 1, 'C': 1}
    return state, card.id


def act(state, seat, action):
    return checked_action(state, RulesEngine(), seat, action)


def one(state):
    assert state.stack and not state.pending_mechanic_choice
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    return act(state, state.priority_player, {'type': 'pass_priority'})


def suspend(state, seat, cid):
    return act(state, seat, {'type': 'suspend', 'card_id': cid})


def ready(state, seat, cid):
    state = suspend(state, seat, cid)
    state.step = Step.UPKEEP
    while state.cards[cid].counters.get('time', 0):
        emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
        state = one(state)
    assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    state = one(state)
    assert state.pending_mechanic_choice['kind'] == 'suspend_cast'
    return state


def restore(state):
    snap = serialize_match_snapshot(state)
    state = deserialize_match_snapshot(deepcopy(snap))
    assert serialize_match_snapshot(state) == snap
    return state


def test_canonical_records_and_supported_parse():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    for row in provenance['cards']:
        content = (DIRECTORY / row['file']).read_bytes()
        assert hashlib.sha256(content).hexdigest() == row['sha256']
        assert json.loads(content)['id'] == row['scryfall_id']
    state, cid = setup()
    assert instruction(state.cards[cid]) == (1, '{R}')
    assert instruction(SimpleNamespace(oracle_text=CARDS['Aeon Chronicler']['oracle_text'])) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count', [('Rift Bolt', 1), ('Errant Ephemeron', 4), ('Ancestral Vision', 4)])
def test_hand_special_action_no_cast_no_target_no_stack_payment_priority(seat, name, count):
    state, cid = setup(seat, name)
    snapshot = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert serialize_match_snapshot(state) == snapshot
    assert any(move['type'] == 'suspend' and move['card_id'] == cid for move in moves)
    state = suspend(state, seat, cid)
    assert state.cards[cid].zone == Zone.EXILE and not state.cards[cid].exile_face_down
    assert state.cards[cid].counters['time'] == count and suspended(state.cards[cid])
    assert state.cards[cid].oracle_text == CARDS[name]['oracle_text']
    assert not state.stack and state.priority_player == seat and state.spells_cast_this_turn[seat] == 0
    assert serialize_card_view(state, cid)['suspended']
    restore(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['unpayable', 'opponent-priority', 'upkeep', 'wrong-zone'])
def test_unavailable_special_action_atomic(seat, control):
    state, cid = setup(seat)
    if control == 'unpayable': state.players[seat].mana_pool.clear()
    elif control == 'opponent-priority': state.priority_player = 3-seat
    elif control == 'upkeep': state.step = Step.UPKEEP
    else:
        state.players[seat].hand.remove(cid)
        state.cards[cid].move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(cid)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): suspend(state, seat, cid)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_upkeep_trigger_separate_last_counter_trigger_target_only_at_cast(seat):
    state, cid = setup(seat)
    state = suspend(state, seat, cid)
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': 3-seat})
    assert not state.stack
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    assert state.stack[-1].effect_key == 'suspend_upkeep' and state.cards[cid].counters['time'] == 1
    assert not state.pending_trigger_order
    state = one(restore(state))
    assert state.stack[-1].effect_key == 'suspend_cast_trigger' and not suspended(state.cards[cid])
    assert not state.pending_mechanic_choice and state.cards[cid].zone == Zone.EXILE
    state = one(restore(state))
    state = restore(state)
    assert any(m['type'] == 'cast_spell' and m['from_exile'] for m in RulesEngine().legal_moves(state, seat))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})
    assert serialize_match_snapshot(state) == before
    life = state.players[3-seat].life
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True, 'targets': {'target_player': 3-seat}})
    assert state.cards[cid].zone == Zone.STACK and len(state.stack) == 1 and not state.pending_mechanic_choice
    assert state.spells_cast_this_turn[seat] == 1
    state = one(restore(state))
    assert state.players[3-seat].life == life-3 and state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_decline_no_counter_no_later_permission_or_duplicate(seat):
    state, cid = setup(seat)
    state = ready(state, seat, cid)
    state = act(restore(state), seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert state.cards[cid].zone == Zone.EXILE and not suspended(state.cards[cid])
    assert not state.pending_mechanic_choice and not state.stack
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True, 'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_external_counter_removal_and_departed_reference_not_reused(seat):
    state, cid = setup(seat)
    state = suspend(state, seat, cid)
    assert remove_time_counters(state, cid) == 1
    assert state.stack[-1].effect_key == 'suspend_cast_trigger'
    state.players[seat].exile.remove(cid)
    state.cards[cid].move_to_zone(Zone.HAND)
    state.players[seat].hand.append(cid)
    state = one(restore(state))
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[cid].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_countered_upkeep_or_cast_trigger_behave_differently(seat):
    state, cid = setup(seat)
    state = suspend(state, seat, cid)
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    resolve_effect(state, 3-seat, 'counter_ability', {'target_stack_id': state.stack[-1].id})
    assert not state.stack and state.cards[cid].counters['time'] == 1
    remove_time_counters(state, cid)
    resolve_effect(state, 3-seat, 'counter_ability', {'target_stack_id': state.stack[-1].id})
    assert not state.stack and not suspended(state.cards[cid]) and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_creature_haste_snapshot_control_loss_departure(seat):
    state, cid = setup(seat, 'Errant Ephemeron')
    state = ready(state, seat, cid)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})
    assert has_keyword(state, cid, 'haste')
    state = one(restore(state))
    assert state.cards[cid].zone == Zone.BATTLEFIELD and has_keyword(state, cid, 'haste')
    state = restore(state)
    resolve_effect(state, 3-seat, 'change_control', {'target_card_id': cid})
    assert not has_keyword(state, cid, 'haste')
    resolve_effect(state, seat, 'change_control', {'target_card_id': cid})
    assert not has_keyword(state, cid, 'haste')
    restore(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_creature_haste_ends_on_departure_and_spell_control_loss(seat):
    state, cid = setup(seat, 'Errant Ephemeron')
    state = ready(state, seat, cid)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})
    lost = deepcopy(state)
    lost.cards[cid].controller = 3-seat
    lost.cards[cid].controller = seat
    assert not has_keyword(restore(lost), cid, 'haste')
    state = one(state)
    resolve_effect(state, 3-seat, 'return_permanent_to_hand', {'target_card_id': cid})
    assert state.cards[cid].zone == Zone.HAND and not state.cards[cid].suspend_haste
    restore(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_no_printed_mana_cost_can_suspend_then_cast_and_draw(seat):
    state, cid = setup(seat, 'Ancestral Vision')
    assert not CARDS['Ancestral Vision']['mana_cost']
    state = ready(state, seat, cid)
    hand = len(state.players[seat].hand)
    state = act(restore(state), seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
                                    'targets': {'target_player': seat}})
    state = one(state)
    assert len(state.players[seat].hand) == hand + 3
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_real_step_start_emits_owner_upkeep_once(seat):
    state, cid = setup(seat)
    state = suspend(state, seat, cid)
    state.step = Step.UNTAP
    RulesEngine().next_step(state)
    assert state.step == Step.UPKEEP
    assert len(state.stack) == 1 and state.stack[-1].effect_key == 'suspend_upkeep'
    state = one(restore(state))
    assert len(state.stack) == 1 and state.stack[-1].effect_key == 'suspend_cast_trigger'


@pytest.mark.parametrize('seat', [1, 2])
def test_permanent_counter_prohibition_does_not_cover_exiled_suspend_card(seat):
    state, cid = setup(seat, 'Errant Ephemeron')
    add(state, 'Solemnity', 3-seat, cards=CARDS)
    state = suspend(state, seat, cid)
    assert state.cards[cid].zone == Zone.EXILE and state.cards[cid].counters['time'] == 4


@pytest.mark.parametrize('seat', [1, 2])
def test_tax_paid_at_cast_not_at_suspension_and_unpayable_cast_atomic(seat):
    from tests.test_surveil_mill import add as canonical_add
    state, cid = setup(seat)
    canonical_add(state, 'Thalia, Guardian of Thraben', 3-seat)
    state.players[seat].mana_pool = {'R': 1}
    state = ready(state, seat, cid)
    assert not any(m['type'] == 'cast_spell' for m in RulesEngine().legal_moves(state, seat))
    before = serialize_match_snapshot(state)
    action = {'type': 'cast_spell', 'card_id': cid, 'from_exile': True, 'targets': {'target_player': 3-seat}}
    with pytest.raises(ActionRejected): act(state, seat, action)
    assert serialize_match_snapshot(state) == before
    state.players[seat].mana_pool = {'C': 1}
    state = act(state, seat, action)
    assert state.players[seat].mana_pool['C'] == 0 and state.cards[cid].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
def test_exile_cast_prohibition_leaves_optional_decline_and_no_cast_permission(seat):
    state, cid = setup(seat)
    add(state, 'Drannith Magistrate', 3-seat, cards=CARDS)
    state = ready(state, seat, cid)
    assert not any(m['type'] == 'cast_spell' for m in RulesEngine().legal_moves(state, seat))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
                         'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert state.cards[cid].zone == Zone.EXILE and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_no_targets_at_suspend_but_impossible_cast_has_only_decline(seat):
    state, cid = setup(seat)
    for owner in (1, 2):
        add(state, 'Ivory Mask', owner, cards=CARDS)
    state = ready(state, seat, cid)
    moves = RulesEngine().legal_moves(state, seat)
    assert [m['type'] for m in moves] == ['choose_mechanic']
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert state.cards[cid].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_old_trigger_does_not_follow_a_reexiled_incarnation(seat):
    state, cid = setup(seat)
    state = suspend(state, seat, cid)
    remove_time_counters(state, cid)
    sequence = state.cards[cid].zone_change_sequence
    state.players[seat].exile.remove(cid)
    state.cards[cid].move_to_zone(Zone.HAND)
    state.players[seat].hand.append(cid)
    state.players[seat].mana_pool['R'] = 1
    # An explicit zone-transition fixture; ordinary sorcery timing would not
    # permit re-suspending while the old trigger is on the stack.
    state.players[seat].hand.remove(cid)
    state.cards[cid].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(cid)
    assert state.cards[cid].zone_change_sequence != sequence
    state = one(restore(state))
    assert not state.pending_mechanic_choice and state.cards[cid].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_cast_targets_can_leave_before_spell_resolution(seat):
    state, cid = setup(seat)
    target = add(state, 'Errant Ephemeron', 3-seat, Zone.BATTLEFIELD, cards=CARDS)
    state = ready(state, seat, cid)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
                             'targets': {'target_card_id': target.id}})
    resolve_effect(state, 3-seat, 'return_permanent_to_hand', {'target_card_id': target.id})
    life = state.players[3-seat].life
    state = one(restore(state))
    assert state.cards[cid].zone == Zone.GRAVEYARD and state.cards[target.id].zone == Zone.HAND
    assert state.players[3-seat].life == life and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_choice_determinism_permission_bound_to_card_owner_and_zone(seat):
    state, cid = setup(seat)
    other = add(state, 'Rift Bolt', seat, Zone.EXILE, cards=CARDS)
    state = ready(state, seat, cid)
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert moves == RulesEngine().legal_moves(restore(state), seat)
    assert serialize_match_snapshot(state) == before
    for player, action in [
        (3-seat, {'type': 'choose_mechanic', 'card_ids': ['decline']}),
        (seat, {'type': 'cast_spell', 'card_id': other.id, 'from_exile': True, 'targets': {'target_player': 3-seat}}),
        (seat, {'type': 'cast_spell', 'card_id': cid, 'from_graveyard': True, 'targets': {'target_player': 3-seat}}),
        (seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True, 'cost_choice': {'id': 'alternate'}, 'targets': {'target_player': 3-seat}}),
    ]:
        with pytest.raises(ActionRejected): act(state, player, action)
        assert serialize_match_snapshot(state) == before
    action = {'type': 'cast_spell', 'card_id': cid, 'from_exile': True, 'targets': {'target_player': 3-seat}}
    assert serialize_match_snapshot(act(state, seat, action)) == serialize_match_snapshot(act(state, seat, action))


@pytest.mark.parametrize('seat', [1, 2])
def test_root_immutability_determinism_and_typed_contract(seat):
    state, cid = setup(seat)
    before = serialize_match_snapshot(state)
    action = ActionRequest.model_validate({'player_id': seat, 'action': {'type': 'suspend', 'card_id': cid}}).action.model_dump()
    first = suspend(state, seat, cid)
    second = act(state, seat, action)
    assert serialize_match_snapshot(first) == serialize_match_snapshot(second)
    assert serialize_match_snapshot(state) == before
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({'player_id': seat, 'action': {'type': 'suspend', 'card_id': cid, 'targets': {'target_player': 3-seat}}})
