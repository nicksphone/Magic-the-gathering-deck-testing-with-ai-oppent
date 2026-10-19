import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {continueRequestForPostResponse, traceStartRecoveryResponses} from './browser-start-recovery-diagnostics.mjs';

// Inert transport protocol, not browser/application or canonical-card evidence.
// Execute the actual recovery function and shared helpers, never the UI module.
const source = readFileSync(new URL('./browser-ui-v2.mjs', import.meta.url), 'utf8');
const begin = source.indexOf('async function recoverDroppedResponse(s) {');
const end = source.indexOf('\ntry {\n  recoverDroppedResponse.requestSignals=', begin);
assert.ok(begin >= 0 && end > begin, 'Extract the complete real recovery function');
const actualRecovery = `(${source.slice(begin, end)})`;
const plain = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const deferred = () => {
  let resolve;
  const promise = new Promise(yes => { resolve = yes; });
  return {promise, resolve};
};
async function pump() { for (let n = 0; n < 256; n++) await Promise.resolve(); }

function protocol(options = {}) {
  const capability = Object.hasOwn(options, 'capability') ? options.capability : true;
  const api = 'http://api.invalid', origin = 'http://ui.invalid';
  const state = {id: 'public-vm-match', revision: 0};
  const actionUrl = `${api}/matches/${state.id}/action`;
  const calls = [], events = [], reports = [], legacy = [], timers = new Map(), budgets = [];
  const tasks = [], pauses = new Map(), ack = deferred();
  const invalidId = new Error(JSON.stringify({code: -32602, message: 'synthetic invalid interception'}));
  let interception, registration, enabled = false, optedPost = false, timerId = 0, now = 0;
  let clicks = 0, commits = 0, dropAcks = 0, awaitingAck = false, uiWaits = 0, reads = 0;
  let settled = false, result, failure;

  function commit() {
    commits++;
    assert.equal(commits, 1, 'No synthetic action retry or duplicate commit');
    state.revision++;
    events.push('commit');
  }
  function pause(method, requestId, fields = {}) {
    return {requestId, request: {method, url: actionUrl}, ...fields};
  }
  function deliver(event) {
    pauses.set(event.requestId, event);
    const task = Promise.resolve(interception(event));
    tasks.push(task); task.catch(() => {});
    return task;
  }
  async function command(method, params) {
    calls.push([method, plain(params)]);
    events.push(method);
    if (method === 'Network.enable') return {};
    if (method === 'Fetch.enable') {
      registration = plain(params);
      enabled = true;
      return {};
    }
    if (method === 'Fetch.disable') { enabled = false; pauses.clear(); return {}; }
    const event = pauses.get(params.requestId);
    assert.ok(event, 'Continuation must refer to an actual delivered pause');
    if (method === 'Fetch.continueRequest') {
      assert.equal(event.responseStatusCode, undefined);
      assert.equal(event.responseErrorReason, undefined);
      if (event.request.method === 'POST') optedPost = params.interceptResponse === true;
      pauses.delete(params.requestId);
      return {};
    }
    if (method === 'Fetch.continueResponse') {
      assert.ok(event.responseStatusCode !== undefined || event.responseErrorReason !== undefined);
      pauses.delete(params.requestId);
      if (event.responseErrorReason !== undefined) throw invalidId;
      return {};
    }
    assert.equal(method, 'Fetch.failRequest');
    assert.equal(event.request.method, 'POST');
    assert.equal(event.request.url, actionUrl);
    assert.equal(event.responseStatusCode, 200);
    assert.equal(params.errorReason, 'Failed');
    awaitingAck = true;
    try {
      if (options.holdAck) await ack.promise;
      if (options.ackError) throw options.ackError;
      dropAcks++; events.push('native-drop-ack');
      pauses.delete(params.requestId);
      return {};
    } finally { awaitingAck = false; }
  }
  const browser = {supportsFetchResourceTypeFilter: capability,
    onIntercept(callback) { interception = callback; },
    async browserIdentity() { return {product: 'SyntheticBrowser/1', protocolVersion: '1'}; }};
  const context = {assert, api, origin, b: browser, command, AbortController,
    continueRequestForPostResponse, traceStartRecoveryResponses,
    reportUiV2DropFailure(record) { reports.push(record); },
    console: {error(...args) { legacy.push(args); }},
    Date: {now: () => now},
    setTimeout(callback, milliseconds) {
      assert.ok([15000, 1000].includes(milliseconds), 'Keep the original recovery/diagnostic clocks');
      budgets.push(milliseconds);
      timers.set(++timerId, {callback, milliseconds});
      return timerId;
    },
    clearTimeout(id) { timers.delete(id); },
    async evaluate() { return {}; },
    async fetch(url, init) {
      assert.equal(url, `${api}/matches/${state.id}`);
      if (init?.method !== 'GET') {
        assert.equal(dropAcks, 1, 'No canonical success read before native drop ACK');
        reads++; events.push('canonical-success-read');
      }
      return {ok: true, json: async () => plain(state)};
    },
    async waitFor(expression, budget) {
      assert.equal(dropAcks, 1, 'No UI reconciliation before native drop ACK');
      assert.ok(budget > 0 && budget <= 15000);
      for (const literal of ['mtg.activeMatch', state.id, 'dataset.matchId',
        "matchRevision === '1'", '.operation-alert', 'Match operation pending',
        'Restoring saved session', 'Play Land Forest']) assert.ok(expression.includes(literal));
      uiWaits++; events.push('ui-reconciled');
    },
    async click(label) {
      assert.equal(label, 'Play Land Forest');
      assert.equal(++clicks, 1);
      const pattern = registration.patterns[0];
      assert.equal(registration.patterns.length, 1);
      assert.equal(pattern.urlPattern, actionUrl);
      assert.equal(Object.hasOwn(pattern, 'resourceType'), false);
      if (pattern.requestStage === 'Response') {
        // Only this obsolete registration produces the preflight response loop.
        await deliver(pause('OPTIONS', 'preflight', {resourceType: 'XHR', responseStatusCode: 200,
          responseHeaders: [{name: 'access-control-allow-origin', value: origin}]}));
        commit();
        await deliver(pause('OPTIONS', 'preflight', {resourceType: 'XHR', responseErrorReason: 'Failed'}));
        return;
      }
      assert.equal(pattern.requestStage, 'Request');
      await deliver(pause('OPTIONS', 'preflight', {resourceType: 'XHR'}));
      // Actual historical POST pause class is unknown; this unit does not assume it.
      await deliver(pause('POST', 'post'));
      commit();
      if (!optedPost) return;
      if (options.extraResponses) {
        await deliver(pause('POST', 'foreign-post', {responseStatusCode: 200,
          request: {method: 'POST', url: `${api}/matches/other-vm-match/action`}}));
        await deliver(pause('POST', 'non-200-post', {responseStatusCode: 204}));
      }
      // Input ACK and response-drop ACK are independent, as in the real caller.
      deliver(pause('POST', 'post', {responseStatusCode: 200}));
    },
  };
  const recover = vm.runInNewContext(actualRecovery, context, {timeout: 1000});
  const promise = recover(state).then(value => {
    settled = true; result = value; return value;
  }, error => { settled = true; failure = error; throw error; });
  promise.catch(() => {});
  async function complete() {
    await pump();
    if (!settled) {
      now = 15000;
      for (const timer of [...timers.values()]) if (timer.milliseconds === 15000) timer.callback();
      await pump();
    }
    assert.equal(settled, true, 'Real recovery must settle within its controlled original deadline');
    return promise;
  }
  async function close() {
    ack.resolve();
    try { await complete(); } catch { /* Cleanup only; tests assert the operation separately. */ }
    await Promise.allSettled(tasks);
    assert.equal(timers.size, 0, 'Actual recovery must clear its own timers');
  }
  return {calls, events, reports, legacy, budgets, state, actionUrl, complete, close,
    releaseAck: () => ack.resolve(),
    get registration() { return registration; }, get settled() { return settled; },
    get awaitingAck() { return awaitingAck; }, get enabled() { return enabled; },
    get result() { return result; }, get failure() { return failure; },
    get clicks() { return clicks; }, get commits() { return commits; },
    get dropAcks() { return dropAcks; }, get uiWaits() { return uiWaits; },
    get successReads() { return reads; }, get pendingCallbacks() { return pauses.size; }};
}

test('[protocol] actual recovery registers exact Request capture for both boolean capabilities without a resource filter', async () => {
  for (const capability of [true, false]) {
    const p = protocol({capability});
    try {
      const result = await p.complete();
      assert.deepEqual(p.registration, {patterns: [{urlPattern: p.actionUrl, requestStage: 'Request'}]});
      assert.equal(result.revision, 1);
      assert.equal(p.clicks, 1); assert.equal(p.commits, 1);
      assert.deepEqual(p.budgets, [15000]);
      assert.equal(p.enabled, false); assert.equal(p.pendingCallbacks, 0);
    } finally { await p.close(); }
  }
});

test('[protocol] actual shared helper continues OPTIONS without a response pause and opts only POST into its response', async () => {
  const p = protocol();
  try {
    await p.complete();
    assert.deepEqual(p.calls, [
      ['Network.enable', undefined], ['Fetch.enable', {patterns: [{urlPattern: p.actionUrl, requestStage: 'Request'}]}],
      ['Fetch.continueRequest', {requestId: 'preflight', interceptResponse: false}],
      ['Fetch.continueRequest', {requestId: 'post', interceptResponse: true}],
      ['Fetch.failRequest', {requestId: 'post', errorReason: 'Failed'}], ['Fetch.disable', undefined],
    ]);
    assert.equal(p.dropAcks, 1); assert.equal(p.commits, 1);
    assert.deepEqual(p.reports, []); assert.deepEqual(p.legacy, []);
  } finally { await p.close(); }
});

test('[protocol] input completion cannot replace native drop ACK before UI and canonical reconciliation', async () => {
  const p = protocol({holdAck: true});
  try {
    await pump();
    assert.equal(p.awaitingAck, true);
    assert.equal(p.settled, false); assert.equal(p.enabled, true);
    assert.equal(p.dropAcks, 0); assert.equal(p.uiWaits, 0); assert.equal(p.successReads, 0);
    assert.equal(p.calls.some(([method]) => method === 'Fetch.disable'), false);
    p.releaseAck();
    const result = await p.complete();
    assert.equal(result.revision, 1); assert.equal(p.commits, 1);
    assert.ok(p.events.indexOf('native-drop-ack') < p.events.indexOf('ui-reconciled'));
    assert.ok(p.events.indexOf('ui-reconciled') < p.events.indexOf('canonical-success-read'));
    assert.ok(p.events.indexOf('canonical-success-read') < p.events.indexOf('Fetch.disable'));
  } finally { await p.close(); }
});

test('[protocol] native drop failure remains fatal with no retry even when the synthetic canonical revision is one', async () => {
  const primary = new Error(JSON.stringify({code: -32602, message: 'synthetic rejected POST drop'}));
  const p = protocol({ackError: primary});
  try {
    await assert.rejects(p.complete(), error => error === primary);
    assert.equal(p.result, undefined); assert.equal(p.failure, primary);
    assert.equal(p.state.revision, 1); assert.equal(p.commits, 1);
    assert.equal(p.calls.filter(([method]) => method === 'Fetch.failRequest').length, 1);
    assert.equal(p.calls.filter(([method]) => method === 'Fetch.disable').length, 1);
    assert.equal(p.dropAcks, 0); assert.equal(p.uiWaits, 0); assert.equal(p.successReads, 0);
    assert.equal(p.reports.length, 1); assert.equal(p.reports[0].dropped, false);
    assert.equal(p.reports[0].canonical.revision, 1);
  } finally { await p.close(); }
});

test('[protocol] only the current POST200 is failed while foreign and non200 responses are continued', async () => {
  const p = protocol({extraResponses: true});
  try {
    await p.complete();
    assert.deepEqual(p.calls.filter(([method]) => method === 'Fetch.continueResponse'), [
      ['Fetch.continueResponse', {requestId: 'foreign-post'}],
      ['Fetch.continueResponse', {requestId: 'non-200-post'}],
    ]);
    assert.deepEqual(p.calls.filter(([method]) => method === 'Fetch.failRequest'), [
      ['Fetch.failRequest', {requestId: 'post', errorReason: 'Failed'}],
    ]);
    assert.equal(p.dropAcks, 1); assert.equal(p.commits, 1); assert.equal(p.result.revision, 1);
  } finally { await p.close(); }
});

test('[protocol] unknown capabilities reject before interception registration or any command or action', async () => {
  for (const capability of [undefined, null, 0, 1, 'true', 'false', {}]) {
    const p = protocol({capability});
    try {
      await assert.rejects(p.complete(), error => error.name === 'TypeError'
        && error.message === 'Explicit boolean Fetch resource-type capability required');
      assert.deepEqual(p.calls, []); assert.deepEqual(p.budgets, []);
      assert.equal(p.registration, undefined); assert.equal(p.clicks, 0); assert.equal(p.commits, 0);
    } finally { await p.close(); }
  }
});
