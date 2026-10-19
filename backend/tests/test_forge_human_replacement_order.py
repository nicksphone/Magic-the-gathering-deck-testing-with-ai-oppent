"""Desired human ordering, using receipts from real paid canonical Salves.

Established-board/resource poses are explicit. No receipt, pending frame,
StackItem, event, or object identity is manufactured by this module.
"""
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.oracle_effects import inspect_target_hints
from rules_engine.replacement import replacement_options
from tests.library_canonical_fixtures import raw_card
from tests.mana_canonical_76 import entry
from tests.test_forge_negative_life_diagnostic import canonical_entry, cast_action
from tests.test_linked_mana_damage import request


FIXTURES = Path(__file__).parent / 'fixtures'


def card_entry(raw, quantity):
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': raw['name'], 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def salve_entry():
    blob = (FIXTURES / 'soulscar_protection_boundaries/healing-salve.json').read_bytes()
    assert hashlib.sha256(blob).hexdigest() == (
        'bbb9f8e419f944cdab82ddf9eec451ad0b24d138d3d80554128ddbbfdc0d0325')
    raw = json.loads(blob)
    assert raw['object'] == 'card' and raw['name'] == 'Healing Salve'
    return card_entry(raw, 2)


def fingerprint(state):
    payload = json.dumps(serialize_match_snapshot(state), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def act(state, seat, action):
    before = fingerprint(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert fingerprint(state) == before
    return result


def restore(state):
    before = fingerprint(state)
    result = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert fingerprint(result) == before and fingerprint(state) == before
    return result


def finish_stack(state):
    for _ in range(8):
        if state.pending_replacement_choice or state.pending_mechanic_choice or not state.stack:
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Existing canonical fixture exceeded bounded stack completion')


def setup(seat):
    deck = [entry('Battlefield Forge', 8), salve_entry(),
            canonical_entry('Wrath of God'), card_entry(raw_card('Lightning Bolt'), 1)]
    state = MatchFactory.from_decks(deck, deck, seed=618)

    def place(card, zone):
        player = state.players[card.owner]
        getattr(player, card.zone.value).remove(card.id)
        card.move_to_zone(zone)
        getattr(player, zone.value).append(card.id)

    forges = [c for c in state.cards.values()
              if c.owner == seat and c.name == 'Battlefield Forge'][:2]
    salves = [c for c in state.cards.values() if c.owner == seat and c.name == 'Healing Salve']
    wrath = next(c for c in state.cards.values() if c.owner == seat and c.name == 'Wrath of God')
    bolt = next(c for c in state.cards.values() if c.owner == 3-seat and c.name == 'Lightning Bolt')
    for card in forges:
        place(card, Zone.BATTLEFIELD)
    for card in [*salves, wrath, bolt]:
        place(card, Zone.HAND)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    # Same flags as one human and one AI match controller; no App import.
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state.players[seat].mana_pool['W'] = 2
    state.players[3-seat].mana_pool['R'] = 1
    frames = []
    for source in salves:
        mode = next(m for m in inspect_target_hints(state, state.cards[source.id], seat)['modes']
                    if m.startswith('Prevent'))
        state = act(state, seat, {'type': 'cast_spell', 'card_id': source.id,
                    'cost_choice': {'id': 'base'},
                    'targets': {'mode_text': mode, 'target_player': seat}})
        frames.append(state.stack[-1].id)
        state = finish_stack(state)
        assert not state.stack and not state.pending_replacement_choice
    receipts = state.numeric_prevention_shields
    assert len(receipts) == 2 and len({r.receipt_id for r in receipts}) == 2
    assert {r.resolving_stack_id for r in receipts} == set(frames)
    assert {r.source_card_id for r in receipts} == {c.id for c in salves}
    assert all(r.source_controller == seat and r.target_player == seat
               and r.target_reference is None and r.remaining == 3 for r in receipts)
    assert all(state.cards[r.source_card_id].zone == Zone.GRAVEYARD
               and state.cards[r.source_card_id].zone_change_sequence
               > r.source_reference['zone_change_sequence'] for r in receipts)
    assert state.players[seat].prevent_damage_shield == 6
    assert state.players[seat].mana_pool['W'] == 0
    assert state.sideboard_facts
    return state, [c.id for c in forges], wrath.id, bolt.id


def balances(state):
    return {r.receipt_id: r.remaining for r in state.numeric_prevention_shields}


def option_ids(state):
    return {'numeric-prevention:' + r.receipt_id for r in state.numeric_prevention_shields}


def choose(state, seat, receipt_id):
    return act(state, seat, {'type': 'choose_replacement',
                            'replacement_source_id': 'numeric-prevention:' + receipt_id})


def assert_initial_choice(state, seat, original_balances):
    pending = state.pending_replacement_choice
    assert pending is not None, 'affected human must choose before either genuine receipt is consumed'
    assert pending['player_id'] == seat and pending['event'] == 'damage_to_player'
    assert {o['source_id'] for o in pending['options']} == option_ids(state)
    assert balances(state) == original_balances
    assert state.players[seat].prevent_damage_shield == 6
    assert state.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_paid_receipts_have_independent_sources_frames_and_restore(seat):
    state, forges, _, _ = setup(seat)
    options = replacement_options(state, 'damage_to_player', target_player=seat,
                                  source_card_id=forges[0], amount=1)
    assert {o['source_id'] for o in options} == option_ids(state)
    assert balances(restore(state)) == balances(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', [0, 1])
def test_existing_checked_bolt_damage_offers_and_consumes_either_real_receipt(seat, selected):
    state, _, _, bolt = setup(seat)
    ids = [r.receipt_id for r in state.numeric_prevention_shields]
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': bolt,
                              'targets': {'target_player': seat}})
    state = finish_stack(state)
    assert_initial_choice(state, seat, {key: 3 for key in ids})
    state = choose(restore(state), seat, ids[selected])
    assert balances(state) == {key: (0 if i == selected else 3) for i, key in enumerate(ids)}
    assert not state.stack and not state.pending_replacement_choice
    assert state.players[seat].life == 20 and state.players[seat].prevent_damage_shield == 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['native', 'legacy', 'bulk'])
@pytest.mark.parametrize('selected', [0, 1])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_single_forge_human_choice_resume_taps_and_produces_exactly_once(
        seat, route, selected, roundtrip):
    state, forges, _, _ = setup(seat)
    original = balances(state)
    ids = list(original)
    source = state.cards[forges[0]]
    result = act(state, seat, request(source, 'W', route))
    assert_initial_choice(result, seat, original)
    assert sum(result.cards[cid].tapped for cid in forges) <= 1
    assert result.players[seat].mana_pool['W'] <= 1
    if roundtrip:
        result = restore(result)
    result = choose(result, seat, ids[selected])
    assert not result.pending_replacement_choice and not result.stack
    assert balances(result) == {key: (2 if i == selected else 3) for i, key in enumerate(ids)}
    assert result.players[seat].prevent_damage_shield == 5 and result.players[seat].life == 20
    assert sum(result.cards[cid].tapped for cid in forges) == 1
    assert result.players[seat].mana_pool['W'] == 1
    before = fingerprint(result)
    with pytest.raises(ActionRejected):
        choose(result, seat, ids[selected])
    assert fingerprint(result) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', [0, 1])
def test_bulk_two_stops_at_each_pending_event_and_resumes_each_source_once(seat, selected):
    state, forges, _, _ = setup(seat)
    original = balances(state)
    ids = list(original)
    action = {**request(state.cards[forges[0]], 'W', 'bulk'), 'count': 2}
    result = act(state, seat, action)
    assert_initial_choice(result, seat, original)
    assert sum(result.cards[cid].tapped for cid in forges) <= 1
    assert result.players[seat].mana_pool['W'] <= 1
    result = choose(restore(result), seat, ids[selected])
    assert result.pending_replacement_choice is not None
    assert balances(result) == {key: (2 if i == selected else 3) for i, key in enumerate(ids)}
    assert result.players[seat].life == 20
    result = choose(restore(result), seat, ids[1-selected])
    assert not result.pending_replacement_choice and not result.stack
    assert balances(result) == {key: 2 for key in ids}
    assert all(result.cards[cid].tapped for cid in forges)
    assert result.players[seat].mana_pool['W'] == 2
    assert result.players[seat].prevent_damage_shield == 4 and result.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', [0, 1])
def test_checked_canonical_autocast_cannot_finish_payment_past_human_choice(seat, selected):
    state, forges, wrath, _ = setup(seat)
    state.players[seat].mana_pool['C'] = 2
    original = balances(state)
    ids = list(original)
    result = act(state, seat, cast_action(state.cards[wrath]))
    assert_initial_choice(result, seat, original)
    assert not result.stack and result.cards[wrath].zone == Zone.HAND
    assert sum(result.cards[cid].tapped for cid in forges) <= 1
    result = choose(restore(result), seat, ids[selected])
    assert result.pending_replacement_choice is not None
    assert not result.stack and result.cards[wrath].zone == Zone.HAND
    assert balances(result) == {key: (2 if i == selected else 3) for i, key in enumerate(ids)}
    result = choose(restore(result), seat, ids[1-selected])
    assert not result.pending_replacement_choice
    assert len(result.stack) == 1 and result.stack[0].source_card_id == wrath
    assert result.cards[wrath].zone == Zone.STACK
    assert balances(result) == {key: 2 for key in ids}
    assert all(result.cards[cid].tapped for cid in forges)
    assert not any(result.players[seat].mana_pool.values())
    assert result.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['native', 'legacy', 'bulk'])
@pytest.mark.parametrize('invalid', ['wrong_seat', 'actual_card_not_a_receipt', 'coherent_stale'])
def test_rejected_pending_choices_keep_root_and_snapshot_resources(seat, route, invalid):
    state, forges, _, _ = setup(seat)
    result = act(state, seat, request(state.cards[forges[0]], 'W', route))
    assert_initial_choice(result, seat, balances(state))
    receipt = result.numeric_prevention_shields[0]
    action = {'type': 'choose_replacement',
              'replacement_source_id': 'numeric-prevention:' + receipt.receipt_id}
    actor = seat
    if invalid == 'wrong_seat':
        actor = 3-seat
    elif invalid == 'actual_card_not_a_receipt':
        action['replacement_source_id'] = receipt.source_card_id
    else:
        # Explicit stale-resource protocol: consume its whole balance coherently,
        # retaining the genuinely queued choice. Not a claimed gameplay episode.
        result.players[seat].prevent_damage_shield -= receipt.remaining
        receipt.remaining = 0
    snapshot = serialize_match_snapshot(result)
    payload_before = json.dumps(snapshot, sort_keys=True)
    before = fingerprint(result)
    with pytest.raises(ActionRejected):
        reloaded = deserialize_match_snapshot(snapshot)
        checked_action(reloaded, RulesEngine(), actor, action)
    assert json.dumps(snapshot, sort_keys=True) == payload_before
    assert fingerprint(result) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_affordability_query_keeps_both_actual_human_receipts_and_rng_unchanged(seat):
    state, _, wrath, _ = setup(seat)
    state.players[seat].mana_pool['C'] = 2
    before = fingerprint(state)
    rng = state.rng.getstate()
    can_pay_with_pool_and_lands(state, seat, state.cards[wrath].mana_cost)
    assert fingerprint(state) == before and state.rng.getstate() == rng
    assert sorted(balances(state).values()) == [3, 3]


@pytest.mark.parametrize('seat', [1, 2])
def test_nonhuman_timestamp_fallback_is_a_separate_configuration_control(seat):
    state, forges, _, _ = setup(seat)
    state.replacement_choice_required = False
    state.replacement_choice_players = set()
    first = max(state.numeric_prevention_shields, key=lambda r: r.effect_timestamp).receipt_id
    result = act(state, seat, request(state.cards[forges[0]], 'W'))
    assert not result.pending_replacement_choice
    assert balances(result) == {r.receipt_id: (2 if r.receipt_id == first else 3)
                                for r in state.numeric_prevention_shields}
    assert result.players[seat].life == 20 and result.players[seat].mana_pool['W'] == 1
