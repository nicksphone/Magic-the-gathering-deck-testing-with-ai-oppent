"""Pure core diagnostics, distinct from strict public DeckEntry admission."""
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from api_contracts import DeckEntry
from decks.sideboard import SideboardError, apply_sideboard_swaps


CARDS = json.loads((Path(__file__).parent / 'fixtures/sideboard_basics.json').read_text())
NAMES = {row['name'] for row in CARDS}
BAD_QUANTITIES = [True, False, 1.5, '1', 0, -1, None]


def entry(name, quantity):
    assert name in NAMES
    return {'card_name': name, 'quantity': quantity}


def inventory():
    return [entry('Island', 45), entry('Mountain', 15)], [entry('Forest', 15)]


def counts(items):
    result = Counter()
    for item in items:
        result[item['card_name']] += item['quantity']
    return result


@pytest.mark.parametrize('amount', [0, 1, 3, 15])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_swap_preserves_every_card_and_board_sizes(amount, roundtrip):
    main, side = inventory()
    original = deepcopy((main, side))
    outgoing = [entry('Mountain', amount)] if amount else []
    incoming = [entry('Forest', amount)] if amount else []
    new_main, new_side = apply_sideboard_swaps(main, side, outgoing, incoming)
    if roundtrip:
        new_main, new_side = json.loads(json.dumps([new_main, new_side]))
    assert counts(new_main) + counts(new_side) == counts(main) + counts(side)
    assert sum(counts(new_main).values()) == 60
    assert sum(counts(new_side).values()) == 15
    assert counts(new_main)['Forest'] == amount
    assert counts(new_main)['Mountain'] == 15 - amount
    assert all(type(row['quantity']) is int and row['quantity'] > 0
               for row in new_main + new_side)
    assert (main, side) == original


def test_duplicate_requests_aggregate_and_inverse_restores_inventory():
    main, side = inventory()
    new_main, new_side = apply_sideboard_swaps(main, side,
        [entry('Mountain', 1), entry('Mountain', 2)], [entry('Forest', 3)])
    assert counts(new_main)['Forest'] == 3
    assert counts(new_side)['Mountain'] == 3
    restored_main, restored_side = apply_sideboard_swaps(new_main, new_side,
        [entry('Forest', 3)], [entry('Mountain', 2), entry('Mountain', 1)])
    assert counts(restored_main) == counts(main)
    assert counts(restored_side) == counts(side)


@pytest.mark.parametrize('outgoing,incoming', [
    ([entry('Mountain', 2)], [entry('Forest', 1)]),
    ([entry('Mountain', 16)], [entry('Forest', 16)]),
    ([entry('Forest', 1)], [entry('Mountain', 1)]),
    ([entry('Mountain', 1)], [entry('Island', 1)]),
])
def test_rejected_inventory_requests_leave_all_inputs_unchanged(outgoing, incoming):
    main, side = inventory()
    original = deepcopy((main, side, outgoing, incoming))
    with pytest.raises(SideboardError):
        apply_sideboard_swaps(main, side, outgoing, incoming)
    assert (main, side, outgoing, incoming) == original


@pytest.mark.parametrize('quantity', BAD_QUANTITIES)
def test_public_entry_rejects_nonpositive_or_noninteger_quantity(quantity):
    value = entry('Mountain', quantity)
    original = deepcopy(value)
    with pytest.raises(ValidationError):
        DeckEntry.model_validate(value)
    assert value == original


@pytest.mark.parametrize('quantity', BAD_QUANTITIES)
def test_core_rejects_invalid_quantities_without_coercion(quantity):
    main, side = inventory()
    outgoing, incoming = [entry('Mountain', quantity)], [entry('Forest', quantity)]
    original = deepcopy((main, side, outgoing, incoming))
    with pytest.raises(SideboardError):
        apply_sideboard_swaps(main, side, outgoing, incoming)
    assert (main, side, outgoing, incoming) == original


@pytest.mark.parametrize('quantity', [1, 250])
def test_public_valid_boundary_roundtrip_keeps_exact_integer(quantity):
    value = DeckEntry.model_validate(entry('Mountain', quantity))
    assert value.model_dump() == entry('Mountain', quantity)
    assert DeckEntry.model_validate_json(value.model_dump_json()) == value


def test_public_entry_rejects_quantity_above_declared_bound():
    with pytest.raises(ValidationError):
        DeckEntry.model_validate(entry('Mountain', 251))


def test_short_mainboard_is_rejected_without_input_mutation():
    main, side = [entry('Island', 59)], []
    original = deepcopy((main, side))
    with pytest.raises(SideboardError):
        apply_sideboard_swaps(main, side, [], [])
    assert (main, side) == original


@pytest.mark.parametrize('bad', [None, 'Island', {},
    {'card_name': '', 'quantity': 1}, {'card_name': '  ', 'quantity': 1},
    {'card_name': None, 'quantity': 1}, {'card_name': 1, 'quantity': 1},
    {'card_name': 'Mountain'}])
def test_malformed_entries_raise_structured_error_without_input_mutation(bad):
    main, side = inventory()
    outgoing, incoming = [bad], [entry('Forest', 1)]
    original = deepcopy((main, side, outgoing, incoming))
    with pytest.raises(SideboardError):
        apply_sideboard_swaps(main, side, outgoing, incoming)
    assert (main, side, outgoing, incoming) == original
