"""Anonymous player prevention context, never fabricated typed provenance."""
from copy import deepcopy
import pytest

from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.prevention import add_player_prevention_shield
from tests.test_numeric_inventory_adapter import positive, pure_inventory


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('recipient', [1, 2])
@pytest.mark.parametrize('amount', [0, 3, -1, True, False, None],
                         ids=['zero','positive','negative','true','false','null'])
def test_player_prevention_zero_nonzero_and_malformed_context(seat, recipient, amount):
    state = positive(seat)
    assert state.numeric_prevention_shields == []
    assert pure_inventory(state, seat)['status'] == 'inert'
    if type(amount) is int and amount >= 0:
        add_player_prevention_shield(state, recipient, amount)
        # Actual legacy omission/restore only for supported scalar types.
        snapshot = serialize_match_snapshot(state)
        snapshot.pop('numeric_prevention_shields')
        state = deserialize_match_snapshot(snapshot)
    else:
        # Explicit invalid metadata injection, not a legal card instruction.
        state.players[recipient].prevent_damage_shield = amount
    result = pure_inventory(state, seat)
    assert result['status'] == ('inert' if type(amount) is int and amount == 0 else 'unknown')
    if result['status'] == 'unknown':
        assert result == {'status': 'unknown', 'reason': 'uncovered player context', 'receipts': []}
    assert state.players[recipient].prevent_damage_shield == amount
    assert state.numeric_prevention_shields == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('recipient', [1, 2])
@pytest.mark.parametrize('amount', [0, 3])
def test_player_prevention_projection_privacy_and_cold_snapshot(seat, recipient, amount):
    state = positive(seat)
    add_player_prevention_shield(state, recipient, amount)
    snapshot = serialize_match_snapshot(state)
    first, _ = decision_view(state, seat, [])
    result = pure_inventory(first, seat)
    assert result['status'] == ('inert' if amount == 0 else 'unknown')
    assert serialize_match_snapshot(state) == snapshot
    changed = deepcopy(state)
    for cid in changed.players[3-seat].hand + changed.players[3-seat].library:
        changed.cards[cid].name = 'Hidden metadata fault injection'
        changed.cards[cid].oracle_text = 'Private unknown text; not an invented gameplay card.'
    second, _ = decision_view(changed, seat, [])
    assert pure_inventory(second, seat) == result
    assert pure_inventory(deserialize_match_snapshot(serialize_match_snapshot(first)), seat) == result
    assert serialize_match_snapshot(state) == snapshot
