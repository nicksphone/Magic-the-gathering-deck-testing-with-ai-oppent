import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {test} from 'node:test';
import vm from 'node:vm';

// Mock protocol only: extract real launcher code, never import/start the launcher.
// All TCP, processes, clocks, filesystem edges and BiDi replies below are inert.
const source = new URL('./release-owned/run-current-built-acceptance.mjs', import.meta.url);
const launcher = readFileSync(source, 'utf8');
const match = launcher.match(/^async function readyFirefoxListener\([^\n]*\) \{\n[\s\S]*?^\}/m);
const barrier = match?.[0] ?? '';
const begin = launcher.indexOf('  const chromium = browserVendor');
const end = launcher.indexOf('  const served = {};', begin);
assert.ok(begin >= 0 && end > begin, 'Use the real owned-native startup block');
const startup = launcher.slice(begin, end);

function protocol({vendor = 'firefox', outcomes = ['connect'], duringProbe,
  lateConnect = false, ackError, asyncError, createConnectionError, setTimeoutError} = {}) {
  let now = 0, listenerReady = false, acknowledged = false, configured = false;
  const events = [], sockets = [], violations = [];
  const ports = {cdp: 18003, hostile: 18004};
  const child = {pid: 701, label: vendor === 'firefox' ? 'firefox' : 'chromium',
    exitCode: null, signalCode: null};
  const executable = vendor === 'firefox' ? '/pinned/firefox' : '/pinned/chrome';
  const frontend = 'http://127.0.0.1:18002', vite = {};
  let context, argv;
  function createConnection(options) {
    assert.deepEqual(JSON.parse(JSON.stringify(options)), {host: '127.0.0.1', port: ports.cdp});
    if (createConnectionError) throw createConnectionError;
    const number = sockets.length;
    const handlers = new Map();
    const socket = {
      destroyed: false, closed: false, timeoutMs: null,
      once(event, callback) { handlers.set(event, callback); return this; },
      on(event, callback) { return this.once(event, callback); },
      setTimeout(ms) {
        if (setTimeoutError) throw setTimeoutError;
        this.timeoutMs = ms; return this;
      },
      destroy() {
        if (this.destroyed) return this;
        this.destroyed = true;
        // Closure is deliberately later than a connect callback/promise resolve.
        queueMicrotask(() => queueMicrotask(() => queueMicrotask(() => {
          this.closed = true; events.push('tcp:closed'); emit('close');
        })));
        return this;
      },
    };
    function emit(event, value) {
      const callback = handlers.get(event); handlers.delete(event); callback?.(value);
    }
    sockets.push(socket); events.push('tcp:attempt');
    queueMicrotask(() => {
      if (socket.destroyed) return;
      if (!(socket.timeoutMs > 0 && socket.timeoutMs <= Math.min(1000, 90000 - now)))
        violations.push('Probe must use a <=1s timeout capped by the original 90s deadline');
      duringProbe?.(context, child, number);
      const outcome = outcomes[Math.min(number, outcomes.length - 1)];
      now += outcome === 'hang' ? (socket.timeoutMs || 1000) : 1;
      if (asyncError) { emit('error', asyncError); return; }
      if (lateConnect && outcome === 'connect') now = 90001;
      if (outcome === 'connect') {
        listenerReady = true; events.push('tcp:connect'); emit('connect');
      } else if (outcome === 'hang') emit('timeout');
      else emit('error', Object.assign(new Error('inert refused listener'), {code: 'ECONNREFUSED'}));
    });
    return socket;
  }
  const transport = {async ready() {
    events.push('bidi:ready');
    assert.equal(listenerReady, true, 'BiDi attempted before the owned Firefox listener was ready');
    assert.ok(sockets.every(socket => socket.closed), 'Close TCP probes before any BiDi session');
    await Promise.resolve();
    if (ackError) throw ackError;
    acknowledged = true; events.push('bidi:ack');
  }};
  context = vm.createContext({assert, path, browserVendor: vendor, ports,
    root: '/owned/source', out: '/owned/evidence', frontend, vite,
    firefox: '/pinned/firefox', chrome: '/pinned/chrome', nativeExecutable: executable,
    children: [child], shuttingDown: false, failure: null,
    firefoxWire: undefined, firefoxTransport: undefined,
    Date: {now: () => now}, createConnection,
    setTimeout(callback, ms) {
      if (!(ms >= 0 && ms <= Math.min(100, 90000 - now)))
        violations.push('Readiness sleep must stay inside the original 90s/100ms bounds');
      now += ms; queueMicrotask(callback); return {};
    },
    clearTimeout() {},
    start(label, binary, args, cwd) {
      assert.equal(label, child.label); assert.equal(binary, executable);
      assert.equal(cwd, '/owned/source'); argv = JSON.parse(JSON.stringify(args));
      events.push('spawn:' + label); return child;
    },
    async readFile(file) {
      assert.equal(file, '/proc/701/stat');
      return '701 (owned-native) ' + [...Array(19).fill('0'), '42'].join(' ');
    },
    async realpath(file) { return file === '/proc/701/exe' ? executable : file; },
    async writeFile() {},
    async ready(url, handle) {
      if (url === frontend) { assert.equal(handle, vite); events.push('http:frontend'); }
      else {
        assert.equal(url, 'http://127.0.0.1:18003/json/version');
        assert.equal(handle, child); events.push('http:chrome');
      }
    },
    createWireTrace() { return {record() {}}; },
    createFirefoxTransport() { return transport; },
    enrollment: {}, bodyCacheDirectory: '/owned/evidence/firefox-body-cache',
    currentBackendIdentity() { return {pid: 702, start: '43'}; },
    process: {env: {}},
    configureFirefoxTransport(value) {
      assert.equal(value, transport);
      assert.equal(acknowledged, true, 'Listener readiness cannot replace actual BiDi readiness');
      configured = true; events.push('bidi:configured');
    },
  });
  async function runStartup() {
    return await new vm.Script(`'use strict';\n${barrier}\n(async()=>{${startup}})()`,
      {filename: 'actual-launcher-native-startup.mjs'}).runInContext(context);
  }
  async function runBarrier() {
    assert.ok(barrier, 'Missing launcher-local bounded readyFirefoxListener(child) barrier');
    context.actualChild = child;
    return await new vm.Script(`'use strict';\n${barrier}\nreadyFirefoxListener(actualChild)`,
      {filename: 'actual-launcher-listener-function.mjs'}).runInContext(context);
  }
  function closed() {
    assert.deepEqual(violations, []);
    assert.ok(sockets.every(socket => socket.destroyed && socket.closed), 'Every probe must close on every path');
  }
  return {child, context, events, sockets, runStartup, runBarrier, closed,
    get elapsed() { return now; }, get configured() { return configured; },
    get argv() { return argv; }};
}

test('[mock] delayed owned Firefox listener closes probes before real BiDi readiness and binding', async () => {
  const p = protocol({outcomes: ['refused', 'refused', 'connect']});
  await p.runStartup(); p.closed();
  assert.equal(p.sockets.length, 3); assert.equal(p.configured, true);
  assert.ok(p.events.lastIndexOf('tcp:closed') < p.events.indexOf('bidi:ready'));
  assert.ok(p.events.indexOf('bidi:ack') < p.events.indexOf('bidi:configured'));
  assert.deepEqual(p.argv, ['--headless', '--no-remote', '--profile', '/owned/evidence/profile',
    '--remote-debugging-port', '18003', 'about:blank']);
});

test('[mock] child exit during a connecting probe aborts rather than grants readiness', async () => {
  const p = protocol({duringProbe(_context, child) { child.exitCode = 23; }});
  await assert.rejects(p.runBarrier()); p.closed();
  assert.equal(p.child.exitCode, 23); assert.equal(p.sockets.length, 1);
  assert.equal(p.configured, false);
});

test('[mock] first failure or shutdown during a connecting probe prevents readiness', async () => {
  const primary = new Error('inert existing first failure');
  for (const key of ['failure', 'shuttingDown']) {
    const p = protocol({duringProbe(context) { context[key] = key === 'failure' ? primary : true; }});
    await assert.rejects(p.runBarrier()); p.closed();
    if (key === 'failure') assert.equal(p.context.failure, primary);
    assert.equal(p.sockets.length, 1); assert.equal(p.configured, false);
  }
});

test('[mock] already exited signaled failed or shutting-down children cannot start a probe', async () => {
  for (const mode of ['exit', 'signal', 'failure', 'shutdown']) {
    const p = protocol();
    if (mode === 'exit') p.child.exitCode = 0;
    if (mode === 'signal') p.child.signalCode = 'SIGTERM';
    if (mode === 'failure') p.context.failure = new Error('inert prior failure');
    if (mode === 'shutdown') p.context.shuttingDown = true;
    await assert.rejects(p.runBarrier()); p.closed();
    assert.equal(p.sockets.length, 0); assert.equal(p.configured, false);
  }
});

test('[mock] a never-listening endpoint exhausts one fixed 90s budget with all probes closed', async () => {
  const p = protocol({outcomes: ['hang']});
  await assert.rejects(p.runBarrier()); p.closed();
  assert.ok(p.sockets.length > 1); assert.equal(p.elapsed, 90000);
  assert.equal(p.configured, false);
});

test('[mock] a connect delivered after expiry cannot become a successful readiness result', async () => {
  const p = protocol({lateConnect: true});
  await assert.rejects(p.runBarrier()); p.closed();
  assert.equal(p.elapsed, 90001); assert.equal(p.sockets.length, 1);
  assert.equal(p.configured, false);
});

test('[mock] Chrome retains its original argv and HTTP readiness without a Firefox TCP probe', async () => {
  const p = protocol({vendor: 'chrome'});
  await p.runStartup(); p.closed();
  assert.deepEqual(p.events, ['spawn:chromium', 'http:frontend', 'http:chrome']);
  assert.equal(p.sockets.length, 0); assert.equal(p.configured, false);
  assert.deepEqual(p.argv, ['--headless', '--no-first-run', '--disable-dev-shm-usage',
    '--disable-background-networking', '--no-default-browser-check', '--password-store=basic',
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost', '--no-sandbox',
    '--user-data-dir=/owned/evidence/profile', '--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port=18003', 'about:blank']);
});

test('[mock] listener success cannot waive a failed real-BiDi readiness result or change transport', async () => {
  const transport = readFileSync(new URL('./firefox-transport.mjs', import.meta.url));
  assert.equal(createHash('sha256').update(transport).digest('hex'),
    '91642e527c8f694cf85036afcdc2a9bb438bacd782e2b1673180c96194b0e973');
  const primary = new Error('inert native session ACK refusal');
  const p = protocol({ackError: primary});
  await assert.rejects(p.runStartup(), error => error === primary); p.closed();
  assert.equal(p.sockets.length, 1); assert.equal(p.configured, false);
  assert.equal(p.events.includes('bidi:configured'), false);
});

test('[mock] unexpected async resource or permission errors reject unchanged after exactly one closed probe', async () => {
  for (const code of ['EMFILE', 'EACCES']) {
    const primary = Object.assign(new Error('inert unexpected listener error'), {code});
    const p = protocol({asyncError: primary});
    await assert.rejects(p.runStartup(), error => error === primary); p.closed();
    assert.equal(p.sockets.length, 1);
    assert.equal(p.events.filter(event => event === 'tcp:attempt').length, 1);
    assert.equal(p.events.filter(event => event === 'tcp:closed').length, 1);
    assert.equal(p.events.includes('bidi:ready'), false);
    assert.equal(p.configured, false);
  }
});

test('[mock] synchronous connection construction failure preserves its identity without a socket or BiDi', async () => {
  const primary = Object.assign(new Error('inert constructor failure'), {code: 'EMFILE'});
  const p = protocol({createConnectionError: primary});
  await assert.rejects(p.runStartup(), error => error === primary); p.closed();
  assert.equal(p.sockets.length, 0);
  assert.equal(p.events.includes('tcp:attempt'), false);
  assert.equal(p.events.includes('bidi:ready'), false);
  assert.equal(p.configured, false);
});

test('[mock] synchronous socket configuration failure closes the returned socket before preserving its error', async () => {
  const primary = new Error('inert socket timeout-configuration failure');
  const p = protocol({setTimeoutError: primary});
  await assert.rejects(p.runStartup(), error => error === primary); p.closed();
  assert.equal(p.sockets.length, 1);
  assert.equal(p.events.filter(event => event === 'tcp:closed').length, 1);
  assert.equal(p.events.includes('bidi:ready'), false);
  assert.equal(p.configured, false);
});
