"""Early/late real static replacements retain the original simultaneous set."""
from copy import deepcopy

import pytest

from game_state.state import Zone, object_incarnation
from effects.handlers import mill_cards
from rules_engine.action_validation import ActionRejected
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import client, install, main_controller_snapshot, public_private_restore
from tests.test_paid_mill_batch_entry_audit import mill_position, entry_collections
from tests.test_actual_annihilator_batch_entry_audit import attack_position, genuine_pending, deliberate_orders
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS as BASE, act, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS
from tests.test_simultaneous_graveyard_entry_audit import passes
from tests.test_spell_admission_safety_http import sql_facts
from tests.readiness_rules_seam_support import normalize


def static_mill(seat, name, order):
    state, source, ids, target, action = mill_position(seat, False, 'library')
    replaced = state.cards[ids[1]]
    if name != replaced.name:
        state.players[target].library.remove(replaced.id)
        del state.cards[replaced.id]
        replaced = raw_card(state, BASE[name], target, Zone.LIBRARY)
    desired = [replaced.id, ids[0]] if order == 'early' else [ids[0], replaced.id]
    for cid in desired:
        state.players[target].library.remove(cid)
    state.players[target].library.extend(reversed(desired))
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(replaced), 'zone_change_sequence': replaced.zone_change_sequence}
    return state, source, desired, replaced.id, probe.id, reference, action


def assert_static(state, probe, cid, reference, origin):
    items = list(state.stack)
    pending = state.pending_trigger_order or {}
    causes = [item.payload['__shuffle_cause'] for item in items if item.source_card_id == probe]
    causes += [item['payload']['__shuffle_cause'] for group in pending.get('groups', {}).values()
               for item in group if item['source_card_id'] == probe]
    assert len(causes) == 1
    cause = causes[0]
    assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
    assert cause['source_card_id'] == cid and cause['source_reference'] == reference
    assert cause['source_zone'] == origin and 'stack_id' not in cause
    row = BASE[state.cards[cid].name]
    assert cause['ability_clause'] == row['oracle_text'].splitlines()[cause['ability_index']]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Darksteel Colossus', 'Progenitus'])
@pytest.mark.parametrize('order', ['early', 'second'])
def test_actual_paid_original_top_set_survives_early_or_second_shuffle(seat, name, order, entry_collections, tmp_path):
    state, source, ids, replaced, probe, reference, action = static_mill(seat, name, order)
    ordinary = next(cid for cid in ids if cid != replaced)
    state = act(state, seat, action)
    assert state.cards[source].tapped and not sum(state.players[seat].mana_pool.values())
    state = restart(state, tmp_path, 'paid-early-static')
    state = passes(state)
    assert state.cards[ordinary].zone == Zone.GRAVEYARD
    assert state.cards[replaced].zone == Zone.LIBRARY
    assert state.cards[replaced].zone_change_sequence == reference['zone_change_sequence']
    assert_static(state, probe, replaced, reference, 'library')
    mills = [row for row in entry_collections if row['event'] == 'mill']
    assert {row['payload']['card_id'] for row in mills} == set(ids)
    entries = [row for row in entry_collections if row['event'] == 'enters_graveyard']
    assert entries and all(row['payload']['card_id'] == ordinary for row in entries)
    assert all(row['zones'][ordinary] == 'graveyard' and row['zones'][replaced] == 'library' for row in entries)
    restart(state, tmp_path, 'actual-early-shuffle-original-set')


@pytest.mark.parametrize('seat', [1, 2])
def test_two_real_static_replacements_each_keep_their_preproof_and_shuffle(seat, entry_collections, tmp_path):
    state, source, ids, replaced, probe, reference, action = static_mill(seat, 'Darksteel Colossus', 'early')
    old = next(cid for cid in ids if cid != replaced)
    state.players[seat].library.remove(old); del state.cards[old]
    second = raw_card(state, BASE['Progenitus'], seat, Zone.LIBRARY)
    state.players[seat].library.remove(replaced)
    state.players[seat].library.append(replaced)
    second_ref = {'incarnation': object_incarnation(second), 'zone_change_sequence': second.zone_change_sequence}
    state = passes(act(state, seat, action))
    assert state.cards[replaced].zone == state.cards[second.id].zone == Zone.LIBRARY
    assert not any(row['event'] == 'enters_graveyard' for row in entry_collections)
    receipts = (state.pending_trigger_order or {}).get('groups', {})
    causes = [item.payload['__shuffle_cause'] for item in state.stack if item.source_card_id == probe]
    causes += [item['payload']['__shuffle_cause'] for group in receipts.values() for item in group if item['source_card_id'] == probe]
    assert len(causes) == 2
    assert {cause['source_card_id'] for cause in causes} == {replaced, second.id}
    for cause in causes:
        assert cause['source_reference'] == {replaced: reference, second.id: second_ref}[cause['source_card_id']]
        assert cause['kind'] == 'static' and 'stack_id' not in cause
    restart(state, tmp_path, 'two-real-replacement-shuffles')


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_stack_mill_preflight_rejects_before_raw_library_removal(seat, entry_collections):
    state, source, ids, _, _, _, action = static_mill(seat, 'Darksteel Colossus', 'second')
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    state = act(state, seat, action)
    before = snap(state)
    # Invoke only the real paid frame's handler to isolate preflight purity.
    with pytest.raises(ActionRejected, match='competing graveyard replacement source'):
        mill_cards(state, seat, state.stack[-1].payload)
    assert snap(state) == before and not entry_collections


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('early', [False, True])
def test_real_annihilator_static_order_keeps_pre_lbf_refs_and_committed_entries(seat, foreign, early, entry_collections, tmp_path):
    state, attacker, victims = genuine_pending(seat, foreign, 'library')
    replaced = next(cid for cid in victims if state.cards[cid].name == 'Darksteel Colossus')
    probe = raw_card(state, ROWS['Psychogenic Probe'], seat, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(state.cards[replaced]), 'zone_change_sequence': state.cards[replaced].zone_change_sequence}
    selected = [cid for cid in victims if cid != replaced]
    selected.insert(0 if early else len(selected), replaced)
    state = act(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': selected})
    assert_static(state, probe.id, replaced, reference, 'battlefield')
    assert state.cards[replaced].zone_change_sequence == reference['zone_change_sequence'] + 1
    entries = [row for row in entry_collections if row['event'] == 'enters_graveyard']
    assert {row['payload']['card_id'] for row in entries} == set(victims) - {replaced}
    assert all(all(row['zones'][cid] == ('library' if cid == replaced else 'graveyard') for cid in victims) for row in entries)
    state = deliberate_orders(restart(state, tmp_path, 'annihilator-pre-order'))
    restart(state, tmp_path, 'annihilator-complete-order')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Darksteel Colossus', 'Progenitus'])
@pytest.mark.parametrize('order', ['early', 'second'])
def test_http_early_or_second_paid_mill_cause_atomic_invalid_sql_restart(repo, client, seat, name, order, entry_collections, tmp_path):
    for row in [*BASE.values(), *ROWS.values()]: repo.upsert_card(normalize(row))
    state, source, ids, replaced, probe, reference, action = static_mill(seat, name, order)
    controller = install(repo, client, state)
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    bad = deepcopy(action); bad['targets']['target_player'] = 99
    rejected = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': bad})
    assert rejected.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    assert not entry_collections
    def send(actor, intent):
        response = client.post('/matches/' + state.id + '/action', json={'player_id': actor, 'action': intent})
        assert response.status_code == 200, response.text
    send(seat, action)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    for _ in range(2): send(controller.state.priority_player, {'type': 'pass_priority'})
    ordinary = next(cid for cid in ids if cid != replaced)
    assert controller.state.cards[ordinary].zone == Zone.GRAVEYARD
    assert_static(controller.state, probe, replaced, reference, 'library')
    assert {row['payload']['card_id'] for row in entry_collections if row['event'] == 'mill'} == set(ids)
    public_private_restore(repo, client, controller, seat, tmp_path)


@pytest.mark.parametrize('seat', [1, 2])
def test_http_competing_mill_resolution_rejects_atomic_after_prior_payment(repo, client, seat, entry_collections):
    for row in [*BASE.values(), *ROWS.values()]: repo.upsert_card(normalize(row))
    state, source, ids, _, _, _, action = static_mill(seat, 'Darksteel Colossus', 'second')
    raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    controller = install(repo, client, state)
    path = '/matches/' + state.id + '/action'
    response = client.post(path, json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    response = client.post(path, json={'player_id': controller.state.priority_player, 'action': {'type': 'pass_priority'}})
    assert response.status_code == 200, response.text
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    response = client.post(path, json={'player_id': controller.state.priority_player, 'action': {'type': 'pass_priority'}})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    assert not entry_collections
    assert controller.state.cards[source].tapped and not sum(controller.state.players[seat].mana_pool.values())
    assert all(controller.state.cards[cid].zone == Zone.LIBRARY for cid in ids)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('early', [False, True])
def test_http_genuine_annihilator_static_order_and_atomic_bad_selection(repo, client, seat, early, entry_collections, tmp_path):
    for row in [*BASE.values(), *ROWS.values()]: repo.upsert_card(normalize(row))
    state, attacker, victims, action = attack_position(seat, True, 'library')
    replaced = next(cid for cid in victims if state.cards[cid].name == 'Darksteel Colossus')
    probe = raw_card(state, ROWS['Psychogenic Probe'], seat, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(state.cards[replaced]), 'zone_change_sequence': state.cards[replaced].zone_change_sequence}
    controller = install(repo, client, state)
    def send(actor, intent):
        response = client.post('/matches/' + state.id + '/action', json={'player_id': actor, 'action': intent})
        assert response.status_code == 200, response.text
    send(seat, action)
    for _ in range(2): send(controller.state.priority_player, {'type': 'pass_priority'})
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    bad = client.post('/matches/' + state.id + '/action', json={'player_id': 3-seat,
                      'action': {'type': 'choose_mechanic', 'card_ids': [replaced] * 4}})
    assert bad.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    assert not entry_collections
    selected = [cid for cid in victims if cid != replaced]
    selected.insert(0 if early else len(selected), replaced)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    send(3-seat, {'type': 'choose_mechanic', 'card_ids': selected})
    assert_static(controller.state, probe.id, replaced, reference, 'battlefield')
    entries = [row for row in entry_collections if row['event'] == 'enters_graveyard']
    assert all(all(row['zones'][cid] == ('library' if cid == replaced else 'graveyard') for cid in victims) for row in entries)
    public_private_restore(repo, client, controller, seat, tmp_path)
