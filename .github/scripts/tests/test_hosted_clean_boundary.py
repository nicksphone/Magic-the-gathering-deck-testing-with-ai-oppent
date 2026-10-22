"""Counterfactual controller boundaries, not physical-container evidence."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock


class HostedBoundaryTests(unittest.TestCase):
    def module(self):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/host.py'
        spec = importlib.util.spec_from_file_location('hosted_boundary_subject', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_own_cgroup_never_admits_host_root_or_foreign_path(self):
        m = self.module()
        self.assertTrue(callable(getattr(m, 'cgroup_path', None)))
        for value in ('0::/', '0::/system.slice/foreign.scope', '0::/../' + 'b' * 64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.cgroup_path(value, 'b' * 64)
        self.assertEqual(m.cgroup_path('0::/system.slice/docker-' + 'b' * 64 + '.scope', 'b' * 64),
                         Path('/sys/fs/cgroup/system.slice/docker-' + 'b' * 64 + '.scope'))

    def test_dispatched_work_uses_real_tmp_namespace_not_deep_home(self):
        m = self.module()
        command = m.container_command('/owned/public', '/owned/work', 'a' * 40)
        self.assertIn('--mount=type=bind,src=/owned/work,dst=/tmp/mtg-hosted-clean', command)

    def test_unknown_guest_report_fields_fail_without_replacement(self):
        m = self.module()
        self.assertTrue(callable(getattr(m, 'read_guest_reports', None)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'lifecycle.json').write_text('{"trace":"PRIVATE_CANARY"}')
            with self.assertRaises(ValueError):
                m.read_guest_reports(root, 'a' * 40)

    def test_mismatched_head_is_rejected_before_report_assignment(self):
        m = self.module()
        self.assertTrue(callable(getattr(m, 'read_guest_reports', None)))
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = m.empty_report('lifecycle', 'c' * 40)
            (root / 'lifecycle.json').write_text(json.dumps(row))
            with self.assertRaises(ValueError):
                m.read_guest_reports(root, 'a' * 40)

    def test_negative_stop_exit_remains_nonzero(self):
        m = self.module()
        command = Mock(return_value=137)
        cid, head = 'b' * 64, 'a' * 40
        inspect = lambda _: {'Id': cid, 'Config': {'Labels': {'mtg.clean.head': head}}}
        self.assertEqual(m.stop_owned(command, cid, head, inspect), 137)

    def test_all_old_donor_functions_are_byte_exact_not_reimplementations(self):
        import hashlib
        root = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean'
        for name, expected in {
            'https/client-gate.py': '4cc3fe17fa44d23afa0a5e1d4014285675121d6f038df3296889ba5597d60ac5',
            'https/backend-python.py': '8006190f3e3d566e8d08f3d1c9797c473d3e1d748e701546fb2daa38ea397277',
            'actors/build-only-driver.py': 'dabf009dbe459d3526343bcb0c8d48d7487eeab8f0799e70db63b8eb7a1d9bf7',
        }.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected)
