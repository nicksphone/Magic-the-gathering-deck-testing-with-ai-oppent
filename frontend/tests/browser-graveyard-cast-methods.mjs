import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const method of ['prototype', 'bestow']) {
  const response = await fetch(`${api}/fixture/graveyard-cast-method?seat=${seat}&method=${method}`, {method:'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json(), id = fixture.match.id;
  const {evaluate, reload, waitFor, click, close} = await openBrowser('http://127.0.0.1:15173/');
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
    await reload();
    const prefix = JSON.stringify(method + '_graveyard:');
    await waitFor(`[...document.querySelectorAll('.hand-row option')].some(option => option.value.startsWith(${prefix}))`);
    await evaluate(`(() => {
      const option = [...document.querySelectorAll('.hand-row option')].find(option => option.value.startsWith(${prefix}));
      const select = option.parentElement; select.value = option.value; select.dispatchEvent(new Event('change', {bubbles:true}));
    })()`);
    if (method === 'bestow') {
      await waitFor(`Boolean(document.querySelector('.hand-row option[value="${fixture.host_id}"]'))`);
      await evaluate(`(() => {
        const select = document.querySelector('.hand-row option[value="${fixture.host_id}"]').parentElement;
        select.value = ${JSON.stringify(fixture.host_id)}; select.dispatchEvent(new Event('change', {bubbles:true}));
      })()`);
    }
    await click(`Cast ${fixture.name}`);
    let state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.some(item => item.label === fixture.name));
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
    if (method === 'prototype') assert.equal(card.mana_cost, '{1}{B}');
    else assert.equal(card.attached_to, fixture.host_id);
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    console.log(`PASS seat ${seat}: real graveyard ${method} choice, target/payment, stack reload and resolution`);
  } finally {await close();}
}
