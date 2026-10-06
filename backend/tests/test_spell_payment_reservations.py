"""Additional-cost selections survive automatic mana payment, both seats."""
import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_mana_executor_choices import position, add
from tests.test_mana_executor_ai_composition import test_actual_ai_spell_cast_uses_internal_mana_plan as _actual_ai_cast


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_reserved_spell_cost_is_not_consumed_for_mana(seat):
    _actual_ai_cast(seat, 'reservation')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('has_fuel', [False, True])
def test_announced_victim_reserved_before_tower_payment(seat, has_fuel):
    state = position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    held = add(state, 'Raging Goblin', seat)
    fuel = add(state, 'Raging Goblin', seat) if has_fuel else None
    spell = add(state, 'Village Rites', seat, Zone.HAND)
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'cost_choice': {'id': 'base', 'sacrifice_card_ids': [held.id]}}
    before = serialize_match_snapshot(state)
    if not has_fuel:
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, action)
    else:
        result = checked_action(state, RulesEngine(), seat, action)
        assert result.cards[spell.id].zone == Zone.STACK
        assert result.cards[held.id].zone == Zone.GRAVEYARD
        assert result.cards[fuel.id].zone == Zone.GRAVEYARD
        assert result.cards[tower.id].tapped
        assert sum('sacrifices Raging Goblin for additional cost' in line for line in result.log) == 1
    assert serialize_match_snapshot(state) == before
