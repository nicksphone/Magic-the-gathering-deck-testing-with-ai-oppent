import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';
import {activateIndexedMana} from './indexed-mana-control.mjs';
const api = 'http://127.0.0.1:10199';
const ready = label => `Boolean([...document.querySelectorAll('button')].find(button =>
  button.textContent.trim() === ${JSON.stringify(label)} && !button.disabled && !button.closest('fieldset[disabled]')))`;

for (const seat of [1, 2]) for (const index of [0, 1, 2, 3]) {
  const landName = index === 3 ? 'Unclaimed Territory' : 'Hallowed Fountain';
  const response = await fetch(`${api}/fixture?face_kind=land_types_${index}_${seat}`, {method: 'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const {evaluate, reload, waitFor, click, close} = browser;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${seat}')`);
    await click(index === 1 ? 'Play Land Hallowed Fountain (pay 2 life, untapped)' : `Play Land ${landName}`);
    let state = await waitForApiState(`${api}/matches/${fixture.id}`, state =>
      state.players[String(seat)].battlefield.some(card => card.name === landName) || state.pending_mechanic_choice);
    assert.equal(state.pending_mechanic_choice, null);
    const land = state.players[String(seat)].battlefield.find(card => card.name === landName);
    assert.ok(land && !land.tapped);
    assert.equal(state.players[String(seat)].life, index === 1 ? 18 : 20);
    assert.ok(index === 3 ? land.base_type_line === 'Land' : land.base_type_line.includes('Island') && land.base_type_line.includes('Plains'));
    assert.deepEqual(land.mana_source_colors.slice().sort(), index === 1 ? ['B', 'G', 'R', 'U', 'W'] : ['R']);
    if (index === 3) {
      await waitFor(`(() => { const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Lightning Bolt')); return Boolean(box && [...box.querySelectorAll('select')].some(select => [...select.options].some(option => option.value === '${3-seat}' || option.value === 'player:${3-seat}'))); })()`);
      await evaluate(`(() => { const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Lightning Bolt')); const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === '${3-seat}' || option.value === 'player:${3-seat}')); if (!select) throw new Error('Missing Bolt player target'); select.value = [...select.options].find(option => option.value === '${3-seat}' || option.value === 'player:${3-seat}').value; select.dispatchEvent(new Event('change', {bubbles: true})); })()`);
      await click('Cast Lightning Bolt');
      state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.stack.length === 1);
      assert.equal(state.players[String(seat)].restricted_mana_pool.length, 0);
      for (let pass = 0; pass < 2; pass++) {
        await waitFor(ready('Pass Priority'));
        await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
        const revision = state.revision;
        await click('Pass Priority');
        state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.revision > revision);
      }
      assert.equal(state.players[String(3-seat)].life, 17);
    } else {
      await activateIndexedMana(browser, {api, id: fixture.id, seat, cardId: land.id, color: 'R'});
      state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.players[String(seat)].mana_pool.R === 1);
    }
    assert.equal(state.stack.length, 0);
    assert.ok(state.players[String(seat)].battlefield.find(card => card.id === land.id).tapped);
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${seat}')`);
    console.log(`PASS seat ${seat}: land-type ${index}, real entry/payment, ${index === 3 ? 'automatic instant cast/resolve' : 'immediate mana'} and reload`);
  } finally { await close(); }
}
