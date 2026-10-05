"""Skip irrelevant sources without changing canonical multiplier semantics."""
from unittest.mock import patch

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine import continuous
from rules_engine.mana_abilities import multiplied_outputs, mana_multiplier_clause
from tests.test_mana_abilities import add
from tests.test_static_ability_suppression import add as add_suppression
from tests.test_variable_mana import clean


def reference(state, card, outputs):
    multiplier = 1
    for cid in state.players[card.controller].battlefield:
        source = state.cards[cid]
        if continuous.printed_abilities_suppressed(state, cid):
            continue
        for line in (source.oracle_text or '').splitlines():
            multiplier *= mana_multiplier_clause(line) or 1
    return {color: amount * multiplier for color, amount in outputs.items()}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('multiplier', [None, 'Mana Reflection', 'Nyxbloom Ancient'])
def test_only_matching_sources_need_suppression_queries(seat, multiplier):
    state = clean()
    land = add(state, 'Forest', seat)
    for _ in range(8):
        add(state, 'Llanowar Elves', seat)
    if multiplier:
        add(state, multiplier, seat)
    add(state, 'Mana Reflection', 3-seat)
    before = serialize_match_snapshot(state)
    expected = reference(state, land, {'G': 1, 'U': 2})
    with patch.object(continuous, 'printed_abilities_suppressed',
                      wraps=continuous.printed_abilities_suppressed) as suppression:
        assert multiplied_outputs(state, land, {'G': 1, 'U': 2}) == expected
        assert suppression.call_count == int(multiplier is not None)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('loss', ['Humility', 'Dress Down'])
def test_suppressed_real_creature_multiplier_still_stops(seat, loss):
    state = clean()
    land = add(state, 'Forest', seat)
    add(state, 'Mana Reflection', seat)
    ancient = add(state, 'Nyxbloom Ancient', seat)
    assert multiplied_outputs(state, land, {'G': 1}) == {'G': 6}
    removal = add_suppression(state, loss, 3-seat)
    assert multiplied_outputs(state, land, {'G': 1}) == reference(state, land, {'G': 1}) == {'G': 2}
    state.players[3-seat].battlefield.remove(removal.id)
    removal.move_to_zone(Zone.GRAVEYARD)
    state.players[3-seat].graveyard.append(removal.id)
    assert multiplied_outputs(state, land, {'G': 1}) == {'G': 6}
    resolve_effect(state, seat, 'temporary_ability_loss', {'target_card_id': ancient.id})
    assert multiplied_outputs(state, land, {'G': 1}) == reference(state, land, {'G': 1}) == {'G': 2}


@pytest.mark.parametrize('seat', [1, 2])
def test_controller_changes_recompute_without_a_persistent_cache(seat):
    state = clean()
    land = add(state, 'Forest', seat)
    multiplier = add(state, 'Mana Reflection', seat)
    assert multiplied_outputs(state, land, {'G': 1}) == {'G': 2}
    state.players[seat].battlefield.remove(multiplier.id)
    state.players[3-seat].battlefield.append(multiplier.id)
    multiplier.controller = 3-seat
    assert multiplied_outputs(state, land, {'G': 1}) == {'G': 1}
