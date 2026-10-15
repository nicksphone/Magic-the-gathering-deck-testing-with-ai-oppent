import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

const script = new URL('../../.github/scripts/run-native-browser-ci.sh', import.meta.url);

test('runner-dependent report paths are resolved at step scope, not job env', () => {
  const workflow = readFileSync(new URL('../../.github/workflows/native-browser.yml', import.meta.url), 'utf8');
  const jobEnv = workflow.match(/^    env:\n([\s\S]*?)^    steps:/m);
  assert.ok(jobEnv);
  assert.equal(jobEnv[1].includes('runner.'), false, 'runner context is unavailable in job-level env');
  assert.match(workflow, /name: Secure native preflight and complete browser suite\n        env:\n          MTG_NATIVE_REPORT_DIR:/);
});

function run(status = 0, extra = {}) {
  const scratch = mkdtempSync(path.join(tmpdir(), 'mtg-native-service-unit-'));
  try {
    mkdirSync(path.join(scratch, 'bin'));
    writeFileSync(path.join(scratch, 'bin/sudo'), `#!/bin/bash
printf '%s\\0' "$@" >> "$SERVICE_CALLS"
printf '\\n' >> "$SERVICE_CALLS"
if [[ "$1" == systemd-run ]]; then exit "$SERVICE_STATUS"; fi
exit 0
`, { mode: 0o755 });
    const result = spawnSync('/bin/bash', [script.pathname], {
      cwd: new URL('../../', import.meta.url), encoding: 'utf8', timeout: 5000,
      env: { ...process.env, PATH: `${scratch}/bin:${process.env.PATH}`,
        MTG_BROWSER_VENDOR: 'chrome', MTG_CHROME: '/opt/google/chrome/chrome',
        MTG_BROWSER_NO_SANDBOX: '0', MTG_NATIVE_REPORT_DIR: scratch,
        RUNNER_TEMP: scratch,
        GITHUB_RUN_ID: '123', GITHUB_RUN_ATTEMPT: '2',
        SERVICE_CALLS: `${scratch}/calls`, SERVICE_STATUS: String(status), ...extra },
    });
    let calls = '';
    let report = null;
    try { calls = readFileSync(`${scratch}/calls`, 'utf8'); } catch { /* Rejected before launch. */ }
    try { report = JSON.parse(readFileSync(`${scratch}/lifecycle.json`, 'utf8')); } catch { /* Rejected before launch. */ }
    return { ...result, calls, report };
  } finally { rmSync(scratch, { recursive: true, force: true }); }
}

test('native service preserves the entire launcher and bounds its process cgroup', () => {
  const result = run();
  assert.equal(result.status, 0, result.stderr);
  const args = result.calls.split('\0');
  for (const flag of ['--wait', '--pipe', '--collect', '--expand-environment=no',
    '--property=KillMode=control-group', '--property=TimeoutStopSec=15s',
    '--property=RuntimeMaxSec=2700s', '--setenv=MTG_BROWSER_NO_SANDBOX=0']) {
    assert.ok(args.includes(flag), flag);
  }
  assert.ok(args.includes('--setenv=GITHUB_ACTIONS=true'));
  assert.ok(args.some(arg => arg.startsWith('--setenv=RUNNER_TEMP=/')));
  assert.ok(args.some(arg => /^--setenv=GITHUB_SHA=[0-9a-f]{40}$/.test(arg)));
  assert.ok(args.includes(`--uid=${process.getuid()}`));
  assert.ok(args.some(arg => arg.includes('node frontend/tests/browser-vendor-preflight.mjs --report')));
  assert.ok(args.some(arg => arg.includes('bash frontend/tests/run-browser-ci.sh')));
  assert.match(result.calls, /systemctl\u0000stop\u0000mtg-native-chrome-123-2\.service/);
  assert.equal(result.report.exit_status, 0);
  assert.equal(result.report.cgroup_empty, true);
});

test('service failure retains its status and still stops the entire owned cgroup', () => {
  const result = run(23);
  assert.equal(result.status, 23, result.stderr);
  assert.match(result.calls, /systemctl\u0000stop/);
  assert.equal(result.report.exit_status, 23);
});

for (const extra of [{ MTG_BROWSER_NO_SANDBOX: '1' }, { MTG_BROWSER_VENDOR: 'chromium' },
  { MTG_CHROME: '/usr/bin/chromium' }, { GITHUB_RUN_ID: '../other' }]) {
  test(`unsafe service input rejects before sudo: ${JSON.stringify(extra)}`, () => {
    const result = run(0, extra);
    assert.equal(result.status, 2, result.stderr);
    assert.equal(result.calls, '');
  });
}
