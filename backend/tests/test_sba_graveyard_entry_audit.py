"""Desired SBA committed-entry semantics; real paid actions, no injected events."""
from copy import deepcopy
import inspect
import json

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import normalize
from tests.scheduler_fixture_position import ordinary_position
from tests.spell_admission_safety_support import RAW
from tests.test_builtin_metadata_refresh import repo
from tests.test_kozilek_graveyard_trigger_audit import KOZILEK, passes
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS, act, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS as LAYERS
from tests.test_spell_admission_safety_http import sql_facts


@pytest.fixture
def observed(monkeypatch, tmp_path):
    from rules_engine import events
    original = events._collect_triggers
    trace, states = [], []

    def collect(state, event, payload):
        result = original(state, event, payload)
        if not any(state is item for item in states):
            states.append(state)
        card = state.cards.get(payload.get('card_id') or payload.get('target_card_id'))
        trace.append({'state_index': next(i for i, item in enumerate(states) if item is state),
                      'event': event, 'payload': deepcopy(payload), 'triggers': deepcopy(result),
                      'source_zone': card.zone.value if card else None,
                      'source_sequence': card.zone_change_sequence if card else None,
                      'source_lki': deepcopy(card.last_known_battlefield) if card else None,
                      'callsite': [{'file': frame.filename.split('/backend/')[-1],
                                    'function': frame.function, 'line': frame.lineno}
                                   for frame in inspect.stack(context=0)[1:14]
                                   if '/backend/' in frame.filename]})
        return result

    monkeypatch.setattr(events, '_collect_triggers', collect)
    yield trace, states
    (tmp_path / 'actual-event-trace.json').write_text(json.dumps(trace, sort_keys=True, default=str))


def target_events(observed, state, cid):
    trace, states = observed
    index = next(i for i, item in enumerate(states) if item is state)
    return [row for row in trace if row['state_index'] == index and row['payload'].get('card_id') == cid]


def position(seat):
    state, _ = setup('Index', seat)
    ordinary_position(state)  # Explicit retained fixture, never a runtime repair.
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {}
    return state


def bolt_position(seat, foreign=False):
    state = position(seat)
    victim = raw_card(state, ROWS['Doomed Traveler'], 3-seat, Zone.BATTLEFIELD)
    if foreign:
        victim.owner = seat  # Controlled retained ownership, not a played control-change episode.
    artist = raw_card(state, ROWS['Blood Artist'], 3-seat, Zone.BATTLEFIELD)
    spell = raw_card(state, RAW['Lightning Bolt'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1}
    assert victim.oracle_text == ROWS['Doomed Traveler']['oracle_text']
    assert spell.oracle_text == RAW['Lightning Bolt']['oracle_text']
    return state, victim.id, artist.id, spell.id, {
        'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': victim.id}}


def paid_bolt(seat, tmp_path, foreign=False):
    state, cid, artist, spell, action = bolt_position(seat, foreign)
    before = snap(state)
    (tmp_path / 'before-paid-bolt.json').write_text(json.dumps(before, sort_keys=True))
    reference = {'incarnation': object_incarnation(state.cards[cid]),
                 'zone_change_sequence': state.cards[cid].zone_change_sequence}
    state = act(state, seat, action)
    assert state.cards[spell].zone == Zone.STACK and state.cards[cid].zone == Zone.BATTLEFIELD
    assert not state.players[seat].mana_pool.get('R', 0)
    state = restart(state, tmp_path, 'paid-bolt-stack')
    state = passes(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert cid in state.players[state.cards[cid].owner].graveyard
    assert state.cards[spell].zone == Zone.GRAVEYARD
    (tmp_path / 'actual-sba-after-bolt.json').write_text(json.dumps(snap(state), sort_keys=True))
    restart(state, tmp_path, 'sba-after-bolt-restart')
    return state, cid, artist, reference


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('required', ['sequence', 'entry'])
def test_paid_bolt_sba_commits_new_zone_identity_and_entry_once(seat, foreign, required, tmp_path, observed):
    state, cid, _, reference = paid_bolt(seat, tmp_path, foreign)
    if required == 'sequence':
        assert state.cards[cid].zone_change_sequence == reference['zone_change_sequence'] + 1
    else:
        entries = [row for row in target_events(observed, state, cid) if row['event'] == 'enters_graveyard']
        assert len(entries) == 1, 'Actual SBA death must use the committed graveyard-entry seam once'
        payload = entries[0]['payload']
        assert payload['owner'] == state.cards[cid].owner and payload['previous_controller'] == 3-seat
        assert payload['from_zone'] == 'battlefield' and payload['previous_reference'] == reference
        assert payload['entry_reference'] == {'incarnation': object_incarnation(state.cards[cid]),
                                             'zone_change_sequence': state.cards[cid].zone_change_sequence}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_paid_bolt_preserves_actual_dies_lki_and_trigger_controller(seat, foreign, tmp_path, observed):
    state, cid, artist, reference = paid_bolt(seat, tmp_path, foreign)
    records = target_events(observed, state, cid)
    assert [row['event'] for row in records] == ['leaves_battlefield', 'enters_graveyard', 'permanent_dies', 'creature_dies']
    lki = next(row['source_lki'] for row in records if row['event'] == 'leaves_battlefield')
    entry = next(row for row in records if row['event'] == 'enters_graveyard')['payload']
    assert entry['previous_reference'] == reference
    assert entry['entry_reference'] == {'incarnation': object_incarnation(state.cards[cid]),
                                        'zone_change_sequence': reference['zone_change_sequence'] + 1}
    assert entry['owner'] == state.cards[cid].owner and entry['previous_controller'] == 3-seat
    assert entry['from_zone'] == 'battlefield'
    assert all(row['source_lki'] == lki for row in records)
    assert lki['oracle_text'] == ROWS['Doomed Traveler']['oracle_text']
    assert lki['controller'] == 3-seat and 'Creature' in lki['types']
    assert not lki['printed_abilities_suppressed']
    assert not state.cards[cid].counters
    for source in (cid, artist):
        items = [item for item in state.stack if item.source_card_id == source]
        assert len(items) == 1 and items[0].controller == 3-seat
    view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert all(is_unknown(view.cards[other]) for other in state.players[seat].hand + state.players[seat].library)


def legend_position(seat, replacements=False):
    state = position(seat)
    keeper = raw_card(state, ROWS[KOZILEK], seat, Zone.BATTLEFIELD)
    newcomer = raw_card(state, ROWS[KOZILEK], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 10}
    sources = []
    if replacements:
        sources = [raw_card(state, LAYERS[name], 3-seat, Zone.BATTLEFIELD).id
                   for name in ('Rest in Peace', 'Leyline of the Void')]
        state.replacement_choice_required = True
        state.replacement_choice_players = {1, 2}
    return state, keeper.id, newcomer.id, sources


def paid_legend(seat, tmp_path, replacements=False):
    state, keeper, cid, sources = legend_position(seat, replacements)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid})
    assert not state.players[seat].mana_pool.get('C', 0)
    assert len(state.stack) == 2, 'Canonical cast trigger must remain a real responding ability'
    state = passes(state)  # Cast draw-four trigger resolves first.
    assert len(state.stack) == 1 and state.cards[cid].zone == Zone.STACK
    state = restart(state, tmp_path, 'paid-legend-before-entry')
    state = passes(state)  # Actual permanent resolution immediately reaches legend SBA.
    (tmp_path / 'actual-legend-checkpoint.json').write_text(json.dumps(snap(state), sort_keys=True))
    restart(state, tmp_path, 'actual-legend-restart')
    (tmp_path / 'actual-legend-offered-actions.json').write_text(json.dumps(
        RulesEngine().legal_moves(state, state.priority_player), sort_keys=True))
    assert state.cards[keeper].zone == Zone.BATTLEFIELD
    return state, keeper, cid, sources


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('required', ['sequence', 'trigger'])
def test_actual_paid_second_kozilek_legend_departure_entry_and_owner_trigger(seat, required, tmp_path, observed):
    state, _, cid, _ = paid_legend(seat, tmp_path)
    records = target_events(observed, state, cid)
    leave = next(row for row in records if row['event'] == 'leaves_battlefield')
    assert state.cards[cid].zone == Zone.GRAVEYARD and cid in state.players[seat].graveyard
    if required == 'sequence':
        assert state.cards[cid].zone_change_sequence == leave['source_sequence'] + 1
    else:
        entries = [row for row in records if row['event'] == 'enters_graveyard']
        assert len(entries) == 1
        items = [item for item in state.stack if item.source_card_id == cid]
        assert len(items) == 1 and items[0].controller == seat
        assert items[0].payload['__trigger_event'] == 'enters_graveyard'


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_legend_replacement_choice_supported_no_false_grave_entry(seat, tmp_path, observed):
    state, _, cid, sources = paid_legend(seat, tmp_path, replacements=True)
    pending = state.pending_replacement_choice
    assert pending and pending['resume_kind'] == 'legend_die' and pending['target_card_id'] == cid
    assert {row['source_id'] for row in pending['options']} == set(sources)
    chosen = next(action for action in RulesEngine().legal_moves(state, seat)
                  if action['type'] == 'choose_replacement' and action['replacement_source_id'] == sources[0])
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, chosen)
    assert snap(state) == before
    state = act(state, seat, chosen)
    assert state.cards[cid].zone == Zone.EXILE and cid not in state.players[seat].graveyard
    assert not any(row['event'] == 'enters_graveyard' for row in target_events(observed, state, cid))
    assert not any(item.source_card_id == cid for item in state.stack)
    restart(state, tmp_path, 'actual-legend-chosen-exile')


def http_position(repo, client, seat):
    import main
    for row in [*ROWS.values(), RAW['Lightning Bolt']]:
        repo.upsert_card(normalize(row))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7441})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state, cid, artist, spell, action = bolt_position(seat)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return controller, cid, action


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_paid_bolt_sba_restart_sql_private_and_new_sequence(repo, client, seat, tmp_path, observed):
    import main
    controller, cid, action = http_position(repo, client, seat)
    mid = controller.state.id
    sequence = controller.state.cards[cid].zone_change_sequence
    before_sql = sql_facts(repo)
    for actor, move in [(seat, action), (seat, {'type': 'pass_priority'}), (3-seat, {'type': 'pass_priority'})]:
        response = client.post('/matches/' + mid + '/action', json={'player_id': actor, 'action': move})
        assert response.status_code == 200, response.text
    state = main.ACTIVE_MATCHES[mid].state
    assert state.cards[cid].zone == Zone.GRAVEYARD and sql_facts(repo) != before_sql
    snapshot = snap(state)
    (tmp_path / 'http-paid-bolt-sba.json').write_text(json.dumps(snapshot, sort_keys=True))
    main.ACTIVE_MATCHES.pop(mid)
    main._restore_active_matches(repo, mid)
    assert snap(main.ACTIVE_MATCHES[mid].state) == snapshot
    view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert all(is_unknown(view.cards[other]) for other in state.players[seat].hand + state.players[seat].library)
    assert state.cards[cid].zone_change_sequence == sequence + 1


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_invalid_bolt_target_preserves_root_controller_and_sql(repo, client, seat):
    import main
    controller, _, action = http_position(repo, client, seat)
    before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    invalid = {**action, 'targets': {'target_card_id': 'unknown'}}
    response = client.post('/matches/' + controller.state.id + '/action', json={'player_id': seat, 'action': invalid})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
