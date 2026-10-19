"""Desired real paid-entry integration; controlled positions, no manual events."""
from copy import deepcopy

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import normalize
from tests.test_builtin_metadata_refresh import repo
from tests.test_kozilek_graveyard_trigger_audit import start, enter, trigger, passes, save, KOZILEK
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS, snap, act
from tests.test_self_graveyard_replacement_interactions import ROWS as OBSERVERS
from tests.test_spell_admission_safety_http import sql_facts


def http_position(repo, client, seat):
    import main
    for row in ROWS.values():
        repo.upsert_card(normalize(row))
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={
        'deck_a': deck, 'deck_b': deck, 'sandbox': True,
        'controller_a': 'human', 'controller_b': 'human', 'seed': 7331})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state, cid, source, old, action = start(seat, 'discard')
    state.id = controller.state.id
    controller.state = state
    main._persist_active_match(repo, controller)
    return controller, cid, source, old, action


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_entry_trigger_survives_http_sqlite_restart_private_views(repo, client, seat):
    import main
    controller, cid, _, _, action = http_position(repo, client, seat)
    mid = controller.state.id
    response = client.post('/matches/' + mid + '/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    state = main.ACTIVE_MATCHES[mid].state
    snapshot = snap(state)
    main.ACTIVE_MATCHES.pop(mid)
    main._restore_active_matches(repo, mid)
    restored = main.ACTIVE_MATCHES[mid].state
    assert snap(restored) == snapshot
    view, _ = decision_view(restored, 3-seat, RulesEngine().legal_moves(restored, 3-seat))
    assert not is_unknown(view.cards[cid])
    assert all(is_unknown(view.cards[other]) for other in restored.players[seat].hand
               + restored.players[seat].library)
    item = trigger(restored, cid)
    assert item.payload['__trigger_source_reference']['zone_change_sequence'] == restored.cards[cid].zone_change_sequence


@pytest.mark.parametrize('seat', [1, 2])
def test_wrong_actor_http_entry_reject_preserves_root_controller_sql(repo, client, seat):
    import main
    controller, _, _, _, action = http_position(repo, client, seat)
    before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + controller.state.id + '/action',
                           json={'player_id': 3-seat, 'action': action})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_resolving_shuffle_cause_retains_trigger_entry_reference(seat, tmp_path):
    state, cid, _, _, action = start(seat, 'discard')
    probe = raw_card(state, OBSERVERS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    state = save(tmp_path, 'entry-reference', enter(state, seat, 'discard', action))
    item = trigger(state, cid)
    reference = deepcopy(item.payload['__trigger_source_reference'])
    state = passes(state)
    assert state.cards[cid].zone == Zone.LIBRARY
    receipts = [other for other in state.stack if other.source_card_id == probe.id]
    assert len(receipts) == 1
    cause = receipts[0].payload['__shuffle_cause']
    assert cause['kind'] == 'triggered' and cause['stack_id'] == item.id
    assert cause['source_reference'] == reference


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_two_card_paid_discard_batch_explicit_order_restart(seat, tmp_path):
    state, cid, source, _, action = start(seat, 'discard')
    second = raw_card(state, ROWS[KOZILEK], seat, Zone.HAND)
    action = deepcopy(action)
    action['targets']['x_value'] = 2
    action['cost_choice']['discard_card_ids'] = [cid, second.id]
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    state = act(state, seat, action)
    state = save(tmp_path, 'batch-entry-pending-order', state)
    pending = state.pending_trigger_order
    assert pending is not None and pending['current_controller'] == seat
    group = pending['groups'][str(seat)]
    assert {entry['source_card_id'] for entry in group} == {cid, second.id}
    assert all(entry['payload']['__trigger_event'] == 'enters_graveyard' for entry in group)
    order = [entry['_choice_id'] for entry in reversed(group)]
    state = act(state, seat, {'type': 'choose_trigger_order', 'trigger_order': order})
    assert [item.source_card_id for item in state.stack] == [source, second.id, cid]
    save(tmp_path, 'batch-entry-ordered', state)
