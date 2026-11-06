"""Empty grant metadata is reviewed; synthetic nonempty/fault cases stay unknown."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from tests.test_numeric_inventory_adapter import positive, pure_inventory


def test_characteristic_boundary_fixture_uses_current_reviewed_schema():
    from game_state.state import CardInstance
    from rules_engine.graveyard_inventory import _SCHEMA_PINS
    from tests.test_graveyard_characteristic_record76 import CURRENT_CARD_SCHEMA
    assert CURRENT_CARD_SCHEMA == _SCHEMA_PINS[CardInstance]


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_grants_and_old_snapshot_omission_preserve_inventory(seat):
    state = positive(seat)
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    payload = serialize_match_snapshot(state)
    for card in payload['cards'].values():
        assert card.pop('activated_ability_effects') == []
    original = deepcopy(payload)
    restored = deserialize_match_snapshot(payload)
    assert payload == original
    assert all(card.activated_ability_effects == [] for card in restored.cards.values())
    assert pure_inventory(restored, seat) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', [Zone.BATTLEFIELD, Zone.GRAVEYARD])
@pytest.mark.parametrize('fault', ['nonempty', 'null', 'tuple', 'dict', 'missing'])
def test_uncovered_grant_metadata_rejects_without_mutating_root(seat, zone, fault):
    state = positive(seat)
    card = next(card for card in state.cards.values() if card.zone == zone)
    # Metadata boundary injections, not claimed canonical grant executions.
    if fault == 'missing':
        del card.activated_ability_effects
    else:
        card.activated_ability_effects = {
            'nonempty': [{'uncovered_ability': True}], 'null': None, 'tuple': (), 'dict': {},
        }[fault]
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_grant_metadata_never_supplies_public_coverage(seat):
    state = positive(seat)
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    hidden = state.cards[state.players[3-seat].library[0]]
    hidden.activated_ability_effects = [{'private_uncovered_ability': True}]
    assert hidden.id not in {row['reference']['id'] for row in expected['receipts']}
    assert pure_inventory(state, seat) == expected
