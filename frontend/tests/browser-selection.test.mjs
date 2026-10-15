import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('./run-browser-ci.sh', import.meta.url), 'utf8');

function select(env = {}) {
  const selection = source.match(/# Select the browser before starting services\.\n([\s\S]*?)\n# The harness owns/);
  assert.ok(selection, 'browser selection must precede service startup');
  const script = `set -euo pipefail
command() {
  if [[ "$2" == google-chrome && "$HAS_CHROME" == 1 ]]; then printf '/usr/bin/google-chrome\\n'; return; fi
  if [[ "$2" == chromium ]]; then printf '/usr/bin/chromium\\n'; return; fi
  return 1
}
node() {
  [[ "$1" == frontend/tests/browser-vendor-preflight.mjs && "$2" == --check-config && "$3" == "$MTG_CHROME" ]]
  return "$CONFIG_STATUS"
}
${selection[1]}
printf '%s\\n' "$browser"`;
  return spawnSync('/bin/bash', ['-c', script], {
    env: { HAS_CHROME: '1', CONFIG_STATUS: '0', ...env }, encoding: 'utf8', timeout: 5000,
  });
}

test('explicit browser executable is retained without fallback', () => {
  const result = select({ MTG_CHROME: '/opt/brave.com/brave/brave' });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), '/opt/brave.com/brave/brave');
});

for (const [name, path] of [['chrome', '/opt/google/chrome/chrome'], ['brave', '/opt/brave.com/brave/brave']]) {
  test(`native ${name} validates its explicit executable`, () => {
    const result = select({ MTG_BROWSER_VENDOR: name, MTG_CHROME: path, MTG_BROWSER_NO_SANDBOX: '0' });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), path);
  });
}

test('legacy automatic selection still prefers Chrome', () => {
  assert.equal(select().stdout.trim(), '/usr/bin/google-chrome');
  assert.equal(select({ HAS_CHROME: '0' }).stdout.trim(), '/usr/bin/chromium');
});

test('native mode never discovers a substitute browser', () => {
  const result = select({ MTG_BROWSER_VENDOR: 'brave', MTG_BROWSER_NO_SANDBOX: '0' });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /requires MTG_CHROME/);
  assert.equal(result.stdout, '');
});

test('native configuration rejection stops the launcher before services', () => {
  const result = select({ MTG_BROWSER_VENDOR: 'chrome', MTG_CHROME: '/wrong/browser', CONFIG_STATUS: '2' });
  assert.equal(result.status, 2);
  assert.equal(result.stdout, '');
});
