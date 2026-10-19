"""Review regressions: canonical bytes and labeled inert schema variations only."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from knowledge.profiles import derive_profile

BACKEND = Path(__file__).resolve().parents[1]


class ReviewRegressions(unittest.TestCase):
    def divination(self):
        return json.loads((BACKEND/'tests/vraska_full/fixtures/divination.json').read_text())

    def sentinel(self):
        path = BACKEND/'tests/fixtures/ai_terminal_draw/darksteel-sentinel.raw.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         'cb8502e81d51884b604f60b56ca9adc85b8d943afde1ae585b714192f58bd423')
        return json.loads(path.read_text())

    def test_separate_parenthetical_raw_paragraph_blocks_numeric_payoff(self):
        raw = self.divination();raw['oracle_text'] += '\n(Unrecognized mandatory instruction.)'
        p = derive_profile(raw)
        self.assertFalse(any(spec['effects'] for spec in p.ability_specs))
        self.assertEqual(p.play_value, 4.0)
        self.assertIn('unaccounted_raw_paragraph', p.limitations)

    def test_separate_quoted_raw_paragraph_blocks_numeric_payoff(self):
        raw = self.divination();raw['oracle_text'] += '\n"Unrecognized mandatory instruction."'
        p = derive_profile(raw)
        self.assertFalse(any(spec['effects'] for spec in p.ability_specs))
        self.assertEqual(p.play_value, 4.0)

    def test_real_canonical_modal_parent_is_front_not_union(self):
        path = BACKEND/'tests/fixtures/graveyard_permissions/bala-ged-recovery.json'
        raw = json.loads(path.read_text());before = copy.deepcopy(raw)
        self.assertEqual(raw['layout'], 'modal_dfc')
        self.assertEqual(raw['type_line'], 'Sorcery // Land')
        p = derive_profile(raw)
        self.assertEqual(p.types, ('sorcery',))
        self.assertEqual(p.cast_windows, ('main_phase',))
        self.assertGreater(p.play_value, 0)
        self.assertEqual(p.faces[0].types, ('sorcery',))
        self.assertEqual(p.faces[1].types, ('land',))
        self.assertEqual(p.faces[1].cast_windows, ('land_play',))
        self.assertEqual(raw, before)

    def test_inert_instant_land_schema_variant_uses_front_face(self):
        # Explicit schema variation, not a fabricated canonical Oracle card.
        raw = {'name': 'Inert front // Inert back', 'layout': 'modal_dfc',
               'type_line': 'Instant // Land', 'card_faces': [
                   {'name': 'Inert front', 'type_line': 'Instant', 'mana_cost': '{U}', 'oracle_text': 'Draw a card.'},
                   {'name': 'Inert back', 'type_line': 'Land', 'oracle_text': '{T}: Add {U}.'}]}
        p = derive_profile(raw)
        self.assertEqual(p.types, ('instant',))
        self.assertIn('instant_window', p.cast_windows)
        self.assertGreater(p.play_value, 0)
        self.assertEqual(p.faces[1].types, ('land',))

    def test_canonical_flash_reminder_preserves_conditional_window(self):
        p = derive_profile(self.sentinel())
        self.assertIn('instant_window', p.cast_windows)
        self.assertIn('priority_timing_costs_targets_not_evaluated', p.limitations)

    def test_canonical_indestructible_reminder_preserves_response_traits(self):
        p = derive_profile(self.sentinel())
        self.assertNotIn('destroy_permanent', p.answerable_by)
        self.assertNotIn('destroy_all_creatures', p.answerable_by)
        self.assertIn('exile', p.answerable_by)
        self.assertIn('counter_spell', p.answerable_by)

    def test_keyword_grants_and_conditions_do_not_promote_intrinsic_traits(self):
        for text in ('Target creature gains flash until end of turn.',
                     'As long as you control an artifact, this creature has flash.',
                     'Target creature gains indestructible until end of turn.',
                     'As long as you control an artifact, this creature has indestructible.'):
            raw = {'name': 'Inert schema', 'type_line': 'Creature', 'mana_cost': '{U}', 'oracle_text': text}
            p = derive_profile(raw)
            self.assertEqual(p.cast_windows, ('main_phase',))
            self.assertIn('destroy_permanent', p.answerable_by)

    def test_multiple_numeric_bodies_blocked_by_unaccounted_raw(self):
        raw = {'name': 'Inert schema', 'type_line': 'Sorcery', 'mana_cost': '{U}',
               'oracle_text': 'Draw a card.\nDraw two cards.\n(Future unknown operation.)'}
        p = derive_profile(raw)
        self.assertFalse(any(spec['effects'] for spec in p.ability_specs))
        self.assertEqual(p.play_value, 4.0)
