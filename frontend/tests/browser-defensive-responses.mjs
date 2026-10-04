import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Adamant Will', 'Moment of Heroism'];
const ready = label => `Boolean([...document.querySelectorAll('button')].find(button =>
  button.textContent.startsWith(${JSON.stringify(label)}) && !button.disabled && !button.closest('fieldset[disabled]')))`;

for (const seat of [1, 2]) for (let index = 0; index < names.length; index++) {
  const response = await fetch(`${api}/fixture?face_kind=defense_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const guard = fixture.players[String(seat)].battlefield.find(card => card.name === 'Burning-Tree Emissary');
  const threat = fixture.players[String(3 - seat)].battlefield[0];
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, reload, waitFor, click, close } = browser;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor(`Boolean([...document.querySelectorAll('.cast-card-box')].find(box =>
      box.textContent.includes(${JSON.stringify(`Cast ${names[index]}`)})))`);
    await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes(${JSON.stringify(`Cast ${names[index]}`)}));
      const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === ${JSON.stringify(guard.id)}));
      if (!select) throw new Error('Missing human creature target control');
      select.value = ${JSON.stringify(guard.id)};
      select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(ready(`Cast ${names[index]}`));
    await click(`Cast ${names[index]}`);
    let state = await waitForApiState(`${api}/matches/${fixture.id}`, value => value.stack.length > 0);
    assert.equal(Object.values(state.players[String(seat)].mana_pool).reduce((sum, value) => sum + value, 0), 9);
    await reload();
    for (let step = 0; step < 16 && state.step !== 'end_combat'; step++) {
      await waitFor(ready('Pass Priority'));
      await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
      const revision = state.revision;
      await click('Pass Priority');
      state = await waitForApiState(`${api}/matches/${fixture.id}`, value => value.revision > revision);
    }
    assert.equal(state.step, 'end_combat');
    const survivor = state.players[String(seat)].battlefield.find(card => card.id === guard.id);
    assert.equal(survivor.power, 4);
    assert.equal(survivor.toughness, 4);
    assert.ok(survivor.keywords.includes(index === 0 ? 'indestructible' : 'lifelink'));
    if (index === 0) assert.ok(state.players[String(3 - seat)].battlefield.some(card => card.id === threat.id));
    else {
      assert.equal(state.players[String(seat)].life, 24);
      assert.ok(state.players[String(3 - seat)].graveyard.some(card => card.id === threat.id));
    }
    await reload();
    await waitFor(ready('Pass Priority'));
    const restored = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.deepEqual(restored.players, state.players);
    console.log(`PASS seat ${seat}: ${names[index]}, chosen defensive recipient, payment, keyword/combat result and reload through App/API`);
  } finally {
    await close();
  }
}
