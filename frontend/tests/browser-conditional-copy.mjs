import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const name of ['groundswell', 'rest-for-the-weary', 'lightning-helix', 'essence-drain']) {
    for (const enhanced of ['groundswell', 'rest-for-the-weary'].includes(name) ? [false, true] : [false]) {
      const response = await fetch(`${api}/fixture/conditional-copy?seat=${seat}&name=${name}&enhanced=${enhanced}`, {method: 'POST'});
      assert.equal(response.status, 200);
      const fixture = await response.json(), id = fixture.match.id;
      const original = fixture.match.stack.find(item => item.id === fixture.original_id);
      const {evaluate, waitFor, reload, click, close} = await openBrowser('http://127.0.0.1:15173/');
      try {
        await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
        await reload();
        await waitFor(`document.body.innerText.includes(${JSON.stringify(fixture.match.pending_mechanic_choice.label)})`);
        await evaluate(`(() => {
          const label = [...document.querySelectorAll('.block-panel label')].find(label => label.textContent.trim() === ${JSON.stringify(fixture.recipient_name)});
          if (!label) throw new Error('Missing conditional copy recipient');
          label.querySelector('input[type=checkbox]').click();
        })()`);
        await click('Confirm Selection');
        await waitFor(`(async () => !(await (await fetch('${api}/matches/${id}')).json()).pending_mechanic_choice)()`);
        await reload();
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
        await reload();
        state = await (await fetch(`${api}/matches/${id}`)).json();
        assert.equal(state.stack[0].id, fixture.original_id);
        if (name === 'groundswell') {
          const amount = enhanced ? 4 : 2;
          const card = state.players[String(3-seat)].battlefield.find(card => card.id === fixture.new_id);
          assert.deepEqual([card.power, card.toughness], [5+amount, 6+amount]);
          const old = state.players[String(seat)].battlefield.find(card => card.id === fixture.old_id);
          assert.deepEqual([old.power, old.toughness], [5, 6]);
        } else if (name === 'rest-for-the-weary') {
          assert.equal(state.players[String(seat)].life, enhanced ? 28 : 24);
          assert.equal(state.players[String(3-seat)].life, 20);
        } else {
          assert.equal(state.players[String(seat)].life, 17);
          assert.equal(state.players[String(3-seat)].life, 23);
        }
        console.log(`PASS copier seat ${3-seat}: paid ${name} ${enhanced ? 'enhanced' : 'ordinary'}, retarget/reload and resolved copy only`);
      } finally { await close(); }
    }
  }
}
