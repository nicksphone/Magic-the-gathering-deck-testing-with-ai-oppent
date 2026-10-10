"""Pure owned filesystem tests; privileged command execution is always mocked."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'ci_backend_capacity.py'


class BackendCapacityTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'Backend capacity preflight is not implemented')
        spec = importlib.util.spec_from_file_location('capacity_under_test', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.original_sdk_roots = self.module.SDK_ROOTS
        self.original_ubuntu24 = self.module.ubuntu24
        self.temporary = tempfile.TemporaryDirectory(prefix='capacity-pure-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / 'workspace/project'
        self.workspace.mkdir(parents=True, mode=0o700)
        self.sdk = (self.root / 'dotnet', self.root / 'android')
        for p in (*self.sdk, self.root / 'tmp', self.root / 'toolcache'):
            p.mkdir(mode=0o700)
        (self.root / 'toolcache/keep').write_text('unchanged')
        self.env = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
            RUNNER_OS='Linux', RUNNER_ARCH='X64', GITHUB_JOB='backend',
            GITHUB_REPOSITORY='nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent',
            GITHUB_WORKSPACE=str(self.workspace), RUNNER_TEMP=str(self.root / 'tmp'),
            RUNNER_TOOL_CACHE=str(self.root / 'toolcache'),
            MTG_CI_CAPACITY_SCOPE='backend-sdk-cleanup')
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch.object(self.module, 'SOURCE', self.workspace))
        self.enter.enter_context(patch.object(self.module, 'SDK_ROOTS', self.sdk))
        self.enter.enter_context(patch.object(self.module, 'ubuntu24', return_value=True))
        self.run = self.enter.enter_context(patch.object(self.module.subprocess, 'run'))
        real_lstat = self.module.os.lstat

        def root_owned(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if Path(path) in self.sdk:
                return SimpleNamespace(st_uid=0, st_mode=info.st_mode,
                    st_dev=info.st_dev, st_ino=info.st_ino)
            return info

        self.enter.enter_context(patch.object(self.module.os, 'lstat', side_effect=root_owned))
        self.enter.enter_context(patch.object(self.module.Path, 'cwd', return_value=self.workspace))

    def call(self, free):
        output = io.StringIO()
        with patch.object(self.module, 'available_bytes', side_effect=free), contextlib.redirect_stdout(output):
            self.module.preflight(self.env)
        return output.getvalue()

    def delete_command(self, argv, **kwargs):
        self.assertEqual(argv[:6], ['/usr/bin/sudo', '-n', '/usr/bin/rm', '-rf', '--one-file-system', '--'])
        target = Path(argv[6])
        self.assertIn(target, self.sdk)
        self.assertEqual(kwargs['timeout'], 120)
        self.assertTrue(kwargs['check'])
        shutil.rmtree(target)  # Only these owned temporary fixture directories.

    def test_sufficient_initial_capacity_still_reclaims_the_unused_sdks(self):
        self.run.side_effect = self.delete_command
        output = self.call([self.module.MIN_FREE_BYTES] * 4)
        self.assertEqual(self.run.call_count, 2)
        self.assertFalse(any(path.exists() for path in self.sdk))
        self.assertIn('CI_BACKEND_CAPACITY_READY cleanup=fixed-unused-sdks', output)

    def test_sufficient_initial_capacity_does_not_bypass_sdk_path_safety(self):
        self.sdk[0].rmdir()
        self.sdk[0].symlink_to(self.root / 'toolcache')
        with self.assertRaisesRegex(self.module.CapacityError, 'sdk-path'):
            self.call([self.module.MIN_FREE_BYTES] * 2)
        self.run.assert_not_called()

    def test_insufficient_capacity_reclaims_only_the_two_fixed_sdk_roots(self):
        self.run.side_effect = self.delete_command
        output = self.call([0, 0, self.module.MIN_FREE_BYTES, self.module.MIN_FREE_BYTES])
        self.assertEqual([Path(c.args[0][-1]) for c in self.run.call_args_list], list(self.sdk))
        self.assertIn('before', output)
        self.assertIn('after', output)
        self.assertEqual((self.root / 'toolcache/keep').read_text(), 'unchanged')

    def test_byte_floor_rejects_one_byte_short_after_cleanup(self):
        self.run.side_effect = self.delete_command
        with self.assertRaisesRegex(self.module.CapacityError, 'byte-floor'):
            self.call([0, 0, self.module.MIN_FREE_BYTES, self.module.MIN_FREE_BYTES - 1])

    def test_each_filesystem_must_meet_the_floor(self):
        self.run.side_effect = self.delete_command
        with self.assertRaisesRegex(self.module.CapacityError, 'byte-floor'):
            self.call([self.module.MIN_FREE_BYTES * 10, 0, self.module.MIN_FREE_BYTES * 10, 0])

    def test_missing_sdk_roots_are_not_created_or_deleted(self):
        for p in self.sdk:
            p.rmdir()
        with self.assertRaisesRegex(self.module.CapacityError, 'byte-floor'):
            self.call([0] * 4)
        self.run.assert_not_called()

    def test_all_roots_are_validated_before_any_deletion(self):
        self.sdk[1].rmdir()
        self.sdk[1].symlink_to(self.root / 'toolcache')
        with self.assertRaisesRegex(self.module.CapacityError, 'sdk-path'):
            self.call([0, 0])
        self.run.assert_not_called()
        self.assertTrue(self.sdk[0].is_dir())

    def test_regular_file_sdk_root_is_rejected(self):
        self.sdk[0].rmdir()
        self.sdk[0].write_text('not a directory')
        with self.assertRaisesRegex(self.module.CapacityError, 'sdk-path'):
            self.call([0, 0])
        self.run.assert_not_called()

    def test_protected_temp_or_toolcache_under_sdk_root_is_rejected(self):
        self.env['RUNNER_TOOL_CACHE'] = str(self.sdk[0])
        with self.assertRaisesRegex(self.module.CapacityError, 'protected-overlap'):
            self.call([0, 0])
        self.run.assert_not_called()

    def test_sdk_inode_change_before_dispatch_is_rejected(self):
        original = self.module.validate_sdk
        calls = 0

        def replaced(path, protected):
            nonlocal calls
            calls += 1
            answer = original(path, protected)
            return (answer[0], answer[1] + 1) if calls > 2 and answer else answer

        with patch.object(self.module, 'validate_sdk', side_effect=replaced):
            with self.assertRaisesRegex(self.module.CapacityError, 'sdk-identity'):
                self.call([0, 0])
        self.run.assert_not_called()

    def test_cleanup_command_failure_stops_admission(self):
        self.run.side_effect = subprocess.CalledProcessError(1, 'mock-only')
        with self.assertRaisesRegex(self.module.CapacityError, 'sdk-cleanup'):
            self.call([0, 0])
        self.assertEqual(self.run.call_count, 1)

    def test_cleanup_cannot_claim_success_if_root_remains(self):
        with self.assertRaisesRegex(self.module.CapacityError, 'sdk-remains'):
            self.call([0, 0])
        self.assertEqual(self.run.call_count, 1)

    def test_local_self_hosted_wrong_job_os_arch_or_scope_are_rejected(self):
        for key, wrong in [('GITHUB_ACTIONS', 'false'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
            ('GITHUB_JOB', 'browser'), ('GITHUB_JOB', 'frontend'), ('RUNNER_OS', 'Windows'),
            ('RUNNER_ARCH', 'ARM64'), ('GITHUB_REPOSITORY', 'another/repo'),
            ('MTG_CI_CAPACITY_SCOPE', ''), ('GITHUB_WORKSPACE', str(self.root))]:
            with self.subTest(key=key, wrong=wrong), patch.dict(self.env, {key: wrong}):
                with self.assertRaises(self.module.CapacityError):
                    self.call([])
                self.run.assert_not_called()

    def test_unsupported_image_is_rejected_without_commands(self):
        with patch.object(self.module, 'ubuntu24', return_value=False):
            with self.assertRaisesRegex(self.module.CapacityError, 'runner-image'):
                self.call([])
        self.run.assert_not_called()

    def test_available_bytes_uses_unprivileged_blocks_and_fragment_size(self):
        with patch.object(self.module.os, 'statvfs', return_value=SimpleNamespace(
            f_bavail=7, f_frsize=4096, f_bsize=8192, f_bfree=999)):
            self.assertEqual(self.module.available_bytes(self.root), 7 * 4096)

    def test_production_path_pins_and_proposed_floor_are_exact(self):
        self.assertEqual(self.original_sdk_roots,
            (Path('/usr/share/dotnet'), Path('/usr/local/lib/android')))
        self.assertEqual(self.module.MIN_FREE_BYTES, 20 * 1024 ** 3)

    def test_writable_sdk_root_is_rejected_before_commands(self):
        self.sdk[1].chmod(0o777)
        with self.assertRaisesRegex(self.module.CapacityError, 'sdk-path'):
            self.call([0, 0])
        self.run.assert_not_called()

    def test_github_dotnet_0777_mode_is_reclaimed(self):
        self.sdk[0].chmod(0o777)
        self.run.side_effect = self.delete_command
        try:
            output = self.call([0, 0, self.module.MIN_FREE_BYTES, self.module.MIN_FREE_BYTES])
        except self.module.CapacityError as error:
            self.fail(f'The documented GitHub dotnet mode must be admitted: {error}')
        self.assertEqual(self.run.call_count, 2)
        self.assertIn('CI_BACKEND_CAPACITY_READY', output)

    def test_other_writable_dotnet_modes_remain_rejected(self):
        self.sdk[0].chmod(0o775)
        with self.assertRaisesRegex(self.module.CapacityError, 'sdk-path'):
            self.call([0, 0])
        self.run.assert_not_called()

    def test_non_root_owned_dotnet_is_rejected_even_with_github_mode(self):
        self.sdk[0].chmod(0o777)
        info = os.lstat(self.sdk[0])
        with patch.object(self.module.os, 'lstat', return_value=SimpleNamespace(
            st_uid=1000, st_mode=info.st_mode, st_dev=info.st_dev, st_ino=info.st_ino)):
            with self.assertRaisesRegex(self.module.CapacityError, 'sdk-path'):
                self.call([0, 0])
        self.run.assert_not_called()

    def test_sdk_with_symlinked_ancestor_is_rejected(self):
        parent = self.root / 'redirect'
        parent.symlink_to(self.root, target_is_directory=True)
        alias = parent / 'dotnet'
        with patch.object(self.module, 'SDK_ROOTS', (alias, self.sdk[1])):
            with self.assertRaisesRegex(self.module.CapacityError, 'sdk-path'):
                self.call([0, 0])
        self.run.assert_not_called()

    def test_missing_context_variables_are_rejected_before_commands(self):
        for key in self.env:
            missing = dict(self.env)
            del missing[key]
            with self.subTest(key=key), patch.object(self.module, 'available_bytes') as measured:
                with self.assertRaises(self.module.CapacityError):
                    self.module.preflight(missing)
                measured.assert_not_called()
            self.run.assert_not_called()

    def test_cli_rejects_arguments_with_constant_diagnostic_and_no_commands(self):
        output = io.StringIO()
        with patch.object(self.module.sys, 'argv', ['script', '/unapproved-root']), contextlib.redirect_stdout(output):
            self.assertEqual(self.module.main(), 2)
        self.assertEqual(output.getvalue(), 'CI_BACKEND_CAPACITY_REJECTED reason=arguments\n')
        self.run.assert_not_called()

    def test_os_release_requires_ubuntu_2404(self):
        for text, expected in [('ID=ubuntu\nVERSION_ID="24.04"\n', True),
            ('ID=debian\nVERSION_ID="24.04"\n', False), ('ID=ubuntu\nVERSION_ID="26.04"\n', False)]:
            with patch.object(self.module.Path, 'read_text', return_value=text):
                self.assertEqual(self.original_ubuntu24(), expected)


if __name__ == '__main__':
    unittest.main()
