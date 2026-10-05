import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const suppressed of [false, true]) {
    const response = await fetch(`${api}/fixture/life-lock?seat=${seat}&suppressed=${suppressed}`, {method: 'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const id = fixture.match.id;
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const {evaluate, waitFor, click, reload, close} = browser;
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
      const moves = await (await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`)).json();
      assert.equal(moves.moves.some(move => move.type === 'activate_ability' && move.card_id === fixture.ability_source_id), suppressed);
      if (!suppressed) {
        assert.equal(await evaluate("[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith('Activate Erebos'))"), false);
        console.log(`PASS seat ${seat}: active printed life lock prevents life-payment action in API and UI`);
        continue;
      }
      await waitFor("[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith('Activate Erebos') && !button.disabled)");
      await reload();
      await waitFor("[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith('Activate Erebos') && !button.disabled)");
      await click('Activate Erebos');
      await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).stack.length === 1)()`);
      let state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.equal(state.players[String(seat)].life, 18);
      assert.equal(state.players[String(seat)].mana_pool.B, 0);
      assert.equal(state.players[String(seat)].mana_pool.C, 0);
      await reload();
      for (let pass = 0; pass < 2; pass++) {
        await waitFor("[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith('Pass Priority') && !button.disabled)");
        await click('Pass Priority');
        await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).${pass === 0 ? `priority_player === ${3-seat}` : 'stack.length === 0'})()`);
      }
      state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.equal(state.players[String(seat)].hand_count, fixture.hand_count_before+1);
      assert.equal(state.players[String(seat)].life, 18);
      console.log(`PASS seat ${seat}: suppressed lock permits real paid activation, pending reload, priority and draw`);
    } finally { await close(); }
  }
}
