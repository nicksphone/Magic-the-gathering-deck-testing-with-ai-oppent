import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const read = name => readFileSync(new URL(name, import.meta.url), 'utf8');

function interactiveFlags(value) {
  const source = read('browser-interactive-preflight.mjs');
  const match = source.match(/const chromium = spawn\([^\n]+, (\[[\s\S]*?\]), \{ stdio:/);
  assert.ok(match, 'actual interactive browser argument expression');
  const env = value === undefined ? {} : { MTG_BROWSER_NO_SANDBOX: value };
  return vm.runInNewContext(match[1], {
    process: { env }, browserPort: 19387, profile: '/owned-profile',
  });
}

function activatedFlags(value) {
  const source = read('run-activated-top-selection.sh');
  const match = source.match(/frontend=\$!\n([\s\S]*?)\nbrowser=\$!/);
  assert.ok(match, 'actual activated-selection browser launch block');
  const runtime = mkdtempSync(path.join(tmpdir(), 'mtg-sandbox-flags-'));
  try {
    const script = `set -euo pipefail
runtime=$1
chrome=capture_launch
capture_launch() { printf '%s\\n' "$@"; }
${match[1]}
browser=$!
wait "$browser"
cat "$runtime/browser.log"
`;
    const env = { PATH: '/usr/bin:/bin' };
    if (value !== undefined) env.MTG_BROWSER_NO_SANDBOX = value;
    return execFileSync('/bin/bash', ['-c', script, 'sandbox-unit', runtime], {
      env, encoding: 'utf8', timeout: 5000,
    }).trim().split('\n');
  } finally {
    rmSync(runtime, { recursive: true });
  }
}

for (const [name, flags] of [['interactive', interactiveFlags], ['activated selection', activatedFlags]]) {
  for (const value of [undefined, '0', '1']) {
    test(`${name}: sandbox disablement is opt-in (${String(value)})`, () => {
      const actual = flags(value);
      assert.equal(actual.filter(flag => flag === '--no-sandbox').length, value === '1' ? 1 : 0);
      assert.ok(actual.includes('--headless'));
      assert.ok(actual.some(flag => flag.startsWith('--user-data-dir=')));
      assert.ok(actual.some(flag => flag.startsWith('--remote-debugging-port=')));
      assert.equal(actual.at(-1), 'about:blank');
    });
  }
}
