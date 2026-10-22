"""Own temporary-file and admission protocols; no Docker or application process."""
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest


class HostedReportTests(unittest.TestCase):
    def module(self):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/host.py'
        spec = importlib.util.spec_from_file_location('hosted_report_subject', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_artifact_directory_must_not_follow_guest_symlink(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            target.mkdir()
            link = root / 'link'
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(ValueError):
                m.write_report(link, 'lifecycle', m.empty_report('lifecycle', 'a' * 40))
            self.assertEqual(list(target.iterdir()), [])

    def test_artifact_regular_file_must_not_overwrite_another_hardlink(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'other'
            target.write_text('OWNED_CANARY')
            os.link(target, root / 'lifecycle.json')
            with self.assertRaises(ValueError):
                m.write_report(root, 'lifecycle', m.empty_report('lifecycle', 'a' * 40))
            self.assertEqual(target.read_text(), 'OWNED_CANARY')

    def test_new_provisioning_admission_counts_image_tools_and_work(self):
        m = self.module()
        self.assertTrue(callable(getattr(m, 'admit_storage', None)))
        self.assertIsNone(m.admit_storage(16 * 1024**3, 5 * 1024**3))
        with self.assertRaises(ValueError):
            m.admit_storage(16 * 1024**3 + 1, 5 * 1024**3)

    def test_start_floor_is_not_lowered_or_bool_coerced(self):
        m = self.module()
        self.assertTrue(callable(getattr(m, 'admit_storage', None)))
        for total, free in ((1, 5 * 1024**3 - 1), (True, 6 * 1024**3), (1, True)):
            with self.subTest(total=total, free=free), self.assertRaises(ValueError):
                m.admit_storage(total, free)
