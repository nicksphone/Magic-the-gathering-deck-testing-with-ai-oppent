import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';
const api = 'http://127.0.0.1:10199';
const ready = label => `Boolean([...document.querySelectorAll('button')].find(button =>
  button.textContent.trim() === ${JSON.stringify(label)} && !button.disabled && !button.closest('fieldset[disabled]')))`;

for (const seat of [1, 2]) for (const index of [0, 1, 2, 3]) {
  const response = await fetch(`${api}/fixture?face_kind=mana_${index}_${seat}`, {method: 'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const {evaluate, reload, waitFor, click, close} = browser;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${seat}')`);
    let state;
    if (index !== 1) {
      const amount = [3, 0, 6, 4][index];
      await waitFor(ready(`Add ${amount} G`));
      await evaluate("[...document.querySelectorAll('details')].find(detail => detail.querySelector('summary')?.textContent.startsWith('Mana abilities')).open = true");
      await click(`Add ${amount} G`);
      state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.players[String(seat)].mana_pool.G === amount);
      assert.equal(state.stack.length, 0, 'Mana activation must resolve without stack/priority passing');
      if (index === 0) {
        assert.equal(state.players[String(seat)].battlefield.filter(card => card.name === 'Forest' && card.tapped).length, 2);
        assert.ok(state.players[String(seat)].battlefield.find(card => card.name.startsWith('Nykthos')).tapped);
        await reload();
        await waitFor(`document.body.innerText.includes('Priority: P${seat}')`);
        console.log(`PASS seat ${seat}: paid mana choice, both cost sources, immediate output and reload`);
        continue;
      }
    }
    const name = index === 3 ? 'Llanowar Elves' : 'Steel Leaf Champion';
    await waitFor(`Boolean([...document.querySelectorAll('button')].find(button => button.textContent.startsWith(${JSON.stringify(`Cast ${name}`)}) && !button.disabled))`);
    await click(`Cast ${name}`);
    state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.stack.length > 0);
    const pool = state.players[String(seat)].mana_pool.G ?? 0;
    assert.equal(pool, index === 1 ? 0 : 3);
    if (index === 1) {
      assert.ok(state.players[String(seat)].battlefield.find(card => card.name.startsWith('Nykthos')).tapped);
      assert.equal(state.players[String(seat)].battlefield.filter(card => card.name === 'Forest' && card.tapped).length, 2);
    }
    for (let step = 0; step < 8 && state.stack.length; step++) {
      await waitFor(ready('Pass Priority'));
      await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
      const revision = state.revision;
      await click('Pass Priority');
      state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.revision > revision);
    }
    assert.equal(state.stack.length, 0);
    assert.ok(state.players[String(seat)].battlefield.some(card => card.name === name));
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    console.log(`PASS seat ${seat}: ${['paid', 'automatic paid', 'stacked multiplier', 'devotion'][index]} mana, actual cast/payment, resolution and reload`);
  } finally { await close(); }
}
