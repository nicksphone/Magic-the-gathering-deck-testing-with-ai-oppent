"""Real printed exile-counter bodies, independent of paid Suspend permission."""
from copy import deepcopy
import hashlib
import json

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event, trigger_target_options
from rules_engine.suspend import remove_time_counters
from tests.test_suspend_lifecycle import one
from tests.test_variable_suspend_keyword import act, canonical_land, live_position
from tests.variable_suspend_support import NAMES, PROVENANCE, RAW, ROOT, resume


def place_raw(state, seat, path, zone):
    raw = json.loads((ROOT / path).read_bytes())
    sample = MatchFactory.from_decks([{**raw, 'card_name': raw['name'], 'quantity': 1}], [], seed=177)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def setup(name, seat, count=2, land_owner=None, with_land=True):
    for fact in PROVENANCE['canonical_cards']:
        assert hashlib.sha256((ROOT / fact['path']).read_bytes()).hexdigest() == fact['sha256']
    state, cid = live_position(name, seat)
    state.trigger_order_choice_required = True
    state = act(state, seat, cid, count)
    land = canonical_land(state, land_owner or 3-seat, 'mutavault.json') if with_land else None
    state.step = Step.UPKEEP
    return state, cid, land


def body_key(name):
    return 'draw_cards' if name == 'Aeon Chronicler' else 'destroy_permanent'


def choose_targets(state, seat, land):
    if not state.pending_trigger_order:
        return state
    assert state.pending_trigger_order['phase'] == 'targets'
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert serialize_match_snapshot(state) == before
    action = next(row for row in moves if row.get('target_card_id') == land.id)
    state = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(resume(state)) == serialize_match_snapshot(state)
    return state


def choose_order(state, seat, name, body_on_top):
    pending = state.pending_trigger_order
    assert pending and pending.get('phase') != 'targets'
    rows = list(pending['groups'][str(seat)])
    assert sorted(row['effect_key'] for row in rows) == sorted([body_key(name), 'suspend_cast_trigger'])
    rows.sort(key=lambda row: (row['effect_key'] == body_key(name)) == body_on_top)
    before = serialize_match_snapshot(state)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_trigger_order', 'trigger_order': [row['_choice_id'] for row in rows]})
    assert before != serialize_match_snapshot(state)
    return state


def assert_body_resolved(state, name, seat, before_hand, land):
    if name == 'Aeon Chronicler':
        assert len(state.players[seat].hand) == before_hand + 1
    else:
        assert state.cards[land.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [2, 1])
def test_real_removal_separate_body_and_keyword_root_snapshot(name, seat, count):
    state, cid, land = setup(name, seat, count)
    root = serialize_match_snapshot(state)
    candidate = deepcopy(state)
    hand = len(candidate.players[seat].hand)
    assert remove_time_counters(candidate, cid) == 1
    assert serialize_match_snapshot(state) == root
    assert candidate.cards[cid].oracle_text == RAW[name]['oracle_text']
    if count == 1:
        candidate = choose_order(resume(candidate), seat, name, True)
    else:
        assert len(candidate.stack) == 1 and candidate.stack[-1].effect_key == body_key(name)
    candidate = choose_targets(candidate, seat, land)
    assert candidate.stack[-1].controller == seat
    candidate = one(resume(candidate))
    assert_body_resolved(candidate, name, seat, hand, land)
    assert serialize_match_snapshot(resume(candidate)) == serialize_match_snapshot(candidate)


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('body_on_top', [False, True])
def test_last_counter_order_both_permutations_actual_resolution(name, seat, body_on_top):
    state, cid, land = setup(name, seat, 1)
    hand = len(state.players[seat].hand)
    remove_time_counters(state, cid)
    state = choose_targets(choose_order(resume(state), seat, name, body_on_top), seat, land)
    for _ in range(2):
        key = state.stack[-1].effect_key
        state = one(resume(state))
        if key == 'suspend_cast_trigger':
            assert state.pending_mechanic_choice['kind'] == 'suspend_cast'
            state = checked_action(state, RulesEngine(), seat,
                                   {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert_body_resolved(state, name, seat, hand, land)
    assert not state.stack and not state.pending_trigger_order and not state.pending_mechanic_choice
    assert state.cards[cid].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['own-only', 'none', 'basic-invalid'])
def test_mandatory_nonbasic_targets_real_options_and_atomic_rejection(seat, case):
    state, cid, land = setup('Detritivore', seat, land_owner=seat, with_land=case != 'none')
    basic = canonical_land(state, 3-seat, 'island.json')
    remove_time_counters(state, cid)
    if case == 'none':
        assert not state.stack and not state.pending_trigger_order
        assert any('no legal target' in message for message in state.log)
        return
    assert state.pending_trigger_order['phase'] == 'targets'
    item = state.stack[-1]
    root = serialize_match_snapshot(state)
    assert {row['target_card_id'] for row in trigger_target_options(state, item)} == {land.id}
    assert serialize_match_snapshot(state) == root
    if case == 'basic-invalid':
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat,
                           {'type': 'choose_trigger_target', 'stack_id': item.id, 'target_card_id': basic.id})
        assert serialize_match_snapshot(state) == root
    state = choose_targets(state, seat, land)
    state = one(resume(state))
    assert state.cards[land.id].zone == Zone.GRAVEYARD
    assert state.cards[basic.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_independent_body_survives_actual_freecast_then_counterspell(name, seat):
    state, cid, land = setup(name, seat, 1)
    hand = len(state.players[seat].hand)
    remove_time_counters(state, cid)
    state = choose_targets(choose_order(state, seat, name, False), seat, land)
    state = one(resume(state))
    assert state.pending_mechanic_choice['kind'] == 'suspend_cast'
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True})
    spell = state.stack[-1]
    assert state.cards[cid].zone == Zone.STACK and spell.source_card_id == cid
    counter = place_raw(state, 3-seat, 'backend/tests/fixtures/empty_hand_attack_witness/counterspell.json', Zone.HAND)
    state.players[3-seat].mana_pool.update({'U': 2})
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'cast_spell', 'card_id': counter.id, 'targets': {'target_stack_id': spell.id}})
    state = one(resume(state))
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert state.stack[-1].effect_key == body_key(name)
    state = one(resume(state))
    assert_body_resolved(state, name, seat, hand, land)


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_inactive_upkeep_no_removal_no_independent_body(name, seat):
    state, cid, land = setup(name, seat)
    before = serialize_match_snapshot(state)
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': 3-seat})
    assert not state.stack and not state.pending_trigger_order
    assert state.cards[cid].counters['time'] == 2
    assert len(state.players[seat].hand) == len(before['players'][str(seat)]['hand'])
    assert state.cards[land.id].zone == Zone.BATTLEFIELD
