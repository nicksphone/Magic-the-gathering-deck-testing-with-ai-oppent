"""Exact owned metadata, explicit public choices, no completion-time guessing."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_private_choice_intent_boundary import (
    environment, owned_disposable_source_only, position, selected,
)


METADATA = (
    'kind', 'options', 'count', 'min_count', 'label', 'option_labels',
    'option_type_lines', 'inspected_cards', 'inspected_card_ids', 'effect_payload',
    'top_reference', 'top_ids', 'bottom_any_order', 'bottom_random',
    'player_id', 'effect_controller', 'followup_effect', 'resolving_item',
)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('key', METADATA)
@pytest.mark.parametrize('value', [None, {'unsupported_nested_alias': None}])
def test_all_supplied_metadata_requires_current_exact_owned_view(seat, family, key, value, monkeypatch):
    state, _, _ = position(family, seat)
    env = environment(state)
    before = env.snapshot()
    view = RulesEngine().legal_moves(deepcopy(state), seat)[0]
    request = {**view, **selected(state, family, True), key: value}
    original = deepcopy(request)

    def forbidden(_):
        pytest.fail('Invalid private context reached completion helper')

    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert env.snapshot() == before and request == original


BAD_SELECTIONS = (
    {}, {'card_ids': None}, {'card_ids': {'choice_id': 'decline'}},
    {'card_ids': [None]}, {'card_ids': [1]}, {'card_ids': [], 'choice_id': 'decline'},
    {'choice_id': {'card_ids': []}}, {'damage_assignment': {'unsupported': None}},
    {'damage_assignment': {'unsupported': True}},
    {'damage_assignment': {'unsupported': -1}},
    {'selected_card_ids': []}, {'targets': {'card_ids': []}},
)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('choice', BAD_SELECTIONS)
@pytest.mark.parametrize('whole_view', [False, True])
def test_public_model_rejects_malformed_selection_before_helper(seat, family, choice, whole_view, monkeypatch):
    state, _, _ = position(family, seat)
    env = environment(state)
    before = env.snapshot()
    view = RulesEngine().legal_moves(deepcopy(state), seat)[0] if whole_view else {}
    request = {**view, 'type': 'choose_mechanic', **choice}
    original = deepcopy(request)

    def forbidden(_):
        pytest.fail('Malformed public action reached completion helper')

    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('decline', [False, True])
def test_whole_training_prompt_raw_view_and_stale_wrong_actor(seat, family, decline, monkeypatch):
    state, _, _ = position(family, seat)
    env = environment(state)
    view = RulesEngine().legal_moves(deepcopy(state), seat)[0]
    hint = env.prompts(seat)[0]['hint']
    action = selected(state, family, decline)
    before = env.snapshot()
    for metadata in (view, hint):
        request = {**deepcopy(metadata), **action}
        original = deepcopy(request)
        assert env.lookup_intent(request, seat) == env.lookup(action, seat)
        assert env.snapshot() == before and request == original

    def forbidden(_):
        pytest.fail('Wrong actor or stale view reached completion helper')

    with monkeypatch.context() as patch:
        patch.setattr('ai.action_contract.complete_action', forbidden)
        for actor in (3-seat, True, '1'):
            with pytest.raises(ActionRejected):
                env.lookup_intent({**view, **action}, actor)
        assert env.snapshot() == before
    env.step(action, seat)
    after = env.snapshot()
    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent({**view, **action}, seat)
    assert env.snapshot() == after


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
def test_no_choices_inferred_from_exact_view_and_failed_ai_marker_preserved(seat, family):
    state, _, _ = position(family, seat)
    env = environment(state)
    before = env.snapshot()
    view = RulesEngine().legal_moves(deepcopy(state), seat)[0]
    with pytest.raises(ActionRejected):
        env.lookup_intent(view, seat)
    with pytest.raises(ActionRejected):
        env.lookup_intent({**view, **selected(state, family, True), '_invalid_ai_choice': True}, seat)
    assert env.snapshot() == before
