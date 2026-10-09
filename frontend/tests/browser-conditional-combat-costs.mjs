import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
for (const kind of ['attack', 'block']) for (const seat of [1, 2]) {
  const response = await fetch(`${backend}/fixture?face_kind=conditional_cost_${kind}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, command, waitFor, click, close } = browser;
  const state = async () => (await fetch(`${backend}/matches/${fixture.id}`)).json();
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    if (kind === 'attack') {
      await waitFor("Boolean(document.querySelector('[aria-label=\"Attack with Grizzly Bears\"]'))");
      await click('Attack all eligible');
      assert.ok(await evaluate("document.body.textContent.includes('Attack cost: {1}')"));
      const before = await state();
      await click('Submit Attackers');
      await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('attack costs'))");
      assert.equal((await state()).revision, before.revision);
      await evaluate("document.querySelector('[aria-label=\"Attack with Llanowar Elves\"]').click()");
      await click('Submit Attackers');
      await waitFor("!document.querySelector('[aria-label=\"Attack with Grizzly Bears\"]')");
      await waitForApiState(`${backend}/matches/${fixture.id}`, state => state.revision > before.revision);
      await waitFor("!document.body.textContent.includes('Match operation pending')");
      assert.equal((await state()).attackers.length, 1);
      assert.equal((await state()).players[String(seat)].mana_pool.U, 0);
    } else {
      await waitFor("[...document.querySelectorAll('h3')].some(node => node.textContent === 'Declare Blockers')");
      async function select(names) {
        await evaluate(`(() => {
          const select = [...document.querySelectorAll('.block-panel .row')].find(node => node.querySelector('span')?.textContent === 'Grizzly Bears').querySelector('select');
          [...select.options].forEach(option => option.selected = ${JSON.stringify(names)}.includes(option.text.trim()));
          select.dispatchEvent(new Event('change', { bubbles: true }));
        })()`);
      }
      await select(['Llanowar Elves', 'Grizzly Bears']);
      await waitFor("document.body.textContent.includes('Block cost for Llanowar Elves: {1}')");
      const before = await state();
      await click('Submit Blocks');
      await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('block costs'))");
      assert.equal((await state()).revision, before.revision);
      await select(['Llanowar Elves']);
      await click('Submit Blocks');
      await waitFor("[...document.querySelectorAll('h3')].every(node => node.textContent !== 'Declare Blockers')");
      const paid = await waitForApiState(`${backend}/matches/${fixture.id}`, state => state.revision > before.revision);
      await waitFor("!document.body.textContent.includes('Match operation pending')");
      const elf = paid.players[String(3-seat)].battlefield.find(card => card.name === 'Llanowar Elves');
      assert.ok(elf.tapped);
      assert.deepEqual(Object.values(paid.blocks), [[elf.id]]);
    }
    console.log(`PASS seat ${seat}: canonical conditional ${kind} cost rejects atomically and commits once through App/API`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
