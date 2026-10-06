"""New canonical tests-only audit; ordinary red expectations are not xfailed."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle, spell_resolution_text
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_spell_cost_overlap_investigation as cards


DIRECTORY = Path(__file__).parent / 'fixtures/spell_trigger_audit'
RAW = {row['name']: row for row in map(json.loads, (DIRECTORY / 'canonical.jsonl').read_text().splitlines())}
cards.ROWS.update(RAW)


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = cards.add(state, name, seat, zone)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def record(request, data):
    root = os.environ.get('MTG_SPELL_TRIGGER_EVIDENCE')
    if root:
        directory = Path(root)
        directory.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
        (directory / (key + '.json')).write_text(json.dumps(
            {'test': request.node.nodeid, **data}, indent=2, sort_keys=True) + '\n')


def position(seat, name='Renewed Faith'):
    state = cards.position(seat)
    source = add(state, name, seat, Zone.HAND)
    for name in ['Island', 'Forest', 'Swamp']:
        add(state, name, seat, Zone.LIBRARY)
    state.players[seat].mana_pool = {'C': 2, 'W': 1, 'U': 1}
    return state, source


def test_raw_records_unchanged():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert hashlib.sha256((DIRECTORY / 'canonical.jsonl').read_bytes()).hexdigest() == provenance['fixture_sha256']
    assert not provenance['facts_modified'] and provenance['offline']
    assert len(RAW) == 10
    for row in provenance['rows']:
        assert RAW[row['name']]['id'] == row['id']
        assert RAW[row['name']]['oracle_id'] == row['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
def test_spell_compiler_does_not_promote_cycling_trigger_instruction(request, seat):
    state, source = position(seat)
    with cards.unchanged_root(state):
        surface = spell_resolution_text(source, source.oracle_text)
        compiled = infer_effect_from_oracle(state, source, seat)
    record(request, {'oracle': source.oracle_text, 'surface': surface,
                     'compiled': compiled, 'setup': serialize_match_snapshot(state)})
    assert 'When you cycle' not in surface
    assert compiled == ('gain_life', {'amount': 6})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('watcher', [False, True])
def test_actual_normal_cast_gains_six_not_eight_and_keeps_external_cast_trigger(request, seat, watcher):
    state, source = position(seat)
    if watcher:
        add(state, 'Shark Typhoon', seat)
    action = cards.cast(source)
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, action)
    queued = [asdict(item) for item in paid.stack]
    for _ in range(4):
        if not paid.stack:
            break
        assert resolve_top_of_stack(paid)
    sharks = [paid.cards[cid] for cid in paid.players[seat].battlefield if paid.cards[cid].is_token]
    record(request, {'action': action, 'queued': queued, 'expected_life': 26,
                     'actual_life': paid.players[seat].life,
                     'resolved': serialize_match_snapshot(paid)})
    assert len(sharks) == int(watcher)
    if watcher:
        assert sharks[0].power == sharks[0].toughness == 3
    assert paid.players[seat].life == 26
    assert not paid.draws_this_turn.get(seat, 0)


@pytest.mark.parametrize('seat', [1, 2])
def test_ordinary_cycling_reminder_does_not_add_an_extra_draw_to_normal_spell(request, seat):
    state, source = position(seat, 'Hieroglyphic Illumination')
    state.players[seat].mana_pool = {'C': 3, 'U': 1}
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, cards.cast(source))
    assert resolve_top_of_stack(paid)
    record(request, {'resolved': serialize_match_snapshot(paid)})
    assert len(paid.players[seat].hand) == 2
    assert len(paid.players[seat].library) == 1


def test_spell_conditionals_are_not_triggered_ability_lines_to_strip():
    state, source = position(1, 'Sunset Revelry')
    with cards.unchanged_root(state):
        surface = spell_resolution_text(source, source.oracle_text)
    assert surface == source.oracle_text


@pytest.fixture
def offline_http(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Canonical audit forbids external sockets')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    original = dict(main.ACTIVE_MATCHES)
    try:
        with TestClient(main.app) as client:
            with Session(engine) as session:
                repo = Repository(session)
                for raw in RAW.values():
                    repo.upsert_card({'scryfall_id': raw['id'], 'name': raw['name'],
                        'oracle_text': raw.get('oracle_text', ''), 'mana_cost': raw.get('mana_cost', ''),
                        'type_line': raw.get('type_line', ''), 'layout': raw.get('layout', ''),
                        'colors': ','.join(raw.get('colors', [])), 'power': raw.get('power'),
                        'toughness': raw.get('toughness'), 'card_faces_json': json.dumps(raw.get('card_faces', [])),
                        'legalities_json': json.dumps(raw.get('legalities', {}))})
            yield client
    finally:
        main.ACTIVE_MATCHES.clear()
        main.ACTIVE_MATCHES.update(original)


def install(state, seat, request, private=False):
    state.id = 'spell-surface-' + hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16]
    match = main.MatchController(state=state, rules=RulesEngine(),
        controllers={pid: 'ai' if private and pid != seat else 'human' for pid in (1, 2)},
        ai={pid: main.AIAgent(difficulty='master', archetype='Midrange', opponent_archetype='Midrange') for pid in (1, 2)},
        mode='player_vs_ai' if private else 'human_vs_human', deck_ids=(None, None),
        mainboards={1: [], 2: []}, sideboards={1: [], 2: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=1, root_seed=37)
    main.ACTIVE_MATCHES[state.id] = match
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)
    return match


def restore(identifier):
    match = main.ACTIVE_MATCHES[identifier]
    before = serialize_match_snapshot(match.state), deepcopy(main._controller_snapshot(match))
    main.ACTIVE_MATCHES.pop(identifier)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), identifier)
    match = main.ACTIVE_MATCHES[identifier]
    assert (serialize_match_snapshot(match.state), main._controller_snapshot(match)) == before
    return match


def snapshot(match):
    with sqlite3.connect(DATABASE_PATH) as db:
        database = list(db.iterdump())
    return serialize_match_snapshot(match.state), deepcopy(main._controller_snapshot(match)), database


def act(client, match, actor, action):
    return client.post('/matches/' + match.state.id + '/action', json={'player_id': actor, 'action': action})


def settle(client, identifier, seat, accept=True):
    choices = []
    for _ in range(12):
        match = restore(identifier)
        pending = match.state.pending_trigger_order
        if pending:
            assert pending['phase'] == 'optional'
            action = {'type': 'choose_optional_effect', 'stack_id': pending['current_stack_id'], 'accept': accept}
            choices.append(deepcopy(pending))
            response = act(client, match, seat, action)
        elif not match.state.stack:
            return match, choices
        elif match.controllers[match.state.priority_player] == 'ai':
            response = client.post('/matches/' + identifier + '/autoplay?ticks=1')
        else:
            response = act(client, match, match.state.priority_player, {'type': 'pass_priority'})
        assert response.status_code == 200, response.text
    raise AssertionError('Bounded expected stack continuation did not finish')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cycling', [False, True])
@pytest.mark.parametrize('accept', [False, True])
def test_actual_human_http_cast_vs_cycle_optional_private_restart(request, offline_http, seat, cycling, accept):
    state, source = position(seat)
    secret = add(state, 'Swamp', 3-seat, Zone.HAND)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    match = install(state, seat, request, private=True)
    action = {'type': 'cycle_card' if cycling else 'cast_spell', 'card_id': source.id}
    before = snapshot(match)
    rejected = act(offline_http, match, 3-seat, action)
    assert rejected.status_code == 403
    assert snapshot(match) == before
    response = act(offline_http, match, seat, action)
    assert response.status_code == 200, response.text
    queued = serialize_match_snapshot(restore(state.id).state)
    match, choices = settle(offline_http, state.id, seat, accept)
    public = main._serialize_match_controller(match)
    assert secret.id not in json.dumps(public) and public['root_seed'] is None
    record(request, {'action': action, 'queued': queued, 'choices': choices,
        'private_rejected_status': rejected.status_code, 'public': public,
        'expected_life': 20 + (2 if accept else 0) if cycling else 26,
        'actual_life': match.state.players[seat].life, 'resolved': serialize_match_snapshot(match.state)})
    assert bool(choices) == cycling
    assert match.state.players[seat].life == (20 + (2 if accept else 0) if cycling else 26)
    assert match.state.draws_this_turn.get(seat, 0) == int(cycling)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Drake Haven', 'Faith of the Devoted'])
@pytest.mark.parametrize('funded', [False, True])
def test_paid_optional_boundary_actual_http_is_not_a_free_reward(request, offline_http, seat, name, funded):
    state, source = position(seat, 'Hieroglyphic Illumination')
    watcher = add(state, name, seat)
    state.players[seat].mana_pool = {'U': 1, 'C': int(funded)}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    match = install(state, seat, request)
    response = act(offline_http, match, seat, {'type': 'cycle_card', 'card_id': source.id})
    assert response.status_code == 200, response.text
    queued = serialize_match_snapshot(restore(state.id).state)
    match, choices = settle(offline_http, state.id, seat)
    record(request, {'canonical_watcher': RAW[name], 'queued': queued, 'choices': choices,
                     'resolved': serialize_match_snapshot(match.state)})
    assert not choices
    assert not any(match.state.cards[cid].is_token for cid in match.state.players[seat].battlefield)
    assert match.state.players[seat].life == match.state.players[3-seat].life == 20
    assert match.state.players[seat].mana_pool.get('C', 0) == int(funded)
    assert any('Unsupported optional trigger payment' in line for line in match.state.log)
    assert any(item['payload'].get('__unsupported_trigger_instruction') for item in queued['stack'])


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_cast_trigger_uses_only_its_matched_instruction(request, offline_http, seat):
    state, source = position(seat)
    add(state, 'Shark Typhoon', seat)
    match = install(state, seat, request)
    response = act(offline_http, match, seat, cards.cast(source))
    assert response.status_code == 200, response.text
    queued = serialize_match_snapshot(restore(state.id).state)
    match, choices = settle(offline_http, state.id, seat)
    sharks = [match.state.cards[cid] for cid in match.state.players[seat].battlefield
              if match.state.cards[cid].is_token]
    record(request, {'queued': queued, 'expected_sharks': 1, 'actual_sharks': len(sharks),
                     'expected_life': 26, 'actual_life': match.state.players[seat].life,
                     'resolved': serialize_match_snapshot(match.state)})
    assert not choices and len(sharks) == 1
    assert sharks[0].power == sharks[0].toughness == 3
    assert match.state.players[seat].life == 26
