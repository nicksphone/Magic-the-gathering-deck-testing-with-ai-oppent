"""Whole inline remainder: real native birth/capture, stopped before publication IO."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from ai import sideboard_facts
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.engine import RulesEngine
from tests.test_modal_fixture_source_authority import APPROVED


ROOT = Path(__file__).resolve().parents[2]
SUBJECT = Path(__file__).with_name('browser_fixture_server.py')
MANIFEST = Path(__file__).parent / 'fixtures/browser_positive83/SOURCES.json'
CASES = [
    'linked_copy_x', 'snow_payment', 'non_snow_payment', 'compleated_payment',
    'phyrexian_payment', 'hybrid_payment', 'thoughtseize', 'duress', 'inquisition',
    'despise', 'appetite', 'revealed_discard', 'each_player_discard',
    'modal_same_kind', 'modal_two_targets', 'modal_targetless', 'player_hexproof',
    'damage_trigger', 'conditional_land', 'conditional_land_effect', 'iteration',
    'search', 'bo3', 'bo3_sideboard', 'bo3_draw', 'trigger', 'cast_trigger',
    'alternative_target', 'first_strike_window', 'combat_damage_assignment',
    'shared_trample', 'banding_damage', 'attacking_band', 'split', 'aftermath',
    'multi_adventure', 'multi_adventure_copy', 'land', 'adventure', 'modal_default',
    'unknown_nonempty', 'default', 'pregame',
]


def raw(name):
    record = json.loads(MANIFEST.read_bytes())['cards'][name]
    encoded = (ROOT / record['path']).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == record['file_sha256']
    location = list(record['location'])
    if location and location[0] == 'line':
        value = json.loads(encoded.splitlines()[location[1] - 1])
        location = location[2:]
    else:
        value = json.loads(encoded)
    for key in location:
        value = value[key]
    assert hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == record['object_sha256']
    assert value['object'] == 'card' and value['name'] == name
    assert value['id'] == record['id'] and value['oracle_id'] == record['oracle_id']
    assert len(value) == record['fields'] and 'legalities' in value
    return value


def assert_entry(item):
    original = raw(item['card_name'])
    front = (original.get('card_faces') or [{}])[0]
    for key in ('id', 'oracle_id', 'legalities', 'layout', 'set', 'uri'):
        assert item[key] == original[key]
    assert item['card_faces'] == original.get('card_faces', [])
    assert item['colors'] == original.get('colors', [])
    assert item['keywords'] == original['keywords']
    assert item['oracle_text'] == (original.get('oracle_text') or front.get('oracle_text') or '')
    assert item['mana_cost'] == (original.get('mana_cost') or front.get('mana_cost') or '')
    assert item['type_line'] == (original.get('type_line') or front.get('type_line') or '')


class PublicationObserved(Exception):
    pass


def observe_scene(monkeypatch, kind):
    text = SUBJECT.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == 'fixture')
    assert hashlib.sha256(ast.get_source_segment(text, node).encode()).hexdigest() == APPROVED
    node.decorator_list = []
    captures, births, publications = [], [], []
    original_capture = sideboard_facts.initialize
    original_factory = MatchFactory.from_decks

    def capture(state, inventory):
        # Observe the actual native argument BEFORE the real stock capture.
        assert set(inventory) == set(state.cards)
        for cid, binding in inventory.items():
            card = state.cards[cid]
            source = raw(binding['stock_key'])
            assert binding['owner'] == card.owner
            assert card.characteristic_record['physical']['card_faces'] == source.get('card_faces', [])
            assert card.characteristic_record['physical']['layout'] == source['layout']
            source_face = (source.get('card_faces') or [{}])[0]
            printed = source_face if source['layout'] in {'modal_dfc', 'transform'} else source
            assert card.characteristic_record['values']['oracle_text'] == (
                printed.get('oracle_text') or source_face.get('oracle_text') or '')
            if source['layout'] == 'normal':
                type_words = set(source['type_line'].split('\u2014')[0].split())
                expected_types = type_words & {'Artifact', 'Battle', 'Creature', 'Enchantment',
                                               'Instant', 'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
                actual_types = card.characteristic_record['values']['types']
                assert type(actual_types) is list and len(actual_types) == len(expected_types)
                assert set(actual_types) == expected_types
                expected = {
                    'name': source['name'], 'type_line': source['type_line'],
                    'mana_cost': source.get('mana_cost') or '',
                    'colors': source.get('colors', []),
                    'printed_power': source.get('power'),
                    'printed_toughness': source.get('toughness'),
                    'power': int(source['power']) if source.get('power') is not None else None,
                    'toughness': int(source['toughness']) if source.get('toughness') is not None else None,
                    'loyalty': int(source['loyalty']) if source.get('loyalty') is not None else None,
                }
                assert {key: card.characteristic_record['values'][key] for key in expected} == expected
            captures.append((cid, deepcopy(card.characteristic_record)))
        original_capture(state, inventory)
        assert state.sideboard_facts['capture_version'] == 3
        assert state.sideboard_facts['inventory'] == inventory

    def factory(a, b, *args, **kwargs):
        for item in a + b:
            assert_entry(item)
        result = original_factory(a, b, *args, **kwargs)
        if sum(item['quantity'] for item in a + b) == 120:
            births.append({'names': {cid: binding['stock_key'] for cid, binding in result.sideboard_facts['inventory'].items()},
                           'rng': deepcopy(result.rng.getstate()), 'seed': kwargs['seed'],
                           'stock': deepcopy(result.sideboard_facts)})
        return result

    def publication(state, deck, *, capture_original_stock=True, mainboards=None):
        assert capture_original_stock is True
        assert state.sideboard_facts['capture_version'] == 3
        assert state.sideboard_facts['inventory'] == births[0]['stock']['inventory']
        publications.append(state)
        # This is a before-publication data protocol, NOT real HTTP/SQL acceptance.
        raise PublicationObserved

    monkeypatch.setattr(sideboard_facts, 'initialize', capture)
    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
    namespace = {'__file__': str(SUBJECT), 'Path': Path, 'MatchFactory': MatchFactory,
                 'CardInstance': CardInstance, 'StackItem': StackItem, 'Step': Step,
                 'Zone': Zone, 'RulesEngine': RulesEngine, 'publish': publication}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SUBJECT), 'exec'), namespace)
    kwargs = {'face_kind': '' if kind in {'default', 'pregame', 'modal_default'} else kind,
              'pregame': kind == 'pregame', 'modal': kind == 'modal_default'}
    with pytest.raises(PublicationObserved):
        namespace['fixture'](**kwargs)
    assert captures and len(births) == len(publications) == 1
    return births[0], publications[0]


@pytest.mark.parametrize('kind', CASES)
def test_every_inline_remainder_has_full_raw_before_factory_and_original_capture(monkeypatch, kind):
    birth, state = observe_scene(monkeypatch, kind)
    assert len(birth['names']) == 120
    assert birth['stock']['coverage_ok'] is True
    assert state.starting_decks


@pytest.mark.parametrize('kind,seed,expected', [
    ('snow_payment', 930, {'p1-053': 'Snow-Covered Forest', 'p1-060': 'Icehide Golem'}),
    ('non_snow_payment', 930, {'p1-053': 'Forest', 'p1-060': 'Icehide Golem'}),
    ('compleated_payment', 925, {'p1-060': 'Tamiyo, Compleated Sage'}),
    ('phyrexian_payment', 922, {'p1-060': 'Mutagenic Growth'}),
    ('hybrid_payment', 921, {'p1-060': 'Spectral Procession'}),
    ('thoughtseize', 920, {'p1-060': 'Thoughtseize', 'p2-060': 'Forest', 'p2-059': 'Lightning Bolt', 'p2-058': 'Llanowar Elves'}),
    ('inquisition', 920, {'p1-060': 'Inquisition of Kozilek', 'p2-057': 'Serra Angel'}),
    ('despise', 920, {'p1-060': 'Despise', 'p2-057': 'Jace, the Mind Sculptor'}),
    ('revealed_discard', 919, {'p1-060': 'Coercion'}),
    ('each_player_discard', 818, {'p1-060': 'Delirium Skeins'}),
    ('iteration', 32, {'p2-051': 'Lightning Bolt', 'p2-052': 'Counterspell', 'p2-053': 'Llanowar Elves'}),
    ('search', 33, {'p2-052': 'Llanowar Elves', 'p2-053': 'Grizzly Bears'}),
])
def test_prebirth_slot_binding_preserves_native_ids_and_rng(monkeypatch, kind, seed, expected):
    birth, _ = observe_scene(monkeypatch, kind)
    assert {cid: birth['names'][cid] for cid in expected} == expected
    rng = random.Random(seed)
    rng.shuffle(list(range(60)))
    rng.shuffle(list(range(60)))
    assert birth['rng'] == rng.getstate()


def test_teferi_printed_and_current_four_are_not_replaced_from_memory(monkeypatch):
    _, state = observe_scene(monkeypatch, 'alternative_target')
    card = state.cards['teferi']
    assert raw('Teferi, Hero of Dominaria')['loyalty'] == '4'
    assert card.loyalty == 4
    assert card.characteristic_record['values']['loyalty'] == 4


def test_full_entries_are_fresh_without_relabeling_or_shared_faces():
    from tests.browser_positive83_canonical import entry
    a = entry('Valki, God of Lies // Tibalt, Cosmic Impostor')
    b = entry('Valki, God of Lies // Tibalt, Cosmic Impostor')
    assert a == b and a['card_faces'] is not b['card_faces']
    a['card_faces'][0]['oracle_text'] = 'explicit corruption, not canonical facts'
    assert b['card_faces'] == raw(b['card_name'])['card_faces']
