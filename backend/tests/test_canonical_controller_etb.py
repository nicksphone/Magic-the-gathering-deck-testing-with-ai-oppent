"""Actual fixture consumption and full native facts for controller-only entry."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.copiable_values import PHYSICAL
from rules_engine.events import emit_event as native_emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_events_apnap as original
from tests.rules_printed_facts_e4 import raw_card


BUNDLE = Path(__file__).parent / 'fixtures/entry_observers_S2/canonical.jsonl'
WITNESS_COUNTS = dict(native_reference_births=0, original_event_boundaries=0,
                      canonical_boundary_checks=0, native_helper_printed_matches=0,
                      foreign_rejection_cases=0, own_reward_cases=0, serde_roundtrips=0)


def raw_observer():
    encoded = BUNDLE.read_bytes()
    assert sha256(encoded).hexdigest() == '8f337660b08660748a0b47d9590a40e106303e578bff37277bbda05dd89018ba'
    raw = json.loads(encoded.splitlines()[1])
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id'], len(raw)) == (
        'card', "Ajani's Welcome", 'c9045fcb-b633-4c35-8058-6234311551ae',
        '4a782bf9-4051-4613-8852-33b0d85a0edd', 63)
    assert sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == '141ed7e918fa87c9c22ab6213a865acf4de0bc800f16b518cc2765c689cb589c'
    return raw


def entry(raw, quantity):
    normalized = ScryfallSyncService._normalize_payload(raw, 'unused:controller-native-reference')
    return {**raw, **normalized, 'card_name': raw['name'], 'quantity': quantity,
            'image_uri': None, 'colors': deepcopy(raw.get('colors', [])),
            'card_faces': deepcopy(raw.get('card_faces', []))}


def printed(card):
    return ({key: deepcopy(getattr(card, key)) for key in PHYSICAL},
            deepcopy(card.characteristic_record), deepcopy(card.printed_characteristics))


def test_original_controller_scope_fixture_consumes_full_native_observer(monkeypatch):
    reference = MatchFactory.from_decks([entry(raw_observer(), 8)], [], seed=0)
    expected = next(card for card in reference.cards.values() if card.zone == Zone.LIBRARY)
    WITNESS_COUNTS['native_reference_births'] += 1
    seen = []
    assert original.emit_event is native_emit_event

    def observe(state, event, payload):
        # Test-owned controlled fixture data; instrumentation never traverses it.
        subject = state.cards['p1']
        WITNESS_COUNTS['original_event_boundaries'] += 1
        assert subject.name == expected.name, 'Canonical controller observer missing at original event boundary'
        assert printed(subject) == printed(expected), 'Original fixture lacks full native printed facts'
        assert (subject.id, subject.owner, subject.controller, subject.zone) == ('p1', 1, 1, Zone.BATTLEFIELD)
        WITNESS_COUNTS['canonical_boundary_checks'] += 1
        seen.append(event)
        return native_emit_event(state, event, payload)

    with monkeypatch.context() as patch:
        patch.setattr(original, 'emit_event', observe)
        original.test_controller_scoped_etb_trigger_does_not_fire_for_opponent_creature()
    assert seen == ['enters_battlefield']
    assert original.emit_event is native_emit_event


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_controller_observer_has_own_entry_reward_and_no_foreign_reward(seat):
    island = raw_card('Island')
    creature = raw_card('Llanowar Elves')
    own = [entry(island, 58), entry(raw_observer(), 1), entry(creature, 1)]
    enemy = [entry(island, 59), entry(creature, 1)]
    state = MatchFactory.from_decks(own if seat == 1 else enemy, enemy if seat == 1 else own, seed=301)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    native_subject = next(card for card in state.cards.values() if card.owner == seat and card.name == raw_observer()['name'])
    subject = original._controller_etb_card(seat, identifier=native_subject.id)
    assert printed(subject) == printed(native_subject)
    WITNESS_COUNTS['native_helper_printed_matches'] += 1

    def place(card):
        player = state.players[card.owner]
        getattr(player, card.zone.value).remove(card.id)
        card.move_to_zone(Zone.BATTLEFIELD)
        player.battlefield.append(card.id)

    place(native_subject)
    state.cards[subject.id] = subject
    entrants = {player: next(card for card in state.cards.values()
                             if card.owner == player and card.name == creature['name'])
                for player in (1, 2)}
    for card in entrants.values():
        place(card)
    snapshot = serialize_match_snapshot(state)
    state = deserialize_match_snapshot(snapshot)
    assert serialize_match_snapshot(state) == snapshot
    WITNESS_COUNTS['serde_roundtrips'] += 1
    before_printed = printed(state.cards[subject.id])
    before_life = {player: state.players[player].life for player in (1, 2)}
    native_emit_event(state, 'enters_battlefield', {'card_id': entrants[3-seat].id, 'controller': 3-seat})
    assert not state.stack
    WITNESS_COUNTS['foreign_rejection_cases'] += 1
    native_emit_event(state, 'enters_battlefield', {'card_id': entrants[seat].id, 'controller': seat})
    assert len(state.stack) == 1
    assert (state.stack[0].source_card_id, state.stack[0].controller) == (subject.id, seat)
    assert resolve_top_of_stack(state)
    assert not state.stack
    assert state.players[seat].life == before_life[seat] + 1
    assert state.players[3-seat].life == before_life[3-seat]
    assert printed(state.cards[subject.id]) == before_printed
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert printed(restored.cards[subject.id]) == before_printed
    assert restored.players[seat].life == before_life[seat] + 1
    WITNESS_COUNTS['serde_roundtrips'] += 1
    WITNESS_COUNTS['own_reward_cases'] += 1
