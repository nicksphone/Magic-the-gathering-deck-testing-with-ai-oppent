import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Goblin Grenade', 'Fodder Launch', 'Natural Order', 'Abjure'];
const payers = ['Goblin Instigator', 'Goblin Instigator', 'Woodland Changeling', 'Hapless Researcher'];
for (const seat of [1, 2]) for (const [index, name] of names.entries()) {
  const response = await fetch(`${api}/fixture?face_kind=qualified_cost_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const owner = fixture.players[String(seat)];
  const payer = owner.battlefield.find(card => card.name === payers[index]);
  const target = fixture.players[String(3-seat)].battlefield.find(card => card.name === 'Baloth Gorger');
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(`document.body.innerText.includes(${JSON.stringify(`Cast ${name}`)})`);
    const selector = `select[aria-label="Sacrifice for cost ${name}"]`;
    await waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)}))`);
    assert.equal(await evaluate(ready(`Cast ${name}`)), false);
    await evaluate(`(() => {
      const select = document.querySelector(${JSON.stringify(selector)});
      const values = [...select.options].filter(option => option.value).map(option => option.value);
      if (values.length !== 1 || values[0] !== ${JSON.stringify(payer.id)}) throw new Error('Incorrect qualified payment candidates');
      [...select.options].forEach(option => option.selected = option.value === ${JSON.stringify(payer.id)});
      select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    if (index !== 2) await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes(${JSON.stringify(`Cast ${name}`)}));
      const matches = option => ${index === 0 ? `option.textContent.includes('Player ${seat === 1 ? 'B' : 'A'}')` : `option.value === ${JSON.stringify(index === 3 ? fixture.stack[0].id : target.id)}`};
      const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(matches));
      select.value = [...select.options].find(matches).value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(ready(`Cast ${name}`));
    await click(`Cast ${name}`);
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === ${index === 3 ? 2 : 1})()`);
    await command('Page.reload');
    for (let pass = 0; pass < 2; pass++) {
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      if (pass === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    if (index === 2) {
      await waitFor("document.body.innerText.includes('Search your library (you may fail to find a matching card)')");
      await command('Page.reload');
      await waitFor("document.body.innerText.includes('Search your library (you may fail to find a matching card)')");
      const pending = await (await fetch(`${api}/matches/${fixture.id}`)).json();
      assert.equal(pending.pending_mechanic_choice.options.length, 1);
      await evaluate(`(() => {
        const panel = [...document.querySelectorAll('.block-panel')].find(panel => panel.textContent.includes('Search your library'));
        const boxes = [...panel.querySelectorAll('input[type="checkbox"]')];
        if (boxes.length !== 1) throw new Error('Wrong qualified search options');
        boxes[0].click();
      })()`);
      await waitFor(ready('Confirm Selection'));
      await click('Confirm Selection');
    }
    await waitFor(`(async () => { const state = await (await fetch('${api}/matches/${fixture.id}')).json(); return state.stack.length === 0 && !state.pending_mechanic_choice; })()`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    const actor = final.players[String(seat)];
    assert.equal(actor.battlefield.some(card => card.id === payer.id), false);
    assert.equal(actor.life, 20);
    if (index < 2) assert.equal(final.players[String(3-seat)].life, 15);
    if (index === 1) assert.equal(final.players[String(3-seat)].battlefield.some(card => card.id === target.id), false);
    if (index === 2) {
      assert.equal(actor.battlefield.some(card => card.name === 'Baloth Gorger'), true);
      assert.equal(actor.battlefield.some(card => card.name === 'Myr Superion'), false);
    }
    if (index === 3) assert.equal(final.players[String(3-seat)].graveyard_count, 1);
    const sum = pool => Object.values(pool).reduce((a, b) => a + b, 0);
    assert.equal(sum(owner.mana_pool) - sum(actor.mana_pool), [1,4,4,1][index]);
    console.log(`PASS seat ${seat}: ${name}, exact qualified payment, stack reload and actual downstream effect`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
