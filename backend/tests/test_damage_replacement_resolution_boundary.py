"""Core damage operations must respect the existing resolution staging boundary."""
import pytest

from effects.handlers import deal_damage
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_counter_prohibitions import source as damage_source
from tests.test_counter_replacements import source
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("restore", [False, True])
def test_replaced_damage_defers_zero_toughness_until_resolution_finishes(seat, restore):
    state = clean()
    damage_source(state, "Soul-Scar Mage", seat)
    target = source(state, "Winding Constrictor", 3 - seat)
    spell = add(state, "Lightning Bolt", seat, Zone.HAND)
    state.trigger_staging = True
    state.trigger_staging_event = "stack_resolution"

    # A core two-damage event, not a fabricated spell or altered Oracle text.
    deal_damage(state, seat, {
        "target_card_id": target.id, "amount": 2, "__source_card_id": spell.id,
    })
    assert state.cards[target.id].counters["-1/-1"] == 3
    assert state.cards[target.id].zone == Zone.BATTLEFIELD
    assert target.id not in state.players[3 - seat].graveyard

    if restore:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.trigger_staging
    assert state.cards[target.id].zone == Zone.BATTLEFIELD

    apply_state_based_actions(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert target.id in state.players[3 - seat].graveyard
