"""Text-only memoization must not retain mutable battlefield effects."""
from copy import deepcopy

import pytest

from game_state.state import object_incarnation
from rules_engine.basic_land_layer import _printed_layer_four_effect, layer_four_view, permanent_land_replacement
from rules_engine.attached_characteristics import attached_compound
from rules_engine.land_types import land_type_instructions
from tests.test_basic_land_layer_goldens import CARDS, add, position


@pytest.mark.parametrize('name', sorted(CARDS))
def test_cached_text_predicate_equals_existing_queries(name):
    text = CARDS[name]['oracle_text']
    expected = bool(land_type_instructions(text) or permanent_land_replacement(text) or attached_compound(text))
    assert _printed_layer_four_effect(text) is expected
    assert _printed_layer_four_effect(text) is expected


@pytest.mark.parametrize('seat', [1, 2])
def test_live_subtype_effect_is_not_cached_with_printed_text(seat):
    state = position(seat)
    card = add(state, 'Dryad Arbor', seat)
    assert not _printed_layer_four_effect(card.oracle_text)
    empty = layer_four_view(state)
    assert not empty[0]
    before = deepcopy(state)
    card.type_effects.append({'types': [], 'creature_subtypes': ['Human'],
                              'incarnation': object_incarnation(card), 'timestamp': 1})
    changed = layer_four_view(state)
    assert changed[0][card.id].endswith('Human')
    card.type_effects.clear()
    assert layer_four_view(state) == empty
    assert state.rng.getstate() == before.rng.getstate()
