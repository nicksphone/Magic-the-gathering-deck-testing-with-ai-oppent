import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import * as diagnostics from './browser-source-diagnostic.mjs';
import {continueRequestForPostResponse} from './browser-start-recovery-diagnostics.mjs';

// Synthetic protocol controls only, never actual browser or application evidence.
const source = readFileSync(new URL('./browser-ui-v2.mjs', import.meta.url), 'utf8');
const secret = 'PRIVATE_URL_ID_MESSAGE_STACK_BODY';
const title = '\n::error title=Browser response drop request state failure::';
const post = () => ({observed: 3, attempted: 2, ack: 1, error: 0, pending: 1});
const snapshot = changes => ({requests: {POST: post()}, uiStatus: 'available',
  actionUi: {enabledPrefixCount: 2, renderedRevision: 0},
  ui: {pending: true, restoring: false, alert: true}, ...changes});
const expected = changes => ({schema: 1, program: 'browser-ui-v2.mjs',
  stage: 'response-drop-request-state', post: post(),
  action: {enabled_prefix_count: 2, rendered_revision: 0},
  ui: {status: 'available', pending: true, restoring: false, alert: true}, ...changes});

function required(name) {
  assert.equal(typeof diagnostics[name], 'function', `Missing actual helper export ${name}`);
  return diagnostics[name];
}
function project(value) {
  return required('uiV2DropRequestStateMetadata')(value);
}
function reporting(writeSync) {
  const actual = required('reportUiV2DropRequestStateFailure');
  return vm.runInNewContext(`(${actual.toString()})`, {
    uiV2DropRequestStateMetadata: required('uiV2DropRequestStateMetadata'), writeSync,
  });
}
function framed(text) {
  assert.ok(text.startsWith(title) && text.endsWith('\n'));
  const body = text.slice(title.length, -1);
  assert.doesNotMatch(body, /[\r\n]/);
  assert.ok(Buffer.byteLength(body) <= 512);
  const record = JSON.parse(body);
  assert.equal(text, title + JSON.stringify(record) + '\n');
  return record;
}
function recoverySource() {
  const start = source.indexOf('async function recoverDroppedResponse(s) {');
  const end = source.indexOf('\ntry {\n  recoverDroppedResponse.requestSignals=', start);
  assert.ok(start >= 0 && end > start, 'Execute the complete actual recovery function');
  return source.slice(start, end);
}

test('actual projector exports only the five POST counters and existing typed action and UI observations', () => {
  assert.deepEqual(project(snapshot()), expected());
  const input = snapshot({requests: {POST: {observed: 0, attempted: 0, ack: 0, error: 0, pending: 0}}});
  assert.deepEqual(project(input), expected({post: {observed: 0, attempted: 0, ack: 0, error: 0, pending: 0}}));
});

test('unavailable and timed-out UI reads retain null unknowns instead of invented false or zero', () => {
  for (const status of ['unavailable', 'timed-out']) {
    assert.deepEqual(project(snapshot({uiStatus: status, actionUi: null, ui: null})), expected({
      action: {enabled_prefix_count: null, rendered_revision: null},
      ui: {status, pending: null, restoring: null, alert: null},
    }));
  }
  assert.deepEqual(project(snapshot({actionUi: {enabledPrefixCount: null, renderedRevision: null}})).action,
    {enabled_prefix_count: null, rendered_revision: null});
});

test('missing coerced negative fractional and unsafe POST counters reject without coercion', () => {
  for (const value of [null, undefined, [], secret, {}, {requests: {}}]) assert.equal(project(value), null);
  for (const key of ['observed', 'attempted', 'ack', 'error', 'pending']) {
    const input = snapshot(); delete input.requests.POST[key];
    assert.equal(project(input), null);
  }
  for (const value of ['1', true, null, -1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    const input = snapshot(); input.requests.POST.observed = value;
    assert.equal(project(input), null);
  }
});

test('unknown read states malformed UI booleans and malformed action scalars reject explicitly', () => {
  const changes = [
    d => { delete d.uiStatus; }, d => { d.uiStatus = secret; },
    d => { d.ui = null; }, d => { delete d.ui.pending; },
    d => { d.ui.restoring = 1; }, d => { d.ui.alert = 'false'; },
    d => { delete d.actionUi; }, d => { delete d.actionUi.renderedRevision; },
    d => { d.actionUi.enabledPrefixCount = -1; }, d => { d.actionUi.enabledPrefixCount = '2'; },
    d => { d.actionUi.renderedRevision = NaN; }, d => { d.actionUi.renderedRevision = Number.MAX_SAFE_INTEGER + 1; },
    d => { d.uiStatus = 'unavailable'; },
    d => { Object.defineProperty(d, 'actionUi', {get() { throw new Error(secret); }}); },
  ];
  for (const change of changes) {
    const input = snapshot(); change(input); assert.equal(project(input), null);
  }
});

test('unprojected request families URLs IDs messages stacks bodies and serialization hooks are not read', () => {
  const input = snapshot(); let reads = 0;
  const poisoned = () => { reads++; throw new Error(secret); };
  for (const record of [input, input.requests, input.requests.POST, input.actionUi, input.ui]) {
    for (const key of ['url', 'id', 'name', 'message', 'stack', 'body', 'payload', 'toJSON', 'toString']) {
      Object.defineProperty(record, key, {enumerable: true, get: poisoned});
    }
  }
  for (const key of ['OPTIONS', 'OTHER', 'errorCode']) Object.defineProperty(input.requests, key, {get: poisoned});
  for (const key of ['responses', 'requestLifecycle', 'requestLifecycleFinal', 'canonical', 'runtime']) {
    Object.defineProperty(input, key, {get: poisoned});
  }
  assert.deepEqual(project(input), expected());
  assert.equal(reads, 0);
  assert.doesNotMatch(JSON.stringify(project(input)), /PRIVATE_|https?:|payload|stack/);
});

test('projection preserves frozen collected input and returns independent nested output records', () => {
  const input = snapshot(); const before = JSON.stringify(input);
  for (const value of [input.requests.POST, input.requests, input.actionUi, input.ui, input]) Object.freeze(value);
  const output = project(input);
  assert.deepEqual(output, expected()); assert.equal(JSON.stringify(input), before);
  assert.notEqual(output.post, input.requests.POST);
  assert.notEqual(output.action, input.actionUi); assert.notEqual(output.ui, input.ui);
});

test('safe integer extrema remain typed and below the fixed 512 byte annotation body limit', () => {
  const n = Number.MAX_SAFE_INTEGER;
  const input = snapshot({requests: {POST: {observed: n, attempted: n, ack: n, error: n, pending: n}},
    actionUi: {enabledPrefixCount: n, renderedRevision: n}});
  const output = project(input);
  assert.deepEqual(output, expected({post: {observed: n, attempted: n, ack: n, error: n, pending: n},
    action: {enabled_prefix_count: n, rendered_revision: n}}));
  assert.ok(Buffer.byteLength(JSON.stringify(output)) <= 512);
});

test('actual reporter emits one framed record stays quiet on invalid data and tolerates sink failure', () => {
  const writes = [];
  const report = reporting((fd, text) => writes.push([fd, text]));
  report(snapshot()); assert.equal(writes.length, 1); assert.equal(writes[0][0], 2);
  assert.deepEqual(framed(writes[0][1]), expected());
  report(null); assert.equal(writes.length, 1);
  assert.doesNotThrow(() => reporting(() => { throw new Error(secret); })(snapshot()));
});

test('actual caller wires one separately guarded failure-only report after existing reads and legacy output', () => {
  assert.match(source, /import\s*\{[^}]*\breportUiV2DropRequestStateFailure\b[^}]*\}\s*from\s*['"]\.\/browser-source-diagnostic\.mjs['"]/);
  const body = recoverySource();
  const calls = [...body.matchAll(/reportUiV2DropRequestStateFailure\(diagnostic\)/g)];
  assert.equal(calls.length, 1);
  assert.match(body, /try\s*\{\s*reportUiV2DropRequestStateFailure\(diagnostic\);\s*\}\s*catch\s*\{/);
  assert.match(body, /    \}catch\{\}\n    try \{ reportUiV2DropRequestStateFailure\(diagnostic\); \} catch \{[^\n]*\}\n    throw error;/);
  assert.ok(calls[0].index > body.indexOf('}finally{collecting=false;'));
  assert.ok(calls[0].index > body.indexOf("console.error('DROP_RESPONSE_TRACE'"));
  assert.ok(body.indexOf('    throw error;', calls[0].index) > calls[0].index);
});

test('actual recovery reports its real POST counter updates and collected UI without added reads or changed failure', async () => {
  for (const sinkThrows of [false, true]) {
    const writes = [], reads = [], commands = [], budgets = [], legacy = [];
    const primary = new Error(secret); const fixture = {id: 'public-inert-match'};
    const api = 'http://api.invalid', origin = 'http://ui.invalid'; let intercept;
    const report = reporting((fd, text) => {
      assert.equal(fd, 2); writes.push(text); if (sinkThrows) throw new Error(secret);
    });
    const command = async (method, params) => { commands.push([method, params]); return {}; };
    const context = {api, origin, command, AbortController, continueRequestForPostResponse,
      reportUiV2DropRequestStateFailure: report,
      reportUiV2DropFailure() {},
      b: {supportsFetchResourceTypeFilter: true, onIntercept(fn) { intercept = fn; },
        async browserIdentity() { reads.push('runtime'); return {product: 'SyntheticBrowser/1', protocolVersion: '1'}; }},
      traceStartRecoveryResponses(_command, handler, _origin, collect) {
        const trace = event => handler(event, command);
        trace.observeControl = () => {};
        trace.reportFailure = () => { reads.push('observer'); collect({}); };
        trace.captureFinal = () => { reads.push('final'); return {}; };
        return trace;
      },
      async click(label) {
        assert.equal(label, 'Play Land Forest');
        await intercept({requestId: 'public-unit-pause', request: {method: 'POST',
          url: `${api}/matches/${fixture.id}/action`}});
        throw primary;
      },
      async evaluate() {
        reads.push('ui'); return {enabledPrefixCount: 2, renderedRevision: '0', pending: true, restoring: false, alert: true};
      },
      async fetch(url, options) {
        assert.equal(url, `${api}/matches/${fixture.id}`); assert.equal(options.method, 'GET');
        reads.push('canonical'); return {ok: true, json: async () => ({revision: 0})};
      },
      setTimeout(_callback, milliseconds) { budgets.push(milliseconds); return 1; }, clearTimeout() {},
      console: {error(label) { legacy.push(label); }},
    };
    const recover = vm.runInNewContext(`(${recoverySource()})`, context, {timeout: 1000});
    await assert.rejects(recover(fixture), error => error === primary);
    assert.equal(writes.length, 1);
    assert.deepEqual(framed(writes[0]), expected({post: {observed: 1, attempted: 1, ack: 1, error: 0, pending: 0}}));
    assert.deepEqual(reads, ['observer', 'ui', 'canonical', 'runtime', 'final']);
    assert.deepEqual(commands.map(([method]) => method), ['Network.enable', 'Fetch.enable', 'Fetch.continueRequest', 'Fetch.disable']);
    assert.deepEqual(budgets, [1000]); assert.deepEqual(legacy, ['DROP_RESPONSE_TRACE']);
  }
});
