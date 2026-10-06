"""Complete canonical paid blink responses, never injected effects or frames."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ai.information import decision_view
from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_targeted_library_search_compiler import setup, act, snap
from tests.test_paid_counter_family_audit import raw_card, passes, restart, http_position
from tests.test_batch_graveyard_publication_audit import client, assert_private
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_spell_admission_safety_http import sql_facts

FIXTURE = Path(__file__).parent / 'fixtures/cloudshift_compound_audit'
for line in (FIXTURE / 'SHA256SUMS').read_text().splitlines():
    digest, filename = line.split()
    assert hashlib.sha256((FIXTURE / Path(filename).name).read_bytes()).hexdigest() == digest
ROWS = {name: json.loads((FIXTURE / (name + '.json')).read_text())
        for name in ('cloudshift', 'flicker-of-fate')}


def position(seat, name, foreign=False):
    state, source, _, lands = setup('Fertilid', seat)
    if foreign:
        # Explicit lawful stolen-creature starting board, not a control-change episode.
        state.cards[source].owner = 3-seat
    spell = raw_card(state, ROWS[name], seat, Zone.HAND).id
    state.players[seat].mana_pool = {'G': 1, 'W': 1, 'C': 5}
    return state, source, spell, lands


def cold_sql(repo, mid, expected):
    filename = repo.session.get_bind().url.database
    if not filename:
        return
    script = '''import json,sqlite3,sys
from game_state.serializers import deserialize_match_snapshot,serialize_match_snapshot
c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
s,k=c.execute('SELECT state_json,controller_json FROM activematchrecord WHERE id=?',(sys.argv[2],)).fetchone()
assert json.loads(json.dumps(serialize_match_snapshot(deserialize_match_snapshot(json.loads(s)))))==json.loads(s)
print(json.dumps([json.loads(s),json.loads(k)]));c.close()
'''
    result = subprocess.run([sys.executable, '-c', script, filename, mid],
                            capture_output=True, text=True, timeout=30, env=os.environ.copy())
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == list(expected)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
def test_complete_body_cannot_compile_as_only_exile(name, seat):
    state, source, spell, _ = position(seat, name)
    before = snap(state)
    spec = build_ability_spec(state, state.cards[spell], seat,
                              {'target_card_id': source}, report_unsupported=False)
    assert snap(state) == before
    assert spec.effect.key not in {'exile', 'noop'}, (spec.effect.key, spec.effect.payload)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
@pytest.mark.parametrize('foreign', [False, True])
def test_actual_http_paid_blink_response_returns_exact_object_then_private_search(
        name, seat, foreign, repo, client, tmp_path):
    import main
    controller, _, _, path = http_position(repo, client, seat, 'Fertilid')
    state, source, spell, lands = position(seat, name, foreign)
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    mid = state.id

    def send(actor, action):
        response = client.post(path + '/action', json={'player_id': actor, 'action': action})
        assert response.status_code == 200, response.text
        return main.ACTIVE_MATCHES[mid].state

    old_sequence = state.cards[source].zone_change_sequence
    state = send(seat, {'type': 'activate_ability', 'card_id': source, 'ability_index': 0,
                        'targets': {'target_player': 3-seat}})
    original = deepcopy(state.stack[-1])
    assert state.cards[source].counters['+1/+1'] == 1
    state = send(seat, {'type': 'cast_spell', 'card_id': spell, 'cost_choice': {'id': 'base'},
                        'targets': {'target_card_id': source}})
    assert len(state.stack) == 2 and state.stack[-1].payload['mana_spent'] == (1 if name == 'cloudshift' else 2)
    controller = main.ACTIVE_MATCHES[mid]
    paused = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    cold_sql(repo, mid, paused[:2])
    main.ACTIVE_MATCHES.pop(mid)
    main._restore_active_matches(repo, mid)
    controller = main.ACTIVE_MATCHES[mid]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == paused
    for _ in range(2):
        state = send(main.ACTIVE_MATCHES[mid].state.priority_player, {'type': 'pass_priority'})
    card = state.cards[source]
    assert card.zone == Zone.BATTLEFIELD, 'Full exile-then-return must not strand the creature in exile'
    assert card.zone_change_sequence == old_sequence + 2
    recipient = seat if name == 'cloudshift' else card.owner
    assert card.controller == recipient and source in state.players[recipient].battlefield
    assert sum(source in player.battlefield for player in state.players.values()) == 1
    assert source not in state.players[card.owner].exile
    assert card.summoning_sick and card.counters.get('+1/+1') == 2
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.stack[0].id == original.id and state.stack[0].controller == seat
    for _ in range(2):
        state = send(state.priority_player, {'type': 'pass_priority'})
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    assert state.pending_mechanic_choice['continuation_controller'] == seat
    assert_private(state)
    chosen = lands[3-seat][1]
    state = send(3-seat, {'type': 'choose_mechanic', 'card_ids': [chosen]})
    assert state.cards[chosen].zone == Zone.BATTLEFIELD and state.cards[chosen].tapped
    assert state.cards[source].counters['+1/+1'] == 2  # No repayment from the new object.
    assert_private(restart(state, tmp_path, 'returned-source-complete'))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
def test_invalid_absent_target_rejects_without_cost_or_root_mutation(seat, name):
    state, _, spell, _ = position(seat, name)
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'cast_spell', 'card_id': spell,
                         'targets': {'target_card_id': 'not-a-card'}})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
def test_hidden_full_response_identity_swap_preserves_actor_input(seat, name):
    state, _, _, _ = position(seat, name)
    first = raw_card(state, ROWS['cloudshift'], 3-seat, Zone.HAND)
    second = raw_card(state, ROWS['flicker-of-fate'], 3-seat, Zone.LIBRARY)
    altered = deepcopy(state)
    for cid, other in [(first.id, second), (second.id, first)]:
        card = deepcopy(other)
        previous = altered.cards[cid]
        card.id, card.zone = cid, previous.zone
        card.zone_change_sequence = previous.zone_change_sequence
        altered.cards[cid] = card
    before = snap(state)
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    other_view, other_moves = decision_view(altered, seat, RulesEngine().legal_moves(altered, seat))
    assert snap(view) == snap(other_view) and moves == other_moves
    assert snap(state) == before
