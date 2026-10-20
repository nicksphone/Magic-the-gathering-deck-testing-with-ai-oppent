"""Actual workflow shell with inert browser commands and owned filesystem data."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
from types import SimpleNamespace
import unittest


WORKFLOW = Path(__file__).resolve().parents[3] / '.github/workflows/browser-recovery-localization.yml'
TIMEOUT_PREFIX = ['--signal=TERM', '--kill-after=15s', '720s', 'bash',
                  'frontend/tests/run-browser-ci.sh']
MOCKS = '''
timeout() {
  printf 'timeout\\n' >> "$TIMEOUT_CALLS"
  printf '%s\\0' "$@" >> "$TIMEOUT_ARGS"
  /usr/bin/env -0 > "$CHILD_ENV"
  return "$PROGRAM_STATUS"
}
ss() {
  printf 'ss\\n' >> "$SS_CALLS"
  printf '%s' "$PORT_OUTPUT"
  return "$QUERY_STATUS"
}
'''


class UiLocalizationScenarioTests(unittest.TestCase):
    @contextmanager
    def run_case(self, *, choice='ui-v2', program=0, query=0, ports='', existing=None):
        source = WORKFLOW.read_text()
        marker = '      - name: Focused transport and start recovery, not the full UI suite\n'
        self.assertEqual(source.count(marker), 1)
        section = source.split(marker, 1)[1]
        self.assertIn('\n  cost-overlap-asgi:', section)
        body = textwrap.dedent(section.split('run: |\n', 1)[1]
                               .split('\n  cost-overlap-asgi:', 1)[0])
        self.assertTrue(body.startswith('set -euo pipefail\n'))
        with tempfile.TemporaryDirectory(prefix='mtg-localization-shell-') as temporary:
            root = Path(temporary)
            runner = root / 'runner'
            runner.mkdir(mode=0o700)
            evidence = runner / 'ui-v2-localization-evidence'
            target = root / 'preserved-target'
            if existing == 'directory':
                evidence.mkdir(mode=0o750)
                (evidence / 'marker').write_bytes(b'public-existing-directory')
            elif existing == 'file':
                evidence.write_bytes(b'public-existing-file')
            elif existing == 'symlink':
                target.write_bytes(b'public-existing-target')
                evidence.symlink_to(target)
            elif existing == 'dangling-symlink':
                evidence.symlink_to(target)
            else:
                self.assertIsNone(existing)
            before = evidence.lstat() if existing is not None else None
            env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(root),
                   'RUNNER_TEMP': str(runner), 'PROGRAM_STATUS': str(program),
                   'QUERY_STATUS': str(query), 'PORT_OUTPUT': ports,
                   'TIMEOUT_CALLS': str(root / 'timeout-calls'),
                   'TIMEOUT_ARGS': str(root / 'timeout-args'),
                   'SS_CALLS': str(root / 'ss-calls'), 'CHILD_ENV': str(root / 'child-env')}
            if choice is not None:
                env['MTG_LOCALIZATION_SCENARIO'] = choice
            result = subprocess.run(['/usr/bin/bash', '--noprofile', '--norc', '-c', MOCKS + body],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=5)
            args_path, child_env_path = root / 'timeout-args', root / 'child-env'
            argv = ([part.decode() for part in args_path.read_bytes().split(b'\0')[:-1]]
                    if args_path.exists() else [])
            child_env = (dict(part.decode().split('=', 1)
                              for part in child_env_path.read_bytes().split(b'\0') if part)
                         if child_env_path.exists() else {})
            yield SimpleNamespace(root=root, runner=runner, evidence=evidence, target=target,
                                  before=before, result=result, argv=argv, child_env=child_env,
                                  timeout_calls=root / 'timeout-calls', ss_calls=root / 'ss-calls',
                                  child_env_path=child_env_path)

    def test_ui_v2_has_fixed_argv_exported_fresh_private_evidence_and_no_overwrite(self):
        with self.subTest(existing=None), self.run_case() as case:
            self.assertEqual(case.result.returncode, 0, case.result.stdout + case.result.stderr)
            self.assertEqual(case.argv, TIMEOUT_PREFIX + ['browser-ui-v2.mjs'])
            self.assertEqual(case.timeout_calls.read_text(), 'timeout\n')
            self.assertEqual(case.child_env.get('MTG_UI_EVIDENCE'), str(case.evidence))
            self.assertEqual(case.evidence.parent, case.runner)
            self.assertFalse(case.evidence.is_symlink())
            info = case.evidence.lstat()
            self.assertTrue(stat.S_ISDIR(info.st_mode))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o700)
            self.assertEqual(info.st_uid, os.getuid())
            self.assertEqual(list(case.evidence.iterdir()), [])
            self.assertIn('::notice title=Browser localization scenario::{"schema":1,"scenario":"ui-v2"}',
                          case.result.stdout)
        for kind in ('directory', 'file', 'symlink', 'dangling-symlink'):
            with self.subTest(existing=kind), self.run_case(existing=kind) as case:
                self.assertNotEqual(case.result.returncode, 0)
                self.assertFalse(case.timeout_calls.exists())
                self.assertFalse(case.ss_calls.exists())
                self.assertFalse(case.child_env_path.exists())
                after = case.evidence.lstat()
                self.assertEqual((after.st_dev, after.st_ino, after.st_mode, after.st_mtime_ns),
                                 (case.before.st_dev, case.before.st_ino,
                                  case.before.st_mode, case.before.st_mtime_ns))
                if kind == 'directory':
                    self.assertEqual((case.evidence / 'marker').read_bytes(), b'public-existing-directory')
                elif kind == 'file':
                    self.assertEqual(case.evidence.read_bytes(), b'public-existing-file')
                else:
                    self.assertEqual(os.readlink(case.evidence), str(case.target))
                    if kind == 'symlink':
                        self.assertEqual(case.target.read_bytes(), b'public-existing-target')
                    else:
                        self.assertFalse(case.target.exists())

    def test_primary_status_survives_port_or_query_failure_and_default_pair_is_unchanged(self):
        for program, query, ports, expected in (
            (23, 0, 'LISTEN fixture', 23), (23, 2, '', 23),
            (124, 2, 'LISTEN fixture', 124), (0, 0, 'LISTEN fixture', 1), (0, 2, '', 1),
        ):
            with self.subTest(program=program, query=query), self.run_case(
                    program=program, query=query, ports=ports) as case:
                self.assertEqual(case.result.returncode, expected, case.result.stdout + case.result.stderr)
                self.assertEqual(case.argv, TIMEOUT_PREFIX + ['browser-ui-v2.mjs'])
                self.assertEqual(case.child_env.get('MTG_UI_EVIDENCE'), str(case.evidence))
                self.assertEqual(case.timeout_calls.read_text(), 'timeout\n')
                self.assertEqual(case.ss_calls.read_text(), 'ss\n')
        for choice in (None, 'start-recovery'):
            with self.subTest(choice=choice), self.run_case(choice=choice) as case:
                self.assertEqual(case.result.returncode, 0, case.result.stdout + case.result.stderr)
                self.assertEqual(case.argv, TIMEOUT_PREFIX + [
                    'browser-cors-transport-diagnostic.mjs', 'browser-start-recovery.mjs'])
                self.assertNotIn('MTG_UI_EVIDENCE', case.child_env)
                self.assertFalse(case.evidence.exists())
                self.assertFalse(case.evidence.is_symlink())
                self.assertIn('::notice title=Browser localization scenario::{"schema":1,"scenario":"start-recovery"}',
                              case.result.stdout)

    def test_unknown_or_hostile_choice_exits_before_timeout_evidence_or_command(self):
        for choice in ('unknown', 'UI-V2', 'ui-v2; touch "$RUNNER_TEMP/injected"',
                       '$(touch "$RUNNER_TEMP/injected")'):
            with self.subTest(choice=choice), self.run_case(choice=choice) as case:
                self.assertEqual(case.result.returncode, 2, case.result.stdout + case.result.stderr)
                self.assertEqual(case.argv, [])
                self.assertFalse(case.timeout_calls.exists())
                self.assertFalse(case.ss_calls.exists())
                self.assertFalse(case.child_env_path.exists())
                self.assertFalse(case.evidence.exists())
                self.assertFalse(case.evidence.is_symlink())
                self.assertEqual(list(case.runner.iterdir()), [])
                self.assertNotIn('Browser localization scenario', case.result.stdout)

    def test_ui_v2_prefix_runs_exact_three_programs_with_exported_private_evidence(self):
        import json

        with self.run_case(choice='ui-v2-prefix') as case:
            argv_matches = case.argv == TIMEOUT_PREFIX + [
                'browser-cors-transport-diagnostic.mjs',
                'browser-driver-async.mjs', 'browser-ui-v2.mjs']
            evidence_exported = case.child_env.get('MTG_UI_EVIDENCE') == str(case.evidence)
            print('::notice title=Browser prefix workflow contract::' + json.dumps({
                'schema': 1, 'scenario': 'ui-v2-prefix', 'runner_exit': case.result.returncode,
                'argv_matches': argv_matches, 'evidence_exported': evidence_exported,
            }, separators=(',', ':')), flush=True)
            self.assertEqual(case.result.returncode, 0)
            self.assertTrue(argv_matches)
            self.assertTrue(evidence_exported)
            self.assertEqual(case.timeout_calls.read_text(), 'timeout\n')
            self.assertEqual(case.ss_calls.read_text(), 'ss\n')
            self.assertFalse(case.evidence.is_symlink())
            info = case.evidence.lstat()
            self.assertTrue(stat.S_ISDIR(info.st_mode))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o700)
            self.assertEqual(info.st_uid, os.getuid())
            self.assertTrue(case.evidence.parent == case.runner)
            self.assertEqual(list(case.evidence.iterdir()), [])
            self.assertTrue('::notice title=Browser localization scenario::{"schema":1,"scenario":"ui-v2-prefix"}'
                            in case.result.stdout)


if __name__ == '__main__':
    unittest.main()
