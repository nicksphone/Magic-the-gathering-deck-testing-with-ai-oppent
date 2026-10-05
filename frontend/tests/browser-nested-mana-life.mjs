import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const life of [3, 5]) {
    const response = await fetch(`${api}/fixture/nested-mana-life?seat=${seat}&life=${life}`, {method: 'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json(), id = fixture.match.id;
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const {evaluate, waitFor, reload, close} = browser;
    const selector = `[data-ability-source="${fixture.source_id}"][data-ability-index="0"]`;
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
      const legal = await (await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`)).json();
      assert.equal(legal.moves.some(move => move.type === 'activate_ability' && move.card_id === fixture.source_id), life === 5);
      if (life === 3) {
        assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}) !== null`), false);
        const before = await (await fetch(`${api}/matches/${id}`)).json();
        const rejected = await fetch(`${api}/matches/${id}/action`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({player_id: seat, action: {type: 'activate_ability', card_id: fixture.source_id, ability_index: 0}})});
        assert.equal(rejected.status, 422);
        assert.deepEqual(await (await fetch(`${api}/matches/${id}`)).json(), before);
        console.log(`PASS seat ${seat}: unavailable combined life payment rejected without changing match`);
        continue;
      }
      await waitFor(`document.querySelector(${JSON.stringify(selector)})?.querySelector('button').disabled === false`);
      await evaluate(`document.querySelector(${JSON.stringify(selector)}).querySelector('button').click()`);
      let state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 1);
      assert.equal(state.players[String(seat)].life, 1);
      assert.equal(Object.values(state.players[String(seat)].mana_pool).reduce((sum, amount) => sum + amount, 0), 0);
      await reload();
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
      state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.equal(state.players[String(seat)].life, 1);
      assert.equal(state.stack.length, 1);
      console.log(`PASS seat ${seat}: actual four-life combined payment and paid-stack reload`);
    } finally { await close(); }
  }
}
