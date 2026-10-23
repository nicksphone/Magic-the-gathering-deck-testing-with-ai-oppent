"""Metadata-only checks: restored legacy constructors are never executed."""
import ast
import hashlib
import json
from pathlib import Path
import unittest

from tests.interface_scope_compatibility import restore_printed_protocol_source


ROOT = Path(__file__).parent
MODULE = 'test_events_apnap.py'
RECIPES = json.loads((ROOT / 'fixtures/interface_scope_compatibility/'
                     'reviewed_task13_fixture_inverses.json').read_bytes())['functions']
GOLDEN = ROOT / 'fixtures/rules_printed_facts_e4/UNCHANGED_FUNCTION_SHA256.json'


def segment(source, name):
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(nodes) == 1
    return ast.get_source_segment(source, nodes[0])


def reviewed_versions():
    source = (ROOT / MODULE).read_text()
    recipes = list(RECIPES.items())
    for mask in range(8):
        text = source
        for bit, (identity, recipe) in enumerate(recipes):
            name = identity.split(':')[1]
            current = segment(text, name)
            digest = hashlib.sha256(current.encode()).hexdigest()
            if digest == recipe['new_sha256']:
                for hunk in reversed(recipe['hunks']):
                    assert current.count(hunk['new']) == 1
                    current = current.replace(hunk['new'], hunk['old'], 1)
            assert hashlib.sha256(current.encode()).hexdigest() == recipe['old_sha256']
            if mask & (1 << bit):
                for hunk in recipe['hunks']:
                    assert current.count(hunk['old']) == 1
                    current = current.replace(hunk['old'], hunk['new'], 1)
                assert hashlib.sha256(current.encode()).hexdigest() == recipe['new_sha256']
            text = text.replace(segment(text, name), current, 1)
        yield text


class FixtureSourceInverseTests(unittest.TestCase):
    def test_all_eight_reviewed_constructor_combinations_restore_exact_hashes(self):
        for source in reviewed_versions():
            restored = restore_printed_protocol_source(MODULE, source)
            for identity, recipe in RECIPES.items():
                actual = segment(restored, identity.split(':')[1])
                self.assertEqual(hashlib.sha256(actual.encode()).hexdigest(), recipe['old_sha256'])

    def test_restoration_is_idempotent(self):
        for source in reviewed_versions():
            restored = restore_printed_protocol_source(MODULE, source)
            self.assertEqual(restore_printed_protocol_source(MODULE, restored), restored)

    def test_changed_constructor_hunks_are_rejected(self):
        source = list(reviewed_versions())[-1]
        for identity, recipe in RECIPES.items():
            name = identity.split(':')[1]
            old = segment(source, name)
            hunk = recipe['hunks'][0]['new']
            mutation = hunk.replace('Soul Warden', 'Unreviewed Warden').replace(
                '_seal_of_removal_card(', '_unreviewed_seal_card(')
            changed = old.replace(hunk, mutation, 1)
            self.assertNotEqual(old, changed)
            with self.assertRaises(AssertionError):
                restore_printed_protocol_source(MODULE, source.replace(old, changed, 1))

    def test_outside_hunk_assertion_and_pose_changes_are_rejected(self):
        source = list(reviewed_versions())[-1]
        for identity in RECIPES:
            old = segment(source, identity.split(':')[1])
            for suffix in ('\n    assert False', '\n    state.active_player = 2'):
                with self.assertRaises(AssertionError):
                    restore_printed_protocol_source(MODULE, source.replace(old, old + suffix, 1))

    def test_missing_duplicate_and_unknown_protected_functions_are_rejected(self):
        source = list(reviewed_versions())[-1]
        old = segment(source, next(iter(RECIPES)).split(':')[1])
        for changed in (source.replace(old, '', 1), source + '\n\n' + old + '\n'):
            with self.assertRaises(AssertionError):
                restore_printed_protocol_source(MODULE, changed)
        with self.assertRaises(AssertionError):
            restore_printed_protocol_source('unreviewed.py', source)

    def test_original_golden_and_unrelated_sibling_remain_exact(self):
        self.assertEqual(hashlib.sha256(GOLDEN.read_bytes()).hexdigest(),
                         '94a314f7a95f8a1f538f06c181c274324b2afef2d97414f8d1c8ce29dd7e3559')
        source = list(reviewed_versions())[-1]
        sibling = '\n\ndef unreviewed_sibling():\n    return "untouched"\n'
        restored = restore_printed_protocol_source(MODULE, source + sibling)
        self.assertTrue(restored.endswith(sibling))
        for identity, digest in json.loads(GOLDEN.read_bytes()).items():
            filename, name = identity.split(':')
            if filename == MODULE:
                actual = segment(restored, name)
                self.assertEqual(hashlib.sha256(actual.encode()).hexdigest(), digest)
