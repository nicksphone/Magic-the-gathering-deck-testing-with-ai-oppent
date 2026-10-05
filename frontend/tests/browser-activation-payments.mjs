import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const kind of ['sacrifice', 'discard', 'artifact']) {
    const response = await fetch(`${api}/fixture/activation-payment?seat=${seat}&kind=${kind}`, {method: 'POST'});
    assert.equal(response.status, 200);
    const fixture = await response.json(), id = fixture.match.id;
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const {evaluate, waitFor, reload, close} = browser;
    const selector = `[data-ability-source="${fixture.source_id}"][data-ability-index="${fixture.ability_index}"]`;
    try {
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)})?.querySelector('fieldset input'))`);
      assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}).querySelector('button').disabled`), true);
      await evaluate(`(() => {
        const row = document.querySelector(${JSON.stringify(selector)});
        const input = [...row.querySelectorAll('input[type=checkbox]')].find(input => input.getAttribute('aria-label').includes(${JSON.stringify(fixture.chosen_id)}));
        if (!input) throw new Error('Missing declared resource checkbox');
        input.click();
      })()`);
      await waitFor(`document.querySelector(${JSON.stringify(selector)})?.querySelector('button').disabled === false`);
      await evaluate(`document.querySelector(${JSON.stringify(selector)}).querySelector('button').click()`);
      let state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 1);
      assert.ok(state.players[String(seat)].graveyard.some(card => card.id === fixture.chosen_id));
      assert.ok(!state.players[String(seat)].graveyard.some(card => card.id === fixture.retained_id));
      if (kind === 'artifact') assert.equal(state.players[String(seat)].mana_pool.C, 0);
      await reload();
      await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
      state = await (await fetch(`${api}/matches/${id}`)).json();
      assert.equal(state.stack.length, 1);
      assert.ok(state.players[String(seat)].graveyard.some(card => card.id === fixture.chosen_id));
      console.log(`PASS seat ${seat}: deliberate ${kind} payment, actual cost and paid-stack reload`);
    } finally { await close(); }
  }
}
