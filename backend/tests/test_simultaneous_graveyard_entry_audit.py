"""Real selected discard batches: committed collection, private choice and APNAP."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import client, install, main_controller_snapshot, public_private_restore
from tests.test_linked_damage_targets import raw_card
from tests.test_library_reorder import setup
from tests.test_self_graveyard_replacement_audit import ROWS as BASE, act, restart, snap
from tests.test_spell_admission_safety_http import sql_facts
from tests.readiness_rules_seam_support import normalize

FIXTURE = Path(__file__).parent / 'fixtures/simultaneous_graveyard_audit/canonical.jsonl'
PROVENANCE = json.loads(FIXTURE.with_name('provenance.json').read_text())
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == PROVENANCE['fixture_sha256']
FRESH = {r['name']: r for r in map(json.loads, FIXTURE.read_text().splitlines())}
KOZILEK = 'Kozilek, Butcher of Truth'


def batch_position(seat):
    state, _ = setup('Index', seat)
    selected = {}
    for pid in (1, 2):
        selected[pid] = [raw_card(state, BASE[KOZILEK], pid, Zone.HAND).id for _ in range(2)]
        selected[pid].append(raw_card(state, BASE['Blood Artist'], pid, Zone.HAND).id)
    source = raw_card(state, FRESH['Delirium Skeins'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'B': 1, 'C': 2}
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    return state, source, selected


def passes(state):
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return state


def start_batch(seat):
    state, source, selected = batch_position(seat)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    assert state.stack[-1].effect_key == 'each_player_discard'
    assert not sum(state.players[seat].mana_pool.values())
    state = passes(state)
    assert state.pending_mechanic_choice['kind'] == 'each_player_discard'
    return state, source, selected


def choose(state, actor, ids):
    return act(state, actor, {'type': 'choose_mechanic', 'card_ids': list(ids)})


def finish_orders(state):
    choices = []
    for _ in range(2):
        pending = state.pending_trigger_order
        assert pending and pending['current_controller'] == [state.active_player, 3-state.active_player][len(choices)]
        actor = pending['current_controller']
        moves = RulesEngine().legal_moves(state, actor)
        move = next(m for m in moves if m['type'] == 'choose_trigger_order')
        order = list(reversed(move['trigger_order']))
        choices.append((actor, order, [next(t['source_card_id'] for t in pending['groups'][str(actor)]
                                          if t['_choice_id'] == key) for key in order]))
        state = act(state, actor, {'type': 'choose_trigger_order', 'trigger_order': order})
    assert state.pending_trigger_order is None
    assert [item.controller for item in state.stack] == [state.active_player] * 2 + [3-state.active_player] * 2
    assert [item.source_card_id for item in state.stack] == [cid for _, _, ids in choices for cid in ids]
    return state


@pytest.fixture
def collected_entries(monkeypatch, tmp_path):
    from rules_engine import events
    original = events._collect_triggers
    observed = []

    def record(state, event, payload):
        if event == 'enters_graveyard':
            observed.append({'payload': deepcopy(payload), 'zones': {cid: c.zone.value for cid, c in state.cards.items()}})
        return original(state, event, payload)

    monkeypatch.setattr(events, '_collect_triggers', record)
    yield observed
    (tmp_path / 'committed-entry-observations.json').write_text(json.dumps(observed, indent=2))


@pytest.mark.parametrize('seat', [1, 2])
def test_entry_collector_only_sees_committed_complete_discard_batch(seat, collected_entries):
    state, _, selected = start_batch(seat)
    state = choose(state, seat, selected[seat])
    assert not collected_entries
    state = choose(state, 3-seat, selected[3-seat])
    ids = set(selected[1] + selected[2])
    relevant = [row for row in collected_entries if row['payload']['card_id'] in ids]
    assert relevant
    assert all(all(row['zones'][cid] == 'graveyard' for cid in ids) for row in relevant), \
        'Simultaneous entry collection must not inspect a partially committed batch'


@pytest.mark.parametrize('seat', [1, 2])
def test_deliberate_private_selections_apnap_public_orders_and_restart(seat, tmp_path):
    state, _, selected = start_batch(seat)
    state = restart(state, tmp_path, 'first-selection')
    state = choose(state, seat, selected[seat])
    assert all(state.cards[cid].zone == Zone.HAND for cid in selected[1] + selected[2])
    view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert all(is_unknown(view.cards[cid]) for cid in selected[seat])
    state = restart(state, tmp_path, 'second-selection')
    state = choose(state, 3-seat, selected[3-seat])
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in selected[1] + selected[2])
    assert all(len(state.pending_trigger_order['groups'][str(pid)]) == 2 for pid in (1, 2))
    state = restart(state, tmp_path, 'public-trigger-order')
    state = finish_orders(state)
    restart(state, tmp_path, 'retained-apnap-stack')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['duplicate', 'wrong_actor'])
def test_invalid_private_selection_preserves_root(seat, invalid):
    state, _, selected = start_batch(seat)
    actor = 3-seat if invalid == 'wrong_actor' else seat
    ids = selected[seat] if invalid == 'wrong_actor' else [selected[seat][0]] * 3
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, {'type': 'choose_mechanic', 'card_ids': ids})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_http_paid_batch_private_root_sql_and_public_order_restore(repo, client, seat, tmp_path):
    http_batch(repo, client, seat, tmp_path)


def http_batch(repo, client, seat, tmp_path):
    for row in FRESH.values():
        repo.upsert_card(normalize(row))
    state, source, selected = batch_position(seat)
    controller = install(repo, client, state)

    def send(actor, action):
        response = client.post('/matches/' + controller.state.id + '/action',
                               json={'player_id': actor, 'action': action})
        assert response.status_code == 200, response.text

    send(seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    for _ in range(2):
        send(controller.state.priority_player, {'type': 'pass_priority'})
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + controller.state.id + '/action',
                           json={'player_id': 3-seat, 'action': {'type': 'choose_mechanic', 'card_ids': selected[seat]}})
    assert response.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    send(seat, {'type': 'choose_mechanic', 'card_ids': selected[seat]})
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    send(3-seat, {'type': 'choose_mechanic', 'card_ids': selected[3-seat]})
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    for _ in range(2):
        actor = controller.state.pending_trigger_order['current_controller']
        move = next(m for m in RulesEngine().legal_moves(controller.state, actor) if m['type'] == 'choose_trigger_order')
        send(actor, {'type': 'choose_trigger_order', 'trigger_order': list(reversed(move['trigger_order']))})
    assert [item.controller for item in controller.state.stack] == [seat] * 2 + [3-seat] * 2
    public_private_restore(repo, client, controller, seat, tmp_path)
