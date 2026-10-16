"""Full-RAW fixture births and actual original consumer-boundary fidelity.

Controlled stock declarations remain the original template, not a certified
canonical deck or a waiver of literal Task 1.3 scope.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.copiable_values import PHYSICAL


TESTS = Path(__file__).parent
SOURCES = TESTS / 'fixtures/same_kind_modal_db4e/SOURCES.json'
SOURCES_SHA = 'cdb331d95b13b531cbab5ef1a454127871a25671c1fa0d8c7858c0a8e7aa7b96'
DISPLAY = 'fixture:same-kind-modal-db4e'


def raw_card(name):
    proof = SOURCES.read_bytes()
    assert hashlib.sha256(proof).hexdigest() == SOURCES_SHA
    record = json.loads(proof)['records'][name]
    data = (TESTS / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    rows = ([json.loads(line) for line in data.splitlines()]
            if record['format'] == 'jsonl' else [json.loads(data)])
    matches = [row for row in rows if row.get('name') == name]
    assert len(matches) == 1
    raw = matches[0]
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == record['object_sha256']
    assert raw['object'] == 'card' and raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def entry(name, quantity):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(raw, DISPLAY)
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def materialize(card_id, name, owner, controller, zone, *, instance_order=0, summoning_sick=True):
    sample = MatchFactory.from_decks([entry(name, 8)], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(deepcopy(template), id=card_id, owner=owner, controller=controller,
                   zone=zone, instance_order=instance_order, summoning_sick=summoning_sick)


def canonicalize_controlled_basics(state):
    """Replace only runtime cards; retain original stock, IDs, positions and RNG."""
    stock = entry('Island', 60)
    sample = MatchFactory.from_decks([stock], [stock], seed=81)
    assert list(sample.cards) == list(state.cards)
    for card_id, card in state.cards.items():
        actual = sample.cards[card_id]
        assert card.name == actual.name == 'Island'
        assert (card.owner, card.controller, card.zone, card.instance_order, card.summoning_sick,
                card.tapped, card.counters) == (
                    actual.owner, actual.controller, actual.zone, actual.instance_order,
                    actual.summoning_sick, actual.tapped, actual.counters)
    state.cards.update(sample.cards)


def original():
    return importlib.import_module('tests.test_same_kind_modal_targets')


def assert_card(card):
    raw = raw_card(card.name)
    normalized = ScryfallSyncService._normalize_payload(raw, DISPLAY)
    assert card.oracle_text == raw['oracle_text']
    assert card.type_line == raw['type_line']
    assert card.mana_cost == raw.get('mana_cost', '')
    assert card.layout == raw['layout']
    assert card.colors == raw['colors']
    assert card.card_faces == raw.get('card_faces', [])
    assert card.printed_power == raw.get('power')
    assert card.printed_toughness == raw.get('toughness')
    assert card.power == (int(raw['power']) if raw.get('power') is not None else None)
    assert card.toughness == (int(raw['toughness']) if raw.get('toughness') is not None else None)
    assert card.image_uri == normalized['image_uri'] == DISPLAY
    assert card.characteristic_record['physical'] == {field: deepcopy(getattr(card, field)) for field in PHYSICAL}
    assert card.characteristic_record['values']['oracle_text'] == raw['oracle_text']
    assert card.characteristic_record['values']['name'] == raw['name']


class CapturedBeforeConsumer(Exception):
    pass


@pytest.mark.parametrize('which', ['spell', 'ring', 'bear', 'island'])
def test_actual_first_legal_read_receives_complete_factory_birth(which, monkeypatch):
    subject = original()
    captured = []

    def capture(rules, state, player):
        captured.append(deepcopy(state))
        raise CapturedBeforeConsumer

    monkeypatch.setattr(subject.RulesEngine, 'legal_moves', capture)
    with pytest.raises(CapturedBeforeConsumer):
        subject.test_ai_announces_distinct_targets_for_each_mode()
    state = captured[0]
    card_id = {'spell': state.players[1].hand[0], 'ring': 'ring', 'bear': 'bear', 'island': 'p2-001'}[which]
    assert_card(state.cards[card_id])


@pytest.mark.parametrize('card_id', ['elf', 'bear-own', 'bear-opp'])
def test_actual_original_graveyard_builder_has_complete_birth_before_cast(card_id):
    state, _ = original()._graveyard_pair()
    assert_card(state.cards[card_id])


@pytest.mark.parametrize('body,card_id', [
    ('test_modal_copy_retargets_each_mode_without_changing_original', 'spare-ring'),
    ('test_shared_same_card_target_is_two_choices_on_modal_copy', 'spare-ring'),
    ('test_ai_copy_redirects_removal_away_from_its_own_permanents', 'enemy-ring'),
])
def test_actual_late_target_birth_is_complete_before_copy_consumer(body, card_id, monkeypatch):
    subject = original()
    captured = []

    def capture(state, controller, payload):
        captured.append(deepcopy(state.cards[card_id]))
        raise CapturedBeforeConsumer

    monkeypatch.setattr(subject, 'copy_spell', capture)
    with pytest.raises(CapturedBeforeConsumer):
        getattr(subject, body)()
    assert_card(captured[0])


@pytest.mark.parametrize('card_id', ['spell', 'ring', 'bear', 'elf', 'bear-own', 'bear-opp', 'p1-001', 'p2-001'])
def test_actual_builder_snapshot_retains_real_birth_without_printed_repair(card_id):
    state, spell_id = original()._graveyard_pair()
    key = spell_id if card_id == 'spell' else card_id
    assert_card(state.cards[key])
    before = deepcopy(state.cards[key].characteristic_record)
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(snapshot)
    assert_card(restored.cards[key])
    assert restored.cards[key].characteristic_record == before
    assert restored.starting_decks == state.starting_decks
    assert restored.rng.getstate() == state.rng.getstate()


@pytest.mark.parametrize('name', ["Kolaghan's Command", 'Sol Ring', 'Grizzly Bears', 'Llanowar Elves', 'Island'])
def test_raw_and_factory_outputs_are_complete_fresh_objects(name):
    one, two = raw_card(name), raw_card(name)
    assert one == two and one is not two
    assert one['legalities'] is not two['legalities']
    first = materialize('first', name, 1, 1, Zone.HAND)
    second = materialize('second', name, 1, 1, Zone.HAND)
    assert_card(first)
    assert_card(second)
    assert first.characteristic_record is not second.characteristic_record
    assert first.characteristic_record['physical'] is not second.characteristic_record['physical']
    assert first.keywords is not second.keywords and first.card_faces is not second.card_faces


def test_original_setup_preserves_controlled_stock_positions_rng_and_resources(monkeypatch):
    subject = original()
    actual = subject.controlled_basic_game
    captured = []

    def capture(*args, **kwargs):
        state = actual(*args, **kwargs)
        captured.append((deepcopy(state.starting_decks), state.rng.getstate(),
                         {pid: (list(p.hand), list(p.library)) for pid, p in state.players.items()}))
        return state

    monkeypatch.setattr(subject, 'controlled_basic_game', capture)
    state, spell_id = subject._setup()
    stock, rng, positions = captured[0]
    assert state.starting_decks == stock == {1: [{'quantity': 60, 'card_name': 'Island'}],
                                           2: [{'quantity': 60, 'card_name': 'Island'}]}
    assert state.rng.getstate() == rng
    assert {pid: (p.hand, p.library) for pid, p in state.players.items()} == positions
    assert spell_id == state.players[1].hand[0]
    assert state.players[1].mana_pool == {'B': 1, 'R': 1, 'C': 1}
