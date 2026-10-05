import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
const fixtureResponse = await fetch(`${backend}/fixture?face_kind=declaration_limits`, { method: 'POST' });
assert.equal(fixtureResponse.status, 200);
const state = await fixtureResponse.json();
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, command, waitFor, click, close } = browser;
try {
  await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(state.id)})`);
  await command('Page.reload');
  await waitFor("document.querySelectorAll('[aria-label=\"Attack with Llanowar Elves\"]').length === 2");
  await click('Attack all eligible');
  const before = await (await fetch(`${backend}/matches/${state.id}`)).json();
  await click('Submit Attackers');
  await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('static combat limit'))");
  const rejected = await (await fetch(`${backend}/matches/${state.id}`)).json();
  assert.equal(rejected.revision, before.revision);
  assert.deepEqual(rejected.attackers, []);
  await evaluate("document.querySelectorAll('[aria-label=\"Attack with Llanowar Elves\"]')[1].click()");
  await waitFor("[...document.querySelectorAll('[aria-label=\"Attack with Llanowar Elves\"]')].filter(box => box.checked).length === 1");
  await click('Submit Attackers');
  await waitFor("[...document.querySelectorAll('h3')].every(node => node.textContent !== 'Declare Attackers')");
  const accepted = await (await fetch(`${backend}/matches/${state.id}`)).json();
  assert.equal(accepted.attackers.length, 1);
  assert.equal(accepted.active_player, 2);
  assert.equal(accepted.revision, before.revision + 1);
  const report = await (await fetch(`${backend}/matches/${state.id}/rules-diagnostics`)).json();
  assert.equal(report.declaration_limits.attack.maximum, 1);
  console.log('PASS seat-2 human sees atomic limit rejection then submits one legal attacker through actual App/API');
} finally {
  await evaluate("localStorage.removeItem('mtg.activeMatch')");
  await close();
}
