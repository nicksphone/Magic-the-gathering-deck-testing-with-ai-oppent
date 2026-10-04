import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Aspect of Hydra', 'Gray Merchant of Asphodel', 'Fanatic of Mogis',
  'Reverent Hunter', 'Evangel of Heliod', 'Setessan Petitioner', 'Abhorrent Overlord'];
const costs = [1, 5, 4, 3, 6, 3, 7];
const ready = label => `Boolean([...document.querySelectorAll('button')].find(button =>
  button.textContent.startsWith(${JSON.stringify(label)}) && !button.disabled && !button.closest('fieldset[disabled]')))`;

for (const seat of [1, 2]) for (let index = 0; index < names.length; index++) {
  const name = names[index];
  const response = await fetch(`${api}/fixture?face_kind=devotion_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const recipient = fixture.players[String(seat)].battlefield.find(card => card.name === 'Burning-Tree Emissary');
  const spell = fixture.players[String(seat)].hand.find(card => card.name === name);
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, reload, waitFor, click, close } = browser;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor(`document.body.innerText.includes(${JSON.stringify(name)})`);
    if (index === 0) {
      await evaluate(`(() => {
        const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast Aspect of Hydra'));
        const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === ${JSON.stringify(recipient.id)}));
        if (!select) throw new Error('Missing human creature target control');
        select.value = ${JSON.stringify(recipient.id)};
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await waitFor(ready(`Cast ${name}`));
    await click(`Cast ${name}`);
    let state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.stack.length > 0);
    assert.equal(Object.values(state.players[String(seat)].mana_pool).reduce((sum, amount) => sum + amount, 0), 40 - costs[index]);
    await reload();
    for (let step = 0; step < 12 && state.stack.length; step++) {
      await waitFor(ready('Pass Priority'));
      await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
      const revision = state.revision;
      await click('Pass Priority');
      state = await waitForApiState(`${api}/matches/${fixture.id}`, state => state.revision > revision);
    }
    assert.equal(state.stack.length, 0);
    const own = state.players[String(seat)];
    const other = state.players[String(3 - seat)];
    if (index === 0) assert.equal(own.battlefield.find(card => card.id === recipient.id).power, 4);
    if (index === 1) assert.deepEqual([own.life, other.life], [22, 18]);
    if (index === 2) assert.equal(other.life, 17);
    if (index === 3) assert.equal(own.battlefield.find(card => card.id === spell.id).power, 4);
    if (index === 5) assert.equal(own.life, 24);
    if (index === 4 || index === 6) {
      const tokens = own.battlefield.filter(card => card.is_token);
      assert.equal(tokens.length, 2);
      assert.ok(tokens.every(card => card.power === 1 && card.toughness === 1));
      if (index === 6) assert.ok(tokens.every(card => card.keywords.includes('flying')));
    }
    await reload();
    await waitFor(ready('Pass Priority'));
    const recovered = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.deepEqual(recovered.players, state.players);
    console.log(`PASS seat ${seat}: ${name}, actual payment, live devotion payoff and stack/result reload through App/API`);
  } finally {
    await close();
  }
}
