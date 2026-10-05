import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const browser = await openBrowser('data:text/html,<body>Async readiness regression</body>');
try {
  await browser.evaluate('window.asyncWaitCalls = 0');
  await browser.waitFor('(async () => ++window.asyncWaitCalls >= 3)()');
  assert.equal(await browser.evaluate('window.asyncWaitCalls'), 3);
  await browser.waitFor('window.asyncWaitCalls === 3');
  await assert.rejects(browser.waitFor('Promise.resolve(false)', 400), /condition timed out/);
  await assert.rejects(browser.waitFor('Promise.reject(new Error("async-ready-rejection"))'), /async-ready-rejection/);
  console.log('PASS synchronous/async readiness, false Promise polling and visible rejection');
} finally { await browser.close(); }
