"""No-container protocols for the real hosted-clean controller and guest wiring."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[3]
SCRIPT = SOURCE / 'ops/ci/hosted-clean/host.py'
HEAD = 'a' * 40
CID = 'b' * 64


class HostedCleanTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.is_file(), 'The real hosted controller must exist')
        spec = importlib.util.spec_from_file_location('hosted_clean_subject', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_provision_schema_positive_and_closed(self):
        m = self.module()
        row = m.empty_report('provisioning', HEAD)
        self.assertEqual(m.validate_report(row, 'provisioning'), row)
        for key, value in [('message', 'PRIVATE_CANARY'), ('argv', []), ('password', 'SECRET')]:
            with self.subTest(key=key):
                bad = dict(row, **{key: value})
                with self.assertRaises(ValueError):
                    m.validate_report(bad, 'provisioning')

    def test_lifecycle_schema_positive_and_closed(self):
        m = self.module()
        row = m.empty_report('lifecycle', HEAD)
        self.assertFalse(row['verified'])
        self.assertEqual(m.validate_report(row, 'lifecycle'), row)
        with self.assertRaises(ValueError):
            m.validate_report(dict(row, trace='PRIVATE_CANARY'), 'lifecycle')

    def test_types_do_not_treat_bool_as_integer(self):
        m = self.module()
        row = m.empty_report('lifecycle', HEAD)
        for key in ('checks', 'passed', 'client_exit', 'exit_code'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.validate_report(dict(row, **{key: True}), 'lifecycle')

    def test_unverified_missing_closure_cannot_be_promoted(self):
        m = self.module()
        row = m.empty_report('lifecycle', HEAD)
        with self.assertRaises(ValueError):
            m.validate_report(dict(row, verified=True), 'lifecycle')

    def test_verified_lifecycle_requires_every_closed_boolean(self):
        m = self.module()
        row = m.empty_report('lifecycle', HEAD)
        row.update(phase='complete', exit_code=0, error_class=None, client_exit=0,
                   checks=563, passed=563, label_count=70, closure_issues=0,
                   db_closed=True, services_closed=True, container_closed=True,
                   cgroup_empty=True, source_equal=True, verified=True)
        self.assertEqual(m.validate_report(row, 'lifecycle'), row)
        for key in ('db_closed', 'services_closed', 'container_closed', 'cgroup_empty', 'source_equal'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.validate_report(dict(row, **{key: False}), 'lifecycle')

    def test_provision_cannot_hide_a_failed_or_unrun_check(self):
        m = self.module()
        row = m.empty_report('provisioning', HEAD)
        row.update(phase='complete', exit_code=0, python_packages=28,
                   python5_exits=[0] * 5, frontend5_exits=[0] * 5,
                   tools={key: 'c' * 64 for key in row['tools']},
                   source_equal=True, runtime_equal=True, verified=True)
        self.assertEqual(m.validate_report(row, 'provisioning'), row)
        for value in ([0, 0, 1, 0, 0], [0, 0, None, 0, 0]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.validate_report(dict(row, frontend5_exits=value), 'provisioning')

    def test_error_projection_never_uses_exception_text(self):
        m = self.module()
        self.assertEqual(m.error_class(PermissionError('PRIVATE_CANARY')), 'PermissionError')
        self.assertEqual(m.error_class(Exception('PASSWORD_CANARY')), 'OtherError')
        self.assertNotIn('CANARY', json.dumps(m.empty_report('lifecycle', HEAD)))

    def test_artifact_writer_rejects_unknown_fields_and_oversize(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = m.empty_report('lifecycle', HEAD)
            m.write_report(root, 'lifecycle', row)
            self.assertEqual(json.loads((root / 'lifecycle.json').read_bytes()), row)
            with self.assertRaises(ValueError):
                m.write_report(root, 'lifecycle', dict(row, private='CANARY' * 20000))
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['lifecycle.json'])

    def test_only_owned_canonical_cid_can_be_stopped(self):
        m = self.module()
        command = Mock()
        for value in ('', 'b' * 12, '--all', CID + '\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.stop_owned(command, value, HEAD, lambda _: {})
        command.assert_not_called()

    def test_foreign_label_never_receives_stop_or_kill(self):
        m = self.module()
        command = Mock()
        inspect = lambda _: {'Id': CID, 'Config': {'Labels': {'mtg.clean.head': 'd' * 40}}}
        with self.assertRaises(ValueError):
            m.stop_owned(command, CID, HEAD, inspect)
        command.assert_not_called()

    def test_cancellation_stops_only_exact_container_with_original_grace(self):
        m = self.module()
        command = Mock(return_value=0)
        state = {'Id': CID, 'Config': {'Labels': {'mtg.clean.head': HEAD}}}
        self.assertEqual(m.stop_owned(command, CID, HEAD, lambda _: state), 0)
        command.assert_called_once_with(['docker', 'stop', '--time', '15', CID], timeout=30)

    def test_nonzero_stage_is_not_retried_or_masked(self):
        m = self.module()
        command = Mock(return_value=23)
        with self.assertRaises(m.StageError) as caught:
            m.checked(command, ['fixed-tool'], 300)
        self.assertEqual(caught.exception.code, 23)
        self.assertEqual(command.call_count, 1)

    def test_report_bounds_and_phase_are_closed(self):
        m = self.module()
        row = m.empty_report('lifecycle', HEAD)
        for change in ({'phase': 'user supplied secret'}, {'checks': 10001},
                       {'error_class': 'PRIVATE_CANARY'}, {'head': '../main'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.validate_report(dict(row, **change), 'lifecycle')

    def test_guest_failure_does_not_qualify_from_docker_exit_alone(self):
        m = self.module()
        row = m.empty_report('lifecycle', HEAD)
        row['exit_code'] = 0
        self.assertFalse(m.validate_report(row, 'lifecycle')['verified'])

    def test_workflow_is_manual_readonly_and_uploads_only_two_json(self):
        path = SOURCE / '.github/workflows/hosted-clean-install.yml'
        self.assertTrue(path.is_file(), 'The closed manual workflow must exist')
        text = path.read_text()
        for required in ('workflow_dispatch:', 'ubuntu-24.04', 'contents: read',
                         'persist-credentials: false', 'provisioning.json', 'lifecycle.json',
                         'retention-days: 7', 'test_hosted_clean.py'):
            self.assertIn(required, text)
        for forbidden in ('pull_request_target:', 'secrets.', 'path: **', 'upload-artifact@main'):
            self.assertNotIn(forbidden, text)

    def test_guest_preserves_original_stage_helpers_and_no_install_cache(self):
        path = SOURCE / 'ops/ci/hosted-clean/guest.py'
        self.assertTrue(path.is_file(), 'The real guest stage driver must exist')
        text = path.read_text()
        for required in ('bootstrap_pip.py', 'pip_offline.py', 'collect_runtime_metadata.py',
                         'build-only-driver.py', 'client-gate.py', 'VITE_API_BASE_URL'):
            self.assertIn(required, text)
        self.assertNotIn('npm install', text)

    def test_provision_rejects_unavailable_or_wrong_curl_without_waiver(self):
        path = SOURCE / 'ops/ci/hosted-clean/provision.sh'
        self.assertTrue(path.is_file(), 'The fixed public provisioning script must exist')
        text = path.read_text()
        for required in ('curl=8.5.0-2ubuntu10.16', 'CURL_UNAVAILABLE',
                         '1ccbd3dae948374ba8eef1ebda26c64b783ede50b463196e53666e0880bdac60',
                         'set -euo pipefail', 'GOTOOLCHAIN=local', 'GOPROXY=off'):
            self.assertIn(required, text)
        for forbidden in ('--allow-unauthenticated', 'trusted=yes', 'curl -k', 'curl --insecure'):
            self.assertNotIn(forbidden, text)

    def test_one_container_no_host_credentials_or_ports(self):
        m = self.module()
        argv = m.container_command('/owned/public', '/owned/work', HEAD)
        self.assertEqual(argv[:2], ['docker', 'create'])
        for required in ('--init', '--memory=4g', '--memory-swap=4g', '--cpus=2',
                         '--pids-limit=256', '--log-driver=none', '--restart=no'):
            self.assertIn(required, argv)
        self.assertTrue(any('ubuntu@sha256:a2d43' in arg for arg in argv))
        text = '\n'.join(argv)
        for forbidden in ('docker.sock', '/mnt/rchfiles', '--privileged', '--network=host', '--publish'):
            self.assertNotIn(forbidden, text)

    def test_caddy_recipe_has_exact_existing_wrapper_hashes(self):
        import hashlib
        directory = SOURCE / 'ops/ci/hosted-clean/caddy'
        for name, expected in {
            'go.mod': 'd173eceee6ce678584bf2f5d2e219aade323ccfb93e578c0b48bc83295e8a59a',
            'go.sum': '6af3a164233778b8a67386362356bfb312d26888ccee645b7180f07fc27e8574',
            'main.go': 'ac320c3ac47ad8abed7a0d2595639d78f9ff55cf1dba8494a66cd8851c5d076e',
        }.items():
            with self.subTest(name=name):
                self.assertTrue((directory / name).is_file())
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
