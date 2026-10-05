import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const scenario of ['discount', 'unrelated-tax', 'prototype']) {
  const response = await fetch(`${api}/fixture/announced-color-cost?seat=${seat}&scenario=${scenario}`, {method:'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json(), id = fixture.match.id;
  const {evaluate, reload, waitFor, click, close} = await openBrowser('http://127.0.0.1:15173/');
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
    await reload();
    await waitFor(`document.body.innerText.includes(${JSON.stringify(fixture.name)})`);
    if (scenario === 'prototype') {
      await waitFor("Boolean(document.querySelector('.hand-row option[value=prototype]'))");
      await evaluate(`(() => {
        const select = document.querySelector('.hand-row option[value=prototype]').parentElement;
        select.value = 'prototype'; select.dispatchEvent(new Event('change', {bubbles:true}));
      })()`);
    }
    await click(`Cast ${fixture.name}`);
    let state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.some(item => item.label === fixture.name));
    assert.equal(Object.values(state.players[String(seat)].mana_pool).reduce((a,b) => a+b, 0), 0);
    await reload();
    for (let step = 0; step < 8 && state.stack.length; step++) {
      const before = state.revision;
      await click('Pass Priority');
      state = await waitForApiState(`${api}/matches/${id}`, state => state.revision > before);
      await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    }
    assert.equal(state.stack.length, 0);
    const card = state.players[String(seat)].battlefield.find(card => card.id === fixture.card_id);
    assert.ok(card);
    if (scenario === 'prototype') assert.equal(card.mana_cost, '{1}{B}');
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    console.log(`PASS seat ${seat}: ${scenario} cost, real UI cast/payment, stack reload and resolution`);
  } finally {await close();}
}
