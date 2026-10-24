import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const implementation = process.env.MTG_CORS_IMPLEMENTATION || new URL('./browser-cors-transport-diagnostic.mjs', import.meta.url).href;
const {patternsFor, continueRequest, interception, runCase, diagnostic} = await import(implementation);
const url = 'http://127.0.0.1:10199/matches/PRIVATE_ID/action';

test('baseline has no interception patterns', () => {
  assert.deepEqual(patternsFor('baseline', url), []);
});
test('current mode retains one native Request pattern', () => {
  assert.deepEqual(patternsFor('current-request', url), [{urlPattern: url, requestStage: 'Request'}]);
});
test('response-only mode uses a native Response pattern', () => {
  assert.deepEqual(patternsFor('response-only', url), [{urlPattern: url, requestStage: 'Response'}]);
});
test('dual-static mode declares Request and Response patterns', () => {
  assert.deepEqual(patternsFor('dual-static', url), ['Request', 'Response'].map(requestStage => ({urlPattern: url, requestStage})));
});
for (const method of ['OPTIONS', 'POST']) {
  test(`dual-static ${method} continuation has no experimental override`, async () => {
    const calls = [];
    assert.equal(await continueRequest('dual-static', async (...args) => calls.push(args), {requestId: 'PRIVATE_ID', request: {method}}), true);
    assert.deepEqual(calls, [['Fetch.continueRequest', {requestId: 'PRIVATE_ID'}]]);
  });
  test(`current ${method} continuation retains the exact existing helper behavior`, async () => {
    const calls = [];
    assert.equal(await continueRequest('current-request', async (...args) => calls.push(args), {requestId: 'PRIVATE_ID', request: {method}}), true);
    assert.deepEqual(calls, [['Fetch.continueRequest', {requestId: 'PRIVATE_ID', interceptResponse: method === 'POST'}]]);
  });
}
test('actual response pauses are not mistaken for request pauses', async () => {
  const command = async () => { throw Error('must not call'); };
  for (const mode of ['current-request', 'dual-static']) {
    assert.equal(await continueRequest(mode, command, {responseStatusCode: 200, request: {method: 'POST'}}), false);
    assert.equal(await continueRequest(mode, command, {responseErrorReason: 'Failed', request: {method: 'POST'}}), false);
  }
});

function capture(command = async () => ({})) {
  const row = {acks: [], pauses: [], pauseCount: 0, infrastructureError: false, errorClass: null};
  return {row, control: interception('response-only', url, command, row)};
}
const pause = (method = 'POST', changes = {}) => ({requestId: 'PRIVATE_ID',
  request: {url, method, postData: 'PRIVATE_BODY', headers: {Authorization: 'PRIVATE_KEY'}}, responseStatusCode: 200, ...changes});

test('only an actual native POST200 pause is held; release occurs once', async () => {
  const calls = [], {row, control} = capture(async (...args) => calls.push(args));
  await control.handle(pause());
  assert.equal(control.held(), true); assert.equal(row.heldPOST200, true); assert.deepEqual(calls, []);
  await control.release();
  assert.deepEqual(calls, [['Fetch.continueResponse', {requestId: 'PRIVATE_ID'}]]);
  assert.equal(row.releaseAccepted, true);
  await assert.rejects(control.release(), /Invalid diagnostic release/);
  assert.equal(calls.length, 1);
});
test('genuine OPTIONS response is continued and never held', async () => {
  const calls = [], {control} = capture(async (...args) => calls.push(args));
  await control.handle(pause('OPTIONS'));
  assert.equal(control.held(), false);
  assert.deepEqual(calls, [['Fetch.continueResponse', {requestId: 'PRIVATE_ID'}]]);
});
test('non200 and native response-error pauses cannot fabricate a POST200 hold', async () => {
  for (const changes of [{responseStatusCode: 422}, {responseStatusCode: undefined, responseErrorReason: 'PRIVATE_ERROR'}]) {
    const {control, row} = capture(); await control.handle(pause('POST', changes));
    assert.equal(control.held(), false); assert.equal(row.heldPOST200, undefined);
    assert.equal(JSON.stringify(row).includes('PRIVATE_'), false);
  }
});
test('unexpected URL/method and rejected ACK fail closed without raw errors', async () => {
  for (const value of [pause('GET'), pause('POST', {request: {url: 'PRIVATE_FOREIGN', method: 'POST'}})]) {
    const {row, control} = capture(); await control.handle(value);
    assert.equal(row.infrastructureError, true); assert.equal(JSON.stringify(row).includes('PRIVATE_'), false);
  }
  const {row, control} = capture(async () => { throw new TypeError('PRIVATE_URL_BODY'); });
  await control.handle(pause('OPTIONS')); assert.equal(row.infrastructureError, true);
  assert.equal(row.acks[0].accepted, false); assert.equal(row.acks[0].errorClass, 'TypeError');
  assert.equal(JSON.stringify(row).includes('PRIVATE_'), false);
});
test('callback drain cannot report closed before the actual command ACK', async () => {
  let finish; const {control} = capture(() => new Promise(resolve => { finish = resolve; }));
  const task = control.handle(pause('OPTIONS')); await Promise.resolve();
  let drained = false; const drain = control.drain().then(value => { drained = value; });
  await Promise.resolve(); assert.equal(drained, false); assert.equal(control.pending(), 1);
  finish({}); await task; await drain;
  assert.equal(drained, true); assert.equal(control.pending(), 0);
});
test('event and command records are bounded under overflow', async () => {
  const {row, control} = capture();
  for (let index = 0; index < 20; index++) await control.handle(pause('OPTIONS'));
  assert.equal(row.pauses.length, 16); assert.equal(row.acks.length, 16);
  assert.equal(row.overflow, true); assert.equal(row.infrastructureError, true);
});
test('native Network observer records only the owned action request and typed failure', () => {
  const {row, control} = capture();
  assert.equal(typeof control.handle.observeBrowserEvent, 'function');
  control.handle.observeBrowserEvent({method: 'Network.requestWillBeSent', params: {requestId: 'PRIVATE_NET', request: {url, method: 'POST', postData: 'PRIVATE_BODY'}}});
  control.handle.observeBrowserEvent({method: 'Network.loadingFailed', params: {requestId: 'PRIVATE_OTHER', errorText: 'PRIVATE_OTHER'}});
  control.handle.observeBrowserEvent({method: 'Network.loadingFailed', params: {requestId: 'PRIVATE_NET', errorText: 'net::ERR_ABORTED', canceled: true}});
  assert.equal(row.nativePOSTs, 1); assert.equal(row.nativeErrorClass, 'net::ERR_ABORTED'); assert.equal(row.nativeCanceled, true);
  assert.equal(JSON.stringify(row).includes('PRIVATE_'), false);
});

// These injected protocol doubles never run React, Chromium, HTTP or an engine.
function protocol(options = {}) {
  let clock = 0, serial = 0, state, browserState;
  const calls = [], browsers = [], signals = [];
  const closeSignals = [], closeSleeps = [];
  let closing = false, closeReads = 0;
  const context = {backend: 'http://127.0.0.1:10199', frontend: 'http://127.0.0.1:15173', usedIds: new Set(),
    now: () => clock, sleep: async ms => { if (closing) closeSleeps.push(ms); clock += ms; }, key: () => 'PRIVATE_KEY',
    async request(location, init = {}) {
      calls.push(location.endsWith('/fixture') ? 'fixture' : location.endsWith('/json/list') ? 'target-list' : 'state');
      if (options.httpFailure) throw new TypeError('PRIVATE_URL_BODY');
      if (location.endsWith('/json/list')) {
        closeSignals.push(init.signal); closeReads++;
        clock += options.closeReadElapsed ?? 0;
        if (options.closeReadFailure) throw new TypeError('PRIVATE_CLOSE_READ');
        return {ok: !options.closeHTTPFailure, status: options.closeHTTPFailure ? 503 : 200, json: async () => {
          clock += options.closeBodyElapsed ?? 0;
          if (options.closeJSONFailure) throw new SyntaxError('PRIVATE_JSON');
          if (Object.hasOwn(options, 'listShape')) return options.listShape;
          return options.targetStillPresent || closeReads <= (options.presentReads ?? 0) ? [{id: `PRIVATE_TARGET_${serial}`}] : [];
        }};
      }
      if (location.endsWith('/fixture')) {
        state = {id: `PRIVATE_FIXTURE_${++serial}`, active_player: options.invalidPose ? 1 : 2, priority_player: 2,
          step: 'precombat_main', revision: 0, players: {'2': {hand: [{id: 'forest'}], battlefield: []}}};
        return {ok: true, json: async () => structuredClone(state)};
      }
      signals.push(init.signal);
      return {ok: true, async json() { clock += options.bodyElapsed ?? 0; return structuredClone(state); }};
    },
    async open() {
      let handler, enabled = false;
      browserState = {state: 'pending', status: null, errorClass: null};
      const browser = {
        onIntercept(value) { handler = value; },
        async command(method) {
          calls.push(method);
          if (options.failCommand === method) throw new Error('PRIVATE_NATIVE_ID');
          if (method === 'Target.getTargetInfo') return options.missingTarget ? {} : {targetInfo: {
            targetId: `PRIVATE_TARGET_${serial}`, type: 'page', url: `${context.frontend}/tests/fixtures/ci-development-runtime/probe.html`}};
          if (method === 'Fetch.enable') enabled = true;
          if (method === 'Fetch.continueResponse') browserState = {state: 'fulfilled', status: 200, errorClass: null};
          return {};
        },
        async evaluate(expression) {
          if (expression.includes('void fetch(')) {
            calls.push('page-POST');
            assert.match(expression, /AbortSignal.timeout\(30000\)/);
            if (!options.abort || options.commitDespiteAbort) {
              state.revision++; state.players['2'].hand = []; state.players['2'].battlefield = [{id: 'forest'}];
            }
            if (options.abort) browserState = {state: 'rejected', status: null, errorClass: 'TypeError'};
            else if (!enabled) browserState = {state: 'fulfilled', status: 200, errorClass: null};
            else await handler(pause('POST', {request: {url: `${context.backend}/matches/${state.id}/action`, method: 'POST'}}));
            if (options.startElapsed) clock += options.startElapsed;
            return true;
          }
          if (options.invalidPage) return {state: 'PRIVATE_BODY', status: null, errorClass: null};
          if (options.prematureFulfillment) return {state: 'fulfilled', status: 200, errorClass: null};
          return structuredClone(browserState);
        },
        async close() { calls.push('close'); closing = true; clock += options.closeElapsed ?? 0; if (options.closeFailure) throw new Error('PRIVATE_CLOSE'); },
      };
      browsers.push(browser); return browser;
    }};
  return {context, calls, browsers, signals, closeSignals, closeSleeps};
}
test('protocol baseline must prove the actual revision and single land transition', async () => {
  const f = protocol(); const row = await runCase('baseline', f.context);
  assert.equal(row.baselineValid, true); assert.equal(row.actionPOSTs, 1);
  assert.equal(row.before.revision, 0); assert.equal(row.afterAttempt.revision, 1);
  assert.equal(row.pageClosed, true); assert.equal(row.callbacksDrained, true); assert.equal(row.fetchDisabled, true);
  assert.equal(f.calls.filter(x => x === 'page-POST').length, 1); assert.equal(f.calls.includes('Fetch.enable'), false);
  assert.equal(f.calls.filter(x => x === 'target-list').length, 1);
  assert.ok(f.calls.indexOf('target-list') > f.calls.indexOf('close'));
});
test('protocol native hold samples pending plus canonical state before one explicit release', async () => {
  const f = protocol(); const row = await runCase('response-only', f.context);
  assert.equal(row.browserBeforeRelease.state, 'pending'); assert.equal(row.beforeHold.revision, 1);
  assert.equal(row.browserAfterRelease.state, 'fulfilled'); assert.equal(row.afterRelease.revision, 1);
  assert.equal(f.calls.filter(x => x === 'Fetch.continueResponse').length, 1);
  const release = f.calls.indexOf('Fetch.continueResponse');
  assert.ok(f.calls.slice(0, release).filter(x => x === 'state').length >= 2);
  assert.ok(f.calls.slice(release + 1).includes('state'));
});
test('protocol expected abort is an observation, never a no-mutation conclusion', async () => {
  for (const committed of [false, true]) {
    const f = protocol({abort: true, commitDespiteAbort: committed}); const row = await runCase('current-request', f.context);
    assert.equal(row.browserFinal.state, 'rejected'); assert.equal(row.afterAttempt.revision, Number(committed));
    assert.equal(row.laterMutationNotRuledOut, true); assert.equal(row.infrastructureError, false);
    assert.equal(row.afterRelease.read, 'unavailable'); assert.equal(row.releaseAttempted, false);
  }
});
test('protocol cannot call an already-settled browser promise a successful native hold', async () => {
  const f = protocol({prematureFulfillment: true}); const row = await runCase('response-only', f.context);
  assert.equal(row.browserBeforeRelease.state, 'fulfilled');
  assert.equal(row.infrastructureError, true);
  assert.equal(row.releaseAccepted, true); assert.equal(row.pageClosed, true);
});
test('protocol body consumption shares the same two-second budget before any action', async () => {
  const f = protocol({bodyElapsed: 2001}); const row = await runCase('baseline', f.context);
  assert.equal(row.before.read, 'unavailable'); assert.equal(row.actionPOSTs, 0);
  assert.equal(row.infrastructureError, true); assert.equal(row.pageClosed, true);
  assert.ok(f.signals[0] instanceof AbortSignal);
});
test('protocol shared budget expiry cannot fabricate after-release availability or reset a clock', async () => {
  const f = protocol({startElapsed: 2001}); const row = await runCase('response-only', f.context);
  assert.equal(row.releaseAccepted, true); assert.equal(row.beforeHold.read, 'unavailable');
  assert.equal(row.afterRelease.read, 'unavailable'); assert.equal(row.browserAfterRelease, null);
  assert.equal(row.laterMutationNotRuledOut, true); assert.equal(f.calls.filter(x => x === 'state').length, 1);
});
test('protocol bad fixture/HTTP and page metadata fail closed without private content', async () => {
  for (const options of [{invalidPose: true}, {httpFailure: true}, {invalidPage: true}]) {
    const f = protocol(options); const row = await runCase('baseline', f.context);
    assert.equal(row.infrastructureError, true); assert.equal(JSON.stringify(row).includes('PRIVATE_'), false);
  }
});
test('protocol rejected disable or page closure is not reported quiet', async () => {
  for (const options of [{failCommand: 'Fetch.disable'}, {closeFailure: true}]) {
    const f = protocol(options); const row = await runCase('baseline', f.context);
    assert.equal(row.infrastructureError, true);
    assert.equal(options.closeFailure ? row.pageClosed : row.fetchDisabled, false);
    assert.equal(JSON.stringify(row).includes('PRIVATE_'), false);
  }
});
test('protocol close-return alone cannot qualify a still-present target or failed debugger read', async () => {
  for (const options of [{targetStillPresent: true}, {closeHTTPFailure: true}]) {
    const f = protocol(options); const row = await runCase('baseline', f.context);
    assert.equal(row.infrastructureError, true); assert.equal(row.pageClosed, false);
    assert.equal(JSON.stringify(row).includes('PRIVATE_'), false);
  }
});
test('protocol missing genuine native target identity cannot produce a closure certificate', async () => {
  const f = protocol({missingTarget: true}); const row = await runCase('baseline', f.context);
  assert.equal(row.infrastructureError, true); assert.equal(row.pageClosed, false);
  assert.equal(row.actionPOSTs, 0);
});
test('protocol baseline invalidity stops the cohort, with one action and no retry', async () => {
  const f = protocol({abort: true}); const rows = await diagnostic(f.context);
  assert.equal(rows.length, 1); assert.equal(rows[0].baselineValid, false);
  assert.equal(rows[0].infrastructureError, true); assert.equal(f.calls.filter(x => x === 'page-POST').length, 1);
});
test('protocol four-mode cohort uses fresh pages/fixtures and exposes scalar-only records', async () => {
  const f = protocol(); const rows = await diagnostic(f.context);
  assert.equal(rows.length, 4); assert.equal(f.browsers.length, 4);
  assert.equal(f.calls.filter(x => x === 'fixture').length, 4); assert.equal(f.calls.filter(x => x === 'page-POST').length, 4);
  assert.ok(rows.every(row => row.pageClosed && row.callbacksDrained && !row.infrastructureError));
  assert.doesNotMatch(JSON.stringify(rows), /PRIVATE_|https?:|Authorization|Idempotency|postData/);
});
test('source never requests response bodies via CDP and prints typed records before a static throw', () => {
  const source = fs.readFileSync(new URL('./browser-cors-transport-diagnostic.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /getResponseBody|fulfillRequest|failRequest|console\.(?:log|error)\([^\n]*error\)/);
  assert.ok(source.indexOf("console.error('CORS_TRANSPORT_DIAGNOSTIC'") < source.indexOf("throw new Error('CORS transport diagnostic failed"));
});
test('ordinary-only launcher hook preserves the entire original program by byte inverse', () => {
  let source = fs.readFileSync(new URL('./run-browser-ci.sh', import.meta.url), 'utf8');
  // Undo exactly the separately exercised zone-keyword scenario before the legacy checks.
  const zoneScenario = '(cd frontend && run_browser_program "browser-zone-keyword-actions.mjs" timeout 300s node tests/browser-zone-keyword-actions.mjs)\n';
  assert.equal(source.split(zoneScenario).length, 2);
  source = source.replace(zoneScenario, '');
  // Undo only the separately tested program-reporting layer before the old hash.
  let wrapped = 0;
  source = source.replace(/run_browser_program ("[a-z0-9._-]+"|"\$scenario") (timeout \d+s )?(node|bash) ("tests\/\$scenario"|(?:frontend\/)?tests\/[a-z0-9._-]+)/g,
    (_match, label, deadline = '', executable, operand) => {
      assert.equal(label.slice(1, -1), operand.replaceAll('"', '').split('/').at(-1));
      wrapped += 1;
      return `${deadline}${executable} ${operand}`;
    });
  assert.equal(wrapped, 73);
  for (const [added, original] of [
    ['source "$root/frontend/tests/browser-program-diagnostic.sh"\n\n', ''],
    ['  if ((status)); then report_browser_bootstrap_failure "$status" "${1:-1}" || :; fi\n', ''],
    ['trap \'cleanup "$LINENO"\' EXIT', 'trap cleanup EXIT'],
  ]) {
    assert.equal(source.split(added).length, 2);
    source = source.replace(added, original);
  }
  const begin = source.indexOf('# CORS transport diagnostic: ordinary hosted CDP only.\n');
  const end = source.indexOf("echo 'Browser CI: async readiness helper'", begin);
  assert.ok(begin >= 0 && end > begin);
  const hook = source.slice(begin, end);
  assert.match(hook, /^# CORS transport diagnostic: ordinary hosted CDP only\.\ncors_diagnostic_status=0\nif \[\[ -z "\$\{MTG_BROWSER_VENDOR:-\}" \]\]; then\n/);
  assert.match(hook, /timeout 45s node tests\/browser-cors-transport-diagnostic\.mjs/);
  assert.match(hook, /classification.*not-applicable.*native-vendor-scope/);
  assert.ok(hook.endsWith('fi\n')); assert.doesNotMatch(hook, /\b(?:exit|return|continue|break)\b/);
  const footer = source.indexOf('# Propagate diagnostic failure only after the unchanged full browser suite.\n');
  assert.ok(footer > end);
  const original = source.slice(0, begin) + source.slice(end, footer);
  assert.equal(createHash('sha256').update(original).digest('hex'), 'f9004615e9da07bfa624f22be2e6c212b5d06dbaf6666564d51c78283e504933');
  assert.equal((source.match(/^echo 'Browser CI: /gm) || []).length, 45);
  assert.ok(source.indexOf('browser-development-runtime-proof.mjs') < begin);
});

function actualLauncherFlow(diagnosticStatus, originalStatus, vendor = '') {
  const source = fs.readFileSync(new URL('./run-browser-ci.sh', import.meta.url), 'utf8');
  const begin = source.indexOf('# CORS transport diagnostic: ordinary hosted CDP only.\n');
  const end = source.indexOf("echo 'Browser CI: async readiness helper'", begin);
  const hook = source.slice(begin, end);
  const footerAt = source.indexOf('# Propagate diagnostic failure only after the unchanged full browser suite.\n');
  const footer = footerAt < 0 ? '' : source.slice(footerAt);
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'mtg-cors-flow-'));
  try {
    fs.mkdirSync(path.join(root, 'frontend'));
    fs.mkdirSync(path.join(root, 'bin'));
    fs.writeFileSync(path.join(root, 'bin/timeout'), `#!/bin/bash
[[ "$#" == 3 && "$1" == 45s && "$2" == node && "$3" == tests/browser-cors-transport-diagnostic.mjs ]] || exit 97
printf 'diagnostic\\n' >> "$CASE_REPORT"
exit "$DIAGNOSTIC_STATUS"
`, {mode: 0o700});
    const script = `set -euo pipefail
source "$DIAGNOSTIC_HELPER"
trap 'status=$?; printf "cleanup:%s\\n" "$status" >> "$CASE_REPORT"; exit "$status"' EXIT
${hook}
printf 'suite-start\\n' >> "$CASE_REPORT"
(exit "$ORIGINAL_STATUS")
printf 'suite-end\\n' >> "$CASE_REPORT"
${footer}`;
    const result = spawnSync('/bin/bash', ['-c', script], {cwd: root, encoding: 'utf8', timeout: 5000,
      env: {...process.env, PATH: `${root}/bin:/usr/bin:/bin`, CASE_REPORT: `${root}/events`,
        DIAGNOSTIC_STATUS: String(diagnosticStatus), ORIGINAL_STATUS: String(originalStatus), MTG_BROWSER_VENDOR: vendor,
        DIAGNOSTIC_HELPER: fileURLToPath(new URL('./browser-program-diagnostic.sh', import.meta.url))}});
    return {...result, events: fs.readFileSync(path.join(root, 'events'), 'utf8').trim().split('\n')};
  } finally { fs.rmSync(root, {recursive: true}); }
}

for (const diagnosticStatus of [0, 1, 124, 143]) {
  test(`actual Bash diagnostic exit${diagnosticStatus} still runs the entire successful original suite`, () => {
    const result = actualLauncherFlow(diagnosticStatus, 0);
    assert.equal(result.error, undefined); assert.equal(result.signal, null);
    assert.equal(result.status, diagnosticStatus, result.stderr);
    assert.deepEqual(result.events, ['diagnostic', 'suite-start', 'suite-end', `cleanup:${diagnosticStatus}`]);
  });
  test(`actual Bash original failure23 takes precedence over diagnostic exit${diagnosticStatus}`, () => {
    const result = actualLauncherFlow(diagnosticStatus, 23);
    assert.equal(result.error, undefined); assert.equal(result.signal, null);
    assert.equal(result.status, 23, result.stderr);
    assert.deepEqual(result.events, ['diagnostic', 'suite-start', 'cleanup:23']);
  });
}
for (const vendor of ['chrome', 'brave', 'firefox']) {
  test(`actual Bash native ${vendor} skips only the CDP spike, not the original suite`, () => {
    const result = actualLauncherFlow(143, 0, vendor);
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(result.events, ['suite-start', 'suite-end', 'cleanup:0']);
    assert.match(result.stdout, /not-applicable.*native-vendor-scope/);
  });
}
test('actual Bash native original failure retains its strict exit and cleanup', () => {
  const result = actualLauncherFlow(143, 23, 'chrome');
  assert.equal(result.status, 23, result.stderr);
  assert.deepEqual(result.events, ['suite-start', 'cleanup:23']);
});

test('closure observes immediate presence then actual absence after exactly one close', async () => {
  const f = protocol({presentReads: 2}); const row = await runCase('baseline', f.context);
  assert.equal(row.baselineValid, true); assert.equal(row.infrastructureError, false);
  assert.equal(row.pageClosed, true); assert.equal(row.closureReason, 'target-absent');
  assert.equal(row.closurePolls, 3); assert.equal(row.closureReadHTTPStatus, 200);
  assert.equal(row.closureListCount, 0); assert.equal(row.closureOwnTargetPresent, false);
  assert.equal(row.closureElapsedMs, 40);
  assert.equal(f.calls.filter(x => x === 'close').length, 1);
  assert.deepEqual(f.closeSleeps, [20, 20]);
});
test('closure permanent presence is strict failure at the finite 100-read cap', async () => {
  const f = protocol({targetStillPresent: true}); const row = await runCase('baseline', f.context);
  assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
  assert.equal(row.closureReason, 'target-still-present'); assert.equal(row.closurePolls, 100);
  assert.equal(row.closureListCount, 1); assert.equal(row.closureOwnTargetPresent, true);
  assert.equal(f.calls.filter(x => x === 'close').length, 1);
  assert.equal(f.calls.filter(x => x === 'target-list').length, 100);
  assert.ok(f.closeSleeps.every(ms => ms > 0 && ms <= 20));
  assert.ok(row.closureElapsedMs < 15000);
});
test('closure rejects malformed list or target identities without retry or private data', async () => {
  for (const listShape of [null, {}, [null], [{id: ''}], [{id: 1}], [{id: 'x'.repeat(257)}],
    [{id: 'PRIVATE_DUP'}, {id: 'PRIVATE_DUP'}], Array.from({length: 17}, (_, i) => ({id: String(i)}))]) {
    const f = protocol({listShape}); const row = await runCase('baseline', f.context);
    assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
    assert.equal(row.closureReason, 'list-shape'); assert.equal(row.closurePolls, 1);
    assert.equal(row.closureListCount, null); assert.equal(row.closureOwnTargetPresent, null);
    assert.doesNotMatch(JSON.stringify(row), /PRIVATE_|https?:/);
  }
});
test('closure failed HTTP is fatal after one read with actual finite status', async () => {
  const f = protocol({closeHTTPFailure: true}); const row = await runCase('baseline', f.context);
  assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
  assert.equal(row.closureReason, 'list-http'); assert.equal(row.closureReadHTTPStatus, 503);
  assert.equal(row.closureListCount, null); assert.equal(row.closurePolls, 1);
  assert.equal(f.closeSleeps.length, 0);
});
test('closure close-call time consumes the same deadline before any observation', async () => {
  const f = protocol({closeElapsed: 14990, targetStillPresent: true}); const row = await runCase('baseline', f.context);
  assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
  assert.equal(row.closureReason, 'deadline-exhausted'); assert.equal(row.closureElapsedMs, 15000);
  assert.equal(row.closurePolls, 1); assert.deepEqual(f.closeSleeps, [10]);
  assert.equal(f.calls.filter(x => x === 'close').length, 1);
});
test('closure zero remaining time cannot issue a read or certify absence', async () => {
  const f = protocol({closeElapsed: 15000}); const row = await runCase('baseline', f.context);
  assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
  assert.equal(row.closureReason, 'deadline-exhausted'); assert.equal(row.closurePolls, 0);
  assert.equal(row.closureReadHTTPStatus, null); assert.equal(row.closureOwnTargetPresent, null);
  assert.equal(f.closeSignals.length, 0);
});
test('closure rejection retains fatal classification with no debugger reads or reclose', async () => {
  const f = protocol({closeFailure: true}); const row = await runCase('baseline', f.context);
  assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
  assert.equal(row.closureReason, 'close-rejected'); assert.equal(row.closurePolls, 0);
  assert.equal(f.calls.filter(x => x === 'close').length, 1);
  assert.doesNotMatch(JSON.stringify(row), /PRIVATE_|https?:/);
});
test('closure read and JSON errors remain fatal without retry and expose only typed fields', async () => {
  for (const option of ['closeReadFailure', 'closeJSONFailure']) {
    const f = protocol({[option]: true}); const row = await runCase('baseline', f.context);
    assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
    assert.equal(row.closureReason, 'list-read-failed'); assert.equal(row.closurePolls, 1);
    assert.equal(row.errorClass, option === 'closeReadFailure' ? 'TypeError' : 'SyntaxError');
    assert.doesNotMatch(JSON.stringify(row), /PRIVATE_|https?:/);
  }
});
test('closure cannot accept an absent result whose request or body exhausted the budget', async () => {
  for (const option of ['closeReadElapsed', 'closeBodyElapsed']) {
    const f = protocol({[option]: 15001}); const row = await runCase('baseline', f.context);
    assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
    assert.equal(row.closureReason, 'deadline-exhausted'); assert.equal(row.closurePolls, 1);
    assert.equal(row.closureElapsedMs, 15000); assert.equal(row.closureOwnTargetPresent, null);
  }
});
test('closure read AbortSignals consume only remaining close budget, never a fresh 15 seconds', async () => {
  const timeout = AbortSignal.timeout, values = [];
  AbortSignal.timeout = ms => { values.push(ms); return timeout(ms); };
  try {
    const f = protocol({closeElapsed: 14000, presentReads: 1}); const row = await runCase('baseline', f.context);
    assert.equal(row.pageClosed, true); assert.equal(row.closurePolls, 2);
    assert.deepEqual(values.slice(-2), [1000, 980]);
    assert.ok(f.closeSignals.every(signal => signal instanceof AbortSignal));
  } finally { AbortSignal.timeout = timeout; }
});
test('closure absence cannot mask rejected disable or missing actual target identity', async () => {
  const rejected = protocol({failCommand: 'Fetch.disable'});
  const row = await runCase('baseline', rejected.context);
  assert.equal(row.infrastructureError, true); assert.equal(row.fetchDisabled, false);
  assert.equal(row.pageClosed, true); assert.equal(row.closureReason, 'target-absent');
  const missing = protocol({missingTarget: true}); const other = await runCase('baseline', missing.context);
  assert.equal(other.infrastructureError, true); assert.equal(other.pageClosed, false);
  assert.equal(other.closureReason, 'identity-unavailable'); assert.equal(other.closurePolls, 0);
});
test('closure expiry between loop check and read cannot admit a one-millisecond fresh request', async () => {
  const f = protocol(), originalNow = f.context.now;
  let closingReads = 0;
  f.context.now = () => originalNow() + (f.calls.includes('close') && ++closingReads > 1 ? 15000 : 0);
  const row = await runCase('baseline', f.context);
  assert.equal(row.pageClosed, false); assert.equal(row.infrastructureError, true);
  assert.equal(row.closureReason, 'deadline-exhausted'); assert.equal(row.closurePolls, 0);
  assert.equal(f.closeSignals.length, 0);
});
