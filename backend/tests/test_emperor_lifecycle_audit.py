"""Paid canonical lifecycle audit; no production edits or injected frames."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
import test_brainstorm_desired as brain
from test_emperor_timing_audit import ROWS


FIXTURES = Path(__file__).parent / 'fixtures'
FLICKER = json.loads((FIXTURES / 'canonical_land_animation_audit/flicker.json').read_text())
FLASH_ROOT = FIXTURES / 'global_flash_timing_audit'
FLASH_ROWS = {}
for entry in json.loads((FLASH_ROOT / 'provenance.json').read_text())['cards']:
    if entry['name'] in {'Leyline of Anticipation', 'Jace Beleren'}:
        raw = (FLASH_ROOT / entry['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        FLASH_ROWS[entry['name']] = json.loads(raw)


def add_raw(state, row, seat):
    sample = MatchFactory.from_decks([{**row, 'card_name': row['name'], 'quantity': 1}], [], seed=4)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    assert card.oracle_text == row['oracle_text']
    return card.id


def setup(seat):
    state = brain.position(seat)
    # Declared starting libraries before any paid action; avoid empty-deck loss.
    for player in (1, 2):
        while len(state.players[player].library) < 20:
            brain.add(state, 'Forest', player, Zone.LIBRARY)
    emperor = add_raw(state, ROWS['The Wandering Emperor'], seat)
    flicker = add_raw(state, FLICKER, seat)
    return state, emperor, flicker


def resolve_cast(state, seat, source, pool, targets=None):
    state, frame = brain.cast(state, seat, source, pool, targets)
    assert next(item for item in state.stack if item.id == frame).payload['mana_spent'] == sum(pool.values())
    return brain.advance(state, lambda s: all(item.id != frame for item in s.stack))


def priority(state, seat):
    return brain.advance(state, lambda s: s.priority_player == seat)


def loyalty_action(source):
    return {'type': 'activate_loyalty', 'card_id': source, 'ability_index': 1, 'targets': {}}


def offered(state, seat, source):
    return any(move['type'] == 'activate_loyalty' and move.get('card_id') == source
               and move.get('ability_index') == 1 for move in brain.RULES.legal_moves(state, seat))


def token_activation(state, seat, source):
    state = priority(state, seat)
    before = set(state.players[seat].battlefield)
    old_loyalty = state.cards[source].loyalty
    state = brain.act(state, seat, loyalty_action(source))
    assert state.cards[source].loyalty == old_loyalty - 1
    frame = next(item.id for item in state.stack if item.source_card_id == source)
    state = brain.advance(state, lambda s: all(item.id != frame for item in s.stack))
    tokens = set(state.players[seat].battlefield) - before
    assert len(tokens) == 1
    token = state.cards[next(iter(tokens))]
    assert token.power == token.toughness == 2
    assert 'vigilance' in {keyword.lower() for keyword in token.keywords}
    return state


def atomic_reject(state, seat, source):
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        brain.act(state, seat, loyalty_action(source))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_same_incarnation_second_loyalty_is_atomic_reject(seat, restore):
    state, source, _ = setup(seat)
    state = resolve_cast(state, seat, source, {'W': 4})
    state = token_activation(state, seat, source)
    state = priority(brain.cold(state) if restore else state, seat)
    assert not offered(state, seat, source)
    atomic_reject(state, seat, source)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_paid_flicker_new_incarnation_can_activate_again(seat, restore):
    state, source, flicker = setup(seat)
    state = resolve_cast(state, seat, source, {'W': 4})
    state = token_activation(state, seat, source)
    state = priority(state, seat)
    incarnation = object_incarnation(state.cards[source])
    sequence = state.cards[source].zone_change_sequence
    turn = state.turn
    state = resolve_cast(state, seat, flicker, {'C': 1, 'W': 1}, {'target_card_id': source})
    card = state.cards[source]
    assert state.cards[flicker].zone == Zone.GRAVEYARD
    assert card.zone == Zone.BATTLEFIELD and card.owner == card.controller == seat
    assert object_incarnation(card) != incarnation and card.zone_change_sequence == sequence + 2
    assert state.turn == turn and card.entered_turn == turn and card.loyalty == 3
    state = priority(brain.cold(state) if restore else state, seat)
    print('REAL_PAID_FLICKER', json.dumps({'seat': seat, 'restore': restore, 'turn': turn,
          'old_incarnation': incarnation, 'new_incarnation': object_incarnation(card),
          'sequence': sequence, 'new_sequence': card.zone_change_sequence,
          'retained_used_ids': sorted(state.loyalty_activated_this_turn)}))
    assert offered(state, seat, source), 'new BF incarnation must have its own once-per-turn eligibility'
    state = token_activation(state, seat, source)
    state = priority(state, seat)
    assert not offered(state, seat, source)
    atomic_reject(state, seat, source)
    brain.cold(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_natural_next_turn_expires_entry_permission(seat, restore):
    state, source, _ = setup(seat)
    state = resolve_cast(state, seat, source, {'W': 4})
    entered = state.cards[source].entered_turn
    # No loyalty activation: rejection below must prove expiry, not a used guard.
    for _ in range(160):
        if state.turn > entered and state.step == Step.UPKEEP:
            break
        state = brain.act(state, state.priority_player, {'type': 'pass_priority'})
        assert state.winner is None
    else:
        raise AssertionError('natural next-turn upkeep bound exceeded')
    assert state.active_player == 3 - seat and state.cards[source].entered_turn == entered
    state = priority(brain.cold(state) if restore else state, seat)
    assert source not in state.loyalty_activated_this_turn
    assert not offered(state, seat, source)
    atomic_reject(state, seat, source)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_paid_global_casting_flash_does_not_grant_loyalty_timing(seat, restore):
    state, _, _ = setup(seat)
    leyline = add_raw(state, FLASH_ROWS['Leyline of Anticipation'], seat)
    jace = add_raw(state, FLASH_ROWS['Jace Beleren'], seat)
    instant = brain.add(state, 'Brainstorm', seat, Zone.HAND)
    state = resolve_cast(state, seat, leyline, {'U': 4})
    state = priority(state, seat)
    state = resolve_cast(state, seat, jace, {'U': 3})
    state = priority(state, seat)
    state, frame = brain.cast(state, seat, instant, {'U': 1})
    state = brain.cold(state) if restore else state
    assert any(item.id == frame for item in state.stack)
    assert state.cards[leyline].zone == state.cards[jace].zone == Zone.BATTLEFIELD
    assert not offered(state, seat, jace)
    atomic_reject(state, seat, jace)
