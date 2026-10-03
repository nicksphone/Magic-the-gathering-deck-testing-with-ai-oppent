import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
for (const kind of ['domain', 'temporary']) for (const seat of [1, 2]) {
  const response = await fetch(`${backend}/fixture?face_kind=combat_${kind}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, command, waitFor, click, close } = browser;
  const getState = async () => (await fetch(`${backend}/matches/${fixture.id}`)).json();
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    if (kind === 'domain') {
      await waitFor("Boolean(document.querySelector('[aria-label=\"Attack with Grizzly Bears\"]'))");
      assert.ok(await evaluate("document.body.textContent.includes('Attack cost: {3}')"));
      const before = await getState();
      await click('Submit Attackers');
      await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('attack costs'))");
      assert.equal((await getState()).revision, before.revision);
      await evaluate("document.querySelector('[aria-label=\"Attack with Llanowar Elves\"]').click()");
      await click('Submit Attackers');
      await waitFor(`(async () => {
        const state = await (await fetch('${backend}/matches/${fixture.id}')).json();
        return state.revision > ${before.revision} && state.attackers.length === 1;
      })()`);
      await waitFor("!document.querySelector('[aria-label=\"Attack with Grizzly Bears\"]')");
      const paid = await getState();
      assert.equal(paid.players[String(seat)].mana_pool.U, 0);
      assert.equal(paid.attackers.length, 1);
      console.log(`PASS seat ${seat}: domain counts nonbasic dual land types; unpaid declaration rejects; paid attack commits once through App/API`);
    } else {
      await waitFor("Boolean(document.querySelector('[aria-label=\"X value for War Cadence ability\"]'))");
      await evaluate(`(() => {
        const input = document.querySelector('[aria-label="X value for War Cadence ability"]');
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '1');
        input.dispatchEvent(new Event('input', { bubbles: true }));
      })()`);
      await click('Activate War Cadence');
      for (let i = 0; i < 10 && (await getState()).step !== 'declare_blockers'; i++) {
        await waitFor("[...document.querySelectorAll('button')].some(node => node.textContent.trim() === 'Pass Priority' && !node.disabled)");
        const previous = (await getState()).revision;
        await click('Pass Priority');
        for (let attempt = 0; attempt < 100 && (await getState()).revision === previous; attempt++) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }
      await waitFor("[...document.querySelectorAll('h3')].some(node => node.textContent === 'Declare Blockers')");
      async function select(names) {
        await evaluate(`(() => {
          const panel = [...document.querySelectorAll('.block-panel')].find(node => node.querySelector('h3')?.textContent === 'Declare Blockers');
          const select = panel.querySelector('select');
          [...select.options].forEach(option => option.selected = ${JSON.stringify(names)}.includes(option.text.trim()));
          select.dispatchEvent(new Event('change', { bubbles: true }));
        })()`);
      }
      await select(['Llanowar Elves', 'Grizzly Bears']);
      await waitFor("document.body.textContent.includes('Block cost for Llanowar Elves: {1}')");
      const before = await getState();
      await click('Submit Blocks');
      await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('block costs'))");
      assert.equal((await getState()).revision, before.revision);
      await select(['Llanowar Elves']);
      await click('Submit Blocks');
      await waitFor("[...document.querySelectorAll('h3')].every(node => node.textContent !== 'Declare Blockers')");
      const paid = await getState();
      const elf = paid.players[String(3-seat)].battlefield.find(card => card.name === 'Llanowar Elves');
      assert.ok(elf.tapped);
      assert.deepEqual(Object.values(paid.blocks), [[elf.id]]);
      assert.equal(paid.players[String(3-seat)].mana_pool.G, 0);
      console.log(`PASS seat ${seat}: actual X activation resolves; block tax rejects atomically; chosen mana blocker pays and still blocks through App/API`);
    }
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
