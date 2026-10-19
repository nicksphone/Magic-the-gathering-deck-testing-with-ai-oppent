"""INTERNALPROTOCOL resolver-interface controls, NOT paid opposite-copy proof."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import domain_paid_support as g
import test_paid_exchange_desired as original
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.exchange_energy import resolve, finish

HERE = Path(__file__).resolve().parent


def captured_state(seat):
    pins = dict(line.split(maxsplit=1)[::-1] for line in
                (HERE / 'fixtures/SHA256SUMS').read_text().splitlines())
    packets = []
    for name in (f'paid-ray-original-{seat}.json', f'paid-same-actor-copy-{seat}.json'):
        raw = (HERE / 'fixtures' / name).read_bytes()
        assert len(raw) < 4 * 1024**2
        assert hashlib.sha256(raw).hexdigest() == pins[name]
        packets.append(json.loads(raw))
    state = deserialize_match_snapshot(packets[0]['snapshot'])
    original_item = state.stack[-1]
    assert original_item.controller == seat
    payload = deepcopy(original_item.payload)
    source = payload['__exchange_source_reference'][0]
    assert state.cards[source].controller == 3-seat
    assert state.cards[payload['target_card_id']].controller == 3-seat
    template = next(item for item in packets[1]['snapshot']['stack']
                    if item['payload'].get('__stack_copy_kind'))
    assert template['controller'] == seat  # Genuine saved copy was same-actor.
    # Synthetic opposite-controller interface invocation. Never claim that the
    # saved real same-actor copy was produced by an opposite-player paid action.
    payload['__stack_copy_kind'] = template['payload']['__stack_copy_kind']
    payload['__copied_from_stack_id'] = original_item.id
    payload['__source_card_id'] = source
    target = next(cid for cid in state.players[seat].battlefield
                  if state.cards[cid].name == 'Raging Goblin')
    payload['target_card_id'] = target
    payload['__trigger_target_reference'] = [object_incarnation(state.cards[target]),
                                             state.cards[target].zone_change_sequence]
    assert payload['__exchange_controller'] == seat
    return state, payload, source, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cold', [False, True])
@pytest.mark.parametrize('pay', [False, True])
def test_INTERNALPROTOCOL_initial_actual_actor_binds_reward_and_payment(seat, cold, pay):
    state, payload, source, target = captured_state(seat)
    before_payload = deepcopy(payload)
    resolve(state, 3-seat, payload)  # Actual production resolver callback interface.
    assert payload == before_payload
    assert state.cards[source].controller == seat and state.cards[target].controller == 3-seat
    assert state.players[seat].counters.get('energy', 0) == 0
    assert state.players[3-seat].counters.get('energy', 0) == 4
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    continuation = state.pending_mechanic_choice['effect_payload']
    assert continuation['__exchange_controller'] == 3-seat
    assert continuation['__exchange_source_reference'] == before_payload['__exchange_source_reference']
    assert continuation['__trigger_target_reference'] == before_payload['__trigger_target_reference']
    if cold:
        state = g.restore(state)
    assert finish(state, 3-seat, {'type': 'choose_mechanic', 'choice_id': 'pay' if pay else 'decline'})
    assert not state.pending_mechanic_choice
    assert state.players[3-seat].counters['energy'] == (3 if pay else 4)
    assert state.players[seat].counters.get('energy', 0) == 0
    assert state.cards[target].zone == (Zone.BATTLEFIELD if pay else Zone.GRAVEYARD)
    if not pay:
        assert target in state.players[seat].graveyard
    original.record(f'actor-INTERNALPROTOCOL-bind-{pay}-{cold}-{seat}', state,
                    original_payload=before_payload, actual_interface_controller=3-seat,
                    paid_opposite_copy_certified=False)


@pytest.mark.parametrize('seat', [1, 2])
def test_INTERNALPROTOCOL_energy_continuation_wrong_actor_is_not_rebound(seat):
    state, payload, source, target = captured_state(seat)
    payload['__exchange_phase'] = 'energy'
    before = serialize_match_snapshot(state)
    resolve(state, 3-seat, payload)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('controller', [True, 0, 3, None])
def test_INTERNALPROTOCOL_invalid_actual_controller_rejects_without_changes(seat, controller):
    state, payload, source, target = captured_state(seat)
    before = serialize_match_snapshot(state)
    resolve(state, controller, payload)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_INTERNALPROTOCOL_payment_cannot_resume_under_original_actor(seat):
    state, payload, source, target = captured_state(seat)
    resolve(state, 3-seat, payload)
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    before = serialize_match_snapshot(state)
    assert not finish(state, seat, {'type': 'choose_mechanic', 'choice_id': 'pay'})
    assert serialize_match_snapshot(state) == before
