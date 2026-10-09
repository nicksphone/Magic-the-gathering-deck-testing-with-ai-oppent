"""Deliberate internal fault-seam probes, not lawful gameplay episodes."""
from pickle import dumps

import pytest

from tests.test_control_layer_contract import metadata_position
from tests.test_static_aura_control_desired import raw_card, COMBAT, Zone, snap
from rules_engine.control_effects import expire_control_effects
from game_state.state import object_incarnation


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['controller', 'timestamp', 'incarnation', 'baseline'])
def test_expiry_rejects_late_noncache_ledger_before_any_root_write(seat, fault):
    state, first = metadata_position(seat)
    later = raw_card(state, COMBAT['Grizzly Bears'], seat, Zone.BATTLEFIELD)
    assert list(state.cards).index(first) < list(state.cards).index(later.id)
    early = state.cards[first]
    early.control_effect_base = seat
    early.control_effects = [{'controller': 3-seat, 'timestamp': 1,
        'incarnation': object_incarnation(early), 'sequence': early.zone_change_sequence,
        'expires_turn': state.turn}]
    state.temporary_control_changes[first] = {'controller': seat, 'expires_turn': state.turn}
    later.control_effect_base = seat
    later.control_effects = [{'controller': 3-seat, 'timestamp': 2,
        'incarnation': object_incarnation(later), 'sequence': later.zone_change_sequence,
        'expires_turn': state.turn + 10}]
    if fault == 'baseline':
        later.control_effect_base = 3
    else:
        later.control_effects[0][fault] = {'controller': 3, 'timestamp': 0,
                                         'incarnation': -1}[fault]
    assert later.id not in state.temporary_control_changes
    before = dumps(state, protocol=5)
    with pytest.raises(ValueError):
        expire_control_effects(state)
    assert dumps(state, protocol=5) == before, 'Rejection must precede every ledger/cache/controller/event write'
