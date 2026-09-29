import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
const decks = await (await fetch(`${backend}/fixture/start-decks`, { method: 'POST' })).json();
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, waitFor, click, command, close, onIntercept } = browser;

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
}

async function matchIds() {
  return new Set((await (await fetch(`${backend}/matches`)).json()).map((match) => match.id));
}

async function startWithDroppedResponses(dropCount) {
  let dropped = 0;
  onIntercept(async (event) => {
    if (event.request.method === 'POST' && event.responseStatusCode === 200 && dropped < dropCount) {
      dropped += 1;
      await command('Fetch.failRequest', { requestId: event.requestId, errorReason: 'Failed' });
    } else await command('Fetch.continueRequest', { requestId: event.requestId });
  });
  await command('Fetch.enable', { patterns: [{ urlPattern: '*/matches/start', requestStage: 'Response' }] });
  await click('Start Best-of-3 Match');
  return () => dropped;
}

try {
  await selectDecks();
  const before = await matchIds();
  const dropped = await startWithDroppedResponses(1);
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Match operation pending') && !localStorage.getItem('mtg.pendingStart')", 75000);
  await command('Fetch.disable');
  const after = await matchIds();
  assert.equal(dropped(), 1);
  assert.equal(after.size, before.size + 1);
  assert.equal(after.has(await evaluate("localStorage.getItem('mtg.activeMatch')")), true);
  console.log('PASS lost successful start response retries one durable match');

  await selectDecks();
  const beforeReload = await matchIds();
  const droppedTwice = await startWithDroppedResponses(2);
  await waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && !!localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  assert.equal(droppedTwice(), 2);
  await command('Page.reload');
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session') && !localStorage.getItem('mtg.pendingStart')");
  const afterReload = await matchIds();
  assert.equal(afterReload.size, beforeReload.size + 1);
  assert.equal(afterReload.has(await evaluate("localStorage.getItem('mtg.activeMatch')")), true);
  console.log('PASS reload recovers ambiguous start without creating another match');

  await selectDecks();
  const beforeClickRetry = await matchIds();
  const droppedForClick = await startWithDroppedResponses(2);
  await waitFor("document.querySelector('[role=alert]') && !document.body.innerText.includes('Match operation pending') && !!localStorage.getItem('mtg.pendingStart')");
  await command('Fetch.disable');
  assert.equal(droppedForClick(), 2);
  await click('Start Best-of-3 Match');
  await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Match operation pending') && !localStorage.getItem('mtg.pendingStart')");
  const afterClickRetry = await matchIds();
  assert.equal(afterClickRetry.size, beforeClickRetry.size + 1);
  assert.equal(afterClickRetry.has(await evaluate("localStorage.getItem('mtg.activeMatch')")), true);
  console.log('PASS repeated Start click recovers pending match without creating another');
} finally { await close(); }
