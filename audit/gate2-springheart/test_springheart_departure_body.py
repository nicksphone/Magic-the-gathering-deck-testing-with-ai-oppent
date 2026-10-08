"""Strict native departure responses; no fabricated frames or attachment changes."""
import hashlib
import json
from pathlib import Path

import pytest
import domain_paid_support as g
import test_springheart_paid_body as original
from free_owner_support import fund
from game_state.state import Zone, object_incarnation
from rules_engine.engine import RulesEngine
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected


@pytest.fixture(scope='module')
def edge_facts():
    here = Path(__file__).resolve().parent / 'fixtures/edges'
    facts = json.loads((here / 'canonical.json').read_bytes())
    proof = json.loads((here / 'provenance.json').read_bytes())
    for name, raw in facts.items():
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True,
            separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        assert digest == proof['cards'][name]['canonical_fullrow_sha256']
    return facts


def response_position(facts, seat, request):
    state = g.position(facts, seat)
    # Canonical starting host is a declared fixture, not a paid-cast claim.
    host = g.add(state, facts, 'Hopeful Eidolon', seat, Zone.BATTLEFIELD)
    source = g.add(state, facts, 'Springheart Nantuko', seat, Zone.HAND)
    land = g.add(state, facts, 'Forest', seat, Zone.HAND)
    fund(state, seat, G=2)
    state = original.announced(request, state, source, host, seat, 'bestow')
    return state, source, host, land


def native_land_frame(state, seat, land, request):
    state = g.respond(state, seat)
    state = g.act(state, seat, 'play_land', card_id=land)
    frames = [item for item in state.stack
              if item.payload.get('__trigger_event') == 'enters_battlefield']
    assert len(frames) == 1
    assert not state.pending_trigger_order and not state.pending_mechanic_choice
    original.record(request, state, 'native-land-before-response', actual_frame_id=frames[0].id)
    return state, frames[0].id


def resolve_response_only(state, responder, card, targets, request):
    state = g.respond(state, responder)
    state = g.act(state, responder, 'cast_spell', card_id=card, targets=targets)
    response = next(item for item in state.stack if item.source_card_id == card)
    original.record(request, state, 'real-paid-response', response_frame_id=response.id)
    assert response.payload['mana_spent'] in (1, 2)
    for _ in range(16):
        if not any(item.id == response.id for item in state.stack):
            original.record(request, state, 'response-complete')
            return state
        assert not state.pending_trigger_order and not state.pending_mechanic_choice
        state = g.act(state, state.priority_player, 'pass_priority')
    raise AssertionError('Native response did not finish within bounded public passes')


def reach_payment(state, request):
    for _ in range(16):
        if state.pending_trigger_order or not state.stack:
            original.record(request, state, 'actual-postdeparture-payment')
            return state
        assert not state.pending_mechanic_choice
        state = g.act(state, state.priority_player, 'pass_priority')
    raise AssertionError('Native retained trigger did not publish or finish')


def owned_tokens(state, seat):
    return [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('pay', [False, True])
def test_simultaneous_source_and_host_departure_retains_complete_body(edge_facts, seat, restore, pay, request):
    state, source, host, land = response_position(edge_facts, seat, request)
    responder = 3 - seat
    spell = g.add(state, edge_facts, 'Back to Nature', responder, Zone.HAND)
    fund(state, seat, G=2)
    fund(state, responder, G=2)
    old_source = [object_incarnation(state.cards[source]), state.cards[source].zone_change_sequence]
    old_host = [object_incarnation(state.cards[host]), state.cards[host].zone_change_sequence]
    state, frame_id = native_land_frame(state, seat, land, request)
    state = resolve_response_only(state, responder, spell, {}, request)
    assert state.cards[source].zone == state.cards[host].zone == Zone.GRAVEYARD
    assert state.cards[source].attached_to is None
    frame = next(item for item in state.stack if item.id == frame_id)
    original.record(request, state, 'strict-simultaneous-departure',
                    actual_source_lki=frame.payload.get('__source_lki'),
                    old_source_reference=old_source, old_host_reference=old_host)
    state = reach_payment(g.restore(state) if restore else state, request)
    before = sum(state.players[seat].mana_pool.values())
    state = original.choice(request, state, seat, pay)
    state = original.finish(g.restore(state) if restore else state)
    tokens = owned_tokens(state, seat)
    original.record(request, state, 'strict-departed-terminal')
    assert len(tokens) == 1
    token = tokens[0]
    if pay:
        assert token.name == edge_facts['Hopeful Eidolon']['name']
        assert token.oracle_text == edge_facts['Hopeful Eidolon']['oracle_text']
        assert token.mana_cost == edge_facts['Hopeful Eidolon']['mana_cost']
        assert token.power == token.toughness == 1
        assert sum(state.players[seat].mana_pool.values()) == before - 2
    else:
        assert 'Insect' in token.type_line
        assert token.power == token.toughness == 1 and token.colors == ['G']
        assert sum(state.players[seat].mana_pool.values()) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_source_only_departure_keeps_original_host_copy(edge_facts, seat, restore, request):
    state, source, host, land = response_position(edge_facts, seat, request)
    responder = 3 - seat
    spell = g.add(state, edge_facts, 'Naturalize', responder, Zone.HAND)
    fund(state, seat, G=2)
    fund(state, responder, G=2)
    state, frame_id = native_land_frame(state, seat, land, request)
    state = resolve_response_only(state, responder, spell, {'target_card_id': source}, request)
    assert state.cards[source].zone == Zone.GRAVEYARD and state.cards[host].zone == Zone.BATTLEFIELD
    assert any(item.id == frame_id for item in state.stack)
    state = reach_payment(g.restore(state) if restore else state, request)
    before = sum(state.players[seat].mana_pool.values())
    state = original.choice(request, state, seat, True)
    state = original.finish(g.restore(state) if restore else state)
    tokens = owned_tokens(state, seat)
    original.record(request, state, 'source-only-terminal')
    assert len(tokens) == 1 and tokens[0].name == edge_facts['Hopeful Eidolon']['name']
    assert tokens[0].power == tokens[0].toughness == 1
    assert sum(state.players[seat].mana_pool.values()) == before - 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_live_source_host_blink_does_not_copy_new_incarnation(edge_facts, seat, restore, request):
    state, source, host, land = response_position(edge_facts, seat, request)
    spell = g.add(state, edge_facts, 'Cloudshift', seat, Zone.HAND)
    fund(state, seat, W=1, G=2)
    old_host = [object_incarnation(state.cards[host]), state.cards[host].zone_change_sequence]
    state, _ = native_land_frame(state, seat, land, request)
    state = resolve_response_only(state, seat, spell, {'target_card_id': host}, request)
    assert state.cards[source].zone == state.cards[host].zone == Zone.BATTLEFIELD
    assert state.cards[source].attached_to is None
    assert [object_incarnation(state.cards[host]), state.cards[host].zone_change_sequence] != old_host
    before = sum(state.players[seat].mana_pool.values())
    state = reach_payment(g.restore(state) if restore else state, request)
    assert not state.pending_trigger_order
    state = original.finish(state)
    tokens = owned_tokens(state, seat)
    original.record(request, state, 'host-blink-terminal', old_host_reference=old_host)
    assert len(tokens) == 1 and 'Insect' in tokens[0].type_line
    assert sum(state.players[seat].mana_pool.values()) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_conditional_resolution_payment_underfunded_accept_rejects_atomically(edge_facts, seat, restore, request):
    state, _, _, land = response_position(edge_facts, seat, request)
    fund(state, seat)
    state, _ = native_land_frame(state, seat, land, request)
    state = reach_payment(g.restore(state) if restore else state, request)
    moves = original.actual_choices(request, state, seat)
    assert any(move.get('accept') is False for move in moves)
    assert not any(move.get('accept') is True for move in moves)
    decline = next(move for move in moves if move.get('accept') is False)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {**decline, 'accept': True})
    assert serialize_match_snapshot(state) == before
    original.record(request, state, 'conditional-underpayment-atomic', complete_root_equal=True)
    state = checked_action(state, RulesEngine(), seat, decline)
    state = original.finish(state)
    tokens = owned_tokens(state, seat)
    assert len(tokens) == 1 and 'Insect' in tokens[0].type_line
