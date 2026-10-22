"""Exercise actual main with fixed Docker-command responses, never a real daemon."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch


class HostedControlTests(unittest.TestCase):
    def invoke(self, cancel):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/host.py'
        spec = importlib.util.spec_from_file_location('hosted_control_subject', path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'public'
            (public / 'ops/caddy').mkdir(parents=True)
            (public / 'ops/caddy/run.py').write_text('# inert public-input presence fixture\n')
            capsule = root / 'capsule'
            (capsule / 'objects').mkdir(parents=True)
            (capsule / 'index').write_bytes(b'owned index presence fixture; Git responses below')
            calls, handlers = [], {}

            def response(argv, **kwargs):
                calls.append(argv)
                if argv[0] == 'git':
                    if argv[-4:] == ['ls-tree', '-r', '-z', 'HEAD']:
                        return subprocess.CompletedProcess(argv, 0, b'100644 blob ' + b'a' * 40 + b'\tops/caddy/run.py\0')
                    if argv[-3:] == ['ls-files', '--stage', '-z']:
                        return subprocess.CompletedProcess(argv, 0, b'100644 ' + b'a' * 40 + b' 0\tops/caddy/run.py\0')
                    return subprocess.CompletedProcess(argv, 0, b'a' * 40 + b'\n')
                if argv[:2] == ['docker', 'pull']:
                    if cancel:
                        handlers[m.signal.SIGTERM](m.signal.SIGTERM, None)
                        return subprocess.CompletedProcess(argv, 0)
                    return subprocess.CompletedProcess(argv, 67)
                if argv[:2] == ['docker', 'create']:
                    return subprocess.CompletedProcess(argv, 0, b'b' * 64 + b'\n')
                if argv[:2] == ['docker', 'inspect']:
                    state = {'Id': 'b' * 64, 'Config': {'Labels': {'mtg.clean.head': 'a' * 40}},
                             'State': {'Pid': 0, 'Running': False}}
                    return subprocess.CompletedProcess(argv, 0, json.dumps([state]).encode())
                return subprocess.CompletedProcess(argv, 0)

            argv = ['host.py', '--head', 'a' * 40, '--public', str(public),
                    '--capsule', str(capsule), '--work', str(root / 'actual')]
            with patch.object(m.sys if hasattr(m, 'sys') else __import__('sys'), 'argv', argv), \
                    patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted'}), \
                    patch.object(m.subprocess, 'run', side_effect=response), \
                    patch.object(m.shutil, 'disk_usage', return_value=Mock(free=6 * 1024**3)), \
                    patch.object(m.os, 'getuid', return_value=1001), \
                    patch.object(m.os, 'getgid', return_value=1001), \
                    patch.object(m.signal, 'signal', side_effect=lambda key, value: handlers.update({key: value})):
                code = m.main()
            output = root / 'actual-public-artifact'
            return code, calls, {name: json.loads((output / (name + '.json')).read_bytes())
                                 for name in ('provisioning', 'lifecycle')}

    def test_cancel_during_pull_never_creates_new_container(self):
        code, calls, rows = self.invoke(True)
        self.assertEqual(code, 1)
        self.assertFalse(any(call[:2] == ['docker', 'create'] for call in calls))
        self.assertEqual(rows['lifecycle']['phase'], 'cancelled')
        self.assertEqual(rows['lifecycle']['error_class'], 'Cancelled')
        self.assertFalse(rows['lifecycle']['verified'])

    def test_failed_pull_records_real_exit_and_never_creates_container(self):
        code, calls, rows = self.invoke(False)
        self.assertEqual(code, 1)
        self.assertFalse(any(call[:2] == ['docker', 'create'] for call in calls))
        self.assertEqual(rows['provisioning']['exit_code'], 67)
        self.assertEqual(rows['provisioning']['error_class'], 'StageError')
        self.assertFalse(rows['provisioning']['verified'])

    def test_public_guest_tools_remain_executable_after_private_root_provisioning(self):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/provision.sh'
        text = path.read_text()
        self.assertIn('umask 022', text)
        self.assertIn('chmod 700 "$F"', text)
        self.assertNotIn('chmod -R', text)

    def test_copied_original_backend_observer_is_executable_for_real_launcher(self):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/guest.py'
        text = path.read_text()
        self.assertIn("(https / 'gate-review/backend-python.py').chmod(0o755)", text)
