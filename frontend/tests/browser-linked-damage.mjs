import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const primary of ['player', 'planeswalker']) {
    for (const enhanced of [false, true]) {
      const response = await fetch(`${api}/fixture/linked-damage?seat=${seat}&primary=${primary}&enhanced=${enhanced}`, {method: 'POST'});
      assert.equal(response.status, 200);
      const fixture = await response.json();
      const id = fixture.match.id;
      const before = await (await fetch(`${api}/matches/${id}`)).json();
      const rejected = await fetch(`${api}/matches/${id}/action`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-Match-Revision': String(before.revision), 'Idempotency-Key': `bad-linked-${id}`},
        body: JSON.stringify({player_id: seat, action: {type: 'cast_spell', card_id: fixture.spell_id,
          targets: {target_player: seat, target_card_id: fixture.creature_id}}}),
      });
      assert.ok(rejected.status >= 400 && rejected.status < 500, `Wrong controller pair must reject, received ${rejected.status}`);
      assert.deepEqual(await (await fetch(`${api}/matches/${id}`)).json(), before, 'Rejected pair must preserve the complete public state');
      const browser = await openBrowser('http://127.0.0.1:15173/');
      const {evaluate, waitFor, click, reload, close} = browser;
      try {
        await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
        await reload();
        await waitFor(`document.querySelector('[aria-label="Linked targets for Searing Blaze"]') !== null`);
        assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith('Cast Searing Blaze')).disabled"), true);
        const index = await evaluate(`(() => {
          const select = document.querySelector('[aria-label="Linked targets for Searing Blaze"]');
          const options = [...select.options];
          return options.find(option => option.textContent.includes(${JSON.stringify(fixture.primary_name)}) && option.textContent.includes('Torrential Gearhulk'))?.value;
        })()`);
        assert.notEqual(index, undefined, 'Expected the complete linked pair among legal options');
        await evaluate(`(() => {
          const select = document.querySelector('[aria-label="Linked targets for Searing Blaze"]');
          select.value = ${JSON.stringify(index)}; select.dispatchEvent(new Event('change', {bubbles:true}));
        })()`);
        await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Cast Searing Blaze') && !b.disabled)");
        await click('Cast Searing Blaze');
        await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).stack.length === 1)()`);
        let state = await (await fetch(`${api}/matches/${id}`)).json();
        assert.equal(state.players[String(seat)].mana_pool.R, 0);
        await reload();
        for (let pass = 0; pass < 2; pass++) {
          await waitFor("[...document.querySelectorAll('button')].some(b => b.textContent.trim().startsWith('Pass Priority') && !b.disabled)");
          await click('Pass Priority');
          await waitFor(`(async () => (await (await fetch('${api}/matches/${id}')).json()).${pass === 0 ? `priority_player === ${3-seat}` : 'stack.length === 0'})()`);
        }
        state = await (await fetch(`${api}/matches/${id}`)).json();
        const opponent = state.players[String(3-seat)];
        const creature = opponent.battlefield.find(card => card.id === fixture.creature_id);
        assert.equal(creature.damage_marked, fixture.amount);
        const after = primary === 'player' ? opponent.life : opponent.battlefield.find(card => card.id === fixture.walker_id).loyalty;
        assert.equal(after, fixture.primary_before - fixture.amount);
        await reload();
        await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
        console.log(`PASS seat ${seat}: ${primary} linked pair, ${enhanced ? 'landfall' : 'ordinary'} damage, paid cast and reload`);
      } finally { await close(); }
    }
  }
}
