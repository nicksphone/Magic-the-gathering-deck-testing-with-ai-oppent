"""Forty canonical HTTP/persistence cases on an explicitly isolated source."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_canonical_land_animation_audit import db_dump, snapshot
from tests.test_canonical_multicharacteristic_audit import FAMILIES, ROWS, position
from tests.test_land_animation_cloudshift_composition import CLOUDSHIFT
from tests.test_linked_damage_targets import raw_card
from tests.temporary_characteristics_http_fixture import api_context


ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def receipt(request, **data):
    path = Path(os.environ['MTG_FROG_HTTP_EVIDENCE']) / (digest(request.node.nodeid) + '.json')
    with path.open('x') as stream:
        json.dump({'node': request.node.nodeid, **data}, stream, sort_keys=True, indent=2)


@pytest.fixture(params=['owned-file', 'file'])
def family_api(monkeypatch, request):
    with api_context(monkeypatch, request, request.param) as api:
        yield api


@pytest.fixture
def file_api(monkeypatch, request):
    with api_context(monkeypatch, request, 'file') as api:
        yield api


def persist(api, controller):
    from sqlmodel import Session
    from persistence.repository import Repository
    with Session(api.engine) as session:
        api.main._persist_active_match(Repository(session), controller)


def install(api, state, seat):
    controller = api.main.MatchController(
        state=state, rules=RulesEngine(), controllers={seat: 'human', 3-seat: 'ai'},
        ai={pid: api.main.AIAgent(difficulty='master', archetype='Midrange') for pid in (1, 2)},
        mode='human_vs_ai', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=1)
    api.main.ACTIVE_MATCHES[state.id] = controller
    persist(api, controller)
    return controller


def controller_view(api, controller):
    return deepcopy(api.main._controller_snapshot(controller))


def public(api, controller, hidden):
    before = snapshot(controller.state), controller_view(api, controller), db_dump(api.engine)
    response = api.client.get('/matches/' + controller.state.id)
    assert response.status_code == 200, response.text
    value = response.json()
    assert hidden not in json.dumps(value)
    assert (snapshot(controller.state), controller_view(api, controller), db_dump(api.engine)) == before
    return value


def post(api, controller, seat, action, hidden):
    response = api.client.post('/matches/' + controller.state.id + '/action',
                               json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert hidden not in json.dumps(response.json())
    return response.json()


def cast_action(card, target):
    return {'type': 'cast_spell', 'card_id': card.id, 'targets': {'target_card_id': target.id}}


def pass_one(api, controller, hidden):
    actor = controller.state.priority_player
    if controller.controllers[actor] == 'human':
        post(api, controller, actor, {'type': 'pass_priority'}, hidden)
    else:
        controller.state = checked_action(controller.state, controller.rules, actor, {'type': 'pass_priority'})
        persist(api, controller)


def resolve_http(api, controller, hidden):
    for _ in range(8):
        if not controller.state.stack:
            return
        pass_one(api, controller, hidden)
    raise AssertionError('Eight actual priority passes did not resolve the stack')


def cleanup_http(api, controller, hidden):
    turn = controller.state.turn
    for _ in range(48):
        if controller.state.turn != turn:
            return
        pass_one(api, controller, hidden)
    raise AssertionError('Native cleanup bound reached')


def restore(api, controller):
    from sqlmodel import Session
    from persistence.repository import Repository
    before = snapshot(controller.state), controller_view(api, controller), db_dump(api.engine)
    api.main.ACTIVE_MATCHES.pop(controller.state.id)
    with Session(api.engine) as session:
        api.main._restore_active_matches(Repository(session), controller.state.id)
    restored = api.main.ACTIVE_MATCHES[controller.state.id]
    assert (snapshot(restored.state), controller_view(api, restored), db_dump(api.engine)) == before
    return restored


def printed(card):
    return deepcopy((card.type_line, card.oracle_text, card.colors, card.power, card.toughness,
                     card.printed_characteristics, card.counters, card.counter_timestamps))


def card_view(value, seat, cid):
    return next(card for card in value['players'][str(seat)]['battlefield'] if card['id'] == cid)


def assert_changed(value, seat, cid, name):
    card = card_view(value, seat, cid)
    assert card['type_line'].split('\u2014', 1)[1].strip().lower() == ('frog' if name == 'Turn to Frog' else 'snake')
    assert card['types'] == ['Creature'] and (card['power'], card['toughness']) == (3, 3)
    assert card['colors'] == (['U'] if name == 'Turn to Frog' else ['G'])
    assert card['keywords'] == [] and card['mana_source_amounts'] == {}
    assert card['counters']['+1/+1'] == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_paid_api_characteristics_native_cleanup_and_persistence(family_api, request, seat, name):
    api = family_api
    state, target, spell = position(seat, name)
    hidden = raw_card(state, ROWS['Snakeform'], 3-seat, Zone.HAND)
    controller = install(api, state, seat)
    before, original = snapshot(state), printed(target)
    post(api, controller, seat, cast_action(spell, target), hidden.id)
    assert snapshot(state) == before and sum(controller.state.players[seat].mana_pool.values()) == 0
    resolve_http(api, controller, hidden.id)
    changed = public(api, controller, hidden.id)
    assert_changed(changed, seat, target.id, name)
    assert printed(controller.state.cards[target.id]) == original
    resolved = snapshot(controller.state)
    controller = restore(api, controller)
    assert public(api, controller, hidden.id) == changed
    cleanup_http(api, controller, hidden.id)
    cleaned = public(api, controller, hidden.id)
    card = card_view(cleaned, seat, target.id)
    assert card['type_line'] == original[0] and card['colors'] == ['G']
    assert (card['power'], card['toughness']) == (2, 3) and 'flying' in card['keywords']
    from rules_engine.mana import repeatable_nonland_mana_outputs
    from rules_engine.mana_abilities import mana_ability_specs, source_ready
    capacity = {color: 1 for color in ('W', 'U', 'B', 'R', 'G')}
    restored_target = controller.state.cards[target.id]
    specs = mana_ability_specs(restored_target, controller.state)
    assert len(specs) == 1 and specs[0][1] == '{T}'
    assert printed(restored_target) == original
    assert repeatable_nonland_mana_outputs(restored_target, state=controller.state) == capacity
    assert controller.state.active_player == 3-seat
    assert not restored_target.tapped and restored_target.summoning_sick
    assert not source_ready(controller.state, restored_target, specs[0])
    assert card['mana_source_amounts'] == {}
    assert not controller.state.cards[target.id].type_effects
    assert snapshot(state) == before
    cleaned_state = snapshot(controller.state)
    cleanup_http(api, controller, hidden.id)
    assert controller.state.active_player == seat and controller.state.priority_player == seat
    ready_target = controller.state.cards[target.id]
    assert not ready_target.tapped and not ready_target.summoning_sick
    assert printed(ready_target) == original
    assert object_incarnation(ready_target) == object_incarnation(restored_target)
    assert source_ready(controller.state, ready_target, specs[0])
    ready = public(api, controller, hidden.id)
    assert card_view(ready, seat, target.id)['mana_source_amounts'] == capacity
    assert not any(controller.state.players[seat].mana_pool.values())
    activation_root = controller.state
    activation_before = snapshot(activation_root)
    action = {'type': 'activate_mana_ability', 'card_id': target.id,
              'ability_index': specs[0][0], 'color': 'G'}
    paid = post(api, controller, seat, action, hidden.id)
    assert snapshot(activation_root) == activation_before
    assert controller.state.cards[target.id].tapped
    assert {color: amount for color, amount in controller.state.players[seat].mana_pool.items()
            if amount} == {'G': 1}
    assert card_view(paid, seat, target.id)['mana_source_amounts'] == {}
    assert printed(controller.state.cards[target.id]) == original
    assert snapshot(state) == before
    receipt(request, storage=api.storage, before=before, resolved=resolved,
            after=snapshot(controller.state), public_changed=changed, public_cleaned=cleaned,
            cleaned_state=cleaned_state, public_ready=ready, activation_action=action,
            activation_before=activation_before, public_after_activation=paid,
            controller=controller_view(api, controller), sql_sha256=digest(db_dump(api.engine)))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_paid_cloudshift_reentry_persisted_old_target_fizzles_before_all_effects(family_api, request, seat, name):
    api = family_api
    state, target, spell = position(seat, name)
    hidden = raw_card(state, ROWS['Snakeform'], 3-seat, Zone.HAND)
    blink = raw_card(state, CLOUDSHIFT, seat, Zone.HAND)
    state.players[seat].mana_pool['W'] = 1
    controller = install(api, state, seat)
    before = snapshot(state)
    old = object_incarnation(target), target.zone_change_sequence
    post(api, controller, seat, cast_action(spell, target), hidden.id)
    refs = deepcopy(controller.state.stack[-1].payload['__announced_target_references'])
    post(api, controller, seat, cast_action(blink, target), hidden.id)
    for _ in range(2):
        pass_one(api, controller, hidden.id)
    assert len(controller.state.stack) == 1
    card = controller.state.cards[target.id]
    assert (object_incarnation(card), card.zone_change_sequence) != old
    pending = snapshot(controller.state)
    controller = restore(api, controller)
    assert controller.state.stack[-1].payload['__announced_target_references'] == refs
    resolve_http(api, controller, hidden.id)
    value = public(api, controller, hidden.id)
    assert controller.state.players[seat].library == state.players[seat].library
    assert controller.state.players[seat].hand == []
    card = card_view(value, seat, target.id)
    assert card['type_line'] == target.type_line and card['colors'] == ['G']
    assert card['power'] == 0 and card['toughness'] == 1 and 'flying' in card['keywords']
    assert not controller.state.cards[target.id].type_effects
    assert any('does not resolve' in line or 'fizzles' in line for line in controller.state.log)
    assert snapshot(state) == before
    receipt(request, storage=api.storage, before=before, pending=pending,
            after=snapshot(controller.state), public=value, target_receipts=refs,
            controller=controller_view(api, controller), sql_sha256=digest(db_dump(api.engine)))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('invalid', ['invalid_target', 'wrong_card_actor'])
def test_real_invalid_target_or_wrong_card_actor_422_is_fully_atomic(family_api, request, seat, name, invalid):
    api = family_api
    state, target, spell = position(seat, name)
    hidden = raw_card(state, ROWS[name], 3-seat, Zone.HAND)
    controller = install(api, state, seat)
    action = cast_action(spell, target)
    if invalid == 'invalid_target':
        action['targets']['target_card_id'] = state.players[seat].library[-1]
    else:
        action['card_id'] = hidden.id
    before = snapshot(state), controller_view(api, controller), db_dump(api.engine)
    database_hash_before = hashlib.sha256(api.path.read_bytes()).hexdigest()
    response = api.client.post('/matches/' + state.id + '/action',
                               json={'player_id': seat, 'action': action})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['code'] == 'illegal_action'
    assert (snapshot(controller.state), controller_view(api, controller), db_dump(api.engine)) == before
    assert hashlib.sha256(api.path.read_bytes()).hexdigest() == database_hash_before
    assert snapshot(state) == before[0]
    public(api, controller, hidden.id)
    receipt(request, storage=api.storage, invalid=invalid, before=before[0],
            controller=before[1], sql_dump=before[2], rejection=response.json())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('stage', ['pending', 'resolved'])
def test_fresh_process_local_file_restore_and_actual_http_continuation(file_api, request, seat, name, stage):
    api = file_api
    state, target, spell = position(seat, name)
    hidden = raw_card(state, ROWS['Snakeform'], 3-seat, Zone.HAND)
    controller = install(api, state, seat)
    post(api, controller, seat, cast_action(spell, target), hidden.id)
    if stage == 'resolved':
        resolve_http(api, controller, hidden.id)
    value = public(api, controller, hidden.id)
    expected = snapshot(controller.state)
    payload = {'database': str(api.path), 'match_id': state.id, 'seat': seat, 'name': name,
               'target_id': target.id, 'hidden_id': hidden.id, 'stage': stage,
               'state': expected, 'controller': controller_view(api, controller), 'public': value,
               'persistent_sql': db_dump(api.engine),
               'database_sha256': hashlib.sha256(api.path.read_bytes()).hexdigest(),
               'parent_pid': os.getpid(), 'root': str(ROOT)}
    evidence = Path(os.environ['MTG_FROG_HTTP_EVIDENCE'])
    config = evidence / (digest(request.node.nodeid) + '-cold-input.json')
    output = evidence / (digest(request.node.nodeid) + '-cold-result.json')
    with config.open('x') as stream:
        json.dump(payload, stream, sort_keys=True)
    api.main.ACTIVE_MATCHES.clear()
    api.close()
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1'}
    try:
        run = subprocess.run([sys.executable, str(Path(__file__).with_name('temporary_characteristics_http_probe.py')),
                              str(config), str(output)], cwd=ROOT, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        # subprocess.run kills and waits for its child before raising.
        with (evidence / (digest(request.node.nodeid) + '-cold-timeout.json')).open('x') as stream:
            json.dump({'timeout': 120, 'child_killed_and_waited': True,
                       'output': (error.stdout or b'').decode(errors='replace')
                       if isinstance(error.stdout, bytes) else error.stdout}, stream)
        raise
    with (evidence / (digest(request.node.nodeid) + '-cold.log')).open('x') as stream:
        stream.write(run.stdout)
    assert run.returncode == 0, run.stdout
    child = json.loads(output.read_text())
    assert child['pid'] != os.getpid() and child['parent_handles_closed']
    assert child['restored_state'] == expected and child['restored_controller'] == payload['controller']
    assert child['restored_public'] == value and child['connections_closed']
    receipt(request, stage=stage, storage='file', before=expected, child=child)
