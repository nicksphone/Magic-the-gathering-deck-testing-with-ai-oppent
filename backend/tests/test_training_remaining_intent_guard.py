"""Remaining public-model guard; display never supplies authoritative choices."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from rules_engine.action_validation import ActionRejected
from game_state.state import Zone
from training.environment import decode_action
from tests.test_linked_damage_targets import raw_card
from tests.test_training_selected_mana import mana_position
from tests.test_training_remaining_intent_audit import scenario


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payload', [None, {}, [], ['not-a-candidate'],
                                   [{'id': None, 'name': 'Grizzly Bears'}],
                                   [{'id': 'public-id', 'name': ''}],
                                   [{'id': 'public-id', 'name': 'Grizzly Bears', 'target_card_id': 'chosen'}]])
def test_equip_malformed_display_cannot_hide_chosen_parameters(seat, payload):
    env, action, _, _, _, _ = scenario(seat, 'equip')
    request = {**action, 'targets': deepcopy(payload)}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ActionRejected, match='Equip targets must be a display candidate list'):
        env.lookup_intent(request)
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['equip', 'crew'])
def test_whole_view_suggestions_do_not_fill_omitted_chosen_parameters(seat, family):
    env, _, hint, _, _, _ = scenario(seat, family)
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(deepcopy(hint))
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['equip', 'crew', 'cycling'])
@pytest.mark.parametrize('payment', [None, {'sacrifice_card_ids': ['unannounced-resource']}])
def test_unsupported_resource_request_is_not_ignored(seat, family, payment):
    env, action, _, _, _, _ = scenario(seat, family)
    before = env.snapshot()
    with pytest.raises(ActionRejected, match='cannot carry requested fields'):
        env.lookup_intent({**action, 'payment_choices': payment})
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_variant_cycling_whole_view_is_display_not_chosen_search(seat):
    env = mana_position(seat)
    rows = json.loads((Path(__file__).parent / 'fixtures/affinity/canonical.json').read_text())['data']
    raw = next(row for row in rows if row['name'] == "Sojourner's Companion")
    source = raw_card(env._state, raw, seat, Zone.HAND)
    env._state.players[seat].mana_pool = {'C': 2}
    action = {'type': 'cycle_card', 'card_id': source.id, 'x_value': 0}
    hint = next(move for move in env._rules.legal_moves(deepcopy(env._state), seat)
                if move['type'] == 'cycle_card' and move['card_id'] == source.id)
    assert hint['cycling_variant'] == 'land'
    before = env.snapshot()
    accepted = env.lookup_intent({**hint, **action})
    assert accepted == env.lookup(action)
    assert 'cycling_variant' not in decode_action(accepted['id'])
    with pytest.raises(ActionRejected, match='cannot carry requested fields'):
        env.lookup_intent({**action, 'card_ids': ['unannounced-search-selection']})
    assert env.snapshot() == before
    # This qualifies the display boundary, not artifact-land search semantics.


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_variable_cycling_preserves_explicit_top_level_x(seat):
    env, action, hint, _, _, _ = scenario(seat, 'cycling', variable_cycling=True)
    before = env.snapshot()
    assert decode_action(env.lookup_intent({**hint, **action})['id'])['x_value'] == 2
    assert env.lookup_intent({**hint, **action}) == env.lookup(action)
    with pytest.raises(ActionRejected):
        env.lookup_intent({**action, 'targets': {'x_value': 7}})
    assert env.snapshot() == before
