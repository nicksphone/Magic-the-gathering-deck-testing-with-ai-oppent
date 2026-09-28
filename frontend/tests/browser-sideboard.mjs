import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
const fixture = await (await fetch(`${backend}/fixture?face_kind=bo3_sideboard`, { method: 'POST' })).json();
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, waitFor, click, command, close } = browser;

try {
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
  await command('Page.reload');
  await waitFor("document.querySelector('.sideboard-panel') && !document.body.innerText.includes('Restoring saved session')");
  assert.equal(await evaluate("document.querySelector('.sideboard-inventory')?.innerText.includes('15 Forest')"), true);
  assert.equal(await evaluate("[...document.querySelector('select[aria-label=\"Sideboarding player\"]').options].map(o => o.value).join(',')"), '1,2');

  await evaluate(`(() => {
    const box = document.querySelector('textarea[aria-label="Cards out"]');
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(box, '1 Island');
    box.dispatchEvent(new Event('input', { bubbles: true }));
    const select = document.querySelector('select[aria-label="Sideboarding player"]');
    select.value = '2';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
  await waitFor("document.querySelector('select[aria-label=\"Sideboarding player\"]').value === '2' && document.querySelector('textarea[aria-label=\"Cards out\"]').value === ''");
  await evaluate(`(() => {
    const select = document.querySelector('select[aria-label="Sideboarding player"]');
    select.value = '1';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
  await waitFor("document.querySelector('select[aria-label=\"Sideboarding player\"]').value === '1'");

  await evaluate(`(() => {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    for (const [label, value] of [['Cards out', '15 Mountain'], ['Cards in', '15 Forest']]) {
      const box = document.querySelector('textarea[aria-label="' + label + '"]');
      setter.call(box, value);
      box.dispatchEvent(new Event('input', { bubbles: true }));
    }
  })()`);
  await waitFor("document.querySelector('textarea[aria-label=\"Cards out\"]').value === '15 Mountain'");
  await click('Apply Sideboard Swaps');
  await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent === 'Sideboard Applied' && b.disabled)");
  let state = await (await fetch(`${backend}/matches/${fixture.id}`)).json();
  assert.equal(state.sideboarding['1'].applied, true);
  assert.deepEqual(state.sideboarding['1'].sideboard, [{ card_name: 'Mountain', quantity: 15 }]);

  await command('Page.reload');
  await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent === 'Sideboard Applied' && b.disabled)");
  await click('P1 Play First');
  await waitFor("document.querySelector('.match-status-grid')?.innerText.includes('2 / 3') && !document.querySelector('.sideboard-panel')");
  state = await (await fetch(`${backend}/matches/${fixture.id}`)).json();
  assert.equal(state.active_player, 1);
  assert.equal(state.game_number, 2);
  const pool = await (await fetch(`${backend}/fixture/sideboard-pool/${fixture.id}`)).json();
  assert.deepEqual(pool, { Island: 45, Forest: 15 });
  console.log('PASS UI sideboard swap survives reload and seeds game two with the swapped deck');
} finally { await close(); }
