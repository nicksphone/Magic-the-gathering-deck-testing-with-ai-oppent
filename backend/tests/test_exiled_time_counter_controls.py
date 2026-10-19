"""Real response cards plus explicit fault boundaries, never fabricated Oracle witnesses."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import trigger_target_options
from rules_engine.suspend import collect_triggers, remove_time_counters
from tests.test_exiled_time_counter_bodies import (
    NAMES, assert_body_resolved, body_key, choose_order, choose_targets,
    one, place_raw, resume, setup,
)
from tests.test_variable_suspend_keyword import canonical_land


def response(state, seat, source, targets):
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'cast_spell', 'card_id': source.id, 'targets': targets})
    return one(resume(state))


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('countered', ['body', 'keyword'])
def test_real_stifle_counters_one_independent_last_removal_ability(name, seat, countered):
    state, cid, land = setup(name, seat, 1)
    hand = len(state.players[seat].hand)
    remove_time_counters(state, cid)
    state = choose_targets(choose_order(state, seat, name, countered == 'body'), seat, land)
    target = state.stack[-1]
    assert target.effect_key == (body_key(name) if countered == 'body' else 'suspend_cast_trigger')
    stifle = place_raw(state, 3-seat, 'backend/tests/fixtures/kozilek_trigger_audit/stifle.json', Zone.HAND)
    state.players[3-seat].mana_pool.update({'U': 1})
    state = response(state, seat, stifle, {'target_stack_id': target.id})
    assert len(state.stack) == 1
    state = one(resume(state))
    if countered == 'body':
        assert state.pending_mechanic_choice['kind'] == 'suspend_cast'
        state = checked_action(state, RulesEngine(), seat,
                               {'type': 'choose_mechanic', 'card_ids': ['decline']})
        assert len(state.players[seat].hand) == hand
        assert state.cards[land.id].zone == Zone.BATTLEFIELD
    else:
        assert_body_resolved(state, name, seat, hand, land)
        assert not state.pending_mechanic_choice
    assert not state.stack
    assert state.cards[cid].zone == Zone.EXILE




@pytest.mark.parametrize('seat', [1, 2])
def test_real_heroic_intervention_later_hexproof_invalidates_nonbasic_target(seat):
    state, cid, land = setup('Detritivore', seat)
    remove_time_counters(state, cid)
    state = choose_targets(state, seat, land)
    heroic = place_raw(state, 3-seat, 'backend/tests/fixtures/permanent_keyword_grants/heroic-intervention.json', Zone.HAND)
    state.players[3-seat].mana_pool.update({'G': 1, 'C': 1})
    state = response(state, seat, heroic, {})
    root = serialize_match_snapshot(state)
    assert trigger_target_options(state, state.stack[-1]) == []
    assert serialize_match_snapshot(state) == root
    state = one(resume(state))
    assert state.cards[land.id].zone == Zone.BATTLEFIELD
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_real_mutavault_animation_cloudshift_changes_target_identity(seat):
    state, cid, land = setup('Detritivore', seat)
    remove_time_counters(state, cid)
    state = choose_targets(state, seat, land)
    state.players[3-seat].mana_pool.update({'C': 1, 'W': 1})
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    activation = next(row for row in RulesEngine().legal_moves(state, 3-seat)
                      if row['type'] == 'activate_ability' and row['card_id'] == land.id)
    state = checked_action(state, RulesEngine(), 3-seat, activation)
    state = one(resume(state))
    sequence = state.cards[land.id].zone_change_sequence
    cloudshift = place_raw(state, 3-seat, 'backend/tests/fixtures/cloudshift_compound_audit/cloudshift.json', Zone.HAND)
    state = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'cast_spell', 'card_id': cloudshift.id, 'targets': {'target_card_id': land.id}})
    state = one(resume(state))
    assert state.cards[land.id].zone == Zone.BATTLEFIELD
    assert state.cards[land.id].zone_change_sequence > sequence
    state = one(resume(state))
    assert state.cards[land.id].zone == Zone.BATTLEFIELD and not state.stack
    assert any('target is illegal' in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
def test_protection_predicate_receipt_is_not_bypassed_by_land_route(monkeypatch, seat):
    # Fault-injected protection predicate, NOT a new canonical protection-land game claim.
    from rules_engine import targeting
    state, cid, land = setup('Detritivore', seat)
    remove_time_counters(state, cid)
    item = state.stack[-1]
    monkeypatch.setattr(targeting, 'validate_protection_targets', lambda *a, **k: (False, 'controlled denial'))
    assert trigger_target_options(state, item) == []


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('tail', ['unknown', 'multi-remove'])
def test_unsupported_instruction_corruption_or_multiple_removal_is_explicit(name, tail):
    # Deliberate corrupt input/future-event boundary, never alternate Oracle provenance.
    state, cid, land = setup(name, 1, 3)
    if tail == 'unknown':
        state.cards[cid].oracle_text += ' Unknown trailing instruction.'
        remove_time_counters(state, cid)
        assert any('Unsupported exile time-counter trigger instruction' in line for line in state.log)
    else:
        remove_time_counters(state, cid, 2)
        assert any('Unsupported multiple time-counter removal body' in line for line in state.log)
    assert not state.stack and not state.pending_trigger_order
    assert state.cards[land.id].zone == Zone.BATTLEFIELD
    assert not state.players[1].hand


@pytest.mark.parametrize('before,after', [(True, 0), (2, True), (1, 1), (1, -1)])
def test_invalid_counter_event_has_no_effect_and_query_is_pure(before, after):
    state, cid, _ = setup('Aeon Chronicler', 1)
    root = serialize_match_snapshot(state)
    assert collect_triggers(state, 'time_counters_removed', {'card_id': cid, 'before': before, 'after': after}) == []
    assert serialize_match_snapshot(state) == root


@pytest.mark.parametrize('seat', [1, 2])
def test_owner_not_stale_controller_receipt_controls_exiled_ability(seat):
    state, cid, land = setup('Detritivore', seat)
    # Stale controller field is an inventory-boundary control, not a claimed control-changing spell.
    state.cards[cid].controller = 3-seat
    remove_time_counters(state, cid)
    assert state.stack[-1].controller == seat
    receipt = state.stack[-1].payload
    assert receipt['__source_lki']['controller'] == seat
    assert receipt['__trigger_source_reference']['zone_change_sequence'] == state.cards[cid].zone_change_sequence


@pytest.mark.parametrize('name', NAMES)
def test_face_down_corruption_has_no_visible_extra_oracle_trigger(name):
    # Fault boundary: real Suspend is face up; do not leak stored Oracle from a hidden object.
    state, cid, land = setup(name, 1, 3)
    state.cards[cid].exile_face_down = True
    remove_time_counters(state, cid)
    assert not state.stack and not state.pending_trigger_order
    assert state.cards[land.id].zone == Zone.BATTLEFIELD and not state.players[1].hand
