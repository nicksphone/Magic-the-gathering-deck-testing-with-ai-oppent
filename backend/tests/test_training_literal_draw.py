"""Real canonical Opt/dredge continuation, separate from context/ABI changes."""
from copy import deepcopy
import json

import pytest

from game_state.state import Zone
from tests.test_training_choice_coverage import card, cast, position
from tests.test_training_environment import resolve
from training import decision_frame as features


def _field(node, name):
    assert node['kind'] == 'map'
    matches = [value for key, value in node['items']
               if key == {'kind': 'text', 'value': name}]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_canonical_draw_literal_retains_offered_semantics_after_frame_roundtrip(seat):
    environment = position(seat)
    imp = card(environment, 'Stinkweed Imp', seat, Zone.GRAVEYARD)
    opt = card(environment, 'Opt', seat)
    environment.step(cast(environment, opt))
    resolve(environment)
    # The empty scry selection really leaves the top card, then native Opt offers dredge.
    environment.step({'type': 'choose_mechanic', 'card_ids': []})
    observation, prompts = environment.observe(seat), environment.prompts(seat)
    hint = prompts[0]['hint']
    assert hint['kind'] == 'draw' and 'draw' in hint['options'] and imp in hint['options']
    assert hint['option_labels']['draw'] == 'Draw normally'
    before = environment.snapshot()
    frame, bindings = features.build_decision_frame(observation, prompts)
    assert frame['prompts'][0]['hint']['kind'] == 'draw'
    choice = {'type': 'choose_mechanic', 'choice_id': 'draw'}
    aliased = bindings.action(choice)
    assert aliased['choice_id'] != 'draw'
    assert bindings.actual_action(aliased) == choice
    restored_frame = json.loads(json.dumps(frame))
    try:
        state_features = features.encode_state(restored_frame)
        action_features = features.encode_action(restored_frame, aliased)
    except ValueError as exc:
        pytest.fail('Genuine offered draw literal lost its descriptor: ' + type(exc).__name__)
    assert state_features == features.encode_state(deepcopy(frame))
    selected = _field(action_features['root'], 'choice_id')
    assert selected['kind'] == 'ref'
    descriptor = action_features['entities'][selected['index']]
    assert _field(descriptor, 'label') == {'kind': 'text', 'value': 'Draw normally'}
    assert environment.snapshot() == before
    environment.lookup(choice, seat)
    environment.step(choice, seat)
    after = environment.observe(seat)
    assert after['pending_choice'] is None
    assert after['players'][str(seat)]['hand_count'] == observation['players'][str(seat)]['hand_count'] + 1
    assert after['players'][str(seat)]['library_count'] == observation['players'][str(seat)]['library_count'] - 1
    assert imp in after['players'][str(seat)]['graveyard']
    assert imp not in after['players'][str(seat)]['hand']
