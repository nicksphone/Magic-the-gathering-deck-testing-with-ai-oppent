import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
for (const kind of ['attack', 'block']) for (const seat of [1, 2]) {
  const response = await fetch(`${backend}/fixture?face_kind=recipient_${kind}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, command, waitFor, click, close } = browser;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    if (kind === 'attack') {
      await waitFor("Boolean(document.querySelector('[aria-label=\"Attack with Grizzly Bears\"]'))");
      assert.ok(await evaluate("document.body.textContent.includes('Attack cost: {3}')"));
      await click('Submit Attackers');
      await waitFor("!document.querySelector('[aria-label=\"Attack with Grizzly Bears\"]')");
    } else {
      await waitFor("[...document.querySelectorAll('h3')].some(node => node.textContent === 'Declare Blockers')");
      await evaluate(`(() => {
        for (const select of document.querySelectorAll('.block-panel .row select')) {
          for (const option of select.options) option.selected = option.text.trim() === 'Wall of Glare';
          select.dispatchEvent(new Event('change', { bubbles: true }));
        }
      })()`);
      await waitFor("document.body.textContent.includes('Block cost for Wall of Glare: {3}')");
      await click('Submit Blocks');
      await waitFor("[...document.querySelectorAll('h3')].every(node => node.textContent !== 'Declare Blockers')");
    }
    // Submission can hide the controls before the HTTP mutation completes.
    await waitFor(`(async () => {
      const state = await (await fetch('${backend}/matches/${fixture.id}')).json();
      return ${kind === 'attack' ? 'state.attackers.length === 2' : 'Object.values(state.blocks).length === 2'};
    })()`);
    const paid = await (await fetch(`${backend}/matches/${fixture.id}`)).json();
    assert.equal(paid.players[String(kind === 'attack' ? seat : 3-seat)].mana_pool.G, 0);
    if (kind === 'attack') assert.equal(paid.attackers.length, 2);
    else {
      const wall = paid.players[String(3-seat)].battlefield.find(card => card.name === 'Wall of Glare');
      assert.deepEqual(Object.values(paid.blocks), [[wall.id], [wall.id]]);
    }
    console.log(`PASS seat ${seat}: specific enchanted-creature ${kind} cost through App/API; unrelated creature remains free`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
