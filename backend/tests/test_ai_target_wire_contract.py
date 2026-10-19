"""Actual canonical land/loyalty and removal choices obey strict wire targets."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_search_prefix import bare_state
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures'


def row(file, name):
    return next(card for card in json.loads((FIXTURES / file).read_text())
                if card['name'] == name)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['land_loyalty', 'noncreature_removal'])
def test_actual_materialized_targets_validate_and_execute_without_display_names(seat, family):
    state = bare_state(seat)
    if family == 'land_loyalty':
        source = raw_card(state, row('type_effect_lifecycle.json', 'Nissa, Who Shakes the World'),
                          seat, Zone.BATTLEFIELD)
        target = raw_card(state, row('type_effect_lifecycle.json', 'Forest'), seat, Zone.BATTLEFIELD)
        kind, style = 'activate_loyalty', 'Ramp'
    else:
        source = raw_card(state, row('ward.json', 'Naturalize'), seat, Zone.HAND)
        target = raw_card(state, row('ward.json', 'Sol Ring'), 3-seat, Zone.BATTLEFIELD)
        kind, style = 'cast_spell', 'Control'
    state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    before = serialize_match_snapshot(state)
    move = next(move for move in RulesEngine().legal_moves(deepcopy(state), seat)
                if move['type'] == kind and move['card_id'] == source.id
                and (kind != 'activate_loyalty' or move['ability_index'] == 0))
    action = AIAgent(difficulty='master', archetype=style)._materialize_action(state, move, seat)
    assert action['targets']['target_card_id'] == target.id
    normalized = complete_action(action)
    assert 'target_card_name' not in normalized['targets']
    result = checked_action(state, RulesEngine(), seat, normalized)
    assert result.stack[-1].source_card_id == source.id
    assert serialize_match_snapshot(state) == before
    # Do not fix the producer by weakening the strict nested public contract.
    with pytest.raises(ActionRejected):
        complete_action({**action, 'targets': {**action['targets'], 'target_card_name': target.name}})
