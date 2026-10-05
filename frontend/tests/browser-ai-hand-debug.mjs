// Explicit ended-match inspection only: no mutations are permitted.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { openBrowser } from './browser-driver.mjs';

const origin = process.env.MTG_FRONTEND_ORIGIN;
const id = process.env.MTG_DEBUG_MATCH_ID;
if (!origin || !id) throw new Error('Set MTG_FRONTEND_ORIGIN and MTG_DEBUG_MATCH_ID to an ended test match');
const response = await fetch(`${origin}/api/matches/${encodeURIComponent(id)}`);
assert.equal(response.status, 200);
const before = await response.json();
assert.equal(before.match_complete, true, 'Never inspect an active live match with this browser probe');
const debugResponse = await fetch(`${origin}/api/matches/${encodeURIComponent(id)}/debug/ai-hands`);
assert.equal(debugResponse.status, 200);
const expected = await debugResponse.json();
const browser = await openBrowser(origin);
const writes = [];
try {
  browser.onIntercept(async request => {
    if (!['GET', 'OPTIONS'].includes(request.request.method)) {
      writes.push(request.request.url);
      await browser.command('Fetch.failRequest', {requestId: request.requestId, errorReason: 'BlockedByClient'});
    } else await browser.command('Fetch.continueRequest', {requestId: request.requestId});
  });
  await browser.command('Fetch.enable', {patterns: [{urlPattern: '*', requestStage: 'Request'}]});
  await browser.evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
  await browser.reload();
  await browser.waitFor("document.querySelector('.debug-ai-hands input') !== null");
  assert.equal(await browser.evaluate("document.querySelector('.debug-ai-hands input').checked"), false);
  assert.equal(await browser.evaluate("document.querySelector('.debug-ai-hand-cards') === null"), true);
  await browser.evaluate("document.querySelector('.debug-ai-hands input').click()");
  await browser.waitFor("document.querySelector('.debug-ai-hand-cards') !== null && !document.querySelector('.debug-ai-hands [role=alert]')");
  const text = await browser.evaluate("document.querySelector('.debug-ai-hands').textContent");
  for (const [seat, cards] of Object.entries(expected.hands)) {
    assert.ok(text.includes(`P${seat} AI hand`));
    for (const card of cards) assert.ok(text.includes(card.name) && text.includes(card.mana_cost || 'No mana cost'));
  }
  await browser.evaluate("document.querySelector('.debug-ai-hand-cards details summary')?.click()");
  if (process.env.MTG_DEBUG_SCREENSHOT) {
    const screenshot = await browser.command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true});
    fs.writeFileSync(process.env.MTG_DEBUG_SCREENSHOT, Buffer.from(screenshot.data, 'base64'));
  }
  await browser.evaluate("document.querySelector('.debug-ai-hands input').click()");
  assert.equal(await browser.evaluate("document.querySelector('.debug-ai-hand-cards') === null"), true);
  assert.deepEqual(writes, [], 'Debug viewing must not trigger game mutations');
  const after = await (await fetch(`${origin}/api/matches/${encodeURIComponent(id)}`)).json();
  assert.equal(after.revision, before.revision);
  console.log('PASS real ended-match browser: hands hidden by default, explicit reveal/read/hide, costs and unchanged revision');
} finally { await browser.close(); }
