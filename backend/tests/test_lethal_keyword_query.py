"""Only destruction-relevant damage requires an indestructible layer query."""
from unittest.mock import patch

import pytest

from rules_engine import state_based_actions as sba
from tests.test_ability_suppression import add
from tests.test_ai_recurring_engines import fixture


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('toughness', [0, -1, 1, 3, None])
@pytest.mark.parametrize('damage,touched', [(0, 0), (1, 0), (3, 0), (0, 1)])
@pytest.mark.parametrize('indestructible', [False, True])
def test_lethal_result_and_keyword_query_match_destruction_conditions(
        seat, toughness, damage, touched, indestructible):
    state = fixture()
    card = add(state, 'Llanowar Elves', seat)
    card.counters.update({sba.DMG_MARK_KEY: damage, sba.DEATHTOUCH_MARK_KEY: touched})
    requires_keyword = toughness is not None and toughness > 0 and (
        damage >= toughness or touched > 0)
    expected = toughness is not None and (toughness <= 0 or (
        requires_keyword and not indestructible))
    with patch.object(sba, 'effective_combat_stats', return_value=(1, toughness)), \
            patch.object(sba, 'has_keyword', return_value=indestructible) as keyword:
        assert sba.creature_has_lethal_state(state, card.id) == expected
    assert keyword.call_count == int(requires_keyword)
    if requires_keyword:
        keyword.assert_called_once_with(state, card.id, 'indestructible')
