import assert from 'node:assert/strict';
import {mkdir, mkdtemp, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {test} from 'node:test';

let sequence = 0;
async function loadDriver(name) {
  return import(new URL(`${name}?firefox-contract=${++sequence}`, import.meta.url));
}

async function ownTrace(t) {
  const previous = process.env.MTG_CDP_DIAGNOSTIC_DIR;
  const directory = await mkdtemp(path.join(tmpdir(), 'mtg-firefox-driver-'));
  process.env.MTG_CDP_DIAGNOSTIC_DIR = directory;
  t.after(async () => {
    if (previous === undefined) delete process.env.MTG_CDP_DIAGNOSTIC_DIR;
    else process.env.MTG_CDP_DIAGNOSTIC_DIR = previous;
    await rm(directory, {recursive: true});
  });
  return directory;
}

function fixture() {
  const commands = [], opened = [], known = new WeakSet();
  let initialized, destroyed, closed = 0, failure, closureFailure, arming;
  const socket = {
    send(text) {
      const message = JSON.parse(text);
      commands.push(message);
      const result = message.method === 'Runtime.evaluate' ? {result: {value: true}} : {};
      queueMicrotask(() => socket.onmessage({data: JSON.stringify({id: message.id, result})}));
    },
    close() { throw new Error('Native page must use native closure'); },
    assertHealthy() { if (failure) throw failure; },
  };
  const page = {
    id: 'owned-firefox-top', socket,
    async close() { closed++; if (closureFailure) throw closureFailure; },
    onChildInitialized(callback, onDestroyed) { initialized = callback; destroyed = onDestroyed; },
    validateChildInitialized(receipt) {
      assert.ok(known.has(receipt), 'Unrecognized native child receipt');
      return receipt;
    },
    async armFutureChildren(patterns) { commands.push({method: 'native-arm', params: patterns}); await arming; },
  };
  return {
    commands, opened,
    transport: {async open(url) { opened.push(url); return page; }, async close() {}},
    child(receipt, authentic = true) { if (authentic) known.add(receipt); initialized(receipt); },
    destroy(context) { destroyed(context); },
    fail(error) { failure = error; },
    failClosure(error) { closureFailure = error; },
    armWith(promise) { arming = promise; },
    get closed() { return closed; },
  };
}

for (const name of ['./browser-driver.mjs', './release-owned/browser-driver.mjs']) {
  test(`${name}: native Firefox uses its transport and closes the actual page`, async t => {
    const driver = await loadDriver(name);
    assert.equal(typeof driver.configureFirefoxTransport, 'function');
    const f = fixture();
    await ownTrace(t);
    t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport(f.transport);
    const page = await driver.openBrowser('http://127.0.0.1:15173/');
    assert.deepEqual(f.opened, ['http://127.0.0.1:15173/']);
    assert.equal(await page.evaluate('true'), true);
    await page.close();
    assert.equal(f.closed, 1);
  });

  test(`${name}: binding rejects invalid or repeated transports`, async () => {
    const driver = await loadDriver(name);
    assert.equal(typeof driver.configureFirefoxTransport, 'function');
    for (const value of [null, {}, {open() {}}, {close() {}}, {open: true, close() {}}]) {
      assert.throws(() => driver.configureFirefoxTransport(value), /once-bound Firefox transport/);
    }
    driver.configureFirefoxTransport(fixture().transport);
    assert.throws(() => driver.configureFirefoxTransport(fixture().transport), /once-bound Firefox transport/);
  });

  test(`${name}: native transport failure remains visible`, async t => {
    const driver = await loadDriver(name);
    assert.equal(typeof driver.configureFirefoxTransport, 'function');
    const f = fixture();
    await ownTrace(t);
    t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport(f.transport);
    const page = await driver.openBrowser('http://127.0.0.1:15173/');
    const error = new Error('Native transport failed');
    f.fail(error);
    assert.throws(() => page.command('Network.enable'), value => value === error);
    await page.close();
  });

  test(`${name}: failed initialization closes only its native page`, async t => {
    const driver = await loadDriver(name);
    const f = fixture();
    await ownTrace(t);
    t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport(f.transport);
    f.fail(new Error('Native transport failed'));
    await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), /Native transport failed|Browser evaluation failed/);
    assert.equal(f.closed, 1);
  });

  test(`${name}: malformed native results never fall back to Chromium`, async t => {
    const driver = await loadDriver(name);
    const fetcher = t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
    driver.configureFirefoxTransport({async open() { return null; }, async close() {}});
    await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'));
    assert.equal(fetcher.mock.callCount(), 0);
  });

  test(`${name}: initialization and cleanup failures are both retained`, async t => {
    const driver = await loadDriver(name);
    const f = fixture();
    await ownTrace(t);
    driver.configureFirefoxTransport(f.transport);
    const opening = new Error('Native initialization failed');
    const closing = new Error('Native closure failed');
    f.fail(opening);
    f.failClosure(closing);
    await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), error => {
      assert.ok(error instanceof AggregateError);
      assert.equal(error.errors[0].cause ?? error.errors[0], opening);
      assert.equal(error.errors[1], closing);
      return true;
    });
    assert.equal(f.closed, 1);
  });
}

test('release driver arms native descendants before accepting genuine child receipts', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  assert.equal(typeof driver.configureFirefoxTransport, 'function');
  const f = fixture();
  await ownTrace(t);
  t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  const patterns = [{urlPattern: '*', requestStage: 'Request'}];
  await page.enableOwnedIframeInterception(patterns);
  assert.deepEqual(f.commands.find(command => command.method === 'native-arm').params, patterns);
  assert.equal(f.commands.some(command => command.method === 'Target.setAutoAttach'), false);
  f.child({context: 'owned-child', parent: 'owned-firefox-top', generation: 1});
  await page.waitForInterceptions(1);
  f.destroy('owned-child');
  await page.waitForInterceptions();
  await page.close();
});

test('release driver rejects an unrecognized native child without fabricating initialization', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  assert.equal(typeof driver.configureFirefoxTransport, 'function');
  const f = fixture();
  await ownTrace(t);
  t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected Chromium discovery'); });
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  await page.enableOwnedIframeInterception([{urlPattern: '*', requestStage: 'Request'}]);
  f.child({context: 'forged-child'}, false);
  assert.throws(() => page.assertInterceptionHealthy(), /Unrecognized native child receipt/);
  await page.close();
});

test('shared driver rejects unsupported passive CDP evidence instead of silently dropping it', async t => {
  const driver = await loadDriver('./browser-driver.mjs');
  assert.equal(typeof driver.configureFirefoxTransport, 'function');
  const previous = process.env.MTG_PASSIVE_CDP_EVIDENCE;
  process.env.MTG_PASSIVE_CDP_EVIDENCE = '/not-a-native-firefox-evidence-directory';
  t.after(() => {
    if (previous === undefined) delete process.env.MTG_PASSIVE_CDP_EVIDENCE;
    else process.env.MTG_PASSIVE_CDP_EVIDENCE = previous;
  });
  const f = fixture();
  driver.configureFirefoxTransport(f.transport);
  await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), /Firefox.*passive CDP/);
  assert.deepEqual(f.opened, []);
});

for (const failClosure of [false, true]) {
  test(`release driver closes its native page when trace finalization fails (closure failure: ${failClosure})`, async t => {
    const driver = await loadDriver('./release-owned/browser-driver.mjs');
    const f = fixture();
    const directory = await ownTrace(t);
    driver.configureFirefoxTransport(f.transport);
    const page = await driver.openBrowser('http://127.0.0.1:15173/');
    await rm(path.join(directory, 'cdp.jsonl'));
    await mkdir(path.join(directory, 'cdp.jsonl'));
    const closing = new Error('Native closure failed');
    if (failClosure) f.failClosure(closing);
    await assert.rejects(page.close(), error => {
      if (failClosure) {
        assert.ok(error instanceof AggregateError);
        assert.equal(error.errors[0].code, 'EISDIR');
        assert.equal(error.errors[1], closing);
      } else assert.equal(error.code, 'EISDIR');
      return true;
    });
    assert.equal(f.closed, 1);
  });
}

test('release driver closes a native page if diagnostic creation fails', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  const f = fixture();
  const directory = await ownTrace(t);
  const occupied = path.join(directory, 'occupied');
  await writeFile(occupied, 'owned fixture');
  process.env.MTG_CDP_DIAGNOSTIC_DIR = occupied;
  driver.configureFirefoxTransport(f.transport);
  await assert.rejects(driver.openBrowser('http://127.0.0.1:15173/'), {code: 'EEXIST'});
  assert.equal(f.closed, 1);
});

test('release driver awaits native arming acknowledgment', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  const f = fixture();
  await ownTrace(t);
  let acknowledge, armed = false;
  f.armWith(new Promise(resolve => { acknowledge = resolve; }));
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  const pending = page.enableOwnedIframeInterception([{urlPattern: '*', requestStage: 'Request'}]).then(() => { armed = true; });
  await Promise.resolve();
  assert.equal(armed, false);
  acknowledge();
  await pending;
  assert.equal(armed, true);
  await page.close();
});

test('release driver remains fail-closed after native arming rejects', async t => {
  const driver = await loadDriver('./release-owned/browser-driver.mjs');
  const f = fixture();
  await ownTrace(t);
  let reject;
  f.armWith(new Promise((resolve, fail) => { reject = fail; }));
  driver.configureFirefoxTransport(f.transport);
  const page = await driver.openBrowser('http://127.0.0.1:15173/');
  const pending = page.enableOwnedIframeInterception([{urlPattern: '*', requestStage: 'Request'}]);
  const error = new Error('Native registration failed');
  reject(error);
  await assert.rejects(pending, value => value === error);
  assert.throws(() => page.command('Runtime.evaluate'), value => value === error);
  await page.close();
});
