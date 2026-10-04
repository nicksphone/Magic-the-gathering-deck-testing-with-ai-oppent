import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const ready = label => `Boolean([...document.querySelectorAll('button')].find(button =>
  button.textContent.startsWith(${JSON.stringify(label)}) && !button.disabled && !button.closest('fieldset[disabled]')))`;

for (const seat of [1, 2]) for (const index of [0, 1]) {
  const response = await fetch(`${api}/fixture?face_kind=creature_type_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const god = fixture.players[String(seat)].battlefield.find(card => card.name.includes('God of'));
  assert.ok(!god.types.includes('Creature'));
  assert.equal(god.power, null);
  const article = `[...document.querySelectorAll('article.card')].find(card => card.title === ${JSON.stringify(god.name)})`;
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, reload, waitFor, click, close } = browser;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor(`Boolean(${article})`);
    assert.equal(await evaluate(`(${article}).querySelector('p').textContent.includes('Creature')`), false);
    assert.ok(await evaluate(`(${article}).textContent.includes('-/-')`));
    await waitFor(ready('Cast Burning-Tree Emissary'));
    await click('Cast Burning-Tree Emissary');
    let state = await waitForApiState(`${api}/matches/${fixture.id}`, value => value.stack.length > 0);
    assert.equal(Object.values(state.players[String(seat)].mana_pool).reduce((sum, amount) => sum + amount, 0), 46);
    for (let step = 0; step < 16 && state.stack.length; step++) {
      await waitFor(ready('Pass Priority'));
      await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
      const revision = state.revision;
      await click('Pass Priority');
      state = await waitForApiState(`${api}/matches/${fixture.id}`, value => value.revision > revision);
    }
    assert.equal(state.stack.length, 0);
    const result = state.players[String(seat)].battlefield.find(card => card.id === god.id);
    assert.ok(result.types.includes('Creature'));
    assert.equal(result.power, 6);
    assert.equal(result.toughness, index === 0 ? 6 : 5);
    await waitFor(`Boolean((${article})?.querySelector('p').textContent.includes('Creature'))`);
    await reload();
    await waitFor(`Boolean((${article})?.querySelector('p').textContent.includes('Creature'))`);
    assert.ok(await evaluate(`(${article}).textContent.includes(${JSON.stringify(index === 0 ? '6/6' : '6/5')})`));
    console.log(`PASS seat ${seat}: ${god.name}, noncreature display, real hybrid cast, live threshold/stats and reload`);
  } finally {
    await close();
  }
}
