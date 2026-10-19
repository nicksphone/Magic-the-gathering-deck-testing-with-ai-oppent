"""Public-record coverage controls, not canonical gameplay or copy qualification."""
from copy import deepcopy
import pickle

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine import graveyard_inventory as inventory
from rules_engine.copiable_values import apply, values
from tests.test_linked_damage_targets import raw_card
from tests.test_numeric_inventory_adapter import positive, pure_inventory
from tests.test_public_graveyard_inventory import DIVINATION


CURRENT_CARD_SCHEMA = 'c6cd00f22c8838effbffa7cdd9d19d29fd16f5879346a071a25d5253bceef8e4'


def grave(state, seat):
    return state.cards[state.players[3 - seat].graveyard[0]]


@pytest.fixture
def current_pin_only(monkeypatch):
    # Isolate missing record validation from the independently tested stale pin.
    # This changes no rules result, instance data, collector or public-field check.
    monkeypatch.setitem(inventory._SCHEMA_PINS, CardInstance, CURRENT_CARD_SCHEMA)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_real_current_stock_is_covered_without_test_pin_override(seat, roundtrip):
    state = positive(seat)
    if roundtrip:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert pure_inventory(state, seat)['status'] == 'inert'


@pytest.mark.parametrize('seat', [1, 2])
def test_artwork_change_alone_is_not_rules_or_copy_change(seat):
    state = positive(seat)
    grave(state, seat).image_uri = 'fixture-artwork-only'
    assert pure_inventory(state, seat)['status'] == 'inert'


FAULTS = [
    'absent', 'null', 'empty', 'list', 'version-bool', 'version-unknown',
    'extra-top-key', 'missing-values', 'physical-list', 'physical-extra-key',
    'physical-missing-key', 'values-list', 'values-extra-key', 'values-scalar-colors',
    'values-bool-power', 'physical-scalar-colors', 'physical-bool-power',
    'physical-rule-change', 'values-rule-change', 'physical-layout-change',
    'physical-face-change', 'physical-index-change', 'physical-artwork-type',
]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', FAULTS)
def test_pin_only_does_not_admit_unavailable_or_malformed_public_record(seat, fault, current_pin_only):
    state = positive(seat)
    card = grave(state, seat)
    record = card.characteristic_record
    if fault == 'absent':
        del card.characteristic_record
    elif fault == 'null':
        card.characteristic_record = None
    elif fault == 'empty':
        card.characteristic_record = {}
    elif fault == 'list':
        card.characteristic_record = []
    elif fault == 'version-bool':
        record['version'] = True
    elif fault == 'version-unknown':
        record['version'] = 2
    elif fault == 'extra-top-key':
        record['future_permission'] = []
    elif fault == 'missing-values':
        del record['values']
    elif fault == 'physical-list':
        record['physical'] = []
    elif fault == 'physical-extra-key':
        record['physical']['future_permission'] = []
    elif fault == 'physical-missing-key':
        del record['physical']['mana_cost']
    elif fault == 'values-list':
        record['values'] = []
    elif fault == 'values-extra-key':
        record['values']['future_permission'] = []
    elif fault == 'values-scalar-colors':
        record['values']['colors'] = 'R'
    elif fault == 'values-bool-power':
        record['values']['power'] = False
    elif fault == 'physical-scalar-colors':
        record['physical']['colors'] = 'R'
    elif fault == 'physical-bool-power':
        record['physical']['power'] = False
    elif fault == 'physical-rule-change':
        record['physical']['oracle_text'] = DIVINATION['oracle_text']
    elif fault == 'values-rule-change':
        record['values']['oracle_text'] = DIVINATION['oracle_text']
    elif fault == 'physical-layout-change':
        record['physical']['layout'] = 'transform'
    elif fault == 'physical-face-change':
        record['physical']['card_faces'] = [{}]
    elif fault == 'physical-index-change':
        record['physical']['selected_face_index'] = 1
    elif fault == 'physical-artwork-type':
        record['physical']['image_uri'] = []
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('erase_old_copy_marker', [False, True])
def test_actual_copy_values_cannot_supply_unmodified_stock_coverage(seat, erase_old_copy_marker, current_pin_only):
    state = positive(seat)
    card = grave(state, seat)
    original_physical = deepcopy(card.characteristic_record['physical'])
    original = raw_card(state, DIVINATION, seat, Zone.HAND)
    apply(card, values(original))
    assert card.characteristic_record['physical'] == original_physical
    assert card.characteristic_record['values'] != {
        key: original_physical[key] for key in card.characteristic_record['values']}
    if erase_old_copy_marker:
        # Explicit metadata tamper, not an additional legal copy operation.
        card.printed_characteristics.clear()
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_live_rule_fields_must_match_retained_values(seat, current_pin_only):
    state = positive(seat)
    grave(state, seat).oracle_text = DIVINATION['oracle_text']
    assert pure_inventory(state, seat)['status'] == 'unknown'


class OpaqueHiddenRecord:
    def __deepcopy__(self, memo):
        raise AssertionError('Hidden record contents must not enter public coverage')


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_record_is_not_inspected_or_copied(seat, current_pin_only):
    state = positive(seat)
    hidden = state.cards[state.players[3 - seat].library[0]]
    hidden.characteristic_record = OpaqueHiddenRecord()
    before = pickle.dumps(state, protocol=5)
    assert inventory.public_graveyard_inventory(state, seat)['status'] == 'inert'
    assert pickle.dumps(state, protocol=5) == before
