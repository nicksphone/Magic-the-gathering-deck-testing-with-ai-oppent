import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const first of ['conversion', 'double']) {
    const response = await fetch(`${api}/fixture/life-conversion?seat=${seat}`, {method: 'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const id = fixture.match.id;
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const {evaluate, waitFor, click, reload, close} = browser;
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor("document.querySelector('.replacement-choice-panel') !== null");
      let state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.equal(state.pending_replacement_choice.player_id, seat);
      assert.equal(state.players[String(seat)].life, 20);
      assert.equal(state.players[String(3-seat)].battlefield.find(card => card.id === fixture.converter_id).damage_marked, 3);
      await reload();
      await waitFor("document.querySelector('.replacement-choice-panel') !== null");
      await click(first === 'conversion' ? 'Plague Drone' : "Alhammarret's Archive");
      await waitFor(`(async () => !(await (await fetch('${api}/matches/${id}')).json()).pending_replacement_choice)()`);
      state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.equal(state.players[String(seat)].life, first === 'conversion' ? 17 : 14);
      assert.ok(state.players[String(3-seat)].graveyard.some(card => card.id === fixture.converter_id));
      assert.ok(state.players[String(seat)].graveyard.some(card => card.id === fixture.spell_id));
      assert.equal(state.players[String(seat)].mana_pool.W, 0);
      assert.equal(state.players[String(seat)].mana_pool.R, 0);
      await reload();
      await waitFor("document.querySelector('.battlefield') !== null && !document.querySelector('.replacement-choice-panel')");
      console.log(`PASS seat ${seat}: ${first} ordering, paused reload, lethal source retained and final spell/creature departure`);
    } finally { await close(); }
  }
}
