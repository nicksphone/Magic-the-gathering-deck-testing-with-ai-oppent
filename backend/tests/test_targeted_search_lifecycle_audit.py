"""Paid canonical response episodes; no fabricated resolving frames or events."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_targeted_library_search_compiler import setup, act, snap
from tests.test_paid_counter_family_audit import raw_card, passes, restart, http_position
from tests.test_batch_graveyard_publication_audit import client
from ai.information import decision_view, is_unknown
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/targeted_search_lifecycle'
for line in (FIXTURE / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split()
    assert hashlib.sha256((FIXTURE / Path(name).name).read_bytes()).hexdigest() == digest
ROWS = {name: json.loads((FIXTURE / (name + '.json')).read_text())
        for name in ('cloudshift', 'ray-of-command', 'unsummon')}


def assert_private(state, revealed):
    for seat in (1, 2):
        view, _ = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
        for cid in state.players[3-seat].hand + state.players[3-seat].library:
            if cid == revealed and state.cards[cid].zone == Zone.HAND:
                assert view.cards[cid].name == state.cards[cid].name == 'Fertilid'
            else:
                assert is_unknown(view.cards[cid])


def cold_sql(repo, mid, expected):
    database = repo.session.get_bind().url.database
    if not database:
        return  # Memory SQL has no independently reopenable file.
    script = '''import json,sqlite3,sys
from game_state.serializers import deserialize_match_snapshot,serialize_match_snapshot
c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
state,controller=c.execute('SELECT state_json,controller_json FROM activematchrecord WHERE id=?',(sys.argv[2],)).fetchone()
assert json.loads(json.dumps(serialize_match_snapshot(deserialize_match_snapshot(json.loads(state)))))==json.loads(state)
print(json.dumps({'state':json.loads(state),'controller':json.loads(controller)},sort_keys=True))
c.close()
'''
    proc = subprocess.run([sys.executable, '-c', script, database, mid],
                          capture_output=True, text=True, timeout=30, env=os.environ.copy())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload['state'] == expected[0] and payload['controller'] == expected[1]


@pytest.fixture
def shuffle_trace(monkeypatch, tmp_path):
    from rules_engine import events
    emit = events.emit_event
    trace = []

    def observe(state, event, payload):
        if event == 'shuffle':
            trace.append(deepcopy(payload))
        return emit(state, event, payload)

    monkeypatch.setattr(events, 'emit_event', observe)
    yield trace
    (tmp_path / 'genuine-shuffles.json').write_text(json.dumps(trace, sort_keys=True))


def position(family, seat, response):
    state, source, _, lands = setup(family, seat)
    target = next(cid for cid in state.players[seat].battlefield
                  if state.cards[cid].name == 'Fertilid')
    responder = 3-seat if response == 'ray-of-command' else seat
    spell = raw_card(state, ROWS[response], responder, Zone.HAND).id if response != 'none' else None
    state.players[seat].mana_pool = {'G': 1, 'C': 6, 'W': 1, 'U': 1}
    state.players[3-seat].mana_pool = {'U': 1, 'C': 3}
    return state, source, target, lands, spell, responder


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('response', ['cloudshift', 'ray-of-command', 'unsummon', 'none'])
@pytest.mark.parametrize('transport', ['checked', 'http'])
def test_fertilid_real_response_retains_paid_controller_and_source_receipt(
        seat, response, transport, tmp_path, shuffle_trace, repo, client):
    import main
    state, source, target, lands, spell, responder = position('Fertilid', seat, response)
    mid = None
    if transport == 'http':
        controller, _, _, path = http_position(repo, client, seat, 'Fertilid')
        state.id = controller.state.id
        controller.state = state
        main._persist_active_match(repo, controller)
        mid = state.id

    def send(current, actor, action):
        if transport == 'checked':
            return act(current, actor, action)
        result = client.post(path + '/action', json={'player_id': actor, 'action': action})
        assert result.status_code == 200, result.text
        return main.ACTIVE_MATCHES[mid].state

    before_ref = {'incarnation': object_incarnation(state.cards[source]),
                  'zone_change_sequence': state.cards[source].zone_change_sequence}
    state = send(state, seat, {'type': 'activate_ability', 'card_id': source,
        'ability_index': 0, 'targets': {'target_player': 3-seat}})
    original = deepcopy(state.stack[-1])
    assert original.controller == seat and state.cards[source].counters['+1/+1'] == 1
    if response != 'none':
        if responder != state.priority_player:
            state = send(state, state.priority_player, {'type': 'pass_priority'})
        state = send(state, responder, {'type': 'cast_spell', 'card_id': spell,
            'targets': {'target_card_id': target}, 'cost_choice': {'id': 'base'}})
        assert state.stack[-1].payload['mana_spent'] == (4 if response == 'ray-of-command' else 1)
        for _ in range(2):
            state = send(state, state.priority_player, {'type': 'pass_priority'})
    if response == 'cloudshift':
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert state.cards[source].zone_change_sequence == before_ref['zone_change_sequence'] + 2
    elif response == 'unsummon':
        assert state.cards[source].zone == Zone.HAND
    elif response == 'ray-of-command':
        assert state.cards[source].controller == 3-seat
    else:
        assert state.cards[source].zone == Zone.BATTLEFIELD and state.cards[source].controller == seat
    assert state.stack[0].id == original.id and state.stack[0].controller == seat
    for _ in range(2):
        state = send(state, state.priority_player, {'type': 'pass_priority'})
    pending = state.pending_mechanic_choice
    assert pending['player_id'] == 3-seat and pending['continuation_controller'] == seat
    assert pending['resolving_item']['id'] == original.id
    assert_private(state, target)
    if transport == 'http':
        controller = main.ACTIVE_MATCHES[mid]
        saved = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
        cold_sql(repo, mid, saved)
        main.ACTIVE_MATCHES.pop(mid)
        main._restore_active_matches(repo, mid)
        controller = main.ACTIVE_MATCHES[mid]
        state = controller.state
        assert (snap(state), main._controller_snapshot(controller), sql_facts(repo)) == saved
        bad = client.post(path + '/action', json={'player_id': seat,
            'action': {'type': 'choose_mechanic', 'card_ids': [lands[3-seat][1]]}})
        assert bad.status_code == 422
        assert (snap(state), main._controller_snapshot(controller), sql_facts(repo)) == saved
    else:
        state = restart(state, tmp_path, 'paused-source-lifecycle')
        before = snap(state)
        with pytest.raises(ActionRejected):
            act(state, seat, {'type': 'choose_mechanic', 'card_ids': [lands[3-seat][1]]})
        assert snap(state) == before
    state = send(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': [lands[3-seat][1]]})
    chosen = state.cards[lands[3-seat][1]]
    assert chosen.zone == Zone.BATTLEFIELD and chosen.tapped and chosen.controller == 3-seat
    causes = [event['cause'] for event in shuffle_trace
              if event.get('cause', {}).get('stack_id') == original.id]
    assert causes and all(cause['controller'] == seat for cause in causes)
    assert all(cause['source_reference'] == before_ref for cause in causes)
    assert_private(restart(state, tmp_path, 'finished-source-lifecycle'), target)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zero', [False, True])
def test_favor_paid_search_survives_real_counter_target_departure_without_free_counters(
        seat, zero, tmp_path, shuffle_trace):
    state, source, target, lands, spell, _ = position("Fertilid's Favor", seat, 'unsummon')
    targets = {'target_player': 3-seat}
    if not zero:
        targets['target_card_id'] = target
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
        'targets': targets, 'cost_choice': {'id': 'base'}})
    frame = deepcopy(state.stack[-1])
    assert frame.payload['mana_spent'] == 4
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell,
        'targets': {'target_card_id': target}, 'cost_choice': {'id': 'base'}})
    state = passes(state)
    assert state.cards[target].zone == Zone.HAND
    state = passes(restart(state, tmp_path, 'favor-response-resolved'))
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    assert state.pending_mechanic_choice['continuation_controller'] == seat
    before = {cid: dict(card.counters) for cid, card in state.cards.items()}
    state = act(restart(state, tmp_path, 'favor-paused'), 3-seat,
        {'type': 'choose_mechanic', 'card_ids': [lands[3-seat][1]]})
    assert state.cards[lands[3-seat][1]].zone == Zone.BATTLEFIELD
    assert {cid: dict(card.counters) for cid, card in state.cards.items()} == before
    assert state.cards[source].zone == Zone.GRAVEYARD and not state.stack
    assert_private(restart(state, tmp_path, 'favor-completed'), target)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Fertilid', "Fertilid's Favor"])
def test_unobserved_response_identity_permutation_has_identical_actor_input(seat, family):
    state, source, target, _, _, _ = position(family, seat, 'unsummon')
    hidden = [raw_card(state, ROWS[name], 3-seat, zone).id for name, zone in
              [('cloudshift', Zone.HAND), ('ray-of-command', Zone.LIBRARY)]]
    request = {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
               'targets': {'target_player': 3-seat}} if family == 'Fertilid' else {
                   'type': 'cast_spell', 'card_id': source,
                   'targets': {'target_player': 3-seat, 'target_card_id': target}}
    state = act(state, seat, request)
    before = snap(state)
    altered = deepcopy(state)
    first, second = [deepcopy(altered.cards[cid]) for cid in hidden]
    for cid, replacement in zip(hidden, [second, first]):
        original = altered.cards[cid]
        replacement.id, replacement.zone = cid, original.zone
        replacement.owner, replacement.controller = original.owner, original.controller
        replacement.zone_change_sequence = original.zone_change_sequence
        altered.cards[cid] = replacement
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    other, other_moves = decision_view(altered, seat, RulesEngine().legal_moves(altered, seat))
    assert snap(view) == snap(other) and moves == other_moves
    assert snap(state) == before
