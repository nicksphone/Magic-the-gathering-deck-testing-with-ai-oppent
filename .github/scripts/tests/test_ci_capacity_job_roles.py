"""Exact hosted job admission; SDK deletion uses the original mocked fixture."""
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import test_ci_backend_capacity as capacity_fixture


class BackendCapacityJobRoleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = capacity_fixture.BackendCapacityTests('runTest')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def admit(self, job):
        fixture = self.fixture
        fixture.env['GITHUB_JOB'] = job
        fixture.run.side_effect = fixture.delete_command
        output = fixture.call([fixture.module.MIN_FREE_BYTES] * 4)
        self.assertIn('CI_BACKEND_CAPACITY_READY cleanup=fixed-unused-sdks', output)
        self.assertEqual([Path(call.args[0][-1]) for call in fixture.run.call_args_list],
                         list(fixture.sdk))
        self.assertEqual((fixture.root / 'toolcache/keep').read_text(), 'unchanged')

    def test_legacy_backend_job_remains_admitted(self):
        self.admit('backend')

    def test_backend_reference_job_is_admitted(self):
        self.admit('backend-reference')

    def test_backend_workers_job_is_admitted(self):
        self.admit('backend-workers')

    def test_other_or_near_match_jobs_reject_before_observation_or_commands(self):
        fixture = self.fixture
        for job in ('frontend', 'browser', 'backend-reference-extra',
                    'backend-workers-extra', 'Backend', '', None, True, 1):
            with self.subTest(job=job), patch.dict(fixture.env, GITHUB_JOB=job), \
                    patch.object(fixture.module, 'available_bytes') as measure:
                with self.assertRaisesRegex(fixture.module.CapacityError,
                                            '^hosted-backend-context$'):
                    fixture.module.preflight(fixture.env)
                measure.assert_not_called()
                fixture.run.assert_not_called()

    def test_new_jobs_preserve_every_other_hosted_context_guard(self):
        fixture = self.fixture
        wrong_values = dict(GITHUB_ACTIONS='false', RUNNER_ENVIRONMENT='self-hosted',
            RUNNER_OS='Windows', RUNNER_ARCH='ARM64',
            GITHUB_REPOSITORY='another/repo', MTG_CI_CAPACITY_SCOPE='')
        for job in ('backend-reference', 'backend-workers'):
            for key, wrong in wrong_values.items():
                with self.subTest(job=job, key=key), \
                        patch.dict(fixture.env, {'GITHUB_JOB': job, key: wrong}), \
                        patch.object(fixture.module, 'available_bytes') as measure:
                    with self.assertRaisesRegex(fixture.module.CapacityError,
                                                '^hosted-backend-context$'):
                        fixture.module.preflight(fixture.env)
                    measure.assert_not_called()
                    fixture.run.assert_not_called()

    def test_new_jobs_do_not_bypass_sdk_symlink_safety(self):
        fixture = self.fixture
        fixture.sdk[0].rmdir()
        fixture.sdk[0].symlink_to(fixture.root / 'toolcache')
        for job in ('backend-reference', 'backend-workers'):
            with self.subTest(job=job), patch.dict(fixture.env, GITHUB_JOB=job):
                with self.assertRaisesRegex(fixture.module.CapacityError, '^sdk-path$'):
                    fixture.call([fixture.module.MIN_FREE_BYTES] * 2)
                fixture.run.assert_not_called()
                self.assertEqual((fixture.root / 'toolcache/keep').read_text(), 'unchanged')


class WorkflowCapacityJobRoleTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (Path(__file__).resolve().parents[2] / 'workflows/ci.yml').read_text()

    def job_steps(self, name):
        body = self.workflow.split(f'  {name}:\n', 1)[1]
        body = re.split(r'^  [A-Za-z0-9_-]+:\n', body, maxsplit=1, flags=re.M)[0]
        return re.split(r'(?=^      - (?:name|uses): )', body, flags=re.M)[1:]

    def test_reference_and_workers_admit_capacity_before_all_application_work(self):
        for name in ('backend-reference', 'backend-workers'):
            with self.subTest(job=name):
                steps = self.job_steps(name)
                self.assertTrue(steps[0].startswith('      - name: Start absolute work deadline\n'))
                self.assertTrue(steps[1].startswith('      - uses: actions/checkout@'))
                self.assertTrue(steps[2].startswith('      - uses: actions/setup-python@'))
                admissions = [step for step in steps
                              if step.startswith('      - name: Backend runner capacity admission\n')]
                self.assertEqual(len(admissions), 1)
                self.assertEqual(steps[3], admissions[0])
                self.assertTrue(steps[4].startswith(
                    '      - name: Admit platform and install complete hashed application closure\n'))

    def test_each_capacity_admission_uses_existing_deadline_and_no_job_forgery(self):
        expected = (
            '      - name: Backend runner capacity admission\n'
            '        timeout-minutes: 330\n'
            '        env:\n'
            '          MTG_CI_CAPACITY_SCOPE: backend-sdk-cleanup\n'
            '        run: |\n'
            '          remaining=$(python .github/scripts/ci_backend_shards.py remaining)\n'
            '          timeout --signal=TERM --kill-after=15s "${remaining}s" python .github/scripts/ci_backend_capacity.py\n')
        for name in ('backend-reference', 'backend-workers'):
            with self.subTest(job=name):
                steps = self.job_steps(name)
                admissions = [step for step in steps
                              if step.startswith('      - name: Backend runner capacity admission\n')]
                self.assertEqual(admissions, [expected])
                self.assertEqual(''.join(steps).count('MTG_CI_WORK_DEADLINE='), 1)
                self.assertIn('time.monotonic() + 19800', steps[0])
        self.assertNotRegex(self.workflow, r'(?m)^\s+GITHUB_JOB\s*:')
        self.assertNotRegex(self.workflow, r'(?m)^\s+(?:export )?GITHUB_JOB=')


if __name__ == '__main__':
    unittest.main()
