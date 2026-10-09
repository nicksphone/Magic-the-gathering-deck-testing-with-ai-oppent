"""Frozen canonical Suspend audit; unsupported intents have one rejection witness."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from api_contracts import SuspendAction
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, encode_action
from tests.test_training_choice_coverage import position
from tests.test_linked_damage_targets import raw_card
from tests.test_suspend_lifecycle import DIRECTORY, ready, restore
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


@pytest.fixture(autouse=True)
def isolated_source():
    root = Path(__file__).resolve().parents[2]
    assert not (root / '.git').exists()
    assert (root / '.private-choice-audit-source').read_text() == str(root)
    assert os.environ['MTG_ISOLATED_TEST_ROOT'] == str(root)
    if not str(root).startswith('/tmp/'):
        from tests.ci_input_contracts import assert_github_owned_source
        assert_github_owned_source()


def suspend_position(seat, name='Rift Bolt'):
    row = next(row for row in json.loads((DIRECTORY / 'provenance.json').read_text())['cards']
               if row['name'] == name)
    body = (DIRECTORY / row['file']).read_bytes()
    assert sha256(body).hexdigest() == row['sha256']
    raw = json.loads(body)
    env = position(seat)
    card = raw_card(env._state, raw, seat, Zone.HAND)
    assert card.oracle_text == raw['oracle_text']
    env._state.players[seat].mana_pool = {'R': 1, 'U': 1, 'C': 1}
    action = {'type': 'suspend', 'card_id': card.id}
    return env, action


def assert_private(env, viewer):
    observation = env.observe(viewer)
    foreign = set(env._state.players[3-viewer].hand + env._state.players[3-viewer].library)
    assert not foreign.intersection(observation['known_cards'])
    assert 'hand' not in observation['players'][str(3-viewer)]
    text = json.dumps(observation)
    assert all(cid not in text for cid in foreign)
    assert 'provenance' not in observation and 'seed' not in observation


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field,value', [
    ('targets', {'target_player': 1}), ('targets', None),
    ('from_exile', True), ('from_exile', None),
    ('payment_choices', {'sacrifice_card_ids': ['requested-card']}), ('payment_choices', None),
    ('resolving_item', {'player_id': 1}), ('resolving_item', None),
])
def test_suspend_unsupported_fields_reject_before_normalization(game, seat, field, value):
    env, action = suspend_position(seat)
    request = {**action, field: value}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ValidationError):
        SuspendAction.model_validate(request)
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert_private(env, seat)
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request, seat)
    finally:
        assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Rift Bolt', 'Ancestral Vision'])
@pytest.mark.parametrize('whole_view', [False, True])
def test_actual_suspend_whole_view_execution_replay_http_restart(game, seat, name, whole_view):
    env, action = suspend_position(seat, name)
    before = env.snapshot()
    hint = next(m for m in env._rules.legal_moves(deepcopy(env._state), seat)
                if m['type'] == 'suspend' and m['card_id'] == action['card_id'])
    assert set(hint) == {'type', 'card_id', 'card_name', 'time_counters', 'mana_cost'}
    assert env.lookup_intent(hint if whole_view else action, seat) == env.lookup(action, seat)
    assert env.snapshot() == before
    fork = TrainingEnvironment()
    fork.restore(before)
    env.step(encode_action(action))
    fork.step(action)
    assert env.snapshot() == fork.snapshot()
    cid = action['card_id']
    assert env._state.cards[cid].zone == Zone.EXILE
    assert env._state.cards[cid].counters['time'] == hint['time_counters']
    assert not env._state.stack and env._state.spells_cast_this_turn[seat] == 0
    assert_private(env, seat)
    client, match = game
    original = TrainingEnvironment()
    original.restore(before)
    identifier = retain(match, original)
    restart(identifier)
    public = next(m for m in client.get(f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
                  if m['type'] == 'suspend' and m['card_id'] == cid)
    assert original.lookup_intent(public, seat) == original.lookup(action, seat)
    rejected(client, match, action, 3-seat)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    state = restart(identifier).state
    assert state.cards[cid].zone == Zone.EXILE and state.cards[cid].counters['time'] == hint['time_counters']
    restored = restore(state)
    assert restored.cards[cid].oracle_text == state.cards[cid].oracle_text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['wrong-zone', 'wrong-timing', 'unpayable', 'stale'])
def test_suspend_authoritative_invalid_choice_root_database_purity(game, seat, invalid):
    env, action = suspend_position(seat)
    if invalid == 'wrong-zone':
        card = env._state.cards[action['card_id']]
        env._state.players[seat].hand.remove(card.id)
        env._state.players[seat].graveyard.append(card.id)
        card.move_to_zone(Zone.GRAVEYARD)
    elif invalid == 'wrong-timing':
        env._state.step = Step.UPKEEP
    elif invalid == 'unpayable':
        env._state.players[seat].mana_pool.clear()
    else:
        action['card_id'] = 'stale-card'
    before = env.snapshot()
    for method in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            method(action, seat)
        assert env.snapshot() == before
    client, match = game
    retain(match, env)
    rejected(client, match, action, seat)
