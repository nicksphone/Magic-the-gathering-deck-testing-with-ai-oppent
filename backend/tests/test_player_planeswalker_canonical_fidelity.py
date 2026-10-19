"""Mixed-IO PREP: genuine original game fixture; no HTTP/persistence stub."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, Zone
from tests import test_player_or_planeswalker_targets as subject
from tests.test_player_or_planeswalker_targets import game, spell_data
from tests.player_planeswalker_canonical import canonical_card


NAMES = ('Lightning Bolt', 'Lava Spike', 'Skullcrack', 'Teferi, Hero of Dominaria')
SEED = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
COPIABLE = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
            'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')
PHYSICAL = (*COPIABLE, 'layout', 'card_faces', 'selected_face_index', 'image_uri')


def _raw(name):
    # Independent whole-source reader: not the producer/normalizer or its output.
    data = SEED.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    found = [row for row in map(json.loads, data.splitlines()) if row.get('name') == name]
    assert len(found) == 1 and found[0]['object'] == 'card'
    assert found[0]['layout'] == 'normal' and found[0]['keywords'] == []
    return found[0]


def _expected(raw):
    types = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
             'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    assert 'power' not in raw and 'toughness' not in raw
    return {**{key: raw.get(key, '') for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'layout')},
            'types': [word for word in raw['type_line'].split('\u2014')[0].split() if word in types],
            'power': None, 'toughness': None, 'printed_power': None, 'printed_toughness': None,
            'loyalty': int(raw['loyalty']) if 'loyalty' in raw else None,
            'keywords': [], 'colors': raw['colors'], 'card_faces': raw.get('card_faces', []),
            'selected_face_index': None, 'image_uri': None}


def _facts(card):
    return {key: deepcopy(getattr(card, key)) for key in PHYSICAL}


def _observe_births(monkeypatch):
    births = []
    original = CardInstance.__post_init__

    def observe(card):
        facts = _facts(card)
        original(card)
        births.append((card, facts))

    monkeypatch.setattr(CardInstance, '__post_init__', observe)
    return births


def _assert_fidelity(card, captured, raw, *, current_loyalty=None):
    expected = _expected(raw)
    assert captured == expected, 'Incomplete facts BEFORE native capture'
    record = card.characteristic_record
    assert set(record) == {'version', 'physical', 'values'}
    assert type(record['version']) is int and record['version'] == 1
    assert record['physical'] == expected, 'Retained physical facts changed'
    assert record['values'] == {key: expected[key] for key in COPIABLE}, 'Retained copiable facts changed'
    live = _facts(card)
    if current_loyalty is not None:
        expected = {**expected, 'loyalty': current_loyalty}
    assert live == expected, 'Live print or explicit scene loyalty changed'


def _birth(card, births):
    rows = [facts for born, facts in births if born is card]
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize('name', NAMES)
def test_complete_RAW_is_present_before_real_native_birth(name, monkeypatch):
    births = _observe_births(monkeypatch)
    raw = _raw(name)
    card = canonical_card(name, id='fidelity-card', owner=2, controller=2, zone=Zone.HAND)
    _assert_fidelity(card, _birth(card, births), raw)
    assert (card.id, card.owner, card.controller, card.zone) == ('fidelity-card', 2, 2, Zone.HAND)
    assert card.zone_change_sequence == 0 and card.instance_order == 0


def test_original_Bolt_body_reaches_real_target_consumer_with_full_facts(monkeypatch):
    births = _observe_births(monkeypatch)
    original, calls = subject.require_declared_targets, []

    def observe(card, *args, **kwargs):
        _assert_fidelity(card, _birth(card, births), _raw('Lightning Bolt'))
        calls.append(card.id)
        return original(card, *args, **kwargs)

    monkeypatch.setattr(subject, 'require_declared_targets', observe)
    subject.test_any_target_rejects_dual_player_and_permanent_declaration()
    assert calls == ['bolt'] * 4


def test_original_setup_has_full_births_and_scene_before_real_persist(game, spell_data, monkeypatch):
    births = _observe_births(monkeypatch)
    stock, decks = deepcopy(game[1].state.sideboard_facts), deepcopy(game[1].state.starting_decks)
    original, calls = subject.persist, []

    def observe(controller):
        state = controller.state
        spell, walker = state.cards['burn-spell'], state.cards['teferi']
        _assert_fidelity(spell, _birth(spell, births), _raw(spell_data[0]))
        _assert_fidelity(walker, _birth(walker, births), _raw('Teferi, Hero of Dominaria'), current_loyalty=4)
        assert state.sideboard_facts == stock and state.starting_decks == decks
        assert state.players[1].mana_pool['R'] == 2
        assert (spell.owner, spell.controller, spell.zone) == (1, 1, Zone.HAND)
        assert (walker.owner, walker.controller, walker.zone) == (2, 2, Zone.BATTLEFIELD)
        calls.append(controller)
        return original(controller)

    monkeypatch.setattr(subject, 'persist', observe)
    client, controller, spell, walker = subject._setup(game, spell_data)
    assert client is game[0] and controller is game[1]
    assert calls == [controller] and (spell.id, walker.id) == ('burn-spell', 'teferi')


def test_real_spell_fixture_tuple_is_complete_RAW_not_manual_Oracle(spell_data):
    raw = _raw(spell_data[0])
    assert spell_data == (raw['name'], raw['mana_cost'], raw['oracle_text'])


@pytest.mark.parametrize('name,surface,field', [
    ('Lightning Bolt', 'birth', 'mana_cost'),
    ('Lightning Bolt', 'physical', 'type_line'),
    ('Lightning Bolt', 'values', 'oracle_text'),
    ('Lightning Bolt', 'live', 'colors'),
    ('Teferi, Hero of Dominaria', 'physical', 'loyalty'),
    ('Teferi, Hero of Dominaria', 'values', 'loyalty'),
])
def test_independent_oracle_rejects_explicit_corruption(name, surface, field, monkeypatch):
    # Invalid metadata-protocol vectors, never canonical-positive card inputs.
    births = _observe_births(monkeypatch)
    raw = _raw(name)
    card = canonical_card(name, id='negative-card', owner=1, controller=1, zone=Zone.HAND)
    captured = _birth(card, births)
    _assert_fidelity(card, captured, raw)
    if surface == 'birth':
        captured[field] = ''
    elif surface == 'live':
        card.colors = ['G']
    elif field == 'loyalty':
        card.characteristic_record[surface][field] += 1
    else:
        card.characteristic_record[surface][field] = 'EXPLICIT INVALID METADATA'
    with pytest.raises(AssertionError):
        _assert_fidelity(card, captured, raw)
