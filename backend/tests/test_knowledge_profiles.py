"""Deterministic data estimates, not gameplay/AI-strength or canonicality proofs."""
import copy
import dataclasses
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND/'tests/vraska_full/fixtures'
SEED = json.loads((BACKEND/'card_data/builtin_oracle_seed.json').read_text())['cards']


class Profiles(unittest.TestCase):
    def api(self):
        try:
            return importlib.import_module('knowledge.profiles')
        except ModuleNotFoundError as error:
            if error.name == 'knowledge.profiles':
                self.fail('NEW profile API absent')
            raise

    def raw(self, filename):
        raw = (FIXTURES/filename).read_bytes()
        pins = json.loads((FIXTURES/'PROVENANCE.json').read_text())['fixture_bytes']
        self.assertEqual(hashlib.sha256(raw).hexdigest(), pins[filename])
        return json.loads(raw)

    def profile(self, raw, corpus=()):
        return self.api().derive_profile(raw, corpus)

    def test_profile_api_and_frozen_dataclass(self):
        p = self.profile(self.raw('lightning-bolt.json'))
        self.assertTrue(dataclasses.is_dataclass(p))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            p.play_value = 99
        self.assertEqual(p.schema_version, 1)
        self.assertEqual(p.estimator_version, 'deterministic-tactical-v1')

    def test_ten_pinned_canonical_threat_and_window_values(self):
        rows = [('lightning-bolt.json', 1, 'instant_window'),
                ('divination.json', 1, 'main_phase'),
                ('grizzly-bears-scryfall-raw.json', 1, 'main_phase'),
                ('colossal-dreadmaw.json', 2, 'main_phase'),
                ('craw-wurm.json', 2, 'main_phase'),
                ('forest.json', 0, 'land_play'), ('island-scryfall-raw.json', 0, 'land_play'),
                ('mountain.json', 0, 'land_play'), ('plains.json', 0, 'land_play'),
                ('swamp.json', 0, 'land_play')]
        for filename, threat, window in rows:
            with self.subTest(filename=filename):
                p = self.profile(self.raw(filename))
                self.assertEqual(p.threat_level, threat)
                self.assertIn(window, p.cast_windows)

    def test_ten_name_metamorphic_canonical_rows(self):
        for filename in ('lightning-bolt.json', 'divination.json', 'grizzly-bears-scryfall-raw.json',
                         'colossal-dreadmaw.json', 'craw-wurm.json', 'forest.json',
                         'island-scryfall-raw.json', 'mountain.json', 'plains.json', 'swamp.json'):
            raw = self.raw(filename)
            renamed = copy.deepcopy(raw)
            renamed['oracle_text'] = raw.get('oracle_text', '').replace(raw['name'], 'Anonymous source')
            renamed['name'] = 'Anonymous source'
            a, b = self.profile(raw), self.profile(renamed)
            self.assertEqual((a.play_value, a.threat_level, a.tags, a.answerable_by, a.cast_windows),
                             (b.play_value, b.threat_level, b.tags, b.answerable_by, b.cast_windows))

    def test_canonical_numeric_effect_payload_and_curve_value(self):
        raw = self.raw('divination.json')
        p = self.profile(raw)
        self.assertEqual(p.ability_specs[0]['effects'][0]['payload']['amount'], 2)
        self.assertEqual(p.ability_specs[0]['effects'][0]['effect_key'], 'draw_cards')
        self.assertEqual(p.play_value, round(3+1+(2*.8)/3, 3))
        corpus = [{'quantity': 4, 'card_metadata': raw}]
        self.assertEqual(self.profile(raw, corpus).play_value, round(3+2+(2*.8)/3, 3))

    def test_supreme_verdict_sweep_uncounterable_and_registry_keys(self):
        from effects.registry import EFFECT_HANDLERS
        p = self.profile(SEED['Supreme Verdict'])
        self.assertEqual(p.threat_level, 3)
        self.assertNotIn('counter_spell', p.answerable_by)
        self.assertTrue(set(p.answerable_by) <= set(EFFECT_HANDLERS))

    def test_haste_does_not_grant_cast_window(self):
        p = self.profile({'name': 'Unrelated', 'type_line': 'Creature', 'mana_cost': '{R}',
                          'oracle_text': 'Haste', 'power': '1', 'toughness': '1'})
        self.assertEqual(p.cast_windows, ('main_phase',))
        self.assertTrue(p.attack_on_entry_hint)

    def test_flash_is_conditional_window_not_action_permission(self):
        p = self.profile({'name': 'Unrelated', 'type_line': 'Creature', 'mana_cost': '{U}',
                          'oracle_text': 'Flash', 'power': '1', 'toughness': '1'})
        self.assertIn('instant_window', p.cast_windows)
        self.assertIn('priority_timing_costs_targets_not_evaluated', p.limitations)

    def test_keyword_grant_and_conditional_keywords_not_intrinsic(self):
        for text in ('Target creature gains flash until end of turn.',
                     'As long as you control an artifact, this creature has flash.'):
            p = self.profile({'name': 'Unrelated', 'type_line': 'Creature', 'oracle_text': text})
            self.assertEqual(p.cast_windows, ('main_phase',))

    def test_hexproof_routes_controller_conditional_and_sweep_survives(self):
        p = self.profile({'name': 'Unrelated', 'type_line': 'Creature', 'oracle_text': 'Hexproof'})
        self.assertNotIn('destroy_permanent', p.answerable_by)
        own = next(r for r in p.answer_routes if r.effect_key == 'destroy_permanent')
        self.assertIn('targeter_is_controller', own.conditions)
        self.assertIn('destroy_all_creatures', p.answerable_by)
        self.assertIn('counter_spell', p.answerable_by)

    def test_shroud_indestructible_protection_have_distinct_routes(self):
        p = self.profile({'name': 'Unrelated', 'type_line': 'Creature', 'oracle_text': 'Shroud'})
        self.assertFalse({'destroy_permanent', 'exile'} & set(p.answerable_by))
        p = self.profile({'name': 'Unrelated', 'type_line': 'Creature', 'oracle_text': 'Indestructible'})
        self.assertNotIn('destroy_permanent', p.answerable_by)
        self.assertNotIn('destroy_all_creatures', p.answerable_by)
        self.assertIn('exile', p.answerable_by)
        p = self.profile({'name': 'Unrelated', 'type_line': 'Creature', 'oracle_text': 'Protection from red'})
        self.assertIn('incoming_source_quality_and_protection_must_be_checked', p.limitations)

    def test_unknown_tail_never_assigns_compiled_numeric_payoff(self):
        raw = self.raw('divination.json');raw['oracle_text'] += ' Unrecognized future instruction.'
        p = self.profile(raw)
        self.assertEqual(p.ability_specs[0]['effects'], [])
        self.assertEqual(p.play_value, 4.0)
        self.assertIn('uncompiled_effect_surface', p.limitations)

    def test_dynamic_token_quantity_not_zero_or_one_guess(self):
        p = self.profile({'name': 'Unrelated', 'type_line': 'Sorcery', 'mana_cost': '{X}{G}',
                          'oracle_text': 'Create X 1/1 green Elf creature tokens.'})
        self.assertIn('dynamic_or_unknown_numeric_payload', p.limitations)
        self.assertFalse(any(e.get('payload', {}).get('amount') in (0, 1)
                             for a in p.ability_specs for e in a['effects']))

    def test_self_etb_numeric_payoff_and_other_entry_not_etb(self):
        raw = {'name': 'Unrelated', 'type_line': 'Creature', 'mana_cost': '{3}{U}',
               'oracle_text': 'When this creature enters, draw two cards.', 'power': '2', 'toughness': '2'}
        self.assertEqual(self.profile(raw).etb_impact, 1.6)
        raw['oracle_text'] = 'Whenever another creature enters, draw two cards.'
        self.assertEqual(self.profile(raw).etb_impact, 0.0)

    def test_faces_have_distinct_types_and_windows_no_parent_union(self):
        raw = {'name': 'Front // Back', 'layout': 'modal_dfc', 'card_faces': [
            {'name': 'Front', 'type_line': 'Land', 'oracle_text': '{T}: Add {U}.'},
            {'name': 'Back', 'type_line': 'Instant', 'mana_cost': '{U}', 'oracle_text': 'Draw a card.'}]}
        p = self.profile(raw)
        self.assertEqual(p.types, ('land',))
        self.assertEqual(p.cast_windows, ('land_play',))
        self.assertEqual(p.faces[1].types, ('instant',))
        self.assertIn('instant_window', p.faces[1].cast_windows)

    def test_cardinstance_style_metadata_adapter(self):
        raw = self.raw('grizzly-bears-scryfall-raw.json')
        p = self.profile(raw)
        other = self.profile(SimpleNamespace(**raw))
        self.assertEqual((p.play_value, p.threat_level, p.tags),
                         (other.play_value, other.threat_level, other.tags))

    def test_full_legacy_profile_and_raw_rulings_preserved(self):
        raw = self.raw('lightning-bolt.json')
        original = {'card_data': raw, 'rulings_verified': True, 'rulings': [],
                    'unknown_future_namespace': {'keep': [1, 2]}, 'tactical_tags': ['legacy'], 'schema_version': 1}
        before = copy.deepcopy(original)
        p = self.profile(raw)
        merged = self.api().merge_profile_payload(original, p)
        self.assertEqual(original, before)
        for key in original:self.assertEqual(merged[key], original[key])
        self.assertEqual(merged['tactical_profile']['play_value'], p.play_value)
        merged['card_data']['name'] = 'Mutated result'
        self.assertEqual(original, before)

    def test_seed_corpus_deterministic_bounded_nonmutating(self):
        api = self.api();before = copy.deepcopy(SEED)
        for raw in SEED.values():
            one, two = self.profile(raw), self.profile(raw)
            self.assertEqual(api.profile_payload(one), api.profile_payload(two))
            self.assertTrue(0 <= one.play_value <= 10)
            self.assertIn(one.threat_level, (0, 1, 2, 3))
            json.dumps(api.profile_payload(one), sort_keys=True, allow_nan=False)
        self.assertEqual(SEED, before)

    def test_resource_limits_before_derivation(self):
        api = self.api()
        for raw in ({'oracle_text': 'x'*16385}, {'card_faces': [{}]*17}):
            with self.assertRaises(ValueError):api.derive_profile(raw)

    def test_direct_legacy_field_functions_match_profile(self):
        api = self.api();raw = self.raw('lightning-bolt.json');p = self.profile(raw)
        for name in ('play_value','threat_level','answerable_by','cast_windows','etb_impact'):
            self.assertEqual(getattr(api, name)(raw), getattr(p, name))

    def test_archetype_context_is_explicit_and_raw_corpus_supported(self):
        api = self.api();raw = self.raw('divination.json');corpus = (raw,)
        pooled = api.derive_profile(raw, corpus)
        declared = api.derive_profile(raw, corpus, archetype='Control')
        self.assertEqual(pooled.context['mode'], 'supplied_corpus')
        self.assertIsNone(pooled.context['archetype'])
        self.assertEqual(declared.context['mode'], 'supplied_archetype')
        self.assertEqual(declared.context['archetype'], 'Control')
        self.assertEqual(declared.context['archetype_verification'], 'caller_declared_not_verified')
        self.assertEqual(pooled.play_value, declared.play_value)
        self.assertEqual(pooled.context['corpus_fingerprint'], declared.context['corpus_fingerprint'])
        self.assertEqual(api.merge_profile({}, declared), api.merge_profile_payload({}, declared))

    def test_conditional_uncounterable_never_blanket_blocks_counter_route(self):
        raw = {'name': 'Unrelated', 'type_line': 'Instant', 'mana_cost': '{U}',
               'oracle_text': "If you control an artifact, this spell can't be countered."}
        self.assertIn('counter_spell', self.profile(raw).answerable_by)

    def test_nested_face_limits_and_nonfinite_statistics_rejected(self):
        api = self.api()
        with self.assertRaises(ValueError):
            api.derive_profile({'card_faces': [{'oracle_text': 'x'*16385}]})
        with self.assertRaises(ValueError):
            api.derive_profile({'type_line': 'Creature', 'power': float('inf')})

    def test_existing_tactical_namespace_unknown_fields_survive_refresh(self):
        api = self.api();profile = self.profile(self.raw('divination.json'))
        previous = {'tactical_profile': {'future_hint': {'keep': [7]}, 'play_value': -1}}
        before = copy.deepcopy(previous)
        merged = api.merge_profile(previous, profile)
        self.assertEqual(merged['tactical_profile']['future_hint'], {'keep': [7]})
        self.assertEqual(merged['tactical_profile']['play_value'], profile.play_value)
        self.assertEqual(previous, before)

    def test_opaque_tactical_namespace_rejected_not_discarded(self):
        api = self.api();profile = self.profile(self.raw('divination.json'))
        previous = {'tactical_profile': ['future opaque data']}
        with self.assertRaises(ValueError):api.merge_profile(previous, profile)
        self.assertEqual(previous, {'tactical_profile': ['future opaque data']})

    def test_raw_parenthetical_tail_never_masked_into_numeric_payoff(self):
        raw = self.raw('divination.json')
        raw['oracle_text'] += ' (Unrecognized mandatory extra instruction.)'
        p = self.profile(raw)
        self.assertEqual(p.ability_specs[0]['effects'], [])
        self.assertEqual(p.play_value, 4.0)

    def test_raw_quoted_tail_never_masked_into_numeric_payoff(self):
        raw = self.raw('divination.json')
        raw['oracle_text'] += ' "Unrecognized future instruction."'
        p = self.profile(raw)
        self.assertEqual(p.ability_specs[0]['effects'], [])
        self.assertEqual(p.play_value, 4.0)
