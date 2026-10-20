import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

// Protocol only: evaluate actual source slices with inert filesystem/process edges.
// Never import the launcher or start an application, browser, listener or child.
const launcher = readFileSync(new URL('./run-current-built-acceptance.mjs', import.meta.url), 'utf8');
function actualFunction(name) {
  const found = launcher.match(new RegExp(`^(?:async )?function ${name}\\([^\\n]*\\) \\{\\n[\\s\\S]*?^\\}`, 'm'));
  assert.ok(found, `Actual ${name} body required`);
  return found[0];
}

async function resultReceipt(primary, cleanup) {
  const begin = launcher.lastIndexOf('\nfinally {\n  shuttingDown = true;');
  const end = launcher.lastIndexOf('\nif (failure)');
  assert.ok(begin >= 0 && end > begin, 'Actual RESULT teardown route required');
  const tail = launcher.slice(begin + '\nfinally {'.length, end);
  const body = tail.slice(0, tail.lastIndexOf('}'));
  const writes = [], context = vm.createContext({assert, path,
    failure: primary, shuttingDown: false, watchdog: null, budgetWatch: null, hardDeadline: null,
    hostileServer: null, allocations: new Set(), children: [], enrollment: undefined,
    firefoxTransport: {async close() { if (cleanup) throw cleanup; }},
    firefoxWire: undefined, closureProven: false, started: Date.now(),
    status: {episodes: [1, 2, 3], paid: Array(40), recovery: Array(3), origins: Array(4)},
    out: '/protocol/evidence/native-browser', clearTimeout() {}, clearInterval() {},
    async stop() { assert.fail('No child in RESULT-only protocol'); },
    async closedReceipt() {}, deadline: async promise => await promise,
    async writeFile(file, data) { writes.push({file, data}); },
    console: {log() {}, error() {}},
    process: {kill() { assert.fail('No real signal'); }, exit() { assert.fail('No early exit'); }},
  });
  await new vm.Script(`(async()=>{${body}})()`, {filename: 'actual-result-route.mjs'})
    .runInContext(context, {timeout: 1000});
  assert.equal(context.failure, primary ?? cleanup);
  assert.equal(writes.length, 1);
  assert.equal(writes[0].file, '/protocol/evidence/native-browser/RESULT.json');
  return JSON.parse(writes[0].data);
}

test('[protocol] RESULT preserves nested primary AggregateError cause and errors plus legacy stack', async () => {
  const cause = new Error('public synthetic primary cause');
  const leaf = new Error('public synthetic nested leaf');
  const inner = new AggregateError([leaf], 'public synthetic inner aggregate', {cause});
  const primary = new AggregateError([inner, new Error('public synthetic peer')],
    'public synthetic outer aggregate', {cause});
  const cleanup = new AggregateError([new Error('public synthetic cleanup leaf')], 'public synthetic cleanup');
  const result = await resultReceipt(primary, cleanup);
  assert.equal(result.failure, primary.stack);
  assert.equal(result.success, false);
  assert.equal(result.primaryFailure?.name, 'AggregateError');
  assert.equal(result.primaryFailure.message, primary.message);
  assert.equal(result.primaryFailure.stack, primary.stack);
  assert.equal(result.primaryFailure.cause.message, cause.message);
  assert.equal(result.primaryFailure.errors.length, 2);
  assert.equal(result.primaryFailure.errors[0].name, 'AggregateError');
  assert.equal(result.primaryFailure.errors[0].cause.stack, cause.stack);
  assert.equal(result.primaryFailure.errors[0].errors[0].stack, leaf.stack);
  assert.equal(result.primaryFailure.errors[1].message, 'public synthetic peer');
  assert.equal(result.cleanupFailures[0].errors[0].message, 'public synthetic cleanup leaf');
});

test('[protocol] RESULT retains an ordinary primary Error without replacing its legacy string', async () => {
  const primary = new Error('public synthetic ordinary', {cause: new Error('public synthetic cause')});
  const result = await resultReceipt(primary);
  assert.equal(result.failure, primary.stack);
  assert.equal(result.primaryFailure?.name, 'Error');
  assert.equal(result.primaryFailure.message, primary.message);
  assert.equal(result.primaryFailure.cause.message, 'public synthetic cause');
  assert.equal(Object.hasOwn(result.primaryFailure, 'errors'), false);
});

test('[protocol] successful RESULT has no invented primary failure or cleanup error', async () => {
  const result = await resultReceipt();
  assert.equal(result.success, true);
  for (const field of ['failure', 'primaryFailure', 'cleanupFailures'])
    assert.equal(Object.hasOwn(result, field), false, field);
});

function lifecycle(label = 'firefox') {
  const child = new EventEmitter();
  Object.assign(child, {pid: 701, exitCode: null, signalCode: null});
  let now = Date.parse('2026-10-20T12:00:00.000Z');
  class ClockDate extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now; }
  }
  const spawns = [], files = [], writes = [];
  const context = vm.createContext({assert, path, Date: ClockDate, children: [],
    root: '/protocol/source', out: '/protocol/evidence/native-browser', ports: {},
    db: '/protocol/runtime/sql/api.db', allocations: new Set(), shuttingDown: false, failure: null,
    authorizeChild(role) { assert.equal(role, label); },
    ownedEnvironment(_executable, env) { return env; },
    openSync(file, mode, permissions) { files.push(['open', file, mode, permissions]); return 42; },
    closeSync(fd) { files.push(['close', fd]); },
    spawn(...args) { spawns.push(args); return child; },
    console: {log() {}}, process: {pid: 100, kill() { assert.fail('No real signal'); }},
    ownedGroupAbsent(value) { assert.equal(value, child); return true; },
    async writeFile(file, data) { writes.push({file, data}); },
  });
  new vm.Script(`
    async function storageInventory() { return {receipts: [], allowed: [], actual: []}; }
    async function readdir() { return []; }
    async function checkFuser() { return {exit: 1, stdout: '', stderr: ''}; }
    async function checkPins() {}
    async function outputBudget() { return {}; }
    ${actualFunction('start')}
    ${actualFunction('closedReceipt')}
    globalThis.subject = {start, closedReceipt};
  `, {filename: 'actual-child-lifecycle.mjs'}).runInContext(context, {timeout: 1000});
  const actual = context.subject.start(label, '/protocol/firefox', ['--headless'], '/protocol/source');
  assert.equal(actual, child);
  assert.equal(spawns.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(spawns[0])), ['/protocol/firefox', ['--headless'], {
    cwd: '/protocol/source', detached: true, stdio: ['ignore', 42, 42], env: {},
  }]);
  assert.deepEqual(files, [['open', '/protocol/evidence/native-browser/' + label + '.log', 'a', 0o600], ['close', 42]]);
  assert.equal(context.children.length, 1);
  return {child, context, writes, advance(ms) { now += ms; },
    close(code = 0) { child.exitCode = code; child.emit('exit', code); child.emit('close', code); }};
}

test('[protocol] Firefox registration and actual close timestamps survive the CLOSURE route', async () => {
  const p = lifecycle();
  assert.equal(p.child.lifecycle?.registeredUTC, '2026-10-20T12:00:00.000Z');
  assert.equal(Object.hasOwn(p.child.lifecycle, 'closeUTC'), false);
  p.advance(1000);
  p.child.exitCode = 0; p.child.emit('exit', 0);
  assert.equal(await p.child.done, 0);
  assert.equal(Object.hasOwn(p.child.lifecycle, 'closeUTC'), false, 'exit is not close');
  p.advance(1000); p.child.emit('close', 0);
  assert.equal(p.child.lifecycle.closeUTC, '2026-10-20T12:00:02.000Z');
  await p.context.subject.closedReceipt();
  const receipt = JSON.parse(p.writes.find(row => row.file.endsWith('/CLOSURE.json')).data);
  assert.deepEqual(receipt.processes[0], {label: 'firefox', pid: 701, exit: 0, signal: null,
    lifecycle: {registeredUTC: '2026-10-20T12:00:00.000Z', closeUTC: '2026-10-20T12:00:02.000Z'}});
});

test('[protocol] Firefox error and close observations retain original done error identity', async () => {
  const p = lifecycle(), error = new Error('public synthetic spawn failure');
  p.advance(20); p.child.emit('error', error);
  assert.equal(await p.child.done, error);
  assert.equal(p.child.lifecycle?.errorUTC, '2026-10-20T12:00:00.020Z');
  assert.equal(Object.hasOwn(p.child.lifecycle, 'closeUTC'), false);
  p.advance(10); p.child.emit('close', -1);
  assert.equal(p.child.lifecycle.closeUTC, '2026-10-20T12:00:00.030Z');
});

test('[protocol] non-Firefox child spawn and done path gains no lifecycle listeners', async () => {
  const p = lifecycle('preview');
  assert.equal(Object.hasOwn(p.child, 'lifecycle'), false);
  assert.equal(p.child.listenerCount('error'), 1);
  assert.equal(p.child.listenerCount('close'), 0);
  p.close();
  assert.equal(await p.child.done, 0);
});
