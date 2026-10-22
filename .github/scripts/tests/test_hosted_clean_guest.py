"""Guest identity and inventory functions only; no actual guest/process/project."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class HostedGuestTests(unittest.TestCase):
    def module(self):
        root = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean'
        spec = importlib.util.spec_from_file_location('host', root / 'host.py')
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        spec = importlib.util.spec_from_file_location('hosted_guest_subject', root / 'guest.py')
        guest = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'host': host}):
            spec.loader.exec_module(guest)
        return guest

    def status(self, uid=1001, caps='0000000000000000', nnp=1):
        return '\n'.join(['Uid:\t' + '\t'.join([str(uid)] * 4),
                          'Gid:\t' + '\t'.join(['1001'] * 4),
                          'PPid:\t1', 'Groups:\t', 'NoNewPrivs:\t' + str(nnp),
                          *[name + ':\t' + caps for name in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')]])

    def test_actual_guest_identity_contract_requires_1001_and_zero_all_caps(self):
        m = self.module()
        self.assertTrue(callable(getattr(m, 'execution_identity', None)))
        self.assertEqual(m.execution_identity(self.status())['uid'], [1001] * 4)
        for status in (self.status(uid=0), self.status(uid=1000), self.status(caps='0000000000000001'), self.status(nnp=0)):
            with self.subTest(status=status), self.assertRaises(ValueError):
                m.execution_identity(status)

    def test_profile_includes_ownership_modes_dirs_and_links_without_following(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'directory').mkdir()
            (root / 'data').write_bytes(b'owned')
            (root / 'link').symlink_to('data')
            rows = m.profile(root)
            self.assertIn('uid', rows['data'])
            self.assertIn('directory', rows)
            self.assertEqual(rows['data']['uid'], os.getuid())
            self.assertEqual(rows['data']['gid'], os.getgid())
            self.assertEqual(rows['directory']['type'], 'directory')
            self.assertEqual(rows['link']['link'], 'data')
            self.assertNotIn('sha256', rows['link'])

    def test_setup_cap_list_is_finite_and_not_reused_for_app(self):
        root = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean'
        text = (root / 'host.py').read_text()
        self.assertIn("'--cap-drop=ALL'", text)
        for cap in ('CHOWN', 'DAC_OVERRIDE', 'FOWNER', 'FSETID', 'SETUID', 'SETGID', 'SETPCAP', 'KILL'):
            self.assertIn('--cap-add=' + cap, text)
        self.assertNotIn('--cap-add=SYS_ADMIN', text)
        self.assertIn('--bounding-set=-all', (root / 'entry.sh').read_text())

    def test_finite_identity_receipt_and_admitted_env_are_bound_before_app_commands(self):
        m = self.module()
        row = m.execution_identity(self.status())
        self.assertIn('schema', row)
        self.assertEqual(row['schema'], 1)
        self.assertEqual(set(row), {'schema', 'uid', 'gid', 'caps', 'no_new_privs', 'parent_pid'})
        root = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean'
        entry, guest = (root / 'entry.sh').read_text(), (root / 'guest.py').read_text()
        self.assertIn('MTG_UID="$MTG_UID" MTG_GID="$MTG_GID"', entry)
        self.assertIn("os.environ['MTG_UID'] == os.environ['MTG_GID'] == '1001'", guest)
        self.assertIn("system=hashlib.sha256(json.dumps(os_before", guest)
        self.assertIn('assert os_after == os_before', guest)
