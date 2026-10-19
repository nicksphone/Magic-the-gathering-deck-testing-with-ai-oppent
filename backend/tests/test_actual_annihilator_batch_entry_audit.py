"""Canonical annihilator through genuine checked attack, not a trusted stack."""
from copy import deepcopy

import pytest

from game_state.state import Step, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client as base_client
from tests.test_direct_graveyard_bypass_audit import client, install, main_controller_snapshot, public_private_restore
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import ROWS as BASE, act, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS
from tests.test_simultaneous_graveyard_entry_audit import KOZILEK, passes
from tests.test_paid_mill_batch_entry_audit import entry_collections
from tests.test_spell_admission_safety_http import sql_facts
from tests.readiness_rules_seam_support import normalize


def attack_position(seat, foreign=False, replacement='ordinary'):
    state, _ = setup('Index', seat)
    defender = 3-seat
    attacker = raw_card(state, BASE[KOZILEK], seat, Zone.BATTLEFIELD)
    attacker.summoning_sick = False
    victim = raw_card(state, BASE[KOZILEK], defender, Zone.BATTLEFIELD)
    if foreign:
        # Trusted lawful retained control position; no control spell claim.
        victim.owner = seat
    victims = [victim.id]
    for _ in range(3):
        victims.append(raw_card(state, BASE['Doomed Traveler'], defender, Zone.BATTLEFIELD).id)
    if replacement == 'library':
        last = victims.pop()
        state.players[defender].battlefield.remove(last); del state.cards[last]
        victims.append(raw_card(state, BASE['Darksteel Colossus'], defender, Zone.BATTLEFIELD).id)
    if replacement == 'exile':
        raw_card(state, ROWS['Rest in Peace'], seat, Zone.BATTLEFIELD)
    state.step = Step.DECLARE_ATTACKERS
    state.active_player = state.priority_player = seat
    state.mechanic_choice_players = {1, 2}
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    action = {'type': 'attack', 'attackers': [attacker.id]}
    return state, attacker.id, victims, action


def genuine_pending(seat, foreign=False, replacement='ordinary'):
    state, attacker, victims, action = attack_position(seat, foreign, replacement)
    state = act(state, seat, action)
    assert attacker in state.attackers and state.cards[attacker].tapped
    assert state.stack[-1].source_card_id == attacker and state.stack[-1].effect_key == 'annihilator'
    assert state.stack[-1].payload['amount'] == 4
    state = passes(state)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'sacrifice' and pending['player_id'] == 3-seat
    assert pending['count'] == 4 and set(pending['options']) == set(victims)
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in victims)
    return state, attacker, victims


def deliberate_orders(state):
    controllers = []
    while state.pending_trigger_order:
        actor = state.pending_trigger_order['current_controller']
        controllers.append(actor)
        move = next(m for m in RulesEngine().legal_moves(state, actor) if m['type'] == 'choose_trigger_order')
        state = act(state, actor, {'type': 'choose_trigger_order', 'trigger_order': list(reversed(move['trigger_order']))})
    assert controllers == sorted(set(controllers), key=lambda x: x != state.active_player)
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_real_annihilator_selection_entry_collection_requires_complete_batch(seat, foreign, entry_collections):
    state, _, victims = genuine_pending(seat, foreign)
    assert not entry_collections
    state = act(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': list(reversed(victims))})
    entries = [row for row in entry_collections if row['event'] == 'enters_graveyard' and row['payload']['card_id'] in victims]
    assert entries and {row['payload']['card_id'] for row in entries} == set(victims)
    assert all(all(row['zones'][cid] == 'graveyard' for cid in victims) for row in entries), \
        'Actual selected annihilator sacrifices must all commit before entry collection'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('replacement', ['ordinary', 'library', 'exile'])
def test_independent_actual_attack_selection_owner_refs_apnap_replacement_restart(seat, foreign, replacement, entry_collections, tmp_path):
    state, attacker, victims = genuine_pending(seat, foreign, replacement)
    refs = {cid: {'incarnation': object_incarnation(state.cards[cid]),
                  'zone_change_sequence': state.cards[cid].zone_change_sequence} for cid in victims}
    owners = {cid: state.cards[cid].owner for cid in victims}
    state = restart(state, tmp_path, 'real-attack-paused')
    state = act(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': list(reversed(victims))})
    for cid in victims:
        expected = Zone.EXILE if replacement == 'exile' else Zone.LIBRARY if state.cards[cid].name == 'Darksteel Colossus' else Zone.GRAVEYARD
        assert state.cards[cid].zone == expected
        assert getattr(state.players[owners[cid]], expected.value).count(cid) == 1
        assert state.cards[cid].zone_change_sequence == refs[cid]['zone_change_sequence'] + 1
    entries = [row for row in entry_collections if row['event'] == 'enters_graveyard' and row['payload']['card_id'] in victims]
    expected_gy = {cid for cid in victims if state.cards[cid].zone == Zone.GRAVEYARD}
    assert {row['payload']['card_id'] for row in entries} == expected_gy
    for row in entries:
        payload = row['payload']; cid = payload['card_id']
        assert payload['owner'] == owners[cid] and payload['previous_controller'] == 3-seat
        assert payload['from_zone'] == 'battlefield' and payload['previous_reference'] == refs[cid]
        assert payload['entry_reference'] == {**refs[cid], 'zone_change_sequence': refs[cid]['zone_change_sequence'] + 1}
    assert {row['payload']['card_id'] for row in entry_collections if row['event'] == 'sacrifice'} == set(victims)
    assert {row['payload']['card_id'] for row in entry_collections if row['event'] == 'creature_dies'} == expected_gy
    if replacement != 'exile':
        expected_controller = seat if foreign else 3-seat
        items = (state.pending_trigger_order or {}).get('groups', {})
        receipts = list(state.staged_triggers) + [item for group in items.values() for item in group]
        assert any(item['source_card_id'] == victims[0] and item['controller'] == expected_controller for item in receipts)
    state = restart(state, tmp_path, 'selected-all-destinations')
    state = deliberate_orders(state)
    assert state.cards[attacker].zone == Zone.BATTLEFIELD and attacker in state.attackers
    restart(state, tmp_path, 'real-apnap-order')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['duplicate', 'wrong_actor'])
def test_genuine_attack_pending_invalid_selection_is_pure(seat, bad, entry_collections):
    state, _, victims = genuine_pending(seat)
    actor = seat if bad == 'wrong_actor' else 3-seat
    ids = victims if bad == 'wrong_actor' else [victims[0]] * 4
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), actor, {'type': 'choose_mechanic', 'card_ids': ids})
    assert snap(state) == before and not entry_collections


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_http_genuine_attack_and_selected_sacrifice_root_sql_private_restart(repo, client, seat, foreign, entry_collections, tmp_path):
    for row in [*BASE.values(), *ROWS.values()]:
        repo.upsert_card(normalize(row))
    state, attacker, victims, action = attack_position(seat, foreign)
    controller = install(repo, client, state)

    def send(actor, intent):
        response = client.post('/matches/' + controller.state.id + '/action', json={'player_id': actor, 'action': intent})
        assert response.status_code == 200, response.text

    send(seat, action)
    assert controller.state.stack[-1].effect_key == 'annihilator'
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    for _ in range(2):
        send(controller.state.priority_player, {'type': 'pass_priority'})
    assert controller.state.pending_mechanic_choice['count'] == 4
    before = snap(controller.state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + controller.state.id + '/action',
                           json={'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': victims}})
    assert rejected.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    assert not entry_collections
    send(3-seat, {'type': 'choose_mechanic', 'card_ids': list(reversed(victims))})
    assert all(controller.state.cards[cid].zone == Zone.GRAVEYARD for cid in victims)
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    while controller.state.pending_trigger_order:
        actor = controller.state.pending_trigger_order['current_controller']
        move = next(m for m in RulesEngine().legal_moves(controller.state, actor) if m['type'] == 'choose_trigger_order')
        send(actor, {'type': 'choose_trigger_order', 'trigger_order': list(reversed(move['trigger_order']))})
    assert any(item.source_card_id == victims[0] and item.controller == (seat if foreign else 3-seat) for item in controller.state.stack)
    public_private_restore(repo, client, controller, seat, tmp_path)
