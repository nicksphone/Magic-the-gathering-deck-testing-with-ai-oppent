import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  const response = await fetch(`${backend}/fixture?face_kind=combat_capacity_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, command, waitFor, click, close } = browser;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor("[...document.querySelectorAll('h3')].some(node => node.textContent === 'Declare Blockers')");
    await evaluate(`(() => {
      const panel = [...document.querySelectorAll('.block-panel')].find(node => node.querySelector('h3')?.textContent === 'Declare Blockers');
      for (const select of panel.querySelectorAll('.row select')) {
        for (const option of select.options) option.selected = option.text.trim() === 'Wall of Glare';
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
    })()`);
    await waitFor("document.body.textContent.includes('Block cost for Wall of Glare: {1}')");
    await click('Submit Blocks');
    await waitFor("[...document.querySelectorAll('h3')].every(node => node.textContent !== 'Declare Blockers')");
    const paid = await (await fetch(`${backend}/matches/${fixture.id}`)).json();
    const wall = paid.players[String(3-seat)].battlefield.find(card => card.name === 'Wall of Glare');
    const elf = paid.players[String(3-seat)].battlefield.find(card => card.name === 'Llanowar Elves');
    assert.equal(paid.attackers.length, 2);
    assert.deepEqual(Object.values(paid.blocks), [[wall.id], [wall.id]]);
    assert.ok(elf.tapped);
    assert.equal(paid.players[String(3-seat)].mana_pool.G, 0);
    assert.ok(paid.log.some(line => line.includes('pays {1} in block costs')));
    assert.ok(!paid.log.some(line => line.includes('pays {1}{1} in block costs')));
    console.log(`PASS seat ${seat}: same multi-block creature assigned to both attackers through App/API; cost paid once`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
