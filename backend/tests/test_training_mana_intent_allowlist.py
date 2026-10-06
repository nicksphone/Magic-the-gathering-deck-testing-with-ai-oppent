"""All four mana consumer models share a strict requested-field boundary."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_training_selected_mana import mana_position, selected_position
from tests.test_training_mana_choice_coverage import card
from tests.test_training_choice_coverage import forbid_database_and_network


def simple_intent(seat, kind):
    env = mana_position(seat)
    env._state.players[seat].mana_pool = {}
    cid = card(env, 'Sol Ring' if kind in ('activate_mana_ability', 'tap_nonland_for_mana') else 'Forest', seat)
    if kind == 'tap_lands_bulk':
        action = {'type': kind, 'land_name': 'Forest', 'count': 1, 'color': 'G'}
    else:
        action = {'type': kind, 'card_id': cid, 'color': 'C' if kind in (
            'activate_mana_ability', 'tap_nonland_for_mana') else 'G'}
        if kind == 'activate_mana_ability':
            action['ability_index'] = 0
    return env, action


KINDS = ('activate_mana_ability', 'tap_nonland_for_mana', 'tap_land_for_mana', 'tap_lands_bulk')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', KINDS)
def test_known_display_metadata_and_simple_actions_stay_legal(seat, kind):
    env, action = simple_intent(seat, kind)
    before = env.snapshot()
    metadata = {'card_name': 'display only', 'cost_options': [], 'target_hints': {},
                'required_choices': {'payment_choices': False}, 'base_output_bundles': [],
                'output_options': [], '_invalid_ai_choice': False}
    assert env.lookup_intent({**action, **metadata}) == env.lookup(action)
    assert env.snapshot() == before
    env.step(action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', KINDS)
def test_unknown_requested_fields_reject_before_complete_action(monkeypatch, seat, kind):
    env, action = simple_intent(seat, kind)
    before = env.snapshot()
    def forbidden(intent):
        pytest.fail('normalizer called before unknown request rejection')
    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected, match='cannot carry'):
        env.lookup_intent({**action, 'unknown_choice': None})
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', KINDS[1:])
@pytest.mark.parametrize('field', ['ability_index', 'output_bundle', 'payment_choices', 'hybrid_choices', 'targets'])
def test_legacy_unsupported_selected_fields_even_null_are_not_display(seat, kind, field):
    env, action = simple_intent(seat, kind)
    before = env.snapshot()
    with pytest.raises(ActionRejected, match='cannot carry'):
        env.lookup_intent({**action, field: None})
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_required_choices_presentation_cannot_authorize_missing_typed_payment(seat):
    env, _, action = selected_position(seat)
    hint = next(move for move in env._rules.legal_moves(deepcopy(env._state), seat)
                if move['type'] == action['type'] and move['card_id'] == action['card_id']
                and move['ability_index'] == action['ability_index'])
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent({**hint, **action, 'required_choices': {'payment_choices': False}})
    assert env.snapshot() == before
