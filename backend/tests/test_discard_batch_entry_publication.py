"""Genuine committed discard receipts; no event/context injection."""
from copy import deepcopy

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.zone_actions import discard_simultaneous, execute_graveyard_entry, put_into_graveyard
from rules_engine.replacement import select_graveyard_entry_plan
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import client, install, main_controller_snapshot, public_private_restore
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS as BASE, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS
from tests.test_simultaneous_graveyard_entry_audit import batch_position, FRESH, KOZILEK
from tests.test_spell_admission_safety_http import sql_facts
from tests.readiness_rules_seam_support import normalize


@pytest.fixture
def collected(monkeypatch, tmp_path):
    from rules_engine import events
    original = events._collect_triggers
    rows = []

    def record(state, event, payload):
        if event in {'enters_graveyard', 'discard'}:
            rows.append((event, deepcopy(payload),
                         {cid: card.zone for cid, card in state.cards.items()},
                         dict(state.discards_this_turn)))
        return original(state, event, payload)

    monkeypatch.setattr(events, '_collect_triggers', record)
    return rows


@pytest.mark.parametrize('seat', [1, 2])
def test_raw_validated_batch_collects_after_all_moves_counters_and_exact_refs(seat, collected, tmp_path):
    state, _, selected = batch_position(seat)
    ids = selected[1] + selected[2]
    before = {cid: (object_incarnation(state.cards[cid]), state.cards[cid].zone_change_sequence) for cid in ids}
    assert discard_simultaneous(state, selected)
    entries = [row for row in collected if row[0] == 'enters_graveyard']
    assert len(entries) == 6 and {row[1]['card_id'] for row in entries} == set(ids)
    for _, payload, zones, counts in entries:
        cid = payload['card_id']
        incarnation, sequence = before[cid]
        assert all(zones[key] == Zone.GRAVEYARD for key in ids)
        assert counts == {1: 3, 2: 3}
        assert payload['previous_reference'] == {'incarnation': incarnation, 'zone_change_sequence': sequence}
        assert payload['entry_reference'] == {'incarnation': incarnation, 'zone_change_sequence': sequence + 1}
        assert payload['owner'] == state.cards[cid].owner
        assert payload['previous_controller'] == state.cards[cid].controller
        assert payload['from_zone'] == 'hand'
    assert [row[0] for row in collected] == ['enters_graveyard'] * 6 + ['discard'] * 6
    restart(state, tmp_path, 'committed-batch')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('empty', [False, True])
def test_empty_selection_has_no_entry_or_discard_event(seat, empty, collected):
    state, _, _ = batch_position(seat)
    before = snap(state)
    assert discard_simultaneous(state, {seat: []} if empty else {})
    assert snap(state) == before and not collected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['duplicate', 'missing', 'opposing', 'invalid_player', 'stale_zone'])
def test_entire_invalid_selection_rejects_before_any_batch_mutation(seat, bad, collected):
    state, _, selected = batch_position(seat)
    invalid = deepcopy(selected)
    if bad == 'duplicate':
        invalid[3-seat] = [selected[3-seat][0]] * 3
    elif bad == 'missing':
        invalid[3-seat][-1] = 'not-a-card'
    elif bad == 'opposing':
        invalid[3-seat][-1] = selected[seat][0]
    elif bad == 'invalid_player':
        invalid[99] = []
    else:
        # Trusted stale input position, not a claimed executed exile spell.
        cid = selected[3-seat][-1]
        state.players[3-seat].hand.remove(cid)
        state.players[3-seat].exile.append(cid)
        state.cards[cid].move_to_zone(Zone.EXILE)
    before = snap(state)
    assert not discard_simultaneous(state, invalid)
    assert snap(state) == before and not collected


@pytest.mark.parametrize('seat', [1, 2])
def test_competing_replacement_preflight_rejects_even_after_other_selected_cards(seat, collected):
    state, _, selected = batch_position(seat)
    colossus = raw_card(state, BASE['Darksteel Colossus'], 3-seat, Zone.HAND)
    raw_card(state, ROWS['Rest in Peace'], seat, Zone.BATTLEFIELD)
    selected[3-seat].append(colossus.id)
    before = snap(state)
    with pytest.raises(ActionRejected, match='competing graveyard replacement source'):
        discard_simultaneous(state, selected)
    assert snap(state) == before and not collected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('replacement', ['library', 'exile', 'humility_hand'])
def test_replaced_entries_do_not_fabricate_graveyard_receipts(seat, replacement, collected, tmp_path):
    state, _, _ = batch_position(seat)
    koz = raw_card(state, BASE[KOZILEK], seat, Zone.HAND)
    name = 'Blood Artist' if replacement == 'exile' else 'Darksteel Colossus'
    replaced = raw_card(state, BASE[name], seat, Zone.HAND)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(replaced), 'zone_change_sequence': replaced.zone_change_sequence}
    if replacement == 'exile':
        raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    elif replacement == 'humility_hand':
        raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    assert discard_simultaneous(state, {seat: [koz.id, replaced.id]})
    entries = [row for row in collected if row[0] == 'enters_graveyard']
    if replacement == 'exile':
        assert not entries and state.cards[koz.id].zone == state.cards[replaced.id].zone == Zone.EXILE
    else:
        assert len(entries) == 1 and entries[0][1]['card_id'] == koz.id
        assert entries[0][2][replaced.id] == Zone.LIBRARY
        receipts = [item for item in state.stack if item.source_card_id == probe.id]
        assert len(receipts) == 1
        cause = receipts[0].payload['__shuffle_cause']
        assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
        assert cause['source_card_id'] == replaced.id and cause['source_reference'] == reference
        assert cause['source_zone'] == 'hand' and 'stack_id' not in cause
        assert cause['ability_clause'] == BASE[name]['oracle_text'].splitlines()[cause['ability_index']]
    assert len([row for row in collected if row[0] == 'discard']) == 2
    restart(state, tmp_path, 'replaced-discard-batch')


@pytest.mark.parametrize('seat', [1, 2])
def test_single_entry_still_publishes_immediately_once(seat, collected):
    state, _, selected = batch_position(seat)
    cid = selected[seat][0]
    assert put_into_graveyard(state, cid) == Zone.GRAVEYARD
    assert len(collected) == 1 and collected[0][0] == 'enters_graveyard'
    assert collected[0][1]['card_id'] == cid
    assert all(state.cards[key].zone == Zone.HAND for key in selected[3-seat])
    assert any(item.source_card_id == cid for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_invalid_internal_sink_rejects_before_commit(seat, collected):
    state, _, selected = batch_position(seat)
    plan = select_graveyard_entry_plan(state, selected[seat][0])
    before = snap(state)
    with pytest.raises(ActionRejected, match='receipt collection'):
        execute_graveyard_entry(state, plan, _entry_receipts={})
    assert snap(state) == before and not collected


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_http_paid_batch_collects_committed_state_and_failed_choice_is_atomic(repo, client, seat, collected, tmp_path):
    for row in [*BASE.values(), *FRESH.values()]:
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
                           json={'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': [selected[seat][0]] * 3}})
    assert response.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    assert not collected
    send(seat, {'type': 'choose_mechanic', 'card_ids': selected[seat]})
    assert not collected
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    send(3-seat, {'type': 'choose_mechanic', 'card_ids': selected[3-seat]})
    ids = set(selected[1] + selected[2])
    entries = [row for row in collected if row[0] == 'enters_graveyard' and row[1]['card_id'] in ids]
    assert len(entries) == 6
    assert all(all(row[2][cid] == Zone.GRAVEYARD for cid in ids) for row in entries)
    assert all(row[3] == {1: 3, 2: 3} for row in entries)
    assert len(controller.state.pending_trigger_order['groups'][str(seat)]) == 2
    assert len(controller.state.pending_trigger_order['groups'][str(3-seat)]) == 2
    public_private_restore(repo, client, controller, seat, tmp_path)
