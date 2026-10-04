import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const [index, name] of ['Tarmogoyf', 'Boneyard Wurm', "Death's Shadow"].entries()) {
  const response = await fetch(`${api}/fixture?face_kind=characteristic_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const { evaluate, reload, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor(ready(`Cast ${name}`)); await click(`Cast ${name}`);
    await waitForApiState(`${api}/matches/${fixture.id}`, state => state.stack.length === 1);
    for (let pass = 0; pass < 2; pass++) {
      await reload();
      await waitFor(ready('Pass Priority'));
      const before = await waitForApiState(`${api}/matches/${fixture.id}`, () => true);
      await click('Pass Priority');
      await waitForApiState(`${api}/matches/${fixture.id}`, state =>
        state.stack.length === (pass === 1 ? 0 : 1) && state.priority_player !== before.priority_player);
    }
    const state = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    const card = state.players[String(seat)].battlefield.find(card => card.name === name);
    assert.ok(card);
    const expected = [[6, 7], [1, 1], [4, 4]][index];
    assert.deepEqual([card.power, card.toughness], expected);
    assert.equal(card.printed_power, index === 2 ? '13' : '*');
    await reload();
    await waitFor(`document.body.innerText.includes(${JSON.stringify(name)}) && document.body.innerText.includes(${JSON.stringify(expected.join('/'))})`);
    console.log(`PASS seat ${seat}: ${name} cast, effective stats, printed expression and reload`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')"); await close();
  }
}
