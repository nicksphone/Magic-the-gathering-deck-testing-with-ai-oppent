import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const shared of [false, true]) {
    const response = await fetch(`${api}/fixture/ordered-modifiers?seat=${seat}`, {method: 'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const id = fixture.match.id;
    const ids = shared ? [fixture.creature_ids[0], fixture.creature_ids[0]] : fixture.creature_ids;
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const {evaluate, waitFor, click, reload, close} = browser;
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor(`document.querySelector('[aria-label="Target 1 for Agony Warp"]') !== null`);
      assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith('Cast Agony Warp')).disabled"), true);
      await evaluate(`(() => {
        const ids = ${JSON.stringify(ids)};
        ids.forEach((value, index) => {
          const select = document.querySelector('[aria-label="Target ' + (index + 1) + ' for Agony Warp"]');
          select.value = value; select.dispatchEvent(new Event('change', {bubbles:true}));
        });
      })()`);
      await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Cast Agony Warp') && !b.disabled)");
      assert.equal(await evaluate(`document.querySelector('[aria-label="Target 2 for Agony Warp"] option[value="${ids[0]}"]').disabled`), false);
      await click('Cast Agony Warp');
      await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).stack.length === 1)()`);
      let state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.deepEqual(state.stack[0].targets, ids);
      assert.equal(state.players[String(seat)].mana_pool.U, 0);
      assert.equal(state.players[String(seat)].mana_pool.B, 0);
      await reload();
      for (let index = 0; index < 2; index++) {
        await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Pass Priority') && !b.disabled)");
        await click('Pass Priority');
        await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).${index === 0 ? `priority_player === ${3-seat}` : 'stack.length === 0'})()`);
      }
      state = await (await fetch(`${api}/matches/${id}`)).json();
      const creatures = state.players[String(3-seat)].battlefield;
      const first = creatures.find(card => card.id === fixture.creature_ids[0]);
      const second = creatures.find(card => card.id === fixture.creature_ids[1]);
      assert.deepEqual([first.power, first.toughness], shared ? [1, 2] : [1, 5]);
      assert.deepEqual([second.power, second.toughness], shared ? [5, 6] : [5, 3]);
      await reload();
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
      console.log(`PASS seat ${seat}: ${shared ? 'shared' : 'different'} ordered modifier recipients, payment, pending reload, actual effective stats and final reload`);
    } finally { await close(); }
  }
}
