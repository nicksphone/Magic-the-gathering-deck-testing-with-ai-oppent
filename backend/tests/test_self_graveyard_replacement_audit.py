"""Strict printed self replacements, distinct from graveyard triggered abilities."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ai.information import decision_view, is_unknown
from card_data.hydration import ready_for_match
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.ability_model import build_spell_spec
from rules_engine.costs import collect_cost_options, check_cost_option_available
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.zone_actions import put_into_graveyard
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import normalize
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/self_graveyard_audit/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
ROWS = {row['name']: row for row in map(json.loads, FIXTURE.read_text().splitlines())}
SELF = ['Darksteel Colossus', 'Progenitus']


def snap(state):
    return json.loads(json.dumps(serialize_match_snapshot(state)))


def restart(state, tmp_path, label):
    before = snap(state)
    path = tmp_path / (label + '.json')
    path.write_text(json.dumps(before))
    script = ('import json,sys; from game_state.serializers import '
              'deserialize_match_snapshot,serialize_match_snapshot; '
              'x=json.load(open(sys.argv[1])); '
              'assert json.loads(json.dumps(serialize_match_snapshot(deserialize_match_snapshot(x))))==x')
    proc = subprocess.run([sys.executable, '-c', script, str(path)],
                          capture_output=True, text=True, timeout=30,
                          env={**os.environ, 'PYTHONPATH': str(FIXTURE.parents[3]),
                               'PYTHONDONTWRITEBYTECODE': '1'})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    restored = deserialize_match_snapshot(before)
    assert snap(restored) == before
    return restored


def act(state, seat, action):
    before = snap(state)
    result = checked_action(state, RulesEngine(), seat, action)
    repeated = checked_action(deserialize_match_snapshot(before), RulesEngine(), seat, action)
    assert snap(state) == before and snap(result) == snap(repeated)
    return result


def position(name, seat, stimulus, foreign_owner=False):
    state, _ = setup('Index', seat)
    # Controlled retained positions, not naturally executed control-changing spells.
    zone = {'sacrifice': Zone.BATTLEFIELD, 'discard': Zone.HAND, 'mill': Zone.LIBRARY}[stimulus]
    target = raw_card(state, ROWS[name], seat, zone)
    if foreign_owner:
        assert stimulus == 'sacrifice'
        target.owner = 3-seat
    observer = raw_card(state, ROWS['Blood Artist'], seat, Zone.BATTLEFIELD)
    if stimulus == 'sacrifice':
        source = raw_card(state, ROWS['Village Rites'], seat, Zone.HAND)
        state.players[seat].mana_pool = {'B': 1}
        action = {'type': 'cast_spell', 'card_id': source.id,
                  'cost_choice': {'id': 'base', 'sacrifice_card_ids': [target.id]}}
    elif stimulus == 'discard':
        source = raw_card(state, ROWS['Sickening Dreams'], seat, Zone.HAND)
        state.players[seat].mana_pool = {'B': 1, 'C': 1}
        action = {'type': 'cast_spell', 'card_id': source.id, 'targets': {'x_value': 1},
                  'cost_choice': {'id': 'base', 'discard_card_ids': [target.id]}}
    else:
        source = raw_card(state, ROWS['Millstone'], seat, Zone.BATTLEFIELD)
        state.players[seat].mana_pool = {'C': 2}
        action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0,
                  'targets': {'target_player': seat}}
    return state, target, source, observer, action


def execute(state, source, seat, stimulus, action):
    result = act(state, seat, action)
    assert any(item.source_card_id == source.id for item in result.stack)
    assert sum(result.players[seat].mana_pool.values()) == 0
    if stimulus == 'mill':
        assert result.cards[source.id].tapped
        assert resolve_top_of_stack(result)
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('stimulus', ['sacrifice', 'discard', 'mill'])
def test_actual_paid_actions_require_owner_self_replacement(seat, name, stimulus, tmp_path):
    state, target, source, observer, action = position(name, seat, stimulus)
    owner = target.owner
    before_sequence = target.zone_change_sequence
    state = restart(state, tmp_path, 'before')
    state = execute(state, source, seat, stimulus, action)
    state = restart(state, tmp_path, 'after')
    if stimulus == 'mill':
        assert state.cards[target.id].zone_change_sequence == before_sequence
    else:
        assert state.cards[target.id].zone_change_sequence > before_sequence
    assert state.cards[target.id].oracle_text == ROWS[name]['oracle_text']
    assert state.cards[target.id].zone == Zone.LIBRARY, 'Printed self replacement must prevent graveyard entry'
    assert target.id in state.players[owner].library
    assert all(target.id not in p.graveyard for p in state.players.values())
    assert not any(item.source_card_id in {target.id, observer.id} for item in state.stack)
    assert any('reveal' in line.lower() and name in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_controlled_foreign_owner_sacrifice_uses_owner_library(seat, name, tmp_path):
    state, target, source, _, action = position(name, seat, 'sacrifice', True)
    other_library = list(state.players[seat].library)
    state = execute(restart(state, tmp_path, 'before'), source, seat, 'sacrifice', action)
    state = restart(state, tmp_path, 'after')
    assert target.id not in state.players[seat].battlefield
    assert state.players[seat].library == other_library
    assert state.cards[target.id].zone == Zone.LIBRARY, 'Owner replacement cannot route to controller graveyard'
    assert target.id in state.players[3-seat].library


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_replaced_sacrifice_must_not_emit_false_dies_receipt(seat, name):
    state, target, source, observer, action = position(name, seat, 'sacrifice')
    state = execute(state, source, seat, 'sacrifice', action)
    assert target.id not in state.players[seat].battlefield
    assert not any(item.source_card_id == observer.id for item in state.stack), 'Replacement is not a death'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('zone', [Zone.STACK, Zone.EXILE])
def test_explicit_zone_entry_seam_covers_other_origins(seat, name, zone, tmp_path):
    # Trusted transition seam only: not an invented spell or permission to discard exile.
    state, _ = setup('Index', seat)
    target = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].hand.remove(target.id)
    target.move_to_zone(zone)
    sequence = target.zone_change_sequence
    put_into_graveyard(state, target.id)
    state = restart(state, tmp_path, 'after-seam')
    assert state.cards[target.id].zone_change_sequence > sequence
    assert state.cards[target.id].zone == Zone.LIBRARY, 'Anywhere replacement must apply at shared transition seam'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_cost_readiness_legal_view_queries_are_pure_and_private(seat, name):
    state, target, source, _, action = position(name, seat, 'sacrifice')
    before = snap(state)
    for _ in range(3):
        assert ready_for_match(ROWS[name])
        build_spell_spec(state, target, seat, report_unsupported=False)
        options = collect_cost_options(state, seat, source)
        assert any(check_cost_option_available(state, seat, source, option) for option in options)
        moves = RulesEngine().legal_moves(state, seat)
        assert any(move.get('card_id') == source.id for move in moves)
        view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
        assert all(is_unknown(view.cards[cid]) for cid in state.players[seat].hand + state.players[seat].library)
        assert snap(state) == before
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, action)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stimulus', ['sacrifice', 'discard', 'mill'])
def test_ordinary_canonical_creature_really_enters_graveyard(seat, stimulus, tmp_path):
    state, target, source, observer, action = position('Doomed Traveler', seat, stimulus)
    state = execute(state, source, seat, stimulus, action)
    state = restart(state, tmp_path, 'ordinary-after')
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert target.id in state.players[seat].graveyard
    if stimulus == 'sacrifice':
        assert any(item.source_card_id == observer.id for item in state.stack)
        assert any(item.source_card_id == target.id for item in state.stack)
    else:
        assert not any(item.source_card_id in {target.id, observer.id} for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_eldrazi_graveyard_trigger_is_not_self_replacement(seat, tmp_path):
    name = 'Kozilek, Butcher of Truth'
    state, target, source, _, action = position(name, seat, 'discard')
    state = execute(state, source, seat, 'discard', action)
    state = restart(state, tmp_path, 'eldrazi-after-discard')
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert target.id in state.players[seat].graveyard
    assert any(item.source_card_id == target.id for item in state.stack), 'Eldrazi needs a respondable graveyard trigger, not replacement'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('bad', ['duplicate', 'foreign', 'stale'])
def test_explicit_sacrifice_selection_rejection_does_not_execute_replacement(seat, name, bad):
    state, target, _, _, action = position(name, seat, 'sacrifice')
    if bad == 'duplicate':
        selected = [target.id, target.id]
    elif bad == 'foreign':
        selected = [raw_card(state, ROWS[name], 3-seat, Zone.BATTLEFIELD).id]
    else:
        state.players[seat].battlefield.remove(target.id)
        target.move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(target.id)
        selected = [target.id]
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
                       {**action, 'cost_choice': {'id': 'base', 'sacrifice_card_ids': selected}})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_actual_http_paid_sacrifice_persists_missing_replacement_without_db_rejection_mutation(repo, client, seat, name, tmp_path):
    import main
    for raw in ROWS.values():
        repo.upsert_card(normalize(raw))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state, target, source, _, action = position(name, seat, 'sacrifice')
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + state.id + '/action', json={'player_id': 3-seat, 'action': action})
    assert rejected.status_code == 422, rejected.text
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert controller.state.players[seat].mana_pool.get('B', 0) == 0
    assert any(item.source_card_id == source.id for item in controller.state.stack)
    assert sql_facts(repo) != before[2]
    expected = snap(controller.state)
    main.ACTIVE_MATCHES.pop(state.id)
    main._restore_active_matches(repo, state.id)
    loaded = main.ACTIVE_MATCHES[state.id]
    assert snap(loaded.state) == expected
    loaded.state = restart(loaded.state, tmp_path, 'http-persisted')
    assert loaded.state.cards[target.id].zone == Zone.LIBRARY, 'HTTP persisted the same missing self replacement'
