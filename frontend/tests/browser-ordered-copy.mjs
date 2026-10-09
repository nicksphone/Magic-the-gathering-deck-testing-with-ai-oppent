import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const shared of [false, true]) {
    const response = await fetch(`${api}/fixture/ordered-copy?seat=${seat}&shared=${shared}`, {method:'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const id = fixture.match.id;
    const [first, second] = fixture.creature_ids;
    const chosen = [second, shared ? second : first];
    const {evaluate, waitFor, reload, click, close} = await openBrowser('http://127.0.0.1:15173/');
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      for (let slot = 0; slot < 2; slot++) {
        const name = slot === 0 || shared ? 'Torrential Gearhulk' : 'Sheoldred, the Apocalypse';
        await waitFor(`document.body.innerText.includes('Choose target ${slot+1} for Agony Warp (copy)')`);
        await click(name);
        await waitFor(`(async () => {
          const state = await (await fetch('${api}/matches/${id}')).json();
          return ${slot === 0 ? 'state.pending_mechanic_choice?.ordered_target_index === 1' : 'state.pending_mechanic_choice === null'};
        })()`);
        await reload();
      }
      let state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.deepEqual(state.stack.at(-1).targets, chosen);
      assert.deepEqual(state.stack.find(item => item.id === fixture.original_id).targets, shared ? [first, first] : [first, second]);
      assert.equal(state.players[String(seat)].mana_pool.U, 0);
      assert.equal(state.players[String(seat)].mana_pool.B, 0);
      for (let pass = 0; pass < 2; pass++) {
        await waitFor("[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith('Pass Priority') && !button.disabled)");
        await click('Pass Priority');
        await waitFor(`(async () => {
          const state = await (await fetch('${api}/matches/${id}')).json();
          return ${pass === 0 ? `state.priority_player === ${3-seat}` : 'state.stack.length === 1'};
        })()`);
      }
      state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.equal(state.stack[0].id, fixture.original_id);
      const board = state.players[String(3-seat)].battlefield;
      const one = board.find(card => card.id === first), two = board.find(card => card.id === second);
      assert.deepEqual([one.power, one.toughness], shared ? [4, 5] : [4, 2]);
      assert.deepEqual([two.power, two.toughness], shared ? [2, 3] : [2, 6]);
      console.log(`PASS seat ${seat}: sequential ${shared ? 'shared' : 'different'} copy targets, inter-choice reload, original unchanged and actual partial-stack resolution`);
    } finally { await close(); }
  }
}
