"""Complete public devotion entry bodies must precede fixed-count drain guards."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.events import _trigger_from_oracle
from rules_engine.oracle_text import without_reminder_text
from tests.test_typed_resource_sacrifice_costs import act, facts, resolve


RAW = (Path(__file__).parent / 'fixtures/devotion.json').read_bytes()
assert hashlib.sha256(RAW).hexdigest() == 'c12906916aed6662491763195a619e12839cb65f6dc13462a44c24f22be0d59e'
ROWS = {row['name']: row for row in json.loads(RAW)}
NEGATIVES = ['plain_suffix', 'parenthetical_suffix', 'conditional_suffix',
             'unbound_x', 'conditional_x', 'wrong_reminder']


def board(seat, zone=Zone.HAND):
    deck = [dict(deepcopy(ROWS[name]), card_name=name, quantity=1)
            for name in ['Gray Merchant of Asphodel', 'Burning-Tree Emissary']]
    deck.append({'card_name': 'Swamp', 'quantity': 58})
    state = MatchFactory.from_decks(deck, deck, seed=371)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        player.hand.clear()
        player.library.clear()
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    for card in state.cards.values():
        card.move_to_zone(Zone.LIBRARY)
        state.players[card.owner].library.append(card.id)
    source = next(card for card in state.cards.values()
                  if card.owner == seat and card.name == 'Gray Merchant of Asphodel')
    emissary = next(card for card in state.cards.values()
                   if card.owner == seat and card.name == 'Burning-Tree Emissary')
    for card, target_zone in [(source, zone), (emissary, Zone.BATTLEFIELD)]:
        state.players[seat].library.remove(card.id)
        card.move_to_zone(target_zone)
        getattr(state.players[seat], target_zone.value).append(card.id)
        if target_zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, card.id)
    assert source.oracle_text == ROWS[source.name]['oracle_text']
    assert source.card_faces == list(ROWS[source.name].get('card_faces') or [])
    return state, source.id, emissary.id


def negative_text(variant):
    raw = ROWS['Gray Merchant of Asphodel']['oracle_text']
    if variant == 'unbound_x':
        return 'When this creature enters, each opponent loses X life and you gain X life.'
    if variant == 'conditional_x':
        return raw.replace('where X is your devotion to black.',
                           'where X is your devotion to black if you control a Swamp.')
    return raw + {
        'plain_suffix': ' Draw a card.',
        'parenthetical_suffix': ' (Draw a card.)',
        'conditional_suffix': ' If you control a Swamp, draw a card.',
        'wrong_reminder': ' (Each {R} in the mana costs of permanents you control counts toward your devotion to red.)',
    }[variant]


def compile_entry(state, source_id, raw, entering):
    before = facts(state)
    source = state.cards[source_id]
    result = _trigger_from_oracle(
        state, source_id, source.controller, without_reminder_text(raw).lower(),
        'Public complete devotion entry', 'enters_battlefield', {'card_id': entering},
        raw_entry_oracle=raw,
    )
    assert facts(state) == before
    return result


def paid_entry(state, source_id):
    seat = state.cards[source_id].controller
    state.players[seat].mana_pool.update(B=2, C=3)
    before = facts(state)
    paid = act(state, seat, {'type': 'cast_spell', 'card_id': source_id, 'targets': {}})
    assert len(paid.stack) == 1
    assert paid.stack[-1].source_card_id == source_id and paid.stack[-1].controller == seat
    assert not any(paid.players[seat].mana_pool.values())
    for _ in range(2):
        paid = act(paid, paid.priority_player, {'type': 'pass_priority'})
    assert paid.cards[source_id].zone == Zone.BATTLEFIELD
    assert len(paid.stack) == 1
    assert facts(state) == before
    return paid


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_raw_canonical_devotion_dispatch_has_live_resource_semantics(seat):
    state, source_id, _ = board(seat, Zone.BATTLEFIELD)
    spec = compile_entry(state, source_id, state.cards[source_id].oracle_text, source_id)
    assert spec['source_card_id'] == source_id and spec['controller'] == seat
    assert spec['effect_key'] == 'devotion_effect'
    assert spec['payload'] == {'devotion': {'kind': 'drain', 'colors': ['B']},
                               'source_incarnation': object_incarnation(state.cards[source_id])}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_full_canonical_paid_devotion_entry_resolves_and_preserves_real_frame(seat, restore):
    state, source_id, _ = board(seat)
    paid = paid_entry(state, source_id)
    trigger = paid.stack[-1]
    assert trigger.source_card_id == source_id and trigger.controller == seat
    assert trigger.effect_key == 'devotion_effect'
    assert trigger.payload['devotion'] == {'kind': 'drain', 'colors': ['B']}
    assert trigger.payload['source_incarnation'] == object_incarnation(paid.cards[source_id])
    if restore:
        frame = deepcopy(trigger)
        paid = deserialize_match_snapshot(serialize_match_snapshot(paid))
        assert paid.stack[-1] == frame
    resolved = resolve(paid)
    assert (resolved.players[seat].life, resolved.players[3-seat].life) == (22, 18)
    assert resolved.cards[source_id].oracle_text == ROWS['Gray Merchant of Asphodel']['oracle_text']
    assert not resolved.stack and not resolved.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', NEGATIVES)
def test_incomplete_raw_devotion_or_arbitrary_x_body_never_compiles_partial_reward(seat, variant):
    state, source_id, _ = board(seat, Zone.BATTLEFIELD)
    text = negative_text(variant)  # Explicit adversarial metadata, not canonical Oracle.
    spec = compile_entry(state, source_id, text, source_id)
    assert spec['effect_key'] == 'noop'
    assert spec['payload']['__unsupported_trigger_instruction'] == text
    assert state.cards[source_id].oracle_text == ROWS['Gray Merchant of Asphodel']['oracle_text']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', NEGATIVES)
def test_adversarial_complete_body_native_paid_entry_never_rewards_life_or_draw(seat, variant):
    state, source_id, _ = board(seat)
    text = negative_text(variant)
    state.cards[source_id].oracle_text = text
    paid = paid_entry(state, source_id)
    trigger = paid.stack[-1]
    assert trigger.source_card_id == source_id and trigger.controller == seat
    assert trigger.effect_key == 'noop'
    assert trigger.payload['__unsupported_trigger_instruction'] == text
    hands = {pid: list(player.hand) for pid, player in paid.players.items()}
    libraries = {pid: list(player.library) for pid, player in paid.players.items()}
    resolved = resolve(paid)
    assert (resolved.players[seat].life, resolved.players[3-seat].life) == (20, 20)
    assert {pid: player.hand for pid, player in resolved.players.items()} == hands
    assert {pid: player.library for pid, player in resolved.players.items()} == libraries
    assert resolved.cards[source_id].oracle_text == text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('wrong', [None, 'emissary'])
def test_complete_devotion_body_does_not_infer_a_missing_or_other_entry_source(seat, wrong):
    state, source_id, emissary_id = board(seat, Zone.BATTLEFIELD)
    assert compile_entry(state, source_id, state.cards[source_id].oracle_text,
                         emissary_id if wrong else None) is None
