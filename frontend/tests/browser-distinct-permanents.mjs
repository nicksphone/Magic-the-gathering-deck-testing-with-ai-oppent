import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const foreign of [false, true]) {
    const response = await fetch(`${api}/fixture/distinct-permanents?seat=${seat}&foreign=${foreign}`, {method: 'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const id = fixture.match.id;
    const ids = [...fixture.target_ids].reverse();
    const {evaluate, waitFor, click, reload, close} = await openBrowser('http://127.0.0.1:15173/');
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor('document.querySelector(\'[aria-label="Target 1 for Ghostly Flicker"]\') !== null');
      assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith('Cast Ghostly Flicker')).disabled"), true);
      assert.ok(await evaluate("document.body.innerText.includes('Choose 2 different permanents')"));
      assert.equal(await evaluate("document.body.innerText.includes('undefined')"), false);
      for (const index of [0, 1]) {
        assert.deepEqual(new Set(await evaluate(`Array.from(document.querySelector('[aria-label="Target ${index + 1} for Ghostly Flicker"]').options).map(option => option.value).filter(Boolean)`)), new Set(ids));
      }
      await evaluate(`(() => {
        const ids = ${JSON.stringify(ids)};
        ids.forEach((value, index) => {
          const select = document.querySelector('[aria-label="Target ' + (index + 1) + ' for Ghostly Flicker"]');
          select.value = value; select.dispatchEvent(new Event('change', {bubbles: true}));
        });
      })()`);
      await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Cast Ghostly Flicker') && !b.disabled)");
      assert.equal(await evaluate(`document.querySelector('[aria-label="Target 2 for Ghostly Flicker"] option[value="${ids[0]}"]').disabled`), true);
      await click('Cast Ghostly Flicker');
      await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).stack.length === 1)()`);
      let state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.deepEqual(state.stack[0].targets, ids);
      assert.equal(Object.values(state.players[String(seat)].mana_pool).reduce((sum, amount) => sum + amount, 0), 0);
      await reload();
      for (let pass = 0; pass < 2; pass++) {
        await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Pass Priority') && !b.disabled)");
        await click('Pass Priority');
        await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).${pass === 0 ? `priority_player === ${3-seat}` : 'stack.length === 0'})()`);
      }
      state = await (await fetch(`${api}/matches/${id}`)).json();
      const returned = fixture.target_ids.map(target => state.players[String(seat)].battlefield.find(card => card.id === target));
      assert.deepEqual(returned.map(card => card.name), ['Fertilid', 'Island']);
      assert.ok(returned.every(Boolean), 'Both objects return to the resolving player\'s public battlefield');
      assert.equal(state.players[String(3-seat)].battlefield.some(card => ids.includes(card.id)), false);
      assert.equal(returned[0].counters['+1/+1'], 2, 'Printed entry counters replace the departed object\'s five counters');
      assert.ok(state.players[String(seat)].graveyard.some(card => card.id === fixture.source_id));
      await reload();
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
      console.log(`PASS seat ${seat}, foreign owner ${foreign}: human exact-two permanent selection, real paid API cast, pending reload, native return and final reload`);
    } finally { await close(); }
  }
}
