import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';
import { reviewStart } from './review-start.mjs';

const backend = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
const decks = await (await fetch(`${backend}/fixture/start-decks`, { method: 'POST' })).json();
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, waitFor, click, command, close, onIntercept } = browser;
await command('Network.enable');

async function selectDecks() {
  await evaluate("localStorage.removeItem('mtg.activeMatch')");
  await command('Page.reload');
  await waitFor(`Boolean(document.querySelector('.controls') && [...document.querySelectorAll('.controls select')][0]?.querySelector('option[value="${decks.a}"]') && [...document.querySelectorAll('.controls select')][1]?.querySelector('option[value="${decks.b}"]'))`);
  await evaluate(`(() => {
    const selects = [...document.querySelectorAll('.controls select')];
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
    for (const [index, value] of [[0, ${decks.a}], [1, ${decks.b}]]) {
      setter.call(selects[index], String(value));
      selects[index].dispatchEvent(new Event('change', { bubbles: true }));
    }
  })()`);
  await waitFor("[...document.querySelectorAll('button')].some(button => button.textContent.startsWith('Start Best-of-') && !button.disabled)");
}

async function matchIds() {
  return new Set((await (await fetch(`${backend}/matches`)).json()).map((match) => match.id));
}

async function startWithDroppedResponses(dropCount) {
  await reviewStart(browser);
  let dropped = 0;
  const attempts = [];
  onIntercept(async (event) => {
    console.log('Start recovery response', JSON.stringify({ method: event.request.method,
      status: event.responseStatusCode, error: event.responseErrorReason, hasPostData: typeof event.request.postData === 'string', dropped }));
    if (event.request.method !== 'POST') {
      assert.equal(event.request.method, 'OPTIONS', 'Only the actual CORS preflight may bypass POST-body capture');
      await command('Fetch.continueResponse', {requestId: event.requestId});
      return;
    }
    assert.equal(new URL(event.request.url).pathname, '/matches/start');
    assert.ok(event.networkId, 'Capture the actual POST body by its Network request ID');
    const captured = await command('Network.getRequestPostData', {requestId: event.networkId});
    const body = captured.base64Encoded ? Buffer.from(captured.postData, 'base64').toString('utf8') : captured.postData;
    assert.equal(typeof body, 'string');
    assert.ok(body.length);
    if (typeof event.request.postData === 'string') assert.equal(body, event.request.postData);
    console.log('Start recovery POST body retrieved from CDP Network', event.networkId);
    attempts.push({key: Object.entries(event.request.headers).find(([name]) => name.toLowerCase() === 'idempotency-key')?.[1],
      payload: JSON.parse(body)});
    if (event.responseStatusCode === 200 && dropped < dropCount) {
      dropped += 1;
      await command('Fetch.failRequest', { requestId: event.requestId, errorReason: 'Failed' });
    } else await command('Fetch.continueResponse', { requestId: event.requestId });
  });
  await command('Fetch.enable', { patterns: [{ urlPattern: '*/matches/start', requestStage: 'Response' }] });
  await click('Start Best-of-3 Match');
  return Object.assign(() => dropped, { attempts });
}

function sameIntent(attempts, pending) {
  assert.ok(attempts.length >= 2, 'Both initial and retry requests observed');
  for (const attempt of attempts) {
    assert.equal(attempt.key, pending?.key ?? attempts[0].key);
    assert.match(attempt.key, /^[0-9a-f]{32}$/);
    assert.deepEqual(attempt.payload, pending?.payload ?? attempts[0].payload);
  }
}

async function resumeRequestCapture() {
  await command('Fetch.enable', { patterns: [{ urlPattern: '*/matches/start', requestStage: 'Response' }] });
}

try {
  await selectDecks();
  const before = await matchIds();
  const dropped = await startWithDroppedResponses(1);
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Match operation pending') && !localStorage.getItem('mtg.pendingStart')", 75000);
  await command('Fetch.disable');
  const after = await matchIds();
  assert.equal(dropped(), 1);
  sameIntent(dropped.attempts);
  assert.equal(after.size, before.size + 1);
  assert.equal(after.has(await evaluate("localStorage.getItem('mtg.activeMatch')")), true);
  console.log('PASS lost successful start response retries one durable match');

  await selectDecks();
  const beforeReload = await matchIds();
  const droppedTwice = await startWithDroppedResponses(2);
  await waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && !!localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  assert.equal(droppedTwice(), 2);
  const reloadIntent = await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart'))");
  assert.equal(reloadIntent.review.exploratoryAcknowledged, true);
  await resumeRequestCapture();
  await command('Page.reload');
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session') && !localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  const afterReload = await matchIds();
  assert.equal(afterReload.size, beforeReload.size + 1);
  assert.equal(afterReload.has(await evaluate("localStorage.getItem('mtg.activeMatch')")), true);
  sameIntent(droppedTwice.attempts, reloadIntent);
  assert.equal(droppedTwice.attempts.length, 3, 'Reload replays the same intent once');
  console.log('PASS reload recovers ambiguous start without creating another match');

  await selectDecks();
  const beforeClickRetry = await matchIds();
  const droppedForClick = await startWithDroppedResponses(2);
  await waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && !!localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  assert.equal(droppedForClick(), 2);
  const clickIntent = await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart'))");
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Start Best-of-3 Match').disabled"), true);
  await resumeRequestCapture();
  await click('Recover pending match start');
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Match operation pending') && !localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  const afterClickRetry = await matchIds();
  assert.equal(afterClickRetry.size, beforeClickRetry.size + 1);
  assert.equal(afterClickRetry.has(await evaluate("localStorage.getItem('mtg.activeMatch')")), true);
  sameIntent(droppedForClick.attempts, clickIntent);
  assert.equal(droppedForClick.attempts.length, 3, 'Explicit recovery replays the same intent once');
  console.log('PASS explicit recovery click retains original reviewed key/payload without creating another');

  await selectDecks();
  const beforeLegacy = await matchIds();
  const droppedLegacy = await startWithDroppedResponses(2);
  await waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && !!localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  assert.equal(droppedLegacy(), 2);
  const legacy = await evaluate("(() => {const pending=JSON.parse(localStorage.getItem('mtg.pendingStart'));delete pending.review;localStorage.setItem('mtg.pendingStart',JSON.stringify(pending));return pending;})()");
  await resumeRequestCapture();
  await command('Page.reload');
  await waitFor("!document.body.innerText.includes('Restoring saved session') && [...document.querySelectorAll('button')].some(b=>b.textContent==='Recover pending match start'&&!b.disabled)");
  assert.deepEqual(await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart'))"), legacy);
  assert.equal((await matchIds()).size, beforeLegacy.size + 1);
  assert.equal(await evaluate("localStorage.getItem('mtg.activeMatch')"), null);
  assert.equal(await evaluate("Boolean(document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]'))"), false);
  assert.equal(droppedLegacy.attempts.length, 2, 'Legacy reload must not replay before review');
  const recoverLabel = await reviewStart(browser, { recover: true });
  assert.deepEqual(await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart'))"), legacy,
    'Manual review must not submit or replace the legacy pending intent');
  assert.equal(droppedLegacy.attempts.length, 2, 'Check and acknowledgement alone must not replay');
  await click(recoverLabel);
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Match operation pending') && !localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  const afterLegacy = await matchIds();
  assert.equal(afterLegacy.size, beforeLegacy.size + 1);
  assert.equal(afterLegacy.has(await evaluate("localStorage.getItem('mtg.activeMatch')")), true);
  sameIntent(droppedLegacy.attempts, legacy);
  assert.equal(droppedLegacy.attempts.length, 3, 'Reviewed legacy recovery replays the original intent once');
  console.log('PASS legacy unreviewed intent stays manual through reload/check/acknowledge, then recovers its same accepted match/key/payload');
} finally { await close(); }
