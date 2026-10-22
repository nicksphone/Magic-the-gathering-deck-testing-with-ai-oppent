"""Real capsule admission over Git's NUL records; no Git child or shared index."""
import importlib.util
from pathlib import Path
import unittest


class HostedIndexTests(unittest.TestCase):
    def subject(self):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/host.py'
        spec = importlib.util.spec_from_file_location('hosted_index_subject', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(getattr(module, 'validate_index', None)), 'Admit the actual populated index')
        return module

    def records(self):
        oid = b'a' * 40
        tree = b'100644 blob ' + oid + b'\tfile\0' + b'100755 blob ' + oid + b'\tsub/tool\0'
        index = b'100644 ' + oid + b' 0\tfile\0' + b'100755 ' + oid + b' 0\tsub/tool\0'
        return tree, index

    def test_full_populated_index_matches_every_head_blob(self):
        module = self.subject()
        tree, index = self.records()
        self.assertEqual(module.validate_index(tree, index), 2)
        self.assertEqual(module.validate_index(tree, b'\0'.join(reversed(index[:-1].split(b'\0'))) + b'\0'), 2)

    def test_missing_empty_partial_foreign_or_unmerged_index_rejected(self):
        module = self.subject()
        tree, index = self.records()
        for bad in (b'', index.split(b'\0', 1)[0] + b'\0', index + index,
                    index.replace(b' 0\t', b' 2\t'), index.replace(b'file\0', b'other\0'),
                    index.replace(b'a' * 40, b'b' * 40), index[:-1]):
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                module.validate_index(tree, bad)

    def test_real_workflow_populates_own_index_and_host_checks_before_pull(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / '.github/workflows/hosted-clean-install.yml').read_text()
        self.assertIn('git --git-dir="$root/capsule" read-tree "$GITHUB_SHA"', workflow)
        host = (root / 'ops/ci/hosted-clean/host.py').read_text()
        self.assertIn("'ls-tree', '-r', '-z', 'HEAD'", host)
        self.assertIn("'ls-files', '--stage', '-z'", host)
        self.assertLess(host.index('validate_index(capture('), host.index("['docker', 'pull'"))
