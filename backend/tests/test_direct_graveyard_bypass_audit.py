"""Two-family strict audit: canonical spell resolution and pending sacrifice.

Annihilator positions are trusted pending-trigger setups, NOT combat episodes.
HTTP uses actual ASGI routes with owned repositories, not fabricated responses.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import pytest

from ai.information import decision_view, is_unknown
from effects import handlers
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine import events
from rules_engine.replacement import graveyard_entry_plans
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_linked_damage_targets import raw_card
from tests.test_library_reorder import setup
from tests.test_self_graveyard_replacement_audit import snap, restart, act

FIXTURE = Path(__file__).parent / 'fixtures/direct_graveyard_audit/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}
SELF = ['Darksteel Colossus', 'Progenitus']


@pytest.fixture
def client(base_client, repo, monkeypatch):
    import main
    # Cold read-only routes have no injected repo argument; use the same owned
    # engine as the HTTP write dependency, not a default empty local database.
    monkeypatch.setattr(main, 'engine', repo.session.get_bind())
    return base_client


def board(seat, name, foreign=False, observers=False):
    state, _ = setup('Index', seat)
    victim = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    if foreign:
        # Trusted retained control/ownership position; not a control spell claim.
        victim.owner = 3-seat
    sources = {}
    if observers:
        for observer in ['Psychogenic Probe', "Cosi's Trickster", 'Blood Artist']:
            sources[observer] = raw_card(state, ROWS[observer], 3-seat, Zone.BATTLEFIELD).id
    return state, victim, sources


def pending_sacrifice(seat, name, foreign=False, observers=False):
    state, victim, sources = board(seat, name, foreign, observers)
    source = raw_card(state, ROWS['Kozilek, Butcher of Truth'], 3-seat, Zone.BATTLEFIELD)
    amount = int(re.search(r'Annihilator (\d+)', source.oracle_text).group(1))
    # Invoke the real resolver on an exact canonical ability; do not attack or
    # claim an HTTP attack caused this trusted input position.
    add_to_stack(state, source.id, 3-seat, source.name + ' annihilator ' + str(amount),
                 'annihilator', {'target_player': seat, 'amount': amount}, is_spell=False)
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['count'] == 1
    assert state.pending_mechanic_choice['options'] == [victim.id]
    return state, victim, source, sources


def select(victim):
    return {'type': 'choose_mechanic', 'card_ids': [victim.id]}


def cast(state, seat, name, target=None):
    source = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 2, 'B': 2, 'R': 1, 'C': 2}
    action = {'type': 'cast_spell', 'card_id': source.id,
              'targets': {} if target is None else {'target_card_id': target.id}}
    return source, action


@pytest.fixture
def receipts(monkeypatch, tmp_path):
    from rules_engine import state_based_actions
    rows = []
    single, batch = events.emit_event, events.emit_event_batch
    def record(state, event, payload):
        cid = payload.get('card_id')
        card = state.cards.get(cid)
        rows.append({'event': event, 'card_id': cid, 'controller': payload.get('controller'),
                     'zone': card.zone.value if card else None,
                     'sequence': card.zone_change_sequence if card else None,
                     'incarnation': object_incarnation(card) if card else None})
    def one(state, event, payload):
        record(state, event, payload)
        return single(state, event, payload)
    def many(state, event, payloads):
        for payload in payloads:
            record(state, event, payload)
        return batch(state, event, payloads)
    monkeypatch.setattr(events, 'emit_event', one)
    monkeypatch.setattr(events, 'emit_event_batch', many)
    monkeypatch.setattr(handlers, 'emit_event', one)
    monkeypatch.setattr(handlers, 'emit_event_batch', many)
    monkeypatch.setattr(state_based_actions, 'emit_event', one)
    monkeypatch.setattr(state_based_actions, 'emit_event_batch', many)
    yield rows
    (tmp_path / 'observed-events.json').write_text(json.dumps(rows, indent=2))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_paid_untargeted_wrath_progenitus_uses_owner_library(seat, foreign, tmp_path):
    state, victim, _ = board(seat, 'Progenitus', foreign)
    source, action = cast(state, seat, 'Wrath of God')
    result = act(restart(state, tmp_path, 'before-wrath'), seat, action)
    assert next(item for item in result.stack if item.source_card_id == source.id).effect_key == 'destroy_all_creatures'
    assert resolve_top_of_stack(result)
    result = restart(result, tmp_path, 'after-wrath')
    assert result.cards[victim.id].zone == Zone.LIBRARY, 'Untargeted destruction does not bypass self-library replacement'
    assert victim.id in result.players[victim.owner].library
    assert all(victim.id not in p.graveyard for p in result.players.values())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('foreign', [False, True])
def test_pending_mechanic_self_library_and_owner(seat, name, foreign, tmp_path):
    state, victim, _, _ = pending_sacrifice(seat, name, foreign)
    result = act(restart(state, tmp_path, 'pending'), seat, select(victim))
    result = restart(result, tmp_path, 'chosen')
    assert result.cards[victim.id].zone == Zone.LIBRARY, 'Pending sacrifice still bypasses shared graveyard executor'
    assert result.players[victim.owner].library.count(victim.id) == 1
    assert all(victim.id not in p.battlefield and victim.id not in p.graveyard for p in result.players.values())
    assert result.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_pending_sacrifice_static_cause_and_no_false_dies(seat, name, tmp_path, receipts):
    state, victim, source, observers = pending_sacrifice(seat, name, observers=True)
    reference = {'incarnation': object_incarnation(victim), 'zone_change_sequence': victim.zone_change_sequence}
    result = act(state, seat, select(victim))
    result = restart(result, tmp_path, 'cause')
    items = [item for item in result.stack if item.source_card_id == observers['Psychogenic Probe']]
    assert len(items) == 1, 'A replacement shuffle needs its real static ability cause'
    cause = items[0].payload['__shuffle_cause']
    assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
    assert cause['source_card_id'] == victim.id and cause['source_card_id'] != source.id
    assert cause['source_owner'] == victim.owner and cause['controller'] == seat
    assert cause['source_zone'] == 'battlefield' and cause['source_reference'] == reference
    assert 'stack_id' not in cause
    assert any(item.source_card_id == observers["Cosi's Trickster"] for item in result.stack)
    assert not any(item.source_card_id == observers['Blood Artist'] for item in result.stack)
    assert not any(row['card_id'] == victim.id and row['event'] in {'permanent_dies', 'creature_dies'} for row in receipts)
    assert any(row['card_id'] == victim.id and row['event'] == 'leaves_battlefield'
               and row['sequence'] == reference['zone_change_sequence'] for row in receipts)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', [*SELF, 'Doomed Traveler'])
def test_mechanic_transition_advances_identity_after_lbf(seat, name, receipts):
    state, victim, _, _ = pending_sacrifice(seat, name)
    sequence, incarnation = victim.zone_change_sequence, object_incarnation(victim)
    result = act(state, seat, select(victim))
    assert result.cards[victim.id].zone_change_sequence == sequence + 1
    assert object_incarnation(result.cards[victim.id]) == incarnation
    assert any(row['card_id'] == victim.id and row['event'] == 'leaves_battlefield'
               and row['sequence'] == sequence and row['zone'] == 'battlefield' for row in receipts)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_competing_pending_replacements_reject_without_mutation(seat, name):
    state, victim, _, _ = pending_sacrifice(seat, name)
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    assert len(graveyard_entry_plans(state, victim.id)) == 2
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, select(victim))
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('bad', ['duplicate', 'wrong_seat', 'foreign', 'stale'])
def test_invalid_mechanic_selection_keeps_full_root(seat, name, bad):
    state, victim, _, _ = pending_sacrifice(seat, name)
    action, actor = select(victim), seat
    if bad == 'duplicate': action['card_ids'] *= 2
    if bad == 'wrong_seat': actor = 3-seat
    if bad == 'foreign': action['card_ids'] = [raw_card(state, ROWS[name], 3-seat, Zone.BATTLEFIELD).id]
    if bad == 'stale':
        state.players[seat].battlefield.remove(victim.id)
        victim.move_to_zone(Zone.EXILE)
        state.players[victim.owner].exile.append(victim.id)
    before = snap(state)
    with pytest.raises(ActionRejected): checked_action(state, RulesEngine(), actor, action)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('rip', [False, True])
def test_humility_suppression_retains_real_destination_not_library(seat, name, rip):
    state, victim, _, _ = pending_sacrifice(seat, name)
    raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    if rip: raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    result = act(state, seat, select(victim))
    expected = Zone.EXILE if rip else Zone.GRAVEYARD
    assert result.cards[victim.id].zone == expected
    assert victim.id in getattr(result.players[victim.owner], expected.value)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_murder_cannot_destroy_unsuppressed_colossus(seat):
    state, victim, _ = board(seat, 'Darksteel Colossus')
    _, action = cast(state, seat, 'Murder', victim)
    result = act(state, seat, action)
    assert resolve_top_of_stack(result)
    assert result.cards[victim.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_real_murder_cannot_target_unsuppressed_progenitus(seat):
    state, victim, _ = board(seat, 'Progenitus')
    _, action = cast(state, seat, 'Murder', victim)
    before = snap(state)
    with pytest.raises(ActionRejected): checked_action(state, RulesEngine(), seat, action)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_wrath_cannot_destroy_unsuppressed_colossus(seat):
    state, victim, _ = board(seat, 'Darksteel Colossus')
    _, action = cast(state, seat, 'Wrath of God')
    result = act(state, seat, action)
    assert resolve_top_of_stack(result)
    assert result.cards[victim.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_bolt_lethal_handler_identity(seat, receipts):
    state, victim, _ = board(seat, 'Doomed Traveler')
    _, action = cast(state, seat, 'Lightning Bolt', victim)
    result = act(state, seat, action)
    assert resolve_top_of_stack(result)
    assert result.cards[victim.id].zone == Zone.GRAVEYARD
    assert result.cards[victim.id].zone_change_sequence == victim.zone_change_sequence + 1
    assert any(row['card_id'] == victim.id and row['event'] == 'creature_dies' for row in receipts)


def install(repo, client, state):
    import main
    for row in ROWS.values(): repo.upsert_card(normalize(row))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return controller


def public_private_restore(repo, client, controller, seat, tmp_path):
    import main
    before = snap(controller.state)
    identifier = controller.state.id
    main.ACTIVE_MATCHES.pop(identifier)
    response = client.get('/matches/' + identifier)
    assert response.status_code == 200
    restored = main.ACTIVE_MATCHES[identifier]
    assert snap(restored.state) == before
    view, _ = decision_view(restored.state, 3-seat, RulesEngine().legal_moves(restored.state, 3-seat))
    assert all(is_unknown(view.cards[cid]) for cid in restored.state.players[seat].hand + restored.state.players[seat].library)
    restored.state = restart(restored.state, tmp_path, 'http-restart')
    assert snap(restored.state) == before
    return restored


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_http_trusted_pending_choice_owner_library_after_restore(repo, client, seat, name, tmp_path):
    state, victim, _, _ = pending_sacrifice(seat, name)
    controller = install(repo, client, state)
    before = snap(state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + state.id + '/action', json={'player_id': 3-seat, 'action': select(victim)})
    assert rejected.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': select(victim)})
    assert response.status_code == 200, response.text
    restored = public_private_restore(repo, client, controller, seat, tmp_path)
    assert restored.state.cards[victim.id].zone == Zone.LIBRARY


def main_controller_snapshot(controller):
    import main
    return main._controller_snapshot(controller)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Progenitus', 'Darksteel Colossus', 'Doomed Traveler'])
def test_http_actual_paid_wrath_and_two_priority_passes(repo, client, seat, name, tmp_path):
    state, victim, _ = board(seat, name)
    source, action = cast(state, seat, 'Wrath of God')
    controller = install(repo, client, state)
    root = snap(state), main_controller_snapshot(controller), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={'player_id': 3-seat, 'action': action})
    assert response.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == root
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert source.id in [item.source_card_id for item in controller.state.stack]
    assert sum(controller.state.players[seat].mana_pool.values()) == 3
    for _ in range(2):
        actor = controller.state.priority_player
        response = client.post('/matches/' + state.id + '/action', json={'player_id': actor, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    restored = public_private_restore(repo, client, controller, seat, tmp_path)
    expected = {'Progenitus': Zone.LIBRARY, 'Darksteel Colossus': Zone.BATTLEFIELD, 'Doomed Traveler': Zone.GRAVEYARD}[name]
    assert restored.state.cards[victim.id].zone == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('route', ['wrath', 'mechanic'])
def test_readonly_observation_receipts_not_a_rules_acceptance(seat, name, route, tmp_path, receipts):
    if route == 'mechanic':
        state, victim, source, observers = pending_sacrifice(seat, name, observers=True)
        action = select(victim)
    else:
        state, victim, observers = board(seat, name, observers=True)
        source, action = cast(state, seat, 'Wrath of God')
    before = snap(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert snap(state) == before
    if route == 'wrath': assert resolve_top_of_stack(result)
    card = result.cards[victim.id]
    data = {'route': route, 'seat': seat, 'name': name,
            'setup': 'trusted pending trigger, no attack' if route == 'mechanic' else 'retained canonical board, actual paid cast',
            'source': {'id': source.id, 'name': source.name, 'oracle_text': source.oracle_text},
            'destination': card.zone.value, 'owner': card.owner, 'controller': card.controller,
            'sequence_before': victim.zone_change_sequence, 'sequence_after': card.zone_change_sequence,
            'lki': card.last_known_battlefield,
            'probe_receipts': sum(item.source_card_id == observers['Psychogenic Probe'] for item in result.stack),
            'cosi_receipts': sum(item.source_card_id == observers["Cosi's Trickster"] for item in result.stack),
            'blood_artist_receipts': sum(item.source_card_id == observers['Blood Artist'] for item in result.stack),
            'events': receipts, 'before': before, 'after': snap(result)}
    (tmp_path / 'readonly-observation.json').write_text(json.dumps(data, indent=2))
    assert card.oracle_text == ROWS[name]['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_http_invalid_duplicate_mechanic_keeps_controller_and_sql(repo, client, seat, name):
    state, victim, _, _ = pending_sacrifice(seat, name)
    controller = install(repo, client, state)
    before = snap(state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={
        'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': [victim.id, victim.id]}})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
