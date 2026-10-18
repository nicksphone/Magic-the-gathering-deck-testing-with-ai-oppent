"""Public canonical checked-cast and payment seams; no spell resolution claim."""
import hashlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from effects import handlers
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands
from rules_engine.prevention import add_player_prevention_shield
from rules_engine.replacement import can_pay_life, player_cant_lose_game
from tests.mana_canonical_76 import entry
from tests.test_linked_mana_damage import request


FIXTURES = Path(__file__).parent / 'fixtures'


def canonical_entry(name):
    if name == 'Platinum Angel':
        blob = (FIXTURES / 'life_conversion/platinum-angel.json').read_bytes()
        assert hashlib.sha256(blob).hexdigest() == (
            '747ff3f591d24373448e75d0dca8512f0315b8b75b2155ff1a68716500d8980b')
        raw = json.loads(blob)
    else:
        assert name == 'Wrath of God'
        blob = (FIXTURES / 'direct_graveyard_audit/canonical.jsonl').read_bytes()
        assert hashlib.sha256(blob).hexdigest() == (
            'fcd7595207c617d47db56754ec09f4dd4a73f31af999af41a275a21a3c3ff76d')
        raw = next(row for row in map(json.loads, blob.splitlines()) if row['name'] == name)
    assert raw['object'] == 'card' and raw['name'] == name
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': name, 'quantity': 1,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def position(seat, *, life=1, forge_count=2, shield=0):
    deck = [entry('Battlefield Forge', 8), canonical_entry('Platinum Angel'),
            canonical_entry('Wrath of God')]
    state = MatchFactory.from_decks(deck, deck, seed=618)
    player = state.players[seat]

    def place(card, zone):
        # Explicit established-board pose, never a recapture or printed rewrite.
        getattr(player, card.zone.value).remove(card.id)
        card.move_to_zone(zone)
        getattr(player, zone.value).append(card.id)

    forges = [card for card in state.cards.values()
              if card.owner == seat and card.name == 'Battlefield Forge'][:forge_count]
    angel = next(card for card in state.cards.values()
                 if card.owner == seat and card.name == 'Platinum Angel')
    spell = next(card for card in state.cards.values()
                 if card.owner == seat and card.name == 'Wrath of God')
    for card in [*forges, angel]:
        place(card, Zone.BATTLEFIELD)
    place(spell, Zone.HAND)
    player.life = life
    player.mana_pool['C'] = 2
    add_player_prevention_shield(state, seat, shield)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    assert spell.mana_cost == '{2}{W}{W}'
    assert player_cant_lose_game(state, seat)
    assert state.sideboard_facts
    return state, forges, angel, spell


def fingerprint(state):
    snapshot = json.dumps(serialize_match_snapshot(state), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(snapshot.encode()).hexdigest()


def cast_action(spell):
    return {'type': 'cast_spell', 'card_id': spell.id, 'cost_choice': {'id': 'base'}}


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_canonical_cast_can_use_two_forges_below_zero_with_angel(seat):
    state, forges, angel, spell = position(seat)
    before = fingerprint(state)
    result = checked_action(state, RulesEngine(), seat, cast_action(spell))
    assert result.players[seat].life == -1
    assert all(result.cards[card.id].tapped for card in forges)
    assert result.cards[angel.id].zone == Zone.BATTLEFIELD
    assert result.cards[spell.id].zone == Zone.STACK
    assert len(result.stack) == 1 and result.stack[0].source_card_id == spell.id
    assert result.winner is None
    assert fingerprint(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_manual_mana_then_same_cast_is_an_available_native_control(seat):
    state, forges, angel, spell = position(seat)
    before = fingerprint(state)
    current = state
    for expected_life, source in zip((0, -1), forges):
        current = checked_action(current, RulesEngine(), seat, request(source, 'W'))
        assert current.players[seat].life == expected_life
        assert current.winner is None and player_cant_lose_game(current, seat)
    result = checked_action(current, RulesEngine(), seat, cast_action(spell))
    assert result.players[seat].life == -1
    assert result.cards[angel.id].zone == Zone.BATTLEFIELD
    assert result.cards[spell.id].zone == Zone.STACK
    assert len(result.stack) == 1 and result.winner is None
    assert fingerprint(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_direct_preflight_observes_real_negative_damage_without_reservation(
        seat, monkeypatch, record_property):
    state, forges, _, spell = position(seat)
    before = fingerprint(state)
    rng_before = state.rng.getstate()
    transitions = []
    original = handlers.deal_damage

    def observe(current, actor, params):
        old_life = current.players[seat].life
        result = original(current, actor, params)
        transitions.append((old_life, current.players[seat].life))
        return result

    monkeypatch.setattr(handlers, 'deal_damage', observe)
    allowed = can_pay_with_pool_and_lands(state, seat, spell.mana_cost)
    assert (1, 0) in transitions and (0, -1) in transitions
    assert fingerprint(state) == before and state.rng.getstate() == rng_before
    assert all(not source.tapped for source in forges)
    record_property('observed_real_trial_life_minus_one', True)
    record_property('protected_life', 0)
    assert allowed, 'zero life reservation must not impose a zero-life floor'


@pytest.mark.parametrize('seat', [1, 2])
def test_direct_payment_without_reservation_can_commit_two_real_damage_events(seat):
    state, forges, _, spell = position(seat)
    assert auto_pay_cost(state, seat, spell.mana_cost)
    assert state.players[seat].life == -1
    assert all(card.tapped for card in forges)
    assert not any(state.players[seat].mana_pool.values())
    assert not state.stack and state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_life_payment_and_already_funded_cost_have_no_negative_life_floor(seat):
    state, forges, _, spell = position(seat, life=-1)
    state.players[seat].mana_pool['W'] = 2
    assert can_pay_life(state, seat, 0)
    assert not can_pay_life(state, seat, 1)
    assert can_pay_with_pool_and_lands(state, seat, spell.mana_cost)
    assert auto_pay_cost(state, seat, spell.mana_cost)
    assert state.players[seat].life == -1
    assert all(not card.tapped for card in forges)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life,held,shield,count,cost,allowed,after_life', [
    (2, 1, 0, 2, '{2}{W}{W}', False, 2),
    (3, 1, 0, 2, '{2}{W}{W}', True, 1),
    (1, 1, 2, 2, '{2}{W}{W}', True, 1),
    (1, 0, 0, 1, '{W}', True, 0),
])
def test_positive_reservation_prevention_and_single_forge_controls(
        seat, life, held, shield, count, cost, allowed, after_life):
    state, forges, _, _ = position(seat, life=life, forge_count=count, shield=shield)
    before = fingerprint(state)
    assert can_pay_with_pool_and_lands(state, seat, cost, protected_life=held) is allowed
    assert fingerprint(state) == before
    assert auto_pay_cost(state, seat, cost, protected_life=held) is allowed
    assert state.players[seat].life == after_life
    if allowed:
        assert all(card.tapped for card in forges)
    else:
        assert fingerprint(state) == before
