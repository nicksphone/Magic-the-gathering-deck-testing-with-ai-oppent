"""Diagnostic consumer audit: canonical remaining non-mana action families."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from training.dataset import EpisodeAliases
from training.environment import TrainingEnvironment, decode_action
from tests.test_linked_damage_targets import raw_card
from tests.test_training_choice_coverage import card
from tests.test_training_selected_mana import mana_position
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


FAMILIES = ('loyalty', 'equip', 'crew', 'cycling')
FIXTURES = Path(__file__).parent / 'fixtures'


def canonical(filename, name):
    data = json.loads((FIXTURES / filename).read_text())
    rows = data if isinstance(data, list) else data.values()
    return next(row for row in rows if row['name'] == name)


def scenario(seat, family, variable_cycling=False):
    env = mana_position(seat)
    env._state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    env._state.mechanic_choice_players = {1, 2}
    target = card(env, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    untouched = card(env, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    selected = card(env, 'Opt', seat)
    filename, name = {
        'loyalty': ('discard_history.json', 'Daretti, Scrap Savant'),
        'equip': ('equip_costs.json', 'Bonesplitter'),
        'crew': ('permanent_spell_context.json', "Smuggler's Copter"),
        'cycling': ('restricted_mana.json', 'Hollow One'),
    }[family]
    if family == 'cycling' and variable_cycling:
        filename, name = 'ai_oracle_semantics.json', 'Shark Typhoon'
    raw = canonical(filename, name)
    source = raw_card(env._state, raw, seat,
                      Zone.HAND if family == 'cycling' else Zone.BATTLEFIELD)
    assert source.oracle_text == raw['oracle_text'] and source.type_line == raw['type_line']
    action = {
        'loyalty': {'type': 'activate_loyalty', 'card_id': source.id, 'ability_index': 0, 'targets': {}},
        'equip': {'type': 'equip', 'card_id': source.id, 'target_card_id': target},
        'crew': {'type': 'crew', 'card_id': source.id, 'crew_card_ids': [target]},
        'cycling': {'type': 'cycle_card', 'card_id': source.id, 'x_value': 2 if variable_cycling else 0},
    }[family]
    hint = next(move for move in env._rules.legal_moves(deepcopy(env._state), seat)
                if move['type'] == action['type'] and move['card_id'] == source.id
                and (family != 'cycling' or move.get('x_value', 0) == action['x_value'])
                and (family != 'loyalty' or move['ability_index'] == 0))
    return env, action, hint, target, untouched, selected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('field', ['source_zone', 'unknown_choice'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_requested_fields_reject_instead_of_normalizing(game, seat, family, field, is_null):
    env, action, _, _, _, _ = scenario(seat, family)
    request = {**action, field: None if is_null else ('graveyard' if field == 'source_zone' else True)}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(request)
    client, match = game
    retain(match, env)
    response = rejected(client, match, request, seat)
    assert response.status_code == 422
    assert env.snapshot() == before
    # Sole consumer expectation: never execute the normalized unsupported request.
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    assert env.snapshot() == before


def completed_state(env, action, family, selected):
    fork = TrainingEnvironment()
    fork.restore(env.snapshot())
    fork.step(action)
    for _ in range(12):
        if fork._state.pending_mechanic_choice:
            assert family == 'loyalty'
            actor = fork.acting_seat
            assert selected in fork.observe(actor)['known_cards']
            assert fork.prompts(3-actor) == []
            assert 'prompts' not in fork.observe(3-actor)['pending_choice']
            pending = fork.snapshot()
            replay = TrainingEnvironment()
            replay.restore(pending)
            choice = {'type': 'choose_mechanic', 'card_ids': [selected]}
            assert fork.lookup(choice) == replay.lookup(choice)
            assert fork.step(choice) == replay.step(choice)
            assert fork.snapshot() == replay.snapshot()
        elif fork._state.stack:
            fork.step({'type': 'pass_priority'})
        else:
            return fork._state
    raise AssertionError('Canonical continuation exceeded bounded priority steps')


def execute_http(client, match, env, action, family, selected):
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': env.acting_seat, 'action': action})
    assert response.status_code == 200, response.text
    restored = restart(identifier)
    for _ in range(12):
        if restored.state.pending_mechanic_choice:
            assert family == 'loyalty'
            chosen = {'type': 'choose_mechanic', 'card_ids': [selected]}
            actor = restored.state.pending_mechanic_choice['player_id']
        elif restored.state.stack:
            chosen = {'type': 'pass_priority'}
            actor = restored.state.priority_player
        else:
            return restored.state
        response = client.post(f'/matches/{identifier}/action', json={'player_id': actor, 'action': chosen})
        assert response.status_code == 200, response.text
        restored = restart(identifier)
    raise AssertionError('Canonical HTTP continuation exceeded bounded priority steps')


def assert_outcome(state, seat, family, source, target, untouched, selected):
    if family == 'loyalty':
        assert state.cards[source].loyalty == 5
        assert selected in state.players[seat].graveyard
        assert state.discards_this_turn[seat] == state.draws_this_turn[seat] == 1
    elif family == 'equip':
        assert state.cards[source].attached_to == target
        assert state.cards[source].attached_to != untouched
    elif family == 'crew':
        assert state.cards[target].tapped and not state.cards[untouched].tapped
        assert 'Creature' in state.cards[source].types
    else:
        assert source in state.players[seat].graveyard
        assert state.draws_this_turn[seat] == 1
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_independent_whole_legal_view_preserves_choices_and_actual_execution(game, seat, family):
    env, action, hint, target, untouched, selected = scenario(seat, family)
    before = env.snapshot()
    intent = {**hint, **action}
    original = deepcopy(intent)
    accepted = env.lookup(action)
    assert env.lookup_intent(intent) == accepted
    normalized = decode_action(accepted['id'])
    for key, value in action.items():
        assert normalized[key] == value
    aliases = EpisodeAliases()
    aliases.observation(env.observe(seat))
    assert aliases.actual_action(aliases.action(normalized, seat), seat) == normalized
    assert intent == original and env.snapshot() == before
    state = completed_state(env, normalized, family, selected)
    assert_outcome(state, seat, family, action['card_id'], target, untouched, selected)
    if family == 'cycling':
        assert sum(env._state.players[seat].mana_pool.values()) - sum(state.players[seat].mana_pool.values()) == 2
    client, match = game
    state = execute_http(client, match, env, normalized, family, selected)
    assert_outcome(state, seat, family, action['card_id'], target, untouched, selected)
    if family == 'cycling':
        assert sum(env._state.players[seat].mana_pool.values()) - sum(state.players[seat].mana_pool.values()) == 2
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_supported_malformed_parameters_reject_at_all_boundaries(game, seat, family):
    env, action, _, _, _, _ = scenario(seat, family)
    changes = {
        'loyalty': {'ability_index': 99},
        'equip': {'target_card_id': 'stale-object'},
        'crew': {'crew_card_ids': ['stale-object']},
        'cycling': {'x_value': -1},
    }[family]
    bad = {**action, **changes}
    before = env.snapshot()
    client, match = game
    retain(match, env)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(bad)
        assert env.snapshot() == before
    rejected(client, match, bad, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_actor_input_bytes_ignore_opposing_hidden_identity_order(seat, family):
    env, action, hint, _, _, _ = scenario(seat, family)
    def inputs():
        aliases = EpisodeAliases()
        observation = aliases.observation(env.observe(seat))
        return json.dumps({'observation': observation, 'action': aliases.action(action, seat),
                           'prompts': env.prompts(seat)}, sort_keys=True).encode()
    before = inputs()
    for ids in (env._state.players[3-seat].hand, env._state.players[3-seat].library):
        first, second = ids[:2]
        a, b = deepcopy(env._state.cards[first]), deepcopy(env._state.cards[second])
        a.id, b.id = second, first
        env._state.cards[first], env._state.cards[second] = b, a
        ids.reverse()
    assert inputs() == before
    assert env.lookup_intent({**hint, **action}) == env.lookup(action)
    assert env.prompts(3-seat) == []
