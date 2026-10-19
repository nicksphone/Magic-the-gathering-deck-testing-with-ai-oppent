"""Paid simultaneous SBA/destruction: strict publication frontier diagnostics."""
from collections import Counter
from copy import deepcopy
import json

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from rules_engine import events
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.generic_import_fixtures import client as base_client
from tests.readiness_rules_seam_support import normalize
from tests.scheduler_fixture_position import ordinary_position
from tests.test_builtin_metadata_refresh import repo
from tests.test_direct_graveyard_bypass_audit import ROWS as DIRECT
from tests.test_kozilek_graveyard_trigger_audit import KOZILEK, passes
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS as SELF, act, restart, snap
from tests.test_spell_admission_safety_http import sql_facts

ROWS = {**DIRECT, 'Sickening Dreams': SELF['Sickening Dreams']}
COHORT_NAMES = {KOZILEK, 'Doomed Traveler', 'Blood Artist', 'Progenitus'}


@pytest.fixture
def client(base_client, repo, monkeypatch):
    import main
    monkeypatch.setattr(main, 'engine', repo.session.get_bind())
    return base_client


@pytest.fixture
def collected(monkeypatch, tmp_path):
    original = events._collect_triggers
    states, trace = [], []

    def collect(state, event, payload):
        result = original(state, event, payload)
        if not any(state is current for current in states):
            states.append(state)
        index = next(i for i, current in enumerate(states) if state is current)
        cohort = {cid: {'name': card.name, 'zone': card.zone.value,
                        'sequence': card.zone_change_sequence, 'owner': card.owner,
                        'membership': cid in getattr(state.players[card.owner], card.zone.value, [])}
                  for cid, card in state.cards.items() if card.name in COHORT_NAMES}
        trace.append({'state_index': index, 'event': event, 'payload': deepcopy(payload),
                      'cohort': cohort, 'collected': deepcopy(result)})
        return result

    monkeypatch.setattr(events, '_collect_triggers', collect)
    yield trace, states
    (tmp_path / 'actual-collector-frontier.json').write_text(json.dumps(trace, sort_keys=True, default=str))


def position(seat, family, *, ordering=False, protected_control=False):
    state, _ = setup('Index', seat, size=16)
    ordinary_position(state)  # Explicit controlled phase fixture, never runtime repair.
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = ordering
    state.trigger_order_choice_players = {1, 2}
    progenitus = (raw_card(state, ROWS['Progenitus'], seat, Zone.BATTLEFIELD)
                  if family == 'wrath' or protected_control else None)
    colossus = raw_card(state, ROWS['Darksteel Colossus'], 3-seat, Zone.BATTLEFIELD)
    cohort, observers, references = {}, {}, {}
    for pid in (seat, 3-seat):
        observers[pid] = {}
        for name in (KOZILEK, 'Doomed Traveler', 'Blood Artist'):
            card = raw_card(state, ROWS[name], pid, Zone.BATTLEFIELD)
            cohort[card.id] = Zone.GRAVEYARD.value
            observers[pid][name] = card.id
            references[card.id] = card.zone_change_sequence
        observers[pid]['Psychogenic Probe'] = raw_card(
            state, ROWS['Psychogenic Probe'], pid, Zone.BATTLEFIELD).id
    if family == 'wrath':
        name, mana = 'Wrath of God', {'W': 2, 'C': 2}
        cohort[progenitus.id] = Zone.LIBRARY.value
        action = {'type': 'cast_spell', 'targets': {}}
    else:
        name, mana = 'Sickening Dreams', {'B': 1, 'C': 1}
        # Controlled starting hand of twelve existing canonical basics, not a deck edit.
        while len(state.players[seat].hand) < 12:
            cid = state.players[seat].library.pop()
            state.cards[cid].move_to_zone(Zone.HAND)
            state.players[seat].hand.append(cid)
        discards = list(state.players[seat].hand[:12])
        action = {'type': 'cast_spell', 'targets': {'x_value': 12},
                  'cost_choice': {'id': 'base', 'discard_card_ids': discards}}
    spell = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].mana_pool = mana
    state.players[3-seat].mana_pool = {}
    action['card_id'] = spell.id
    data = {'cohort': cohort, 'observers': observers, 'references': references,
            'progenitus': progenitus.id if progenitus else None, 'colossus': colossus.id, 'spell': spell.id,
            'family': family, 'seat': seat, 'action': action}
    return state, data


def rows_for(collected, state, data):
    trace, states = collected
    index = next(i for i, current in enumerate(states) if state is current)
    return [row for row in trace if row['state_index'] == index
            and row['payload'].get('card_id') in data['cohort']]


def paid(seat, family, tmp_path, collected, *, ordering=False, protected_control=False):
    state, data = position(seat, family, ordering=ordering, protected_control=protected_control)
    before = snap(state)
    state = act(state, seat, data['action'])
    assert not sum(state.players[seat].mana_pool.values())
    if family == 'dreams':
        assert all(state.cards[cid].zone == Zone.GRAVEYARD
                   for cid in data['action']['cost_choice']['discard_card_ids'])
    state = restart(state, tmp_path, 'paid-stack')
    state = passes(state)
    rows = rows_for(collected, state, data)
    (tmp_path / 'actual-before.json').write_text(json.dumps(before, sort_keys=True))
    (tmp_path / 'actual-after.json').write_text(json.dumps(snap(state), sort_keys=True))
    (tmp_path / 'actual-data.json').write_text(json.dumps(data, sort_keys=True))
    return state, data, rows


def assert_outcomes(state, data):
    for cid, zone in data['cohort'].items():
        assert state.cards[cid].zone.value == zone
        assert getattr(state.players[state.cards[cid].owner], zone).count(cid) == 1
    assert state.cards[data['colossus']].zone == Zone.BATTLEFIELD
    if data['family'] == 'dreams' and data['progenitus']:
        assert state.cards[data['progenitus']].zone == Zone.BATTLEFIELD
    assert state.cards[data['spell']].zone == Zone.GRAVEYARD
    for cid, reference in data['references'].items():
        assert state.cards[cid].zone_change_sequence == reference + 1


def assert_publication_frontier(rows, data):
    entries = [row for row in rows if row['event'] == 'enters_graveyard']
    assert len(entries) == 6
    for row in entries:
        frontier = {cid: details['zone'] for cid, details in row['cohort'].items()
                    if cid in data['cohort']}
        assert frontier == data['cohort'], 'Entry collector must see every simultaneous batch move committed'
        assert all(row['cohort'][cid]['membership'] for cid in data['cohort'])


def assert_observers(state, data, rows):
    deaths = [row for row in rows if row['event'] == 'creature_dies']
    entries = [row for row in rows if row['event'] == 'enters_graveyard']
    assert len(deaths) == len(entries) == 6
    assert len({row['payload']['card_id'] for row in deaths}) == 6
    counts = Counter(item.source_card_id for item in state.stack)
    for pid, group in data['observers'].items():
        assert counts[group[KOZILEK]] == counts[group['Doomed Traveler']] == 1
        assert counts[group['Blood Artist']] == 6
        assert counts[group['Psychogenic Probe']] == (1 if data['family'] == 'wrath' else 0)
        for item in state.stack:
            if item.source_card_id in group.values():
                assert item.controller == pid
    assert not counts[data['progenitus']] and not counts[data['colossus']]
    for item in state.stack:
        if item.source_card_id in {group[KOZILEK] for group in data['observers'].values()}:
            assert item.payload['__trigger_event'] == 'enters_graveyard'
            assert item.payload['__trigger_source_reference']['zone_change_sequence'] == state.cards[item.source_card_id].zone_change_sequence


def assert_private(state):
    for seat in (1, 2):
        view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
        assert all(is_unknown(view.cards[cid]) for cid in state.players[3-seat].hand + state.players[3-seat].library)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['dreams', 'wrath'])
@pytest.mark.parametrize('proof', ['publication', 'observers'])
def test_actual_paid_simultaneous_batch_frontier(seat, family, proof, tmp_path, collected):
    state, data, rows = paid(seat, family, tmp_path, collected)
    assert_outcomes(state, data)
    state = restart(state, tmp_path, 'actual-resolved')
    assert_private(state)
    if proof == 'publication':
        assert_publication_frontier(rows, data)
    else:
        assert_observers(state, data, rows)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['dreams', 'wrath'])
def test_actual_paid_batch_explicit_apnap_restart_atomic_choices(seat, family, tmp_path, collected):
    state, data, rows = paid(seat, family, tmp_path, collected, ordering=True)
    assert_outcomes(state, data)
    pending = state.pending_trigger_order
    assert pending['controller_order'] == [seat, 3-seat]
    assert set(pending['groups']) == {'1', '2'}
    for actor in (seat, 3-seat):
        state = restart(state, tmp_path, 'before-order-' + str(actor))
        pending = state.pending_trigger_order
        assert pending['current_controller'] == actor
        choice = {'type': 'choose_trigger_order', 'trigger_order': [
            row['_choice_id'] for row in reversed(pending['groups'][str(actor)])]}
        before = snap(state)
        with pytest.raises(ActionRejected):
            act(state, 3-actor, choice)
        assert snap(state) == before
        state = act(state, actor, choice)
    # Resolve only the actually offered target choices; do not resolve any triggers.
    while state.pending_trigger_order:
        pending = state.pending_trigger_order
        assert pending['phase'] == 'targets'
        legal = RulesEngine().legal_moves(state, state.priority_player)
        choice = next(move for move in legal if move['type'] == 'choose_trigger_target')
        state = act(state, state.priority_player, choice)
    assert [item.controller for item in state.stack] == sorted(
        [item.controller for item in state.stack], key=lambda pid: pid != seat)
    assert_observers(state, data, rows)
    restart(state, tmp_path, 'actual-apnap-stack')
    assert_private(state)


def http_position(repo, client, seat, family, *, protected_control=False):
    import main
    for row in ROWS.values():
        repo.upsert_card(normalize(row))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7881})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state, data = position(seat, family, protected_control=protected_control)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return controller, data


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['dreams', 'wrath'])
@pytest.mark.parametrize('proof', ['publication', 'observers'])
def test_actual_http_paid_batch_frontier_restart_private_sql(repo, client, seat, family, proof, tmp_path, collected):
    import main
    controller, data = http_position(repo, client, seat, family)
    mid = controller.state.id
    before_sql = sql_facts(repo)
    for actor, move in [(seat, data['action']), (seat, {'type': 'pass_priority'}),
                        (3-seat, {'type': 'pass_priority'})]:
        response = client.post('/matches/' + mid + '/action', json={'player_id': actor, 'action': move})
        assert response.status_code == 200, response.text
    state = main.ACTIVE_MATCHES[mid].state
    rows = rows_for(collected, state, data)
    assert sql_facts(repo) != before_sql
    assert_outcomes(state, data)
    snapshot = snap(state)
    restart(state, tmp_path, 'actual-http-resolved')
    main.ACTIVE_MATCHES.pop(mid)
    main._restore_active_matches(repo, mid)
    restored = main.ACTIVE_MATCHES[mid].state
    assert snap(restored) == snapshot
    assert_private(restored)
    if proof == 'publication':
        assert_publication_frontier(rows, data)
    else:
        assert_observers(restored, data, rows)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['dreams', 'wrath'])
def test_actual_http_wrong_actor_preserves_root_controller_sql(repo, client, seat, family):
    import main
    controller, data = http_position(repo, client, seat, family)
    before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + controller.state.id + '/action',
                           json={'player_id': 3-seat, 'action': data['action']})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_dreams_protection_control_not_silenced(seat, tmp_path, collected):
    # Separately preserve the discovered strict protected-control assertion.
    state, data, _ = paid(seat, 'dreams', tmp_path, collected, protected_control=True)
    assert state.cards[data['progenitus']].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_dreams_protection_control_not_silenced(repo, client, seat, tmp_path):
    import main
    controller, data = http_position(repo, client, seat, 'dreams', protected_control=True)
    for actor, action in [(seat, data['action']), (seat, {'type': 'pass_priority'}),
                          (3-seat, {'type': 'pass_priority'})]:
        response = client.post('/matches/' + controller.state.id + '/action',
                               json={'player_id': actor, 'action': action})
        assert response.status_code == 200, response.text
    state = main.ACTIVE_MATCHES[controller.state.id].state
    restart(state, tmp_path, 'actual-http-protected-control')
    assert state.cards[data['progenitus']].zone == Zone.BATTLEFIELD
