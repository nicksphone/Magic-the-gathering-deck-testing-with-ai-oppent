import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  const response = await fetch(`${api}/fixture/casting-trigger?seat=${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const ids = fixture.players[String(seat)].battlefield.map(card => card.id);
  const { evaluate, waitFor, click, reload, close } = await openBrowser('http://127.0.0.1:15173/');
  try {
    await waitFor("document.body.innerText.includes('Saved matches')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor("document.querySelector('[aria-label=\"Target 1 for Incremental Growth\"]') !== null");
    assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith('Cast Incremental Growth')).disabled"), true);
    // Dispatch the whole choice in one task to test batched controlled updates.
    await evaluate(`(() => {
      const ids = ${JSON.stringify(ids)};
      ids.forEach((id, index) => {
        const select = document.querySelector('[aria-label="Target ' + (index + 1) + ' for Incremental Growth"]');
        select.value = id; select.dispatchEvent(new Event('change', { bubbles: true }));
      });
    })()`);
    await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Cast Incremental Growth') && !b.disabled)");
    assert.equal(await evaluate(`document.querySelector('[aria-label="Target 2 for Incremental Growth"] option[value="${ids[0]}"]').disabled`), true);
    await click('Cast Incremental Growth');
    for (let index = 0; index < 2; index++) {
      await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Pass Priority') && !b.disabled)");
      await click('Pass Priority');
      await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).${index === 0 ? `priority_player === ${3-seat}` : 'stack.length === 0'})()`);
    }
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.deepEqual(ids.map(id => final.players[String(seat)].battlefield.find(card => card.id === id).counters['+1/+1']), [1, 2, 3]);
    assert.equal(Object.values(final.players[String(seat)].mana_pool).reduce((sum, amount) => sum + amount, 0), 0);
    await reload();
    await waitFor("document.body.innerText.includes('Battlefield') && !document.body.innerText.includes('Restoring saved session')");
    console.log(`PASS seat ${seat}: deliberate distinct 1/2/3 target allocation, batched selection, paid cast, priority resolution and reload through App/API`);
  } finally {
    await close();
  }
}
