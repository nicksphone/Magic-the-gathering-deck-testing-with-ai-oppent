"""Real checked HTTP payments use only the disposable checkout's local SQLite."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_training_selected_mana import selected_position, filter_position
from tests.test_training_mana_choice_coverage import mana
from tests.test_training_mana_choice_coverage import card
from tests.test_training_choice_coverage import card as existing_card
from tests.test_linked_damage_targets import raw_card
from ai.action_contract import complete_action


@pytest.fixture(autouse=True)
def forbid_external_network(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('HTTP qualification cannot connect to an external server')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


def retain(match, env):
    identifier = match.state.id
    match.state = deepcopy(env._state)
    match.state.id = identifier
    persist(match)
    return identifier


def restart(identifier):
    before = serialize_match_snapshot(main.ACTIVE_MATCHES[identifier].state)
    main.ACTIVE_MATCHES.pop(identifier)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), identifier)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[identifier].state) == before
    return main.ACTIVE_MATCHES[identifier]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Phyrexian Tower', 'Skirk Prospector'])
def test_actual_resource_payment_checked_http_and_restart(game, seat, name):
    client, match = game
    env, choices, action = selected_position(seat, name)
    rows = json.loads((Path(__file__).parent / 'fixtures/mana_resources.json').read_text())
    raw = next(row for row in rows if row['name'] == 'Skirk Prospector')
    foreign = raw_card(env._state, raw, 3-seat, Zone.BATTLEFIELD).id
    wrong_zone = raw_card(env._state, raw, seat, Zone.HAND).id
    wrong_kind = (card(env, 'Sol Ring', seat) if name == 'Phyrexian Tower' else
                  existing_card(env, 'Grizzly Bears', seat, Zone.BATTLEFIELD))
    identifier = retain(match, env)
    rejected(client, match, action, seat)
    for selected in ([], [foreign], [wrong_zone], [wrong_kind], ['stale-object'], [choices[0], choices[0]]):
        rejected(client, match, {**action, 'payment_choices': {'sacrifice_card_ids': selected}}, seat)
    rejected(client, match, {**action, 'card_id': foreign,
             'payment_choices': {'sacrifice_card_ids': [choices[0]]}}, seat)
    # Reservations are a trusted planner parameter, not an accepted HTTP field.
    rejected(client, match, {**action, 'reserved_card_ids': [choices[0]],
             'payment_choices': {'sacrifice_card_ids': [choices[0]]}}, seat)
    action['payment_choices'] = {'sacrifice_card_ids': [choices[1]]}
    assert complete_action({**action, 'card_name': name, 'target_hints': {}, 'cost_options': []}) == action
    match = restart(identifier)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    paid = restart(identifier)
    assert choices[1] in paid.state.players[seat].graveyard
    assert choices[0] in paid.state.players[seat].battlefield
    assert not paid.state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,branch,color,bundle', [
    ('graven-cairns', 'B', 'R', {'R': 2}), ('flooded-grove', 'U', 'G', {'G': 2}),
    ('graven-cairns', 'B', 'R', {'B': 1, 'R': 1}), ('flooded-grove', 'U', 'G', {'G': 1, 'U': 1})])
def test_actual_hybrid_payment_checked_http_and_restart(game, seat, name, branch, color, bundle):
    client, match = game
    env, cid = filter_position(seat, name, branch)
    identifier = retain(match, env)
    action = {**mana(cid, color, 1), 'output_bundle': bundle}
    rejected(client, match, action, seat)
    rejected(client, match, {**action, 'hybrid_choices': ['W']}, seat)
    rejected(client, match, {**action, 'hybrid_choices': [branch], 'output_bundle': {'W': 1, 'B': 1}}, seat)
    rejected(client, match, {**action, 'hybrid_choices': [branch], 'targets': {'x_value': 1}}, seat)
    restart(identifier)
    action['hybrid_choices'] = [branch]
    assert complete_action({**action, 'card_name': name, 'mana_cost': '{1}'}) == action
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    paid = restart(identifier)
    assert all(paid.state.players[seat].mana_pool.get(key, 0) == amount for key, amount in bundle.items())
    assert sum(paid.state.players[seat].mana_pool.values()) == 2
    assert not paid.state.stack
