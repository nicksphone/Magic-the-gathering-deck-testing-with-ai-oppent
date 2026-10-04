import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
const response = await fetch(`${backend}/fixture?face_kind=combat_payments_requirements`, { method: 'POST' });
assert.equal(response.status, 200);
const fixture = await response.json();
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, command, waitFor, click, close } = browser;
const getState = async () => (await fetch(`${backend}/matches/${fixture.id}`)).json();
try {
  await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
  await command('Page.reload');
  await waitFor("Boolean(document.querySelector('[aria-label=\"Attack with Prized Unicorn\"]'))");
  const before = await getState();
  await click('Submit Attackers');
  await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('attack costs'))");
  assert.equal((await getState()).revision, before.revision);
  await evaluate("document.querySelector('[aria-label=\"Attack with Llanowar Elves\"]').click()");
  await click('Submit Attackers');
  await waitFor("!document.querySelector('[aria-label=\"Attack with Prized Unicorn\"]')");
  const paid = await getState();
  assert.equal(paid.players['1'].mana_pool.U, 0);
  assert.equal(paid.attackers.length, 1);
  for (let i = 0; i < 4 && (await getState()).step !== 'declare_blockers'; i++) {
    const previous = (await getState()).revision;
    await click('Pass Priority');
    for (let attempt = 0; attempt < 100 && (await getState()).revision === previous; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    await waitFor("[...document.querySelectorAll('button')].some(node => node.textContent.trim() === 'Pass Priority' && !node.disabled)");
  }
  await waitFor("[...document.querySelectorAll('h3')].some(node => node.textContent === 'Declare Blockers')");
  const blocking = await getState();
  await click('Submit Blocks');
  await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('requirements'))");
  assert.equal((await getState()).revision, blocking.revision);
  await evaluate(`(() => {
    const panel = [...document.querySelectorAll('.block-panel')].find(node => node.querySelector('h3')?.textContent === 'Declare Blockers');
    const select = panel.querySelector('select');
    select.options[0].selected = true;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
  await click('Submit Blocks');
  await waitFor("[...document.querySelectorAll('h3')].every(node => node.textContent !== 'Declare Blockers')");
  const blocked = await getState();
  assert.equal(blocked.blocks[paid.attackers[0]].length, 1);
  assert.equal(blocked.revision, blocking.revision + 1);
  console.log('PASS actual App/API exercises paid attack and target-specific blocking, rejecting both invalid declarations atomically');
} finally {
  await evaluate("localStorage.removeItem('mtg.activeMatch')");
  await close();
}
