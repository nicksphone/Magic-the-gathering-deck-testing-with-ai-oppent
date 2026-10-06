"""Funded canonical observer audit; retained board setup is not natural play."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine import events
from rules_engine.targeting import stack_object_kind
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import act, restart, snap
from tests.test_trigger_instruction_compilation_audit import passes
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import client, install, public_private_restore, main_controller_snapshot
from tests.test_trigger_instruction_compilation_http_audit import submit, responses
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/creature_observer_audit'
ROWS = {}
for entry in json.loads((FIXTURE / 'provenance.json').read_text())['cards']:
    data = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    row = json.loads(data)
    assert row['oracle_id'] == entry['oracle_id'] and row['object'] == 'card'
    ROWS[row['name']] = row
FAMILIES = ('Primordial Sage', 'Soul of the Harvest')


@pytest.fixture(autouse=True)
def trace(monkeypatch, tmp_path):
    log = []
    emit, compiler = events.emit_event, events._trigger_from_oracle
    collect = events._collect_triggers
    def observed_collect(state, event, payload):
        log.append({"kind": "event", "event": event, "payload": deepcopy(payload)})
        return collect(state, event, payload)
    def observed_emit(state, event, payload):
        log.append({'kind': 'event', 'event': event, 'payload': deepcopy(payload)})
        return emit(state, event, payload)
    def observed_compile(state, source_card_id, controller, oracle, default_label, event, payload):
        source = source_card_id
        result = compiler(state, source, controller, oracle, default_label, event, payload)
        log.append({'kind': 'compile', 'source': source, 'controller': controller,
                    'oracle': oracle, 'event': event, 'result': deepcopy(result)})
        return result
    monkeypatch.setattr(events, 'emit_event', observed_emit)
    monkeypatch.setattr(events, '_collect_triggers', observed_collect)
    monkeypatch.setattr(events, '_trigger_from_oracle', observed_compile)
    yield log
    (tmp_path / 'observer-trace.json').write_text(json.dumps(log, default=str, sort_keys=True))


def position(name, seat, stimulus='Grizzly Bears', actor=None, self_entry=False):
    deck = [{**ROWS['Island'], 'card_name': 'Island', 'quantity': 24}]
    state = MatchFactory.from_decks(deck, deck, seed=8721)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    actor = actor or seat
    state.active_player = state.priority_player = actor
    state.step = Step.PRECOMBAT_MAIN
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    observer = raw_card(state, ROWS[name], seat, Zone.HAND if self_entry else Zone.BATTLEFIELD)
    card = observer if self_entry else raw_card(state, ROWS[stimulus], actor, Zone.HAND)
    pools = {'Grizzly Bears': {'C': 1, 'G': 1}, 'Raise the Alarm': {'C': 1, 'W': 1},
             'Soul of the Harvest': {'C': 4, 'G': 2}, 'Primordial Sage': {'C': 4, 'G': 2},
             'Village Rites': {'B': 1}}
    state.players[actor].mana_pool = pools[card.name]
    return state, observer.id, card.id, {'type': 'cast_spell', 'card_id': card.id, 'targets': {}}


def observer_items(state, oid):
    return [s for s in state.stack if s.source_card_id == oid and stack_object_kind(state, s) == 'triggered']


def trigger_boundary(state, seat, name, action):
    state = act(state, seat, action)
    assert sum(state.players[seat].mana_pool.values()) == 0
    return passes(state) if name == 'Soul of the Harvest' else state


def optional(state, seat, oid, accept, tmp_path):
    state = passes(state)
    choices = [m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'choose_optional_effect']
    assert len(choices) == 2 and {m['accept'] for m in choices} == {False, True}, 'Printed you-may draw needs both deliberate choices'
    assert state.stack[-1].source_card_id == oid
    before = len(state.players[seat].hand)
    state = act(restart(state, tmp_path, 'optional'), seat,
                {'type': 'choose_optional_effect', 'stack_id': choices[0]['stack_id'], 'accept': accept})
    assert len(state.players[seat].hand) == before + int(accept)
    return state


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_paid_observer_deliberate_optional_draw(name, seat, accept, tmp_path, trace):
    state, oid, cid, action = position(name, seat)
    state = trigger_boundary(state, seat, name, action)
    state = restart(state, tmp_path, 'trigger-boundary')
    (tmp_path / 'boundary.json').write_text(json.dumps(snap(state), sort_keys=True))
    assert len(observer_items(state, oid)) == 1, 'Canonical observer missing at actual cast/entry boundary'
    assert observer_items(state, oid)[0].controller == seat
    optional(state, seat, oid, accept, tmp_path)


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stimulus', ['opponent', 'noncreature', 'self_entry'])
def test_observer_filters_on_paid_real_actions(name, seat, stimulus, trace):
    actor = 3-seat if stimulus == 'opponent' else seat
    state, oid, cid, action = position(name, seat, 'Raise the Alarm' if stimulus == 'noncreature' else 'Grizzly Bears',
                                       actor, self_entry=stimulus == 'self_entry')
    state = act(state, actor, action)
    assert not observer_items(state, oid)
    state = passes(state)
    assert state.cards[cid].zone in (Zone.BATTLEFIELD, Zone.GRAVEYARD)
    assert not observer_items(state, oid)
    if stimulus == 'noncreature':
        tokens = [c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD]
        assert len(tokens) == 2 and all(c.controller == actor for c in tokens)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accept', [False, True])
def test_existing_optional_handler_control_real_paid_death(seat, accept, tmp_path):
    state, oid, cid, action = position('Harvester of Souls', seat, 'Village Rites')
    victim = raw_card(state, ROWS['Grizzly Bears'], seat, Zone.BATTLEFIELD)
    action['cost_choice'] = {'id': 'base', 'sacrifice_card_ids': [victim.id]}
    state = act(state, seat, action)
    assert len(observer_items(state, oid)) == 1
    state = optional(state, seat, oid, accept, tmp_path)
    state = passes(state)
    assert len(state.players[seat].hand) == 2 + int(accept)
    assert state.cards[victim.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
def test_source_departure_response_does_not_cancel_observer(name, seat, tmp_path):
    state, oid, cid, action = position(name, seat)
    state = trigger_boundary(state, seat, name, action)
    assert len(observer_items(state, oid)) == 1, 'Missing observer blocks canonical pending-trigger response episode'
    actor = state.priority_player
    bounce = raw_card(state, ROWS['Unsummon'], actor, Zone.HAND)
    state.players[actor].mana_pool = {'U': 1}
    state = act(state, actor, {'type': 'cast_spell', 'card_id': bounce.id, 'targets': {'target_card_id': oid}})
    state = passes(state)
    assert state.cards[oid].zone == Zone.HAND
    state = restart(state, tmp_path, 'source-gone')
    assert len(observer_items(state, oid)) == 1
    optional(state, seat, oid, True, tmp_path)


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['wrong_actor', 'underpaid'])
def test_http_invalid_cast_root_database_atomic(repo, client, name, seat, bad):
    for row in ROWS.values(): repo.upsert_card(normalize(row))
    state, oid, cid, action = position(name, seat)
    if bad == 'underpaid': state.players[seat].mana_pool = {}
    controller = install(repo, client, state)
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={
        'player_id': 3-seat if bad == 'wrong_actor' else seat, 'action': action})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
def test_http_actual_observer_cold_restore_privacy(repo, client, name, seat, tmp_path):
    for row in ROWS.values(): repo.upsert_card(normalize(row))
    state, oid, cid, action = position(name, seat)
    controller = install(repo, client, state)
    submit(client, controller, seat, action)
    if name == 'Soul of the Harvest': responses(client, controller)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    (tmp_path / 'boundary.json').write_text(json.dumps(snap(controller.state), sort_keys=True))
    assert len(observer_items(controller.state, oid)) == 1, 'HTTP observer missing after actual paid cast/entry and cold restore'
    responses(client, controller)
    choices = [m for m in RulesEngine().legal_moves(controller.state, seat) if m['type'] == 'choose_optional_effect']
    assert len(choices) == 2 and {m['accept'] for m in choices} == {False, True}
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + state.id + '/action', json={'player_id': 3-seat,
        'action': {'type': 'choose_optional_effect', 'stack_id': choices[0]['stack_id'], 'accept': True}})
    assert rejected.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    submit(client, controller, seat, {'type': 'choose_optional_effect', 'stack_id': choices[0]['stack_id'], 'accept': True})
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    assert len(controller.state.players[seat].hand) == 1


@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('seat', [1, 2])
def test_offline_compiler_probe_from_actual_emitted_event(name, seat, trace, tmp_path):
    state, oid, cid, action = position(name, seat)
    state = trigger_boundary(state, seat, name, action)
    event = 'spell_cast' if name == 'Primordial Sage' else 'enters_battlefield'
    actual = [row for row in trace if row['kind'] == 'event' and row['event'] == event
              and row['payload'].get('source_card_id' if event == 'spell_cast' else 'card_id') == cid]
    assert actual, 'Read-only probe requires an actual emitted paid-action event'
    before = snap(state)
    probe = deepcopy(state)
    compiled = events._trigger_from_oracle(probe, oid, seat, state.cards[oid].oracle_text.lower(),
                                          'offline compiler probe only', event, actual[-1]['payload'])
    (tmp_path / 'compiler-probe.json').write_text(json.dumps(compiled, sort_keys=True))
    assert snap(state) == before, 'Diagnostic probe cannot mutate real state or install a trigger'
    assert compiled['source_card_id'] == oid and compiled['controller'] == seat
    assert compiled['effect_key'] == 'draw_cards' and compiled['payload']['amount'] == 1
    assert compiled['payload']['__may'] is True
