"""Canonical paid triggers: honest diagnostics and unimplemented choice contracts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_cycle_discard_paid_limits import PATH, ROWS
from tests.test_death_cycle_ordering_audit import add, cards, cycle_position, restart, tokens
from tests.test_death_cycle_ordering_http_audit import (
    act, drain, frozen, install, offline_client, restore)


class PaidTriggerContinuationMissing(AssertionError):
    """Only the exact canonical unsupported noop is an expected failure."""


@pytest.fixture(autouse=True, scope='module')
def exclusive_local_source_required():
    root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve()
    assert root == Path(__file__).resolve().parents[2]
    assert root != Path('/home/nick/mtg-deck-testing-lab')
    assert not str(root).startswith('/mnt/')
    assert not (root / 'backend/mtg_lab.db').is_symlink()


def evidence(request, **data):
    directory = os.environ.get('MTG_PAID_TRIGGER_EVIDENCE')
    if directory:
        destination = Path(directory) / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
        with destination.open('x') as stream:
            json.dump({'node': request.node.nodeid, **data}, stream, sort_keys=True, indent=2)
            stream.write('\n')


def position(seat, name, route, funding):
    state, discarded, action = cycle_position(seat, 'Lonely Sandbar')
    watcher = add(state, name, seat)
    # Trigger control must not accidentally become ownership or opponent control.
    watcher.owner = 3 - seat
    secret = add(state, 'Swamp', 3 - seat, Zone.HAND)
    land = add(state, 'Island', seat) if funding == 'land' else None
    if route == 'discard':
        spell = add(state, 'Tormenting Voice', seat, Zone.HAND)
        action = cards.cast(spell, cost_choice={'id': 'base', 'discard_card_ids': [discarded.id]})
        state.players[seat].mana_pool = {'R': 1, 'C': 1 + int(funding == 'pool')}
    else:
        state.players[seat].mana_pool = {'U': 1, 'C': int(funding == 'pool')}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    return state, watcher, discarded, secret, land, action


def queued(state, seat, watcher, action):
    with cards.unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, action)
    assert len([item for item in result.stack if item.source_card_id == watcher.id]) == 1
    assert len(result.stack) == 2
    return restart(result)


def private_root(state, seat, secret):
    with cards.unchanged_root(state):
        view, _ = decision_view(state, seat, [])
    assert view is not state and view.cards[secret.id] is not state.cards[secret.id]
    assert view.cards[secret.id].name == view.cards[secret.id].oracle_text == ''
    assert view.cards[secret.id].ai_unknown and not view.cards[secret.id].types
    assert all(not view.cards[cid].name for cid in state.players[seat].library)


def unchanged_reward(state, seat):
    assert not tokens(state, seat)
    assert state.players[seat].life == state.players[3-seat].life == 20


def require_pending(state, watcher):
    pending = state.pending_trigger_order
    if not pending:
        trigger = next(item for item in state.stack if item.source_card_id == watcher.id)
        assert trigger.effect_key == 'noop'
        assert trigger.payload['__unsupported_trigger_instruction'] in ROWS[watcher.name]['oracle_text'].lower()
        assert any('Unsupported optional trigger payment' in line for line in state.log)
        unchanged_reward(state, watcher.controller)
        raise PaidTriggerContinuationMissing('Canonical paid trigger is an explicit unsupported noop; no paid choice exists')
    assert pending['phase'] == 'optional'
    assert pending['current_controller'] == watcher.controller
    assert pending['current_stack_id'] == state.stack[-1].id
    return pending


def offered(pending, accept):
    return {'type': 'choose_optional_effect', 'stack_id': pending['current_stack_id'], 'accept': accept}


def reward(state, seat, name, paid):
    if name == 'Drake Haven':
        generated = tokens(state, seat)
        assert len(generated) == int(paid)
        if paid:
            token = generated[0]
            assert token.power == token.toughness == 2
            assert token.colors == ['U'] and 'Flying' in token.keywords
            assert 'Drake' in token.type_line and 'Creature' in token.types
        assert state.players[seat].life == state.players[3-seat].life == 20
    else:
        assert not tokens(state, seat)
        assert state.players[seat].life == 20 + 2 * int(paid)
        assert state.players[3-seat].life == 20 - 2 * int(paid)


def fresh_readonly_restore(match):
    """No lifespan/schema writes; recovery uses an explicitly read-only local URI."""
    import main
    from persistence.db import DATABASE_PATH
    backend = Path(__file__).resolve().parents[1]
    assert Path(DATABASE_PATH).resolve() == backend / 'mtg_lab.db'
    before = frozen(match)
    script = '''
import json, pathlib, sys
path = pathlib.Path(sys.argv[1]).resolve()
def guard(event, args):
    if event == 'socket.connect':
        raise AssertionError('Offline recovery')
    if event == 'sqlite3.connect':
        assert str(args[0]) == 'file:' + str(path) + '?mode=ro'
sys.addaudithook(guard)
from sqlalchemy import create_engine
from sqlmodel import Session
import main
from persistence.repository import Repository
from game_state.serializers import serialize_match_snapshot
engine = create_engine('sqlite:///file:' + str(path) + '?mode=ro&uri=true')
with Session(engine) as session:
    main._restore_active_matches(Repository(session), sys.argv[2])
match = main.ACTIVE_MATCHES[sys.argv[2]]
print(json.dumps({'state': serialize_match_snapshot(match.state),
                  'controller': main._controller_snapshot(match)}, sort_keys=True))
engine.dispose()
'''
    result = subprocess.run([sys.executable, '-c', script, str(DATABASE_PATH), match.state.id],
                            cwd=backend, capture_output=True, text=True, check=True, timeout=30)
    recovered = json.loads(result.stdout)
    assert recovered['state'] == json.loads(json.dumps(before[0]))
    assert recovered['controller'] == json.loads(json.dumps(before[1]))
    assert frozen(match) == before
    return {'fresh_process_readonly_restore_equal': True, 'sql_dump_equal': True}




@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('route', ['cycle', 'discard'])
@pytest.mark.parametrize('funding,accept', [('pool', True), ('land', True), ('pool', False), ('none', False), ('none', True)])
def test_desired_paid_optional_accept_decline_and_unavailable(request, seat, name, route, funding, accept):
    root, watcher, _, secret, land, action = position(seat, name, route, funding)
    state = queued(root, seat, watcher, action)
    before = serialize_match_snapshot(state)
    resolve_top_of_stack(state)
    evidence(request, queued=before, attempted_resolution=serialize_match_snapshot(state),
             funding=funding, accept=accept, desired_contract=True)
    # Current noop was removed by actual resolution; inspect a fresh replay, not fabricated pending data.
    if not state.pending_trigger_order:
        require_pending(queued(root, seat, watcher, action), watcher)
    pending = require_pending(state, watcher)
    state = restart(state)
    private_root(state, seat, secret)
    for actor, choice in [(3-seat, offered(pending, accept)),
                          (seat, {**offered(pending, accept), 'stack_id': 'stale'})]:
        with cards.unchanged_root(state):
            with pytest.raises(ActionRejected):
                checked_action(state, RulesEngine(), actor, choice)
    if funding == 'none' and accept:
        with cards.unchanged_root(state):
            with pytest.raises(ActionRejected):
                checked_action(state, RulesEngine(), seat, offered(pending, True))
        accept = False
    with cards.unchanged_root(state):
        result = checked_action(state, RulesEngine(), seat, offered(pending, accept))
    paid = accept and funding != 'none'
    reward(result, seat, name, paid)
    assert result.players[seat].mana_pool.get('C', 0) == int(funding == 'pool' and not paid)
    if land:
        assert result.cards[land.id].tapped is paid
        assert sum(result.players[seat].mana_pool.values()) == 0
    assert len(result.stack) == 1 and not result.pending_trigger_order
    result = restart(result)
    assert resolve_top_of_stack(result)
    reward(result, seat, name, paid)
    assert not result.stack




@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
@pytest.mark.parametrize('route', ['cycle', 'discard'])
@pytest.mark.parametrize('accept', [False, True])
def test_desired_http_paid_pending_restore_and_actor_guard(request, offline_client, seat, name, route, accept):
    import main
    root, watcher, _, secret, _, action = position(seat, name, route, 'pool')
    match = install(root, request, seat, private=True)
    assert act(offline_client, match, seat, action).status_code == 200
    match = restore(root.id)
    queued_state = restart(match.state)
    for _ in range(8):
        if match.state.pending_trigger_order or not match.state.stack:
            break
        actor = match.state.priority_player
        response = (offline_client.post('/matches/' + root.id + '/autoplay?ticks=1')
                    if match.controllers[actor] == 'ai' else
                    act(offline_client, match, actor, {'type': 'pass_priority'}))
        assert response.status_code == 200, response.text
        match = restore(root.id)
    else:
        raise AssertionError('Paid trigger did not reach resolution within this exact stack protocol')
    evidence(request, queued=serialize_match_snapshot(queued_state),
             attempted_resolution=serialize_match_snapshot(match.state), accept=accept,
             desired_http_pending_contract=True)
    if not match.state.pending_trigger_order:
        unchanged_reward(match.state, seat)
        assert match.state.players[seat].mana_pool.get('C', 0) == 1
        require_pending(queued_state, watcher)
    pending = require_pending(match.state, watcher)
    fresh_readonly_restore(match)
    match = restore(root.id)
    private_root(match.state, seat, secret)
    public = main._serialize_match_controller(match)
    encoded = json.dumps(public)
    assert secret.id not in encoded
    assert all(cid not in encoded for cid in match.state.players[seat].library)
    before = frozen(match)
    response = act(offline_client, match, 3-seat, offered(pending, accept))
    assert response.status_code in (403, 422)
    assert frozen(main.ACTIVE_MATCHES[root.id]) == before
    response = act(offline_client, match, seat, {**offered(pending, accept), 'stack_id': 'stale'})
    assert response.status_code == 422
    assert frozen(main.ACTIVE_MATCHES[root.id]) == before
    response = act(offline_client, match, seat, offered(pending, accept))
    assert response.status_code == 200, response.text
    match = restore(root.id)
    reward(match.state, seat, name, accept)
    assert match.state.players[seat].mana_pool.get('C', 0) == int(not accept)
    fresh_readonly_restore(match)
    before = frozen(match)
    response = act(offline_client, match, seat, offered(pending, accept))
    assert response.status_code == 422
    assert frozen(main.ACTIVE_MATCHES[root.id]) == before
    match = drain(offline_client, root.id)
    reward(match.state, seat, name, accept)
    assert not match.state.stack


def test_raw_facts_not_rewritten():
    assert hashlib.sha256(PATH.read_bytes()).hexdigest() == '03a372fe6a2e9a121d10e3f855d6186ac5a85d44f3f771ca45e5a1f324905b38'
    assert ROWS['Drake Haven']['oracle_id'] == '86d3def3-53fa-4cad-bb25-d3275af1e3f5'
    assert ROWS['Faith of the Devoted']['oracle_id'] == '99af5247-06cf-40b2-9a7c-65ad59b1ddf6'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', list(ROWS))
def test_opponent_cycle_does_not_offer_own_paid_reward(request, seat, name):
    state, _, action = cycle_position(3-seat, 'Lonely Sandbar')
    add(state, name, seat)
    state.players[3-seat].mana_pool = {'U': 1}
    with cards.unchanged_root(state):
        result = checked_action(state, RulesEngine(), 3-seat, action)
    assert len(result.stack) == 1
    assert resolve_top_of_stack(result)
    unchanged_reward(result, seat)
    assert not any('Unsupported optional trigger payment' in line for line in result.log)
    evidence(request, resolved=serialize_match_snapshot(result), own_trigger_count=0)
