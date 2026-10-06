"""Canonical pending sacrifices: batch preflight, real causes and continuation."""
from copy import deepcopy
import json
from pathlib import Path
import re

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine import events, zone_actions
from rules_engine.keyword_actions import finish_mechanic_choice
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from tests.test_linked_damage_targets import raw_card
from tests.test_direct_graveyard_bypass_audit import (
    ROWS, SELF, board, pending_sacrifice, select, install,
    main_controller_snapshot, public_private_restore, repo, client, base_client,
)
from tests.test_self_graveyard_replacement_audit import snap, restart, act
from tests.test_spell_admission_safety_http import sql_facts


def batch_position(seat, names, foreign=False):
    state, first, _ = board(seat, names[0], foreign)
    victims = [first, *(raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD) for name in names[1:])]
    source = raw_card(state, ROWS['Kozilek, Butcher of Truth'], 3-seat, Zone.BATTLEFIELD)
    amount = int(re.search(r'Annihilator (\d+)', source.oracle_text).group(1))
    add_to_stack(state, source.id, 3-seat, source.name + ' annihilator ' + str(amount),
                 'annihilator', {'target_player': seat, 'amount': amount}, is_spell=False)
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['count'] == min(amount, len(victims))
    return state, victims, source


def chosen(victims):
    return {'type': 'choose_mechanic', 'card_ids': [card.id for card in victims]}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_all_static_causes_precede_first_lbf_and_departure(seat, foreign, monkeypatch, tmp_path):
    state, victims, source = batch_position(seat, SELF, foreign)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    for card in victims: card.counters['+1/+1'] = 2
    references = {card.id: {'incarnation': object_incarnation(card),
                            'zone_change_sequence': card.zone_change_sequence} for card in victims}
    order = []
    original_prepare = zone_actions.prepare_graveyard_entry_causes
    original_emit = events.emit_event_batch
    def prepare(current, plans):
        plans = tuple(plans)
        assert {plan.card_id for plan in plans} == set(references)
        assert all(current.cards[cid].zone == Zone.BATTLEFIELD for cid in references)
        result = original_prepare(current, plans)
        assert all(result[cid] is not None for cid in references)
        order.append('all_causes')
        return result
    def emit(current, event, payloads):
        if event == 'leaves_battlefield':
            order.append('lbf')
            assert order == ['all_causes', 'lbf']
            assert all(current.cards[cid].zone == Zone.BATTLEFIELD for cid in references)
        return original_emit(current, event, payloads)
    monkeypatch.setattr(zone_actions, 'prepare_graveyard_entry_causes', prepare)
    monkeypatch.setattr(events, 'emit_event_batch', emit)
    before = snap(state)
    result = checked_action(state, RulesEngine(), seat, chosen(victims))
    assert snap(state) == before and order == ['all_causes', 'lbf']
    result = restart(result, tmp_path, 'batch-static')
    receipts = [item for item in result.stack if item.source_card_id == probe.id]
    assert len(receipts) == 2
    assert {item.payload['__shuffle_cause']['source_card_id'] for item in receipts} == set(references)
    for item in receipts:
        cause = item.payload['__shuffle_cause']
        assert cause['source_reference'] == references[cause['source_card_id']]
        assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
        assert 'stack_id' not in cause and cause['source_card_id'] != source.id
    for old in victims:
        card = result.cards[old.id]
        assert card.zone == Zone.LIBRARY
        assert result.players[old.owner].library.count(card.id) == 1
        assert card.zone_change_sequence == old.zone_change_sequence + 1
        assert card.counters == {} and card.last_known_battlefield['counters']['+1/+1'] == 2
    assert result.pending_mechanic_choice is None
    assert result.cards[source.id].zone == Zone.BATTLEFIELD
    assert sum(line == source.name + ' annihilator 4 resolves.' for line in result.log) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_mixed_library_and_real_death_preserve_single_dies_batch(seat, monkeypatch):
    state, victims, source = batch_position(seat, ['Progenitus', 'Doomed Traveler'])
    artist = raw_card(state, ROWS['Blood Artist'], 3-seat, Zone.BATTLEFIELD)
    rows = []
    original = events.emit_event_batch
    def observe(current, event, payloads):
        rows.extend((event, row['card_id']) for row in payloads)
        return original(current, event, payloads)
    monkeypatch.setattr(events, 'emit_event_batch', observe)
    mana, source_sequence = deepcopy(state.players[seat].mana_pool), source.zone_change_sequence
    result = checked_action(state, RulesEngine(), seat, chosen(victims))
    assert result.cards[victims[0].id].zone == Zone.LIBRARY
    assert result.cards[victims[1].id].zone == Zone.GRAVEYARD
    assert [(event, cid) for event, cid in rows if event == 'sacrifice'] == [('sacrifice', c.id) for c in victims]
    assert [(event, cid) for event, cid in rows if event == 'creature_dies'] == [('creature_dies', victims[1].id)]
    assert sum(item.source_card_id == artist.id for item in result.stack) == 1
    assert sum(item.source_card_id == victims[1].id for item in result.stack) == 1
    assert result.players[seat].mana_pool == mana and result.cards[source.id].zone_change_sequence == source_sequence


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_raw_core_complete_preflight_rejects_last_ambiguous_card_before_any_event(seat, name, monkeypatch):
    state, victims, _ = batch_position(seat, ['Doomed Traveler', 'Rest in Peace', name])
    rows = []
    original = events.emit_event_batch
    def observe(current, event, payloads):
        rows.append(event)
        return original(current, event, payloads)
    monkeypatch.setattr(events, 'emit_event_batch', observe)
    before = snap(state)
    with pytest.raises(ActionRejected, match='competing graveyard replacement source'):
        finish_mechanic_choice(state, seat, chosen(victims))
    assert snap(state) == before and rows == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_selected_humility_departure_preserves_suppressed_preflight_destination(seat, name):
    state, victims, _ = batch_position(seat, [name, 'Humility'])
    result = act(state, seat, chosen(victims))
    assert all(result.cards[card.id].zone == Zone.GRAVEYARD for card in victims)
    assert result.cards[victims[0].id].last_known_battlefield['printed_abilities_suppressed']
    assert all(result.cards[card.id].zone_change_sequence == card.zone_change_sequence + 1 for card in victims)


@pytest.mark.parametrize('seat', [1, 2])
def test_trigger_order_continuation_does_not_repeat_sacrifice_or_refund(seat, tmp_path):
    state, victim, source, observers = pending_sacrifice(seat, 'Progenitus', observers=True)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {3-seat}
    mana = deepcopy(state.players[seat].mana_pool)
    result = act(restart(state, tmp_path, 'before-choice'), seat, select(victim))
    result = restart(result, tmp_path, 'before-order')
    assert result.pending_mechanic_choice is None and result.pending_trigger_order is not None
    pending = result.pending_trigger_order
    actor = pending['current_controller']
    group = pending['groups'][str(actor)]
    assert {item['source_card_id'] for item in group} == {observers['Psychogenic Probe'], observers["Cosi's Trickster"]}
    result = act(result, actor, {'type': 'choose_trigger_order', 'trigger_order': [item['_choice_id'] for item in reversed(group)]})
    assert result.cards[victim.id].zone == Zone.LIBRARY and result.players[victim.owner].library.count(victim.id) == 1
    assert result.cards[victim.id].zone_change_sequence == victim.zone_change_sequence + 1
    assert result.players[seat].mana_pool == mana and result.cards[source.id].zone == Zone.BATTLEFIELD
    before = snap(result)
    with pytest.raises(ActionRejected): checked_action(result, RulesEngine(), seat, select(victim))
    assert snap(result) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_http_batch_actual_static_receipts_and_cold_restore(repo, client, seat, foreign, tmp_path):
    state, victims, _ = batch_position(seat, SELF, foreign)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    controller = install(repo, client, state)
    before = snap(state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    rejected = client.post('/matches/' + state.id + '/action', json={
        'player_id': 3-seat, 'action': chosen(victims)})
    assert rejected.status_code == 422
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before
    response = client.post('/matches/' + state.id + '/action', json={
        'player_id': seat, 'action': chosen(victims)})
    assert response.status_code == 200, response.text
    controller = public_private_restore(repo, client, controller, seat, tmp_path)
    assert all(controller.state.cards[card.id].zone == Zone.LIBRARY for card in victims)
    assert sum(item.source_card_id == probe.id for item in controller.state.stack) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_http_competing_batch_rejection_keeps_root_controller_sql(repo, client, seat, name):
    state, victims, _ = batch_position(seat, ['Doomed Traveler', 'Rest in Peace', name])
    controller = install(repo, client, state)
    before = snap(state), deepcopy(main_controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat, 'action': chosen(victims)})
    assert response.status_code == 422, response.text
    assert 'competing graveyard replacement source' in response.json()['detail']['message']
    assert (snap(controller.state), main_controller_snapshot(controller), sql_facts(repo)) == before


def test_only_authorized_sacrifice_slice_changes():
    import ast
    import hashlib
    root = Path(__file__).parents[2]
    before = json.loads((Path(__file__).parent / 'fixtures/keyword_graveyard_plans/preimage.json').read_text())
    current = (root / 'backend/rules_engine/keyword_actions.py').read_text()
    after = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
             for node in ast.parse(current).body if isinstance(node, ast.FunctionDef) and node.name != 'finish_mechanic_choice'}
    assert before['other_functions'] == after
    prefix = '    events = [{"card_id": cid, "controller": player_id} for cid in ids]\n'
    suffix = '    emit_event_batch(state, "sacrifice", events)\n'
    assert before['prefix_sha256'] == hashlib.sha256(current.split(prefix)[0].encode()).hexdigest()
    assert before['suffix_sha256'] == hashlib.sha256(current.split(suffix)[1].encode()).hexdigest()
