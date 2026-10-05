import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const originalFetch = globalThis.fetch;
const originalSocket = globalThis.WebSocket;
let navigationErrors = [];
let evaluations = 0;
globalThis.fetch = async () => ({ json: async () => ({ webSocketDebuggerUrl: 'ws://fixture' }) });
globalThis.WebSocket = class {
  constructor() { queueMicrotask(() => this.onopen()); }
  send(raw) {
    const { id, method, params } = JSON.parse(raw);
    let message = { id, result: {} };
    if (method === 'Runtime.evaluate') {
      if (params.expression.includes('performance.timeOrigin !==') || params.expression.includes('fixtureReady')) {
        evaluations++;
        const error = navigationErrors.shift();
        if (error) message = { id, error: { code: -32000, message: error } };
        else message.result = { result: { value: true } };
      } else message.result = { result: { value: params.expression === 'performance.timeOrigin' ? 1 : true } };
    }
    queueMicrotask(() => this.onmessage({ data: JSON.stringify(message) }));
  }
  close() {}
};

try {
  for (const detail of ['Inspected target navigated or closed', 'Execution context was destroyed', 'Cannot find context with specified id']) {
    navigationErrors = [detail];
    evaluations = 0;
    const browser = await openBrowser('http://fixture.test/');
    try { await browser.reload(); assert.equal(evaluations, 2); }
    finally { await browser.close(); }
    const navigatingBrowser = await openBrowser('http://fixture.test/');
    navigationErrors = [detail];
    evaluations = 0;
    try { await navigatingBrowser.waitFor('window.fixtureReady'); assert.equal(evaluations, 2); }
    finally { await navigatingBrowser.close(); }
    const legacyBrowser = await openBrowser('http://fixture.test/');
    navigationErrors = [detail];
    evaluations = 0;
    try { await legacyBrowser.command('Page.reload'); assert.equal(evaluations, 2); }
    finally { await legacyBrowser.close(); }
  }
  navigationErrors = ['Unrelated protocol failure'];
  evaluations = 0;
  const browser = await openBrowser('http://fixture.test/');
  try {
    await assert.rejects(browser.reload(), error => String(error.cause?.message).includes('Unrelated protocol failure'));
    assert.equal(evaluations, 1, 'Unrelated failures must not be retried');
  } finally { await browser.close(); }
  console.log('PASS readiness/reload retry transient execution-context changes, not unrelated protocol failures');
  let reads = 0;
  globalThis.fetch = async () => {
    reads++;
    if (reads === 1) throw new DOMException('Timed out', 'TimeoutError');
    return { ok: true, json: async () => ({ revision: 2 }) };
  };
  assert.deepEqual(await waitForApiState('http://fixture/state', state => state.revision === 2), { revision: 2 });
  assert.equal(reads, 2);
  reads = 0;
  globalThis.fetch = async () => { reads++; throw new Error('Connection refused'); };
  await assert.rejects(waitForApiState('http://fixture/state', () => true), error => error.cause?.message === 'Connection refused');
  assert.equal(reads, 1, 'Non-timeout read errors must not be retried');
  globalThis.fetch = async () => { await new Promise(resolve => setTimeout(resolve, 10)); throw new DOMException('Timed out', 'TimeoutError'); };
  await assert.rejects(waitForApiState('http://fixture/state', () => true, 5), /State read failed/);
  console.log('PASS read-timeout retry preserves deadline and does not retry mutations or unrelated errors');
} finally {
  globalThis.fetch = originalFetch;
  globalThis.WebSocket = originalSocket;
}
