"""Actual original callers and native birth; not paid-cast or protocol waivers."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from tests import test_mass_exile_rules as original
from tests import mass_exile_canonical_fixture as canonical


FIXTURES = Path(__file__).parent / 'fixtures'
RAW_SHA = '0bc8a7a902fcfe58169a1e26f71785c730dccac3c616717aa65b1b1621789875'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
ORIGINALS = [
    ('test_exile_all_creatures_preserves_ownership_and_emits_leave_event', 61, 120),
    ('test_farewell_style_text_uses_exile_not_destroy', 62, 121),
]


def _official(name):
    if name == 'Final Judgment':
        data = (FIXTURES / 'mass_exile_audit/final-judgment.json').read_bytes()
        assert hashlib.sha256(data).hexdigest() == RAW_SHA
        raw = json.loads(data)
        assert raw['id'] == '2503e136-031f-498a-b042-4077baebe8f8'
    else:
        assert name == 'Forest'
        data = (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
        assert hashlib.sha256(data).hexdigest() == SEED_SHA
        raw = json.loads(data.splitlines()[38])
        encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == '602b1fe3c5c18846061929fee422e97c8e9c2c431e57e8c6c810f2da7643fad3'
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['keywords'] == [] and not any(raw.get(k) for k in ('power', 'toughness', 'loyalty'))
    return raw


def _expected(raw):
    kinds = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    types = [word for word in raw['type_line'].split('\u2014')[0].split() if word in kinds]
    return {'name': raw['name'], 'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
            'oracle_text': raw['oracle_text'], 'types': types, 'keywords': [],
            'colors': raw['colors'], 'power': None, 'toughness': None,
            'printed_power': None, 'printed_toughness': None, 'loyalty': None}


def _assert_card(card, raw):
    expected = _expected(raw)
    assert {key: deepcopy(getattr(card, key)) for key in expected} == expected
    assert card.layout == raw['layout'] and card.card_faces == raw.get('card_faces', [])
    physical = {**expected, 'layout': raw['layout'], 'card_faces': raw.get('card_faces', []),
                'selected_face_index': None, 'image_uri': None}
    assert card.characteristic_record == {'version': 1, 'physical': physical, 'values': expected}
    assert card.is_token is False


def _assert_stock(state, spell):
    inventory = state.sideboard_facts['inventory']
    assert len(state.cards) == len(inventory) == 121
    assert set(state.cards) == set(inventory)
    assert Counter((row['owner'], row['stock_key']) for row in inventory.values()) == {
        (1, 'Forest'): 60, (1, 'Final Judgment'): 1, (2, 'Forest'): 60}
    assert inventory[spell.id] == {'owner': 1, 'stock_key': 'Final Judgment'}
    assert state.cards[spell.id] is spell and spell.owner == spell.controller == 1
    assert spell.zone == Zone.HAND and state.players[1].hand.count(spell.id) == 1
    locations = [(pid, zone.value) for pid, player in state.players.items() for zone in Zone
                 if hasattr(player, zone.value) and spell.id in getattr(player, zone.value)]
    assert locations == [(1, 'hand')]


def _assert_positive(state, card):
    _assert_card(card, _official('Final Judgment'))
    _assert_stock(state, card)


def _run_original(monkeypatch, before_consumer):
    real = original.build_ability_spec
    observed = []

    def observe(state, card, controller, *args, **kwargs):
        before_consumer(state, card)
        observed.append((state, card, controller))
        return real(state, card, controller, *args, **kwargs)

    monkeypatch.setattr(original, 'build_ability_spec', observe)
    original.test_farewell_style_text_uses_exile_not_destroy()
    assert len(observed) == 1 and observed[0][2] == 1
    return observed[0][:2]


@pytest.mark.parametrize('name,seed,count', ORIGINALS, ids=['protocol-120', 'positive-121'])
def test_actual_original_factory_receives_complete_forest_and_positive_rows(monkeypatch, name, seed, count):
    real = original.MatchFactory
    seen = []

    class ObservedFactory:
        @staticmethod
        def from_decks(deck_a, deck_b, *args, **kwargs):
            assert kwargs['seed'] == seed
            expected_a = [('Forest', 60)] + ([('Final Judgment', 1)] if count == 121 else [])
            assert [(row['card_name'], row['quantity']) for row in deck_a] == expected_a
            assert [(row['card_name'], row['quantity']) for row in deck_b] == [('Forest', 60)]
            for deck in (deck_a, deck_b):
                forest = [row for row in deck if row['card_name'] == 'Forest']
                assert len(forest) == 1 and forest[0]['quantity'] == 60
                for key in ('name', 'oracle_text', 'type_line', 'mana_cost', 'colors', 'layout'):
                    assert forest[0].get(key) == _official('Forest')[key]
                for row in deck:
                    raw = _official(row['card_name'])
                    assert all(row[key] == value for key, value in raw.items())
            state = real.from_decks(deck_a, deck_b, *args, **kwargs)
            assert len(state.cards) == len(state.sideboard_facts['inventory']) == count
            expected_counts = {(1, 'Forest'): 60, (2, 'Forest'): 60}
            if count == 121:
                expected_counts[(1, 'Final Judgment')] = 1
            assert Counter((row['owner'], row['stock_key']) for row in state.sideboard_facts['inventory'].values()) == expected_counts
            for card in state.cards.values():
                _assert_card(card, _official(card.name))
            before = serialize_match_snapshot(state)
            assert serialize_match_snapshot(deserialize_match_snapshot(before)) == before
            seen.append(True)
            return state

    monkeypatch.setattr(original, 'MatchFactory', ObservedFactory)
    getattr(original, name)()
    assert seen == [True]


def test_actual_original_positive_reaches_inference_after_real_hand_move(monkeypatch):
    native = CardInstance.move_to_zone
    moves = []
    real_factory = original.MatchFactory
    birth = []

    def observe_move(card, zone):
        previous, sequence = card.zone, card.zone_change_sequence
        result = native(card, zone)
        moves.append((card.id, previous, zone, sequence, card.zone_change_sequence))
        return result

    class ObservedFactory:
        @staticmethod
        def from_decks(*args, **kwargs):
            state = real_factory.from_decks(*args, **kwargs)
            birth.append((set(state.cards), deepcopy(state.sideboard_facts['inventory']), len(moves)))
            return state

    monkeypatch.setattr(CardInstance, 'move_to_zone', observe_move)
    monkeypatch.setattr(original, 'MatchFactory', ObservedFactory)
    state, spell = _run_original(monkeypatch, _assert_positive)
    assert len(birth) == 1 and len(birth[0][0]) == 121
    assert birth[0][0] == set(state.cards) and birth[0][1] == state.sideboard_facts['inventory']
    after_birth = moves[birth[0][2]:]
    assert len(after_birth) == 1 and after_birth[0][0] == spell.id and after_birth[0][2] == Zone.HAND
    assert after_birth[0][4] == after_birth[0][3] + int(after_birth[0][1] != Zone.HAND)


def test_actual_original_positive_snapshot_preserves_full_print_and_stock(monkeypatch):
    state, spell = _run_original(monkeypatch, _assert_positive)
    encoded = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(encoded)
    assert serialize_match_snapshot(restored) == encoded
    _assert_positive(restored, restored.cards[spell.id])


@pytest.mark.parametrize('field', ['name', 'oracle_text', 'types', 'keywords', 'colors', 'power',
                                  'printed_power', 'layout', 'card_faces'])
def test_actual_consumer_oracle_rejects_coherent_live_physical_and_value_mutation(monkeypatch, field):
    wrong = {'name': 'Farewell', 'oracle_text': 'Exile all creatures. Draw a card.',
             'types': ['Creature'], 'keywords': ['flying'], 'colors': [], 'power': 3,
             'printed_power': '3', 'layout': 'transform', 'card_faces': [{'name': 'Invalid protocol face'}]}

    def corrupt(state, card):
        _assert_positive(state, card)
        mutant = deepcopy(state)
        changed = mutant.cards[card.id]
        setattr(changed, field, deepcopy(wrong[field]))
        for slot in ('physical', 'values'):
            if field in changed.characteristic_record[slot]:
                changed.characteristic_record[slot][field] = deepcopy(wrong[field])
        with pytest.raises(AssertionError):
            _assert_positive(mutant, changed)
        _assert_positive(state, card)

    _run_original(monkeypatch, corrupt)


@pytest.mark.parametrize('kind', ['missing-inventory', 'wrong-binding-owner', 'missing-hand', 'duplicate-hand'])
def test_actual_consumer_oracle_rejects_invalid_native_stock_or_zone_lists(monkeypatch, kind):
    def corrupt(state, card):
        _assert_positive(state, card)
        mutant = deepcopy(state)
        changed = mutant.cards[card.id]
        if kind == 'missing-inventory':
            del mutant.sideboard_facts['inventory'][card.id]
        elif kind == 'wrong-binding-owner':
            mutant.sideboard_facts['inventory'][card.id]['owner'] = 2
        elif kind == 'missing-hand':
            mutant.players[1].hand.remove(card.id)
        else:
            mutant.players[1].hand.append(card.id)
        with pytest.raises(AssertionError):
            _assert_positive(mutant, changed)
        _assert_positive(state, card)

    _run_original(monkeypatch, corrupt)


def test_existing_final_judgment_full_source_is_retained_by_entry():
    raw = _official('Final Judgment')
    row = canonical.final_judgment_entry()
    assert all(row[key] == value for key, value in raw.items())
    assert row['quantity'] == 1 and row['card_name'] == raw['name']
    assert row['image_uri'] is None
