"""Actual admission/parser projections and full public seed; no SQL/native games."""
import ast
import builtins
import copy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any
import unittest

from tests import test_matchup_round_robin_protocol as protocol

BACKEND = Path(__file__).resolve().parents[1]


def fixture():
    seed = json.loads((BACKEND/'card_data/builtin_oracle_seed.json').read_bytes())['cards']
    sync = protocol.project(BACKEND/'card_data/sync.py', {'re': re, 'json': json},
                            {'oracle_fields_valid', 'needs_split_color_sync'})
    hydration = protocol.project(BACKEND/'card_data/hydration.py', sync,
        {'ready_for_match', 'is_playable_deck_card', '_required_characteristics_available'})
    search = protocol.project(BACKEND/'card_data/search.py', {'re': re,
        '_DECKLIST_ANNOTATION_RE': re.compile(r'\s*[\[(]\s*[A-Za-z0-9]{2,8}\s*[\])]$', re.IGNORECASE)},
        {'normalize_card_lookup_name'})
    parser = protocol.project(BACKEND/'decks/parser.py', dict(dataclass=dataclass, Any=Any, re=re,
        Repository=object, normalize_card_lookup_name=search['normalize_card_lookup_name']))
    tree = ast.parse((BACKEND/'decks/parser.py').read_bytes())
    constants = [node for node in tree.body if isinstance(node, ast.Assign)]
    exec(compile(ast.Module(body=constants, type_ignores=[]), 'actual-parser-regex-source', 'exec'), parser)
    path = BACKEND/'scripts/matchup_round_robin.py'
    api = {'__file__': str(path), '__name__': 'canonical_admission_projection',
           '__builtins__': dict(vars(builtins))}
    exec(compile(path.read_bytes(), str(path), 'exec'), api)
    real_import = builtins.__import__
    modules = {'card_data.hydration': SimpleNamespace(ready_for_match=hydration['ready_for_match']),
               'card_data.fallback_cards': SimpleNamespace(FALLBACK_CARD_DATA=seed)}
    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        return modules[name] if name in modules else real_import(name, globals, locals, fromlist, level)
    api['__builtins__']['__import__'] = imports
    repo = SimpleNamespace(list_cards=lambda: [SimpleNamespace(name=value['name']) for value in seed.values()],
                           list_card_knowledge_names=lambda: [])
    deck_parser = parser['DeckParser'](repo)
    by_canonical = {value['name']: value for value in seed.values()}
    rows = []
    for name, text in api['builtin_templates']().items():
        parsed = deck_parser.parse(text)
        if parsed.errors or parsed.suggestions:
            raise AssertionError('Full shipped builtin must parse without suggestions')
        boards = {key: [dict(copy.deepcopy(by_canonical[card['card_name']]), **card)
                        for card in getattr(parsed, key)] for key in ('mainboard', 'sideboard')}
        rows.append(dict(source='builtin', id=None, name=name, classification_status='unknown',
                         archetype='Unknown', **boards))
    return api, rows, seed, hydration['ready_for_match']


class CanonicalAdmissionTests(unittest.TestCase):
    def test_all11_actual_parser_full_canonical_names_and_seed_admit_unchanged(self):
        api, rows, seed, ready = fixture()
        before = copy.deepcopy(rows)
        self.assertEqual(len(rows), 11)
        self.assertTrue(any(' // ' in card['card_name'] for row in rows for card in row['mainboard']))
        self.assertTrue(all(ready(card) for row in rows for key in ('mainboard', 'sideboard') for card in row[key]))
        try:
            api['admit_execution_rows'](rows)
        except ValueError as error:
            self.fail('Exact canonical DeckParser inventory rejected: '+str(error))
        self.assertEqual(api['canonical_bytes'](rows), api['canonical_bytes'](before))

    def test_all11_exact_printed_seed_keys_still_admit(self):
        api, rows, seed, _ = fixture()
        printed = {value['name']: key for key, value in seed.items()}
        for row in rows:
            for key in ('mainboard', 'sideboard'):
                for card in row[key]:
                    card['card_name'] = printed[card['card_name']]
        before = copy.deepcopy(rows)
        api['admit_execution_rows'](rows)
        self.assertEqual(rows, before)

    def test_exact_printed_and_canonical_alias_quantities_aggregate_without_mutation(self):
        api, rows, seed, _ = fixture()
        board = rows[0]['mainboard']
        card = next(card for card in board if ' // ' in card['card_name'] and card['quantity'] > 1)
        printed = next(key for key, value in seed.items() if value['name'] == card['card_name'])
        extra = dict(copy.deepcopy(card), quantity=1, card_name=printed)
        card['quantity'] -= 1
        board.append(extra)
        before = copy.deepcopy(rows)
        try:
            api['admit_execution_rows'](rows)
        except ValueError as error:
            self.fail('Exact seed alias quantity conservation rejected: '+str(error))
        self.assertEqual(rows, before)

    def test_foreign_seed_card_unknown_fuzzy_and_bogus_face_names_reject(self):
        api, rows, seed, _ = fixture()
        card = next(card for card in rows[0]['mainboard'] if ' // ' in card['card_name'])
        canonical = card['card_name']
        front, back = canonical.split(' // ')
        for name in ('Island', 'Unsupported Exact Card', front+' // Bogus Face', back,
                     canonical.lower(), canonical+' ', front.replace(' ', '-')):
            with self.subTest(name=name):
                card['card_name'] = name
                with self.assertRaises(ValueError):
                    api['admit_execution_rows'](rows)
        card['card_name'] = canonical

    def test_quantity_types_totals_and_board_membership_stay_exact(self):
        api, rows, _, _ = fixture()
        for quantity in (True, 1.0, 0, 251, rows[0]['mainboard'][0]['quantity']+1):
            with self.subTest(quantity=quantity):
                changed = copy.deepcopy(rows)
                changed[0]['mainboard'][0]['quantity'] = quantity
                with self.assertRaises(ValueError):
                    api['admit_execution_rows'](changed)
        for key in ('mainboard', 'sideboard'):
            changed = copy.deepcopy(rows)
            changed[0][key].append(copy.deepcopy(changed[0]['mainboard'][0]))
            with self.assertRaises(ValueError):
                api['admit_execution_rows'](changed)

    def test_actual_readiness_rejects_incomplete_faces_and_malformed_printed_body(self):
        api, rows, _, ready = fixture()
        for mutation in ('faces', 'layout', 'oracle', 'type'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(rows)
                card = next(card for card in changed[0]['mainboard'] if ' // ' in card['card_name'])
                if mutation == 'faces':
                    card['card_faces'] = card['card_faces'][:1]
                elif mutation == 'layout':
                    card['layout'] = 'token'
                elif mutation == 'oracle':
                    card['oracle_text'] = 1
                else:
                    card['type_line'] = ''
                self.assertFalse(ready(card))
                with self.assertRaises(ValueError):
                    api['admit_execution_rows'](changed)
