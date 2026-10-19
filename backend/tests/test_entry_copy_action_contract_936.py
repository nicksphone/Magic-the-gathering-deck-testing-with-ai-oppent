"""Existing mechanic action encodings at genuine paid copy-entry boundaries."""
from copy import deepcopy

import pytest

from api_contracts import MechanicChoice
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_entry_copy_native_936 import pending_steel


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('form', ['id', 'ids', 'id_default_empty', 'id_default_null', 'decline'])
def test_existing_selected_forms_and_nullable_defaults_reach_real_entry(seat, form):
    state, steel, target, _ = pending_steel(seat)
    fields = {'id': {'choice_id': target}, 'ids': {'card_ids': [target]},
              'id_default_empty': {'choice_id': target, 'card_ids': []},
              'id_default_null': {'choice_id': target, 'card_ids': None},
              'decline': {'choice_id': None, 'card_ids': []}}[form]
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', **fields})
    assert state.cards[steel].zone == Zone.BATTLEFIELD
    assert state.cards[steel].name == ('Sculpting Steel' if form == 'decline' else 'Sol Ring')
    assert not state.pending_mechanic_choice and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('form', ['missing', 'nulls', 'both', 'duplicate', 'unknown_id',
    'unknown_ids', 'bool_id', 'tuple_ids', 'bool_ids', 'extra_source', 'damage'])
def test_bad_choice_shapes_and_unavailable_selections_preserve_entire_pending_root(seat, form):
    state, _, target, _ = pending_steel(seat)
    fields = {'missing': {}, 'nulls': {'choice_id': None, 'card_ids': None},
              'both': {'choice_id': target, 'card_ids': [target]},
              'duplicate': {'card_ids': [target, target]},
              'unknown_id': {'choice_id': 'unavailable'}, 'unknown_ids': {'card_ids': ['unavailable']},
              'bool_id': {'choice_id': True}, 'tuple_ids': {'card_ids': (target,)},
              'bool_ids': {'card_ids': [True]},
              'extra_source': {'choice_id': target, 'entry_card_id': target},
              'damage': {'choice_id': target, 'damage_assignment': {target: 1}}}[form]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', **fields})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['entry_card_id', 'resolving_item'])
def test_missing_required_pending_source_identity_is_not_a_defaultable_choice(seat, field):
    state, _, target, _ = pending_steel(seat)
    assert field in state.pending_mechanic_choice
    state.pending_mechanic_choice.pop(field)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'choice_id': target})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('form', ['id', 'ids', 'decline'])
def test_existing_public_model_roundtrip_reaches_real_checked_resolution_without_http(seat, form):
    state, steel, target, _ = pending_steel(seat)
    fields = {'id': {'choice_id': target}, 'ids': {'card_ids': [target]}, 'decline': {'card_ids': []}}[form]
    payload = MechanicChoice.model_validate({'type': 'choose_mechanic', **fields}).model_dump()
    state = checked_action(state, RulesEngine(), seat, payload)
    assert state.cards[steel].name == ('Sculpting Steel' if form == 'decline' else 'Sol Ring')
    assert state.cards[steel].zone == Zone.BATTLEFIELD and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_whole_existing_environment_hint_is_truthful_and_private_context_cannot_be_discarded(seat):
    from training.environment import TrainingEnvironment
    state, steel, target, _ = pending_steel(seat)
    env = TrainingEnvironment()
    env._state, env._provenance = state, {}
    offered, = RulesEngine().legal_moves(state, seat)
    assert offered['min_count'] == 0 and offered['count'] == 1
    assert 'optional' not in offered
    before = serialize_match_snapshot(state)
    qualified = env.lookup_intent({**offered, 'card_ids': [target]}, seat)
    assert qualified['action'] == {'type': 'choose_mechanic', 'card_ids': [target]}
    prompt, = env.prompts(seat)
    assert prompt['hint']['options'] == offered['options']
    assert prompt['hint']['min_count'] == 0 and prompt['hint']['count'] == 1
    for key in ('options', 'min_count', 'kind'):
        tampered = deepcopy(offered)
        tampered[key] = [] if key == 'options' else 1 if key == 'min_count' else 'land_entry'
        with pytest.raises(ActionRejected):
            env.lookup_intent({**tampered, 'card_ids': [target]}, seat)
    with pytest.raises(ActionRejected):
        env.lookup_intent({**offered, 'card_ids': [target],
            'effect_payload': deepcopy(state.pending_mechanic_choice['effect_payload'])}, seat)
    assert serialize_match_snapshot(state) == before
