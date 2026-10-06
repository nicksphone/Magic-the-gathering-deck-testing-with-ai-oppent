"""Independent real mana controls; never inject an animation effect."""
import pytest

from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_canonical_land_animation_audit import FAMILIES, position, record, snapshot


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('newly_played', [False, True])
def test_actual_unanimated_land_mana_payment_and_same_turn_entry(request, seat, name, newly_played):
    state, land = position(seat, name, newly_played)
    color = 'C' if name == 'Mutavault' else 'U'
    action = {'type': 'tap_land_for_mana', 'card_id': land.id, 'color': color}
    before = snapshot(state)
    if name == 'Celestial Colonnade' and newly_played:
        assert land.tapped
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, action)
        result = state
    else:
        result = checked_action(state, RulesEngine(), seat, action)
        assert result.cards[land.id].tapped
        assert result.players[seat].mana_pool[color] == state.players[seat].mana_pool.get(color, 0) + 1
    assert snapshot(state) == before
    assert result.cards[land.id].oracle_text == land.oracle_text
    record(request, result, phase='native_mana_control', newly_played=newly_played,
           root_and_rng_unchanged=True, enters_tapped_rejection=name == 'Celestial Colonnade' and newly_played)
