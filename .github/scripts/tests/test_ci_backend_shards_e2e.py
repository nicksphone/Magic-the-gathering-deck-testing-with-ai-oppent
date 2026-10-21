"""Real public-toy CLI plumbing, not hosted/private/gameplay qualification.

Only private preparation is a public stand-in. Python, runner, storage, auditor,
sanitizer, shard CLI, pytest and native waits are real and unmodified. Outputs
remain in owned scratch, including on failure; archive/cleanup is external.
"""
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

import test_backend_ci_privacy as privacy


SCRIPTS = privacy.SCRIPTS
SENTINEL = privacy.SENTINEL
TOOLS = ('run-backend-ci.sh', 'ci_backend_shards.py', 'ci_backend_evidence.py',
         'ci_backend_metadata.py', 'ci_backend_storage.py',
         'ci_backend_snapshot_cleanup.py', 'ci_backend_progress.py')
MODULES = ['backend/audit/body-goldens/test_outside.py',
           *[f'backend/tests/test_{name}.py' for name in 'abcd']]

# This script never imports or reads the real preparer or any secret payload.
PUBLIC_PREPARER = '''\
import json, os, sys
from pathlib import Path
assert not any(f'MTG_HEAT_WITNESS_{i:02}' in os.environ for i in range(1, 14))
destination = Path(sys.argv[1])
destination.mkdir(mode=0o700)
with (destination / 'sealed-self-removal-witness.json').open('x') as stream:
    os.chmod(stream.name, 0o600)
    json.dump({'public_synthetic': MARKER}, stream)
print(MARKER)
print(MARKER, file=sys.stderr)
'''.replace('MARKER', repr(SENTINEL))

TOY_CONFTEST = '''\
import json, os, sys
from pathlib import Path
attempts = []
def deny(event, args):
    if event.startswith(('sqlite3.', 'socket.', 'subprocess.', 'os.exec',
                         'os.spawn', 'os.posix_spawn', 'os.fork')) or event == 'os.system':
        attempts.append(event)
        raise RuntimeError('TOY_SQL_SOCKET_CHILD_DENIED')
    if event == 'import' and args[0].split('.')[0] in {
            'main', 'persistence', 'rules_engine', 'requests', 'httpx',
            'urllib', 'openai', 'anthropic', 'boto3'}:
        attempts.append('import:' + args[0])
        raise RuntimeError('TOY_APP_PROVIDER_DENIED')
sys.addaudithook(deny)
def pytest_sessionfinish(session, exitstatus):
    with (Path(os.environ['MTG_CI_EVIDENCE']) / 'toy-denials.json').open('x') as stream:
        json.dump(attempts, stream)
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_map(root):
    return {path.relative_to(root).as_posix(): (sha(path), path.stat().st_mode & 0o7777)
            for path in sorted(root.rglob('*')) if path.is_file()
            and '.git' not in path.relative_to(root).parts}


def command_failure_metadata(root, label, directory, actual, expected):
    """Only finite statuses and bounded stream fingerprints, never their text."""
    def stream_metadata(path):
        unavailable = dict(status='unavailable', bytes=None, sha256=None)
        try:
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                return unavailable
            if before.st_size > 65536:
                return dict(status='oversize', bytes=before.st_size, sha256=None)
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            with os.fdopen(descriptor, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    return unavailable
                data = stream.read(65537)
            if len(data) > 65536:
                return dict(status='oversize', bytes=len(data), sha256=None)
            return dict(status='available', bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        except (OSError, ValueError):
            return unavailable

    role = ('reference' if label == 'reference' else 'failed_worker' if label == 'failed-worker'
            else 'worker' if label in {f'worker-{i}' for i in range(4)} else 'other')
    closeout = None
    if role != 'other':
        try:
            candidates = iter((root / (label + '-temp')).glob('mtg-backend-evidence-*'))
            evidence = next(candidates, None)
            if evidence is not None and next(candidates, None) is None:
                spec = importlib.util.spec_from_file_location(
                    'toy_failure_existing_sanitizer', SCRIPTS / 'ci_backend_metadata.py')
                reporter = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(reporter)
                text = reporter.read_text(evidence, 'pytest-exit-code.txt', max_bytes=4).strip()
                code = int(text) if text.isascii() and text.isdecimal() and int(text) <= 255 else None
                projected = reporter.closeout_fields(evidence, code).get('runner_closeout')
                if projected is not None:
                    diagnostics = projected['diagnostics']
                    closeout = dict(status=projected['status'], runner=projected['runner'],
                                    diagnostic_count=len(diagnostics),
                                    finished_count=sum(row['finished'] for row in diagnostics),
                                    forced_count=sum(row['forced'] for row in diagnostics),
                                    nonzero_wait_count=sum(row['wait_exit_code'] not in (None, 0)
                                                           for row in diagnostics))
        except Exception:
            # Optional diagnostics must never replace the original failed assertion.
            closeout = None
    return dict(schema=1, role=role, actual_exit=actual, expected_exit=expected,
                stdout=stream_metadata(directory / 'stdout'),
                stderr=stream_metadata(directory / 'stderr'), runner_closeout=closeout)


class ShardCliE2ETests(unittest.TestCase):
    def _json(self, path):
        return json.loads(path.read_text())

    def _group_absent(self, pid, deadline=None):
        until = time.monotonic() + 2
        if deadline is not None:
            until = min(until, deadline)
        while True:
            try:
                os.killpg(pid, 0)  # Presence only, only a Popen-owned setsid group.
            except ProcessLookupError:
                return
            self.assertLess(time.monotonic(), until, 'OWNED_GROUP_CLOSURE_UNKNOWN')
            time.sleep(0.05)

    def _command(self, label, argv, env=None, expected=0):
        self.assertLess(time.monotonic(), self.work_until, 'TOY_WORK_ADMISSION_EXPIRED')
        directory = self.root / label
        directory.mkdir()
        record = dict(label=label, argv=list(map(str, argv)), pid=None, exit=None)
        self.records.append(record)
        with (directory / 'stdout').open('xb') as out, (directory / 'stderr').open('xb') as err:
            process = subprocess.Popen(argv, cwd=self.repo, env=env or self.env,
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       start_new_session=True, umask=0o022)
            self.handles.append(process)  # Ownership before any fallible recording.
            record['pid'] = process.pid
            self._write_records()
            record['exit'] = process.wait(timeout=min(90, self.work_until - time.monotonic()))
        self._group_absent(process.pid)
        self.assertFalse(Path(f'/proc/{process.pid}').exists(), 'OWNED_PID_STILL_PRESENT')
        self._write_records()
        if record['exit'] != expected:
            try:
                diagnostic = command_failure_metadata(self.root, label, directory, record['exit'], expected)
                print('CI_TOY_COMMAND_FAILURE ' + json.dumps(diagnostic, sort_keys=True), file=sys.stderr)
            except (OSError, ValueError):
                pass
        self.assertEqual(record['exit'], expected, f'{label}: real command status')
        for stream in ('stdout', 'stderr'):
            self.assertLessEqual((directory / stream).stat().st_size, 65536)
            self.assertNotIn(SENTINEL, (directory / stream).read_text())
        return record

    def _write_records(self):
        (self.root / 'owned-commands.json').write_text(json.dumps(self.records, indent=2) + '\n')

    def _helper(self, label, *args, env=None, expected=0):
        return self._command(label, [sys.executable, '-I', '-B',
            str(self.repo / '.github/scripts/ci_backend_shards.py'), *map(str, args)],
            env=env, expected=expected)

    def _runner(self, label, role, shard=None, fail=False):
        temporary = self.root / (label + '-temp')
        temporary.mkdir()
        output = self.root / (label + '-output')
        environment = {**self.env, 'RUNNER_TEMP': str(temporary), 'GITHUB_OUTPUT': str(output),
                       'MTG_CI_SHARD_ROLE': role, 'MTG_CI_PROGRESS': '1',
                       'MTG_CI_WORK_DEADLINE': str(time.monotonic() + 45)}
        if shard is not None:
            environment.update(MTG_CI_SHARD=str(shard), MTG_CI_REFERENCE_DIR=str(self.reference))
        if fail:
            environment['PUBLIC_TOY_FAIL'] = '1'
        record = self._command(label, ['/bin/bash', '-c',
            'exec 5>&1; exec /bin/bash .github/scripts/run-backend-ci.sh'],
            env=environment, expected=1 if fail else 0)
        rows = output.read_text().splitlines()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith('evidence='))
        evidence = Path(rows[0].removeprefix('evidence='))
        self.assertEqual(evidence.parent, temporary)
        self.assertEqual((evidence / 'pytest-exit-code.txt').read_text().strip(), str(record['exit']))
        identity = self._json(evidence / 'deadline.json.identity.json')
        self.assertEqual(identity['parent'], record['pid'])
        self.assertEqual(identity['pid'], identity['pgrp'])
        self.assertEqual(identity['pid'], identity['session'])
        self._group_absent(identity['pid'])
        self.assertFalse(Path(f"/proc/{identity['pid']}").exists())
        for name in ('deadline.json', 'group-quiet-after-wait.json', 'group-quiet-final.json'):
            self.assertEqual(self._json(evidence / name), dict(status='GROUP_ABSENT', signals=[]))
        closeout = [line.split('\t') for line in
                    (evidence / 'diagnostic-closeout.tsv').read_text().splitlines()]
        self.assertTrue({'pressure', 'sink', 'sampler', 'progress', 'logger'} <=
                        {row[0] for row in closeout})
        for role_name, pid, finished, forced, waited in closeout:
            self.assertEqual((finished, forced, waited), ('1', '0', '0'), role_name)
            self.assertFalse(Path(f'/proc/{int(pid)}').exists())
        self.assertEqual(self._json(evidence / 'toy-denials.json'), [])
        self.assertIn(SENTINEL, (evidence / 'runner.log').read_text())
        for name in ('runner.log.stream.json', 'pytest.log.stream.json'):
            self.assertTrue(self._json(evidence / name)['full_raw_retained'])
        paths = dict(line.split('=', 1) for line in (evidence / 'owned-paths.txt').read_text().splitlines())
        scratch, work = Path(paths['source']), Path(paths['work'])
        self.assertEqual(work.parent, temporary)
        self.assertEqual(scratch, work / 'source')
        binding = self._json(evidence / 'binding.json')
        self.assertEqual(binding, {**self.binding, 'archive_sha256': sha(work / 'source.tar')})
        # The archived source and every declared original tool remain unchanged.
        for path, value in self.before.items():
            self.assertEqual(sha(scratch / path), value[0])
            # All toy paths are nonexecutables: Git archives store 100644,
            # independent of the creator's group-write umask on local inputs.
            self.assertEqual((scratch / path).stat().st_mode & 0o7777, 0o644)
        self.assertFalse(list(scratch.rglob('*.db')))
        return evidence, record['exit']

    def _metadata(self, label, evidence):
        directory = self.root / (label + '-diagnostic')
        directory.mkdir()
        metadata = directory / 'backend-metadata.json'
        record = self._command(label + '-sanitize', [sys.executable, '-I', '-B',
            str(self.repo / '.github/scripts/ci_backend_metadata.py'),
            str(evidence), str(self.repo), str(metadata)])
        self._helper(label + '-diagnostic-bound', 'diagnostic-file', metadata)
        self.assertNotIn(SENTINEL, metadata.read_text())
        return metadata, record['exit']

    def test_real_reference_four_workers_and_failed_worker_cannot_qualify(self):
        self.root = Path(tempfile.mkdtemp(prefix='ci-real-shards-',
            dir=os.environ.get('MTG_CI_E2E_TEMP_ROOT'))).resolve()
        self.records, self.handles = [], []
        self.work_until = time.monotonic() + 420
        self.repo = self.root / 'source'
        scripts = self.repo / '.github/scripts'
        scripts.mkdir(parents=True)
        self.env = {'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin',
                    'HOME': str(self.root), 'LANG': 'C.UTF-8',
                    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                    'GIT_OPTIONAL_LOCKS': '0', 'GIT_AUTHOR_NAME': 'Synthetic',
                    'GIT_AUTHOR_EMAIL': 'synthetic@example.invalid',
                    'GIT_COMMITTER_NAME': 'Synthetic',
                    'GIT_COMMITTER_EMAIL': 'synthetic@example.invalid',
                    'PYTHONDONTWRITEBYTECODE': '1', 'GITHUB_WORKSPACE': str(self.repo),
                    'GITHUB_RUN_ID': '17', 'GITHUB_RUN_ATTEMPT': '1',
                    'GITHUB_OUTPUT': str(self.root / 'export-output')}
        frozen = {name: sha(SCRIPTS / name) for name in TOOLS}
        try:
            for name in TOOLS:
                shutil.copyfile(SCRIPTS / name, scripts / name)
                self.assertEqual(sha(scripts / name), frozen[name])
            backend = self.repo / 'backend'
            backend.mkdir()
            lock = backend / 'requirements-py312-linux.lock'
            shutil.copyfile(SCRIPTS.parents[1] / 'backend/requirements-py312-linux.lock', lock)
            (scripts / 'prepare-backend-private-inputs.py').write_text(PUBLIC_PREPARER)
            (backend / 'conftest.py').write_text(TOY_CONFTEST)
            for index, path in enumerate(MODULES):
                target = self.repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(textwrap.dedent(f'''\
                    import json, os
                    from pathlib import Path
                    import pytest
                    @pytest.mark.parametrize('public_label', [{SENTINEL!r}])
                    def test_public_{index}(public_label):
                        print(public_label)
                        assert json.loads(Path(os.environ['MTG_HEAT_WITNESS']).read_text()) == {{
                            'public_synthetic': public_label}}
                        assert not ({index} == 0 and os.environ.get('PUBLIC_TOY_FAIL') == '1'), public_label
                    '''))
            for label, arguments in (
                    ('git-init', ['init', '-q']), ('git-add', ['add', '.']),
                    ('git-commit', ['-c', 'commit.gpgsign=false', 'commit', '-qm', 'public toy']),
                    ('git-head', ['rev-parse', 'HEAD'])):
                self._command(label, ['/usr/bin/git', *arguments])
            commit = (self.root / 'git-head/stdout').read_text().strip()
            self.env['GITHUB_SHA'] = commit
            self.binding = dict(run_id='17', attempt='1', commit=commit, lock_sha256=sha(lock))
            self.before = source_map(self.repo)
            self.reference = self.root / 'public-reference'
            self.reference.mkdir()
            evidence, status = self._runner('reference', 'reference')
            observation = self._json(evidence / 'shard-observation.json')
            self.assertTrue(observation['session_finished'])
            self.assertEqual(observation['pytest_exit'], 0)
            self.assertEqual(len(observation['items']), 5)
            raw_expected = [f"{path.removeprefix('backend/')}::test_public_{index}[{SENTINEL}]"
                            for index, path in enumerate(MODULES)]
            self.assertEqual([row['nodeid'] for row in observation['items']], raw_expected)
            self.assertEqual(observation['discovered'], raw_expected)
            self.assertEqual((evidence / 'phases.jsonl').read_text(), '')
            self._helper('export-reference', 'export-reference', evidence,
                         self.reference / 'plan.json', status)
            plan = self._json(self.reference / 'plan.json')
            self.assertEqual([row['path'] for row in plan['modules']], MODULES)
            self.assertEqual([row['shard'] for row in plan['modules']], [0, 1, 2, 3, 0])
            expected = [hashlib.sha256(node.encode()).hexdigest() for node in raw_expected]
            self.assertEqual(plan['node_sha256'], expected)
            self.assertEqual(plan['plan_sha256'], hashlib.sha256(json.dumps(
                {key: value for key, value in plan.items() if key != 'plan_sha256'},
                sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
            self.assertEqual(plan['runtime'], self._json(evidence / 'runtime-identity.json'))
            self.assertEqual(plan['binding'], self._json(evidence / 'binding.json'))
            self.assertEqual(plan['context']['rootdir'], 'backend')
            self.assertIsNone(plan['context']['config'])
            self.assertEqual(plan['context']['importmode'], 'prepend')
            self.assertEqual(plan['context']['plugins'], ['ci_backend_evidence',
                'ci_backend_snapshot_cleanup', 'ci_backend_storage', 'ci_backend_shards'])
            self.assertNotIn(SENTINEL, (self.reference / 'plan.json').read_text())
            workers = self.root / 'public-workers'
            workers.mkdir()
            for shard in range(4):
                evidence, status = self._runner(f'worker-{shard}', 'worker', shard)
                metadata, metadata_exit = self._metadata(f'worker-{shard}', evidence)
                target = workers / str(shard)
                target.mkdir()
                self._helper(f'export-{shard}', 'export-worker', self.reference / 'plan.json',
                             evidence, metadata, shard, status, metadata_exit, target / 'worker.json')
            job_results = {**self.env, 'REFERENCE_JOB_RESULT': 'success', 'WORKERS_JOB_RESULT': 'success'}
            joined_path = self.root / 'qualified.json'
            self._helper('join-positive', 'join', self.reference, workers, joined_path, env=job_results)
            joined = self._json(joined_path)
            self.assertEqual(joined['reference_node_sha256'], expected)
            self.assertEqual(joined['plan_sha256'], plan['plan_sha256'])
            self.assertEqual(joined['binding'], plan['binding'])
            self.assertEqual([row['shard'] for row in joined['workers']], list(range(4)))
            actual = Counter()
            for worker in joined['workers']:
                self.assertEqual(worker['runtime'], plan['runtime'])
                assigned = [node for row in plan['modules'] if row['shard'] == worker['shard']
                            for node in row['node_sha256']]
                self.assertEqual(worker['metadata']['collected_node_sha256'], assigned)
                self.assertEqual(worker['metadata']['coverage']['phase_counts'],
                    {phase + '/passed': len(assigned) for phase in ('setup', 'call', 'teardown')})
                actual.update(worker['metadata']['collected_node_sha256'])
            self.assertEqual(actual, Counter(expected))
            self.assertNotIn(SENTINEL, joined_path.read_text())

            # A real failed assertion is diagnostic, never a successful worker.
            evidence, status = self._runner('failed-worker', 'worker', 0, fail=True)
            metadata, metadata_exit = self._metadata('failed-worker', evidence)
            failure = self._json(metadata)
            self.assertEqual(failure['pytest_exit_code'], 1)
            self.assertTrue(failure['rows_exported'])
            self.assertTrue(failure['coverage']['all_collected_completed'])
            self.assertFalse(failure['coverage']['ci_success_consistent'])
            self.assertEqual(failure['coverage']['phase_counts'],
                             {'setup/passed': 2, 'call/passed': 1, 'call/failed': 1, 'teardown/passed': 2})
            self.assertEqual(len(failure['failures']), 1)
            rejected = self.root / 'rejected-worker.json'
            self._helper('export-failed-worker', 'export-worker', self.reference / 'plan.json',
                         evidence, metadata, 0, status, metadata_exit, rejected, expected=2)
            self.assertFalse(rejected.exists())
            rejected_join = self.root / 'rejected-join.json'
            self._helper('join-failed-job', 'join', self.reference, workers, rejected_join,
                         env={**job_results, 'WORKERS_JOB_RESULT': 'failure'}, expected=2)
            self.assertFalse(rejected_join.exists())
            self._command('git-status', ['/usr/bin/git', 'status', '--porcelain'])
            self.assertEqual((self.root / 'git-status/stdout').read_text(), '')
        finally:
            # Actual handles only. Unknown groups retain evidence and fail closed.
            primary = sys.exc_info()[1]
            until = time.monotonic() + 150
            cleanup = []
            for process in self.handles:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=max(0, min(135, until - time.monotonic())))
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=max(0, min(15, until - time.monotonic())))
                    self._group_absent(process.pid, deadline=until)
                    self.assertFalse(Path(f'/proc/{process.pid}').exists())
                except (OSError, subprocess.TimeoutExpired, AssertionError) as error:
                    cleanup.append(dict(pid=process.pid, status=type(error).__name__))
            source_equal = source_map(self.repo) == self.before if hasattr(self, 'before') else None
            tools_equal = {name: sha(SCRIPTS / name) == value for name, value in frozen.items()}
            (self.root / 'closure.json').write_text(json.dumps(dict(
                source_equal=source_equal, tools_equal=tools_equal, cleanup_errors=cleanup,
                primary_error=type(primary).__name__ if primary is not None else None,
                owned_pids=[process.pid for process in self.handles]), indent=2) + '\n')
            self._write_records()
            if primary is None:
                self.assertEqual(cleanup, [], 'OWNED_CHILD_CLOSURE_UNKNOWN: outputs retained')
                self.assertTrue(source_equal)
                self.assertTrue(all(tools_equal.values()))


if __name__ == '__main__':
    unittest.main()
