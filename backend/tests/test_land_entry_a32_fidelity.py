"""Independent official-RAW oracle at the original factory and consumer seams."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import random

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory


FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '7b4e6891174bd118e73b5c5e308183bfea39b1c6644392c7c69bebf6c31b4bc2'
NAMES = ('Sacred Foundry', 'Lightning Bolt', 'Island', 'Font of Agonies')
CASES = (
    ('foundry', 'test_land_play_requires_explicit_entry_choice_and_payment_is_atomic', 'legal_moves', 'Sacred Foundry', None),
    ('island', 'test_land_play_requires_explicit_entry_choice_and_payment_is_atomic', 'legal_moves', 'Island', None),
    ('bolt', 'test_land_payment_unavailable_below_two_life_and_ai_prefers_tapped_without_followup', 'best_land', 'Lightning Bolt', 'bolt'),
    ('font-a', 'test_multiple_paid_effect_entries_defer_trigger_order_until_all_lands_enter', 'topdeck', 'Font of Agonies', 'font-a'),
    ('font-b', 'test_multiple_paid_effect_entries_defer_trigger_order_until_all_lands_enter', 'topdeck', 'Font of Agonies', 'font-b'),
)


def _raw(name):
    data = (FIXTURES / 'land_entry_a32/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)['cards'][name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    for proof in record['provenance']:
        assert hashlib.sha256((FIXTURES / proof['file']).read_bytes()).hexdigest() == proof['sha256']
    if record['line'] is not None:
        data = data.splitlines()[record['line'] - 1]
    raw = json.loads(data)
    canonical = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == record['object_sha256']
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    assert len(raw) == record['fields'] >= 60
    return raw


def _assert_complete(card, name):
    raw = _raw(name)
    # These four RAW cards are noncreatures with no printed keyword abilities.
    # Derive types independently, not through the migration helper or game parser.
    head = raw['type_line'].split(' \u2014 ', 1)[0].split()
    types = [kind for kind in head if kind in {
        'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant', 'Land', 'Planeswalker', 'Sorcery', 'Kindred', 'Tribal'}]
    assert 'Creature' not in types and raw['keywords'] == []
    assert not any(field in raw for field in ('power', 'toughness', 'loyalty'))
    expected = {
        'name': raw['name'], 'mana_cost': raw['mana_cost'], 'type_line': raw['type_line'],
        'types': types, 'oracle_text': raw['oracle_text'], 'colors': raw['colors'], 'keywords': [],
        'power': None, 'toughness': None, 'printed_power': None, 'printed_toughness': None, 'loyalty': None,
    }
    assert {key: getattr(card, key) for key in expected} == expected
    assert card.layout == raw['layout'] == 'normal'
    assert card.card_faces == [] and card.selected_face_index is None
    assert card.image_uri == raw['image_uris']['normal']
    assert card.characteristic_record == {
        'version': 1, 'values': expected,
        'physical': {**expected, 'layout': raw['layout'], 'card_faces': [],
                     'selected_face_index': None, 'image_uri': raw['image_uris']['normal']},
    }


class ConsumerCaptured(BaseException):
    pass


def _capture(monkeypatch, case):
    _, function, seam, name, cid = case
    module = importlib.import_module('tests.test_land_entry_choice')
    actual_factory = MatchFactory.from_decks
    captured = {'births': []}

    def observe_factory(left, right, *args, **kwargs):
        state = actual_factory(left, right, *args, **kwargs)
        captured['births'].append((deepcopy([left, right]), kwargs.get('seed'), deepcopy(state)))
        return state

    def observe(state):
        selected = state.cards[cid] if cid else next(c for c in state.cards.values() if c.name == name)
        captured.update(state=state, card=selected)
        raise ConsumerCaptured

    actual_best = module.AIAgent._best_land_move

    def observe_best(agent, state, *args, **kwargs):
        if 'bolt' in state.cards:
            return observe(state)
        return actual_best(agent, state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        if seam == 'legal_moves':
            patch.setattr(module.RulesEngine, 'legal_moves', lambda engine, state, *a, **k: observe(state))
        elif seam == 'best_land':
            patch.setattr(module.AIAgent, '_best_land_move', observe_best)
        else:
            patch.setattr(module, 'topdeck_put_permanents_battlefield', lambda state, *a, **k: observe(state))
        with pytest.raises(ConsumerCaptured):
            getattr(module, function)()
    assert captured['card'].name == name and captured['card'].owner == captured['card'].controller == 1
    return captured


@pytest.mark.parametrize('name', NAMES)
def test_complete_existing_official_raw_and_provenance_are_pinned(name):
    raw = _raw(name)
    assert raw['layout'] == 'normal' and raw['image_uris']['normal']


@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
def test_original_first_consumer_receives_independent_complete_printed_facts(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    _assert_complete(captured['card'], case[3])


@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
def test_real_factory_birth_full_raw_stock_ids_and_rng_precede_original_consumer(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    seen = False
    for decks, seed, state in captured['births']:
        rng = random.Random(seed)
        for owner, rows in enumerate(decks, 1):
            expanded = []
            for row in rows:
                raw = _raw(row['card_name'])
                assert {key: row[key] for key in raw} == raw
                expanded.extend([raw['name']] * row['quantity'])
            rng.shuffle(expanded)
            for index, name in enumerate(expanded, 1):
                card = state.cards[f'p{owner}-{index:03d}']
                assert card.name == name and card.owner == card.controller == owner
                _assert_complete(card, name)
                assert state.sideboard_facts['inventory'][card.id] == {'owner': owner, 'stock_key': name}
                seen |= name == case[3]
            assert len(state.players[owner].hand) == min(7, len(expanded))
        assert state.rng.getstate() == rng.getstate()
        assert len(state.sideboard_facts['inventory']) == len(state.cards)
    assert seen
    main = next(state for _, _, state in captured['births'] if len(state.cards) == 120)
    assert sum(b['owner'] == 1 for b in main.sideboard_facts['inventory'].values()) == 60
    assert sum(b['owner'] == 2 for b in main.sideboard_facts['inventory'].values()) == 60
    assert captured['state'].starting_decks == main.starting_decks
    assert captured['state'].sideboard_facts['inventory'] == main.sideboard_facts['inventory']


@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
def test_full_printed_values_survive_actual_snapshot(monkeypatch, case):
    captured = _capture(monkeypatch, case)
    restored = deserialize_match_snapshot(serialize_match_snapshot(captured['state']))
    _assert_complete(restored.cards[captured['card'].id], case[3])
    assert restored.sideboard_facts == captured['state'].sideboard_facts


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('mutation', ['oracle', 'cost', 'colors', 'creature_traits', 'keywords', 'image'])
def test_independent_oracle_rejects_coherent_live_and_retained_corruption(name, mutation):
    raw = _raw(name)
    # A native full-RAW test specimen, independent of the migration helper.
    entry = {**raw, 'card_name': name, 'quantity': 8, 'image_uri': raw['image_uris']['normal']}
    state = MatchFactory.from_decks([entry], [], seed=0)
    card = next(iter(state.cards.values()))
    _assert_complete(card, name)
    fields = {
        'oracle': {'oracle_text': 'Invented shortened instruction.'},
        'cost': {'mana_cost': '{99}'}, 'colors': {'colors': ['G']},
        'creature_traits': {'types': ['Creature'], 'power': 8, 'toughness': 8,
                            'printed_power': '8', 'printed_toughness': '8'},
        'keywords': {'keywords': ['Flying']}, 'image': {'image_uri': 'incorrect-printing'},
    }[mutation]
    for key, value in fields.items():
        setattr(card, key, deepcopy(value))
        card.characteristic_record['physical'][key] = deepcopy(value)
        if key in card.characteristic_record['values']:
            card.characteristic_record['values'][key] = deepcopy(value)
    with pytest.raises(AssertionError):
        _assert_complete(card, name)
