import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const primary of ['player', 'planeswalker']) {
    const response = await fetch(`${api}/fixture/linked-copy?seat=${seat}&primary=${primary}`, {method:'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const id = fixture.match.id;
    const original = fixture.match.stack.find(item => item.id === fixture.original_id);
    const {evaluate, waitFor, reload, click, close} = await openBrowser('http://127.0.0.1:15173/');
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      for (let slot = 0; slot < 2; slot++) {
        const name = slot === 0 ? fixture.primary_name : 'Torrential Gearhulk';
        await waitFor(`document.body.innerText.includes('Choose linked target ${slot+1} for Searing Blaze (copy)')`);
        await evaluate(`(() => {
          const label = [...document.querySelectorAll('.block-panel label')].find(label => label.textContent.trim() === ${JSON.stringify(name)});
          if (!label) throw new Error('Missing linked copy recipient');
          label.querySelector('input[type=checkbox]').click();
        })()`);
        await click('Confirm Selection');
        await waitFor(`(async () => {
          const state = await (await fetch('${api}/matches/${id}')).json();
          return ${slot === 0 ? 'state.pending_mechanic_choice?.linked_target_index === 1' : 'state.pending_mechanic_choice === null'};
        })()`);
        await reload();
      }
      let state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.deepEqual(state.stack.find(item => item.id === fixture.original_id), original);
      assert.equal(state.players[String(3-seat)].mana_pool.U, 0);
      assert.ok(state.players[String(3-seat)].graveyard.some(card => card.name === 'Twincast'));
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
      assert.equal(state.players[String(seat)].life, 19);
      assert.equal(state.players[String(seat)].battlefield.find(card => card.id === fixture.second_id).damage_marked, 1);
      assert.equal(state.players[String(3-seat)].battlefield.find(card => card.id === fixture.first_id).damage_marked, 0);
      console.log(`PASS seat ${3-seat}: paid ${primary} linked-copy retarget, inter-choice reload, original unchanged and actual damage`);
    } finally { await close(); }
  }
}
