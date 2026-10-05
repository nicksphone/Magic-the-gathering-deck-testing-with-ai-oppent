import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  const response = await fetch(`${api}/fixture/joint-activation-payment?seat=${seat}`, {method: 'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json(), id = fixture.match.id;
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const {evaluate, waitFor, reload, close} = browser;
  const selector = `[data-ability-source="${fixture.source_id}"][data-ability-index="3"]`;
  try {
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
    await reload();
    await waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)})?.querySelector('fieldset input'))`);
    await evaluate(`(() => {
      const row = document.querySelector(${JSON.stringify(selector)});
      const input = [...row.querySelectorAll('input[type=checkbox]')].find(input => input.getAttribute('aria-label').includes(${JSON.stringify(fixture.chosen_id)}));
      if (!input) throw new Error('Missing selected sacrifice resource');
      input.click();
    })()`);
    await waitFor(`document.querySelector(${JSON.stringify(selector)})?.querySelector('button').disabled === false`);
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).querySelector('button').click()`);
    let state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 1);
    for (const resource of [fixture.chosen_id, fixture.mana_source_id]) {
      assert.ok(state.players[String(seat)].graveyard.some(card => card.id === resource));
    }
    assert.ok(state.players[String(seat)].battlefield.some(card => card.id === fixture.source_id && card.tapped));
    assert.equal(Object.values(state.players[String(seat)].mana_pool).reduce((sum, amount) => sum + amount, 0), 0);
    await reload();
    await waitFor("document.querySelector('.battlefield') !== null && !document.body.innerText.includes('Restoring saved session')");
    state = await (await fetch(`${api}/matches/${id}`)).json();
    assert.equal(state.stack.length, 1);
    console.log(`PASS seat ${seat}: deliberate artifact cost preserved through separate mana sacrifice and reload`);
  } finally { await close(); }
}
