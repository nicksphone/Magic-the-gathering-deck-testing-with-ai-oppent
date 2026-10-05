import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, waitFor, click, command, close } = browser;
async function load(window) {
  const response = await fetch(`${backend}/fixture/auto-progress?window=${window}`, {method: 'POST'});
  assert.ok(response.ok, `fixture failed: ${response.status}`);
  const state = await response.json();
  const id = state.id;
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
  await command('Page.reload');
  await waitFor("document.querySelector('.battlefield') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Resume automatic play')");
  await click('Resume automatic play');
  return id;
}
try {
  await waitFor("!document.body.innerText.includes('Restoring saved session')");
  const id = await load('empty');
  await waitFor("document.body.innerText.includes('Play Land Island')");
  let state = await (await fetch(`${backend}/matches/${id}`)).json();
  assert.equal(state.step, 'precombat_main');
  assert.equal(state.players['1'].hand.length, 1, 'draw occurs once automatically');
  const revision = state.revision;
  await new Promise(resolve => setTimeout(resolve, 2300));
  state = await (await fetch(`${backend}/matches/${id}`)).json();
  assert.equal(state.revision, revision, 'playable land stops automatic progression');
  console.log('PASS browser automatically crosses untap/upkeep/draw, ignores bare mana, stops for land');
  for (const window of ['end_step', 'draw']) {
    const id = await load(window);
    const before = await (await fetch(`${backend}/matches/${id}`)).json();
    await new Promise(resolve => setTimeout(resolve, 2500));
    const after = await (await fetch(`${backend}/matches/${id}`)).json();
    assert.equal(after.revision, before.revision, `${window} instant opportunity must not be skipped`);
    assert.equal(after.priority_player, 1);
    assert.equal(after.players['1'].mana_pool.U, 2);
    console.log(`PASS browser preserves payable control instant in opponent ${window}`);
  }
} finally { await close(); }
