"""Pure consumer contract; inert row descriptors, no repository or gameplay proof."""
from copy import deepcopy
from dataclasses import fields
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from card_data.tactical import printed_card_types, tactical_tags
from game_state.state import CardInstance
from knowledge.profiles import derive_profile, merge_profile_payload


FIXTURES = Path(__file__).parent / 'fixtures/knowledge_profiles'
RAW_BYTES = (FIXTURES / 'seed155-scryfall.jsonl').read_bytes()
RAW = {card['name']: card for card in map(json.loads, RAW_BYTES.splitlines())}


class KnowledgeSnapshotContract(unittest.TestCase):
    def api(self):
        try:
            return importlib.import_module('knowledge.service')
        except ModuleNotFoundError as error:
            if error.name == 'knowledge.service':
                self.fail('Task2.2 knowledge.service consumer API absent')
            raise

    def fixture(self, name='Lightning Bolt'):
        provenance = json.loads((FIXTURES / 'PROVENANCE.json').read_bytes())
        self.assertEqual(hashlib.sha256(RAW_BYTES).hexdigest(), provenance['snapshot_sha256'])
        raw = deepcopy(RAW[name])
        profile = merge_profile_payload({'card_data': raw, 'rulings_verified': False,
                                         'rulings': [], 'future_key': {'retain': True}},
                                        derive_profile(raw))
        row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'],
                              oracle_source='scryfall', profiles_json=json.dumps(profile))
        surface = raw['card_faces'][0] if raw.get('card_faces') else raw
        hydrated = {'card_name': name, 'name': raw['name'], 'layout': raw['layout'],
                    'card_faces': deepcopy(raw.get('card_faces', []))}
        hydrated.update({key: surface.get(key, '') for key in ('oracle_text', 'type_line', 'mana_cost')})
        return raw, row, hydrated

    def card(self, raw, hydrated, snapshot):
        return SimpleNamespace(name=raw['name'], oracle_text=hydrated['oracle_text'],
                               type_line=hydrated['type_line'], mana_cost=hydrated['mana_cost'],
                               types=list(printed_card_types(hydrated['type_line'])),
                               layout=raw['layout'], card_faces=deepcopy(raw.get('card_faces', [])),
                               selected_face_index=None, knowledge_snapshot=deepcopy(snapshot))

    def test_canonical_persisted_tags_without_mutating_raw_or_row(self):
        api = self.api()
        raw, row, hydrated = self.fixture()
        before = deepcopy((raw, vars(row), hydrated))
        snapshot = api.snapshot_for(row, raw['name'], hydrated)
        self.assertIsInstance(snapshot, dict)
        result = api.tags_for(self.card(raw, hydrated, snapshot))
        self.assertEqual(result.source, 'persisted')
        self.assertEqual(set(result.tags), set(derive_profile(raw).tags))
        self.assertEqual((raw, vars(row), hydrated), before)

    def test_missing_carrier_uses_exact_existing_tactical_fallback(self):
        api = self.api()
        raw, row, hydrated = self.fixture()
        card = self.card(raw, hydrated, {})
        card.name = 'Bolt Spike Shock Lava without identity authority'
        card.oracle_text = 'Draw a card.'
        result = api.tags_for(card)
        self.assertEqual(result.source, 'fallback')
        self.assertEqual(set(result.tags), tactical_tags(card.oracle_text, card.type_line, card.types))
        self.assertNotIn('burn', result.tags)

    def test_row_printing_mismatch_is_not_admitted(self):
        api = self.api()
        raw, row, hydrated = self.fixture()
        row.scryfall_id = 'wrong-printing'
        self.assertIsNone(api.snapshot_for(row, raw['name'], hydrated))

    def test_profile_source_body_hash_mismatch_is_not_admitted(self):
        api = self.api()
        raw, row, hydrated = self.fixture()
        profile = json.loads(row.profiles_json)
        profile['tactical_profile']['input_sha256'] = '0' * 64
        row.profiles_json = json.dumps(profile)
        self.assertIsNone(api.snapshot_for(row, raw['name'], hydrated))

    def test_final_cache_surface_conflict_is_not_admitted(self):
        api = self.api()
        raw, row, hydrated = self.fixture()
        hydrated['oracle_text'] = 'Draw a card.'
        self.assertIsNone(api.snapshot_for(row, raw['name'], hydrated))

    def test_unknown_profile_version_is_not_admitted(self):
        api = self.api()
        raw, row, hydrated = self.fixture()
        profile = json.loads(row.profiles_json)
        profile['tactical_profile']['schema_version'] = 999
        row.profiles_json = json.dumps(profile)
        self.assertIsNone(api.snapshot_for(row, raw['name'], hydrated))

    def test_forged_tags_do_not_borrow_correct_source_hash(self):
        api = self.api()
        raw, row, hydrated = self.fixture()
        profile = json.loads(row.profiles_json)
        profile['tactical_profile']['tags'] = ['ramp']
        row.profiles_json = json.dumps(profile)
        self.assertIsNone(api.snapshot_for(row, raw['name'], hydrated))

    def test_actual_adventure_second_face_uses_only_its_persisted_tags(self):
        api = self.api()
        raw, row, hydrated = self.fixture('Bonecrusher Giant // Stomp')
        snapshot = api.snapshot_for(row, 'Bonecrusher Giant', hydrated)
        self.assertIsInstance(snapshot, dict)
        card = self.card(raw, hydrated, snapshot)
        face = raw['card_faces'][1]
        card.selected_face_index = 1
        for key in ('name', 'oracle_text', 'type_line', 'mana_cost'):
            setattr(card, key, face.get(key, ''))
        card.types = list(printed_card_types(card.type_line))
        result = api.tags_for(card)
        self.assertEqual(result.source, 'persisted')
        self.assertEqual(result.face_index, 1)
        self.assertEqual(set(result.tags), set(derive_profile(raw).faces[1].tags))

    def test_selected_face_outside_actual_roster_falls_back(self):
        api = self.api()
        raw, row, hydrated = self.fixture('Bonecrusher Giant // Stomp')
        snapshot = api.snapshot_for(row, 'Bonecrusher Giant', hydrated)
        card = self.card(raw, hydrated, snapshot)
        card.selected_face_index = 99
        self.assertEqual(api.tags_for(card).source, 'fallback')

    def test_opaque_unknown_never_reads_private_carrier(self):
        api = self.api()

        class Opaque:
            ai_unknown = True
            name = ''
            types = []

            @property
            def knowledge_snapshot(self):
                raise AssertionError('Unknown identity carrier was accessed')

        result = api.tags_for(Opaque())
        self.assertEqual(result.source, 'opaque')
        self.assertEqual(set(result.tags), set())

    def test_card_carrier_has_empty_default_not_global_name_lookup(self):
        self.assertIn('knowledge_snapshot', {field.name for field in fields(CardInstance)})
        from game_state.state import Zone
        card = CardInstance('inert', '', 1, 1, Zone.LIBRARY)
        self.assertFalse(card.knowledge_snapshot)

    def test_decision_usage_field_is_optional_without_altering_existing_fields(self):
        from ai.agent import AIDecision
        self.assertIn('knowledge_usage', {field.name for field in fields(AIDecision)})
        decision = AIDecision(action={'type': 'pass_priority'}, reasoning='Existing reason')
        self.assertEqual(decision.action, {'type': 'pass_priority'})
        self.assertEqual(decision.reasoning, 'Existing reason')
        self.assertFalse(decision.knowledge_usage)
