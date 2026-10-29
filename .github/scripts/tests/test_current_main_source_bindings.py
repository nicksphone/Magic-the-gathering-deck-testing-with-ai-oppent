"""Exact public Main admission; no application imports or service execution."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[3]
MAIN_SHA256 = '4bc041adc47412fb97f0b4527ada9ca2f823c27dea4bb999fd9b95cee997512c'


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CurrentMainSourceBindingsTests(unittest.TestCase):
    def setUp(self):
        self.api = load('backend/tests/interface_scope_compatibility.py',
                        'current_main_compatibility')
        self.generator = load('backend/scripts/generate_startup_media_pins.py',
                              'current_startup_media_generator')
        self.main = (SOURCE / 'backend/main.py').read_bytes()
        self.assertEqual(hashlib.sha256(self.main).hexdigest(), MAIN_SHA256)

    def test_current_main_retains_exact_production_hash_admission(self):
        historical = self.api.CONTRACT['production']['main.py']['old_sha256']
        self.assertEqual(self.api.compatible_product_hash('main.py', self.main, historical),
                         MAIN_SHA256)

    def test_current_main_restores_exact_reviewed_cold_http_ancestor(self):
        historical = self.api.ACCEPTED_MAIN_DELTA['old_sha256']
        restored = self.api.restore_reviewed_source('main.py', self.main, historical)
        self.assertEqual(hashlib.sha256(restored).hexdigest(), historical)

    def test_startup_media_admits_only_the_current_main_source_digest(self):
        self.assertEqual(self.generator.SOURCE_MODULE_PINS['backend/main.py'], MAIN_SHA256)
        self.assertEqual(self.generator.PUBLIC_INPUT_PINS['backend/main.py'], MAIN_SHA256)

    def test_later_symlink_rejection_is_not_masked_by_stale_main_pin(self):
        with tempfile.TemporaryDirectory(prefix='current-main-symlink-') as directory:
            root = Path(directory)
            for relative in self.generator.PUBLIC_INPUT_PINS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SOURCE / relative, target)
            relative = 'backend/decks/bootstrap.py'
            target = root / relative
            target.unlink()
            target.symlink_to(SOURCE / relative)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                self.generator.build_artifact(root)

    def test_unapproved_bytes_outside_current_main_delta_still_reject(self):
        historical = self.api.CONTRACT['production']['main.py']['old_sha256']
        with self.assertRaises(AssertionError):
            self.api.compatible_product_hash('main.py', self.main + b'\n# unapproved\n', historical)

    def test_unapproved_policy_field_change_inside_delta_still_rejects(self):
        changed = self.main.replace(b'policy_provenance: dict[int, dict]',
                                    b'policy_provenance: dict[int, object]', 1)
        self.assertNotEqual(changed, self.main)
        historical = self.api.ACCEPTED_MAIN_DELTA['old_sha256']
        with self.assertRaises(AssertionError):
            self.api.restore_reviewed_source('main.py', changed, historical)

    def test_full_land_choice_comparison_mutation_still_rejects(self):
        changed = self.main.replace(b'if complete_action(move) == chosen:',
                                    b'if complete_action(move) != chosen:', 1)
        self.assertNotEqual(changed, self.main)
        historical = self.api.ACCEPTED_MAIN_DELTA['old_sha256']
        with self.assertRaises(AssertionError):
            self.api.restore_reviewed_source('main.py', changed, historical)

    def test_existing_repository_admission_and_unknown_mutation_stay_strict(self):
        name = 'persistence/repository.py'
        raw = (SOURCE / 'backend' / name).read_bytes()
        historical = self.api.CONTRACT['production'][name]['old_sha256']
        self.assertEqual(self.api.compatible_product_hash(name, raw, historical),
                         hashlib.sha256(raw).hexdigest())
        with self.assertRaises(AssertionError):
            self.api.compatible_product_hash(name, raw + b'\n# unapproved\n', historical)


if __name__ == '__main__':
    unittest.main()
