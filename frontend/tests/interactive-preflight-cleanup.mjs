import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { readFile } from 'node:fs/promises';
import { PassThrough, Writable } from 'node:stream';
import { finished } from 'node:stream/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = (await readFile(new URL('./browser-interactive-preflight.mjs', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '')
  .replaceAll('import.meta.url', JSON.stringify(new URL('./browser-interactive-preflight.mjs', import.meta.url).href));
const profile = '/declared-owned-preflight-profile';
const nextTurn = () => new Promise(resolve => setImmediate(resolve));

// Only external process/CDP/Vite/filesystem boundaries are mocked. Execute the
// actual driver's setup/body/finally; stop the body at its first fixture wait.
function run({ alreadyExited = false, alreadyClosed = false, numericExit = false,
  logDelayed = false, removeError, browserError, serverError, cleanupOnly = false } = {}) {
  const primary = new Error('Declared first preflight wait failure');
  const events = [];
  const child = new EventEmitter();
  child.pid = 12345;
  child.exitCode = null;
  child.signalCode = null;
  child.stdout = new PassThrough();
  child.stderr = new PassThrough();
  let closed = false;
  function exit() {
    child.exitCode = numericExit ? 0 : null;
    child.signalCode = numericExit ? null : 'SIGTERM';
    events.push('exit');
    child.emit('exit', child.exitCode, child.signalCode);
  }
  function close() {
    closed = true;
    events.push('close');
    child.emit('close', child.exitCode, child.signalCode);
  }
  function finishStdio() {
    child.stdout.end('stdout');
    setImmediate(() => { child.stderr.end('stderr-tail'); setImmediate(close); });
  }
  child.kill = signal => {
    assert.equal(signal, 'SIGTERM');
    events.push('kill');
    if (!alreadyExited) setImmediate(() => { exit(); finishStdio(); });
    else if (!alreadyClosed) setImmediate(finishStdio);
    return !alreadyExited;
  };
  const chunks = [];
  const log = new Writable({
    write(chunk, _encoding, callback) { chunks.push(chunk.toString()); callback(); },
    final(callback) {
      const flush = () => { events.push('log-finished'); callback(); };
      if (logDelayed) setImmediate(flush); else flush();
    },
  });
  const server = {
    async listen() {},
    async close() { events.push('server-close'); if (serverError) throw serverError; },
  };
  const browser = {
    async command(method) {
      if (method === 'Browser.getBrowserCommandLine') return { arguments: [`--user-data-dir=${profile}`] };
      assert.equal(method, 'Page.navigate');
    },
    async waitFor() { throw primary; },
    async close() { events.push('browser-close'); if (browserError) throw browserError; },
  };
  const setupEnd = source.indexOf('\ntry {');
  const finallyStart = source.lastIndexOf('\n} finally {');
  assert.ok(setupEnd > 0 && finallyStart > setupEnd);
  const programSource = cleanupOnly
    ? source.slice(0, setupEnd) + '\n' + source.slice(finallyStart + '\n} finally '.length)
    : source;
  const program = vm.runInNewContext(`(async () => { ${programSource}\n})()`, {
    assert, finished, process: { pid: 1, env: { MTG_UI_EVIDENCE: '/declared-evidence' } },
    console: { log() {} }, URL, setTimeout, fileURLToPath: () => '/declared-frontend',
    tmpdir: () => '/declared-temp', mkdir: async () => {}, mkdtemp: async () => profile,
    createServer: async () => server, react: () => ({}), createWriteStream: () => log,
    spawn: (_executable, _args, options) => {
      assert.deepEqual(Array.from(options.stdio), ['ignore', 'pipe', 'pipe']);
      if (alreadyExited) setImmediate(() => { exit(); if (alreadyClosed) finishStdio(); });
      return child;
    },
    fetch: async () => {
      // Deliver earlier signal termination after spawn listeners can be latched,
      // but before finally begins. Startup succeeds only in this declared mock.
      if (alreadyExited) await nextTurn();
      if (alreadyClosed) { await nextTurn(); await nextTurn(); }
      return { ok: true };
    },
    openBrowser: async () => browser,
    writeFile: async () => assert.fail('No game completion receipt in this early-failure contract'),
    rm: async (path, options) => {
      events.push('remove-profile');
      assert.equal(path, profile);
      assert.deepEqual(Object.keys(options), ['recursive']);
      assert.equal(options.recursive, true);
      if (!closed) throw Object.assign(new Error('Declared active profile writer'), { code: 'ENOTEMPTY' });
      if (logDelayed && !log.writableFinished) throw new Error('Log not flushed before profile removal');
      if (removeError) throw removeError;
    },
  });
  return { primary, events, log, chunks, child, program };
}

async function outcome(sample) {
  let result;
  sample.program.then(() => { result = { ok: true }; }, error => { result = { error }; });
  for (let turn = 0; turn < 12 && !result; turn++) await nextTurn();
  try {
    assert.ok(result, 'Cleanup must not wait again for an already-delivered exit/close event');
    return result;
  } finally {
    // Release a broken old driver's synthetic listener, not a game retry.
    sample.child.emit('exit', null, 'SIGTERM');
    if (!sample.log.writableEnded) sample.log.end();
    await sample.program.catch(() => {});
  }
}

test('real driver waits for stdio close after exit before profile removal', async () => {
  const sample = run();
  const result = await outcome(sample);
  assert.equal(result.error, sample.primary);
  assert.ok(sample.events.indexOf('close') < sample.events.indexOf('remove-profile'));
  assert.equal(sample.events.filter(event => event === 'kill').length, 1);
});

for (const [name, options] of [
  ['already signal-terminated, stdio still open', { alreadyExited: true }],
  ['already signal-terminated and closed', { alreadyExited: true, alreadyClosed: true }],
  ['already exited numerically, stdio still open', { alreadyExited: true, numericExit: true }],
]) {
  test(`real driver drains ${name} without a second exit wait`, async () => {
    const sample = run(options);
    assert.equal((await outcome(sample)).error, sample.primary);
    assert.ok(sample.events.includes('remove-profile'));
  });
}

test('real driver awaits actual Writable completion before removing profile', async () => {
  const sample = run({ logDelayed: true });
  assert.equal((await outcome(sample)).error, sample.primary);
  assert.ok(sample.events.indexOf('log-finished') < sample.events.indexOf('remove-profile'));
});

test('real driver retains primary wait error and later profile-removal error', async () => {
  const cleanup = Object.assign(new Error('Declared closed-profile removal failure'), { code: 'ENOTEMPTY' });
  const sample = run({ removeError: cleanup });
  const error = (await outcome(sample)).error;
  assert.equal(error.name, 'AggregateError');
  assert.equal(error.cause, sample.primary);
  assert.deepEqual(Array.from(error.errors), [sample.primary, cleanup]);
});

for (const stage of ['browser', 'server']) {
  test(`real driver still shuts down owned Chromium after ${stage} cleanup fails`, async () => {
    const cleanup = new Error(`Declared ${stage} close failure`);
    const sample = run({ [`${stage}Error`]: cleanup });
    const error = (await outcome(sample)).error;
    assert.equal(error.name, 'AggregateError');
    assert.deepEqual(Array.from(error.errors), [sample.primary, cleanup]);
    assert.ok(sample.events.includes('server-close'));
    assert.ok(sample.events.includes('close'));
    assert.ok(sample.events.includes('remove-profile'));
  });
}

test('actual cleanup-only branch preserves a removal failure without a primary error', async () => {
  const cleanup = new Error('Declared profile-removal failure');
  const sample = run({ cleanupOnly: true, removeError: cleanup });
  assert.equal((await outcome(sample)).error, cleanup);
});

test('actual cleanup-only branch succeeds after close and log completion', async () => {
  const sample = run({ cleanupOnly: true, logDelayed: true });
  assert.deepEqual(await outcome(sample), { ok: true });
  assert.ok(sample.events.indexOf('close') < sample.events.indexOf('remove-profile'));
  assert.ok(sample.events.indexOf('log-finished') < sample.events.indexOf('remove-profile'));
});

test('real driver retains the stderr tail after stdout has ended', async () => {
  const sample = run();
  const result = await outcome(sample);
  assert.equal(result.error, sample.primary);
  assert.deepEqual(sample.chunks, ['stdout', 'stderr-tail']);
});
