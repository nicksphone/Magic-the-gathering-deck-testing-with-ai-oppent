"""Unsupported chosen-parameter aliases, distinct from actual legal-view display."""
import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_selected_mana_http import game, retain, rejected, forbid_external_network
from tests.test_training_remaining_intent_audit import FAMILIES, scenario


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('is_null', [False, True])
def test_misplaced_chosen_parameters_are_not_display_metadata(game, seat, family, is_null):
    env, action, _, target, untouched, _ = scenario(seat, family, variable_cycling=family == 'cycling')
    field, value = {
        'loyalty': ('target_card_id', target),
        'equip': ('targets', {'target_card_id': untouched}),
        'crew': ('targets', {'target_card_id': untouched}),
        'cycling': ('targets', {'x_value': 7}),
    }[family]
    request = {**action, field: None if is_null else value}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    # In particular, an equip targets object/null is not its offered targets list.
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request)
    finally:
        assert env.snapshot() == before
