import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Bog Down', 'Phyrexian Scuta', 'Vicious Offering'];
for (const seat of [1, 2]) for (const index of [0, 1, 2]) for (const kicked of [false, true]) {
  const response = await fetch(`${api}/fixture?face_kind=nonmana_kicker_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const name = names[index];
  const owner = fixture.players[String(seat)];
  const payers = owner.battlefield.filter(card => card.types.includes(index === 0 ? 'Land' : 'Creature'));
  const target = fixture.players[String(3-seat)].battlefield.find(card => card.name === 'Baloth Gorger');
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(`document.body.innerText.includes('Cast ${name}')`);
    await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast ${name}'));
      const cost = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === 'kicker'));
      cost.value = '${kicked ? 'kicker' : 'base'}'; cost.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    if (kicked && index !== 1) {
      await waitFor(`Boolean(document.querySelector('select[aria-label="Sacrifice for cost ${name}"]'))`);
      assert.equal(await evaluate(ready(`Cast ${name}`)), false);
      await evaluate(`(() => {
        const select = document.querySelector('select[aria-label="Sacrifice for cost ${name}"]');
        const ids = ${JSON.stringify(payers.map(card => card.id))};
        [...select.options].forEach(option => option.selected = ids.includes(option.value));
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    if (index !== 1) await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast ${name}'));
      const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => ${index === 0 ? `option.textContent.includes('Player ${seat === 1 ? 'B' : 'A'}')` : `option.value === ${JSON.stringify(target.id)}`}));
      select.value = [...select.options].find(option => ${index === 0 ? `option.textContent.includes('Player ${seat === 1 ? 'B' : 'A'}')` : `option.value === ${JSON.stringify(target.id)}`}).value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(ready(`Cast ${name}`));
    await click(`Cast ${name}`);
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 1)()`);
    await command('Page.reload');
    for (let pass = 0; pass < 2; pass++) {
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      if (pass === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    if (index === 0) {
      await waitFor("document.body.innerText.includes('Choose cards to discard')");
      await command('Page.reload');
      await waitFor("document.body.innerText.includes('Choose cards to discard')");
      await evaluate(`(() => {
        const panel = [...document.querySelectorAll('.block-panel')].find(panel => panel.textContent.includes('Choose cards to discard'));
        [...panel.querySelectorAll('input[type="checkbox"]')].slice(0, ${kicked ? 3 : 2}).forEach(input => input.click());
      })()`);
      await waitFor(ready('Confirm Selection'));
      await click('Confirm Selection');
    }
    await waitFor(`(async () => { const state = await (await fetch('${api}/matches/${fixture.id}')).json(); return state.stack.length === 0 && !state.pending_mechanic_choice; })()`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    const actor = final.players[String(seat)];
    assert.equal(actor.life, kicked && index === 1 ? 17 : 20);
    for (const payer of payers) assert.equal(actor.battlefield.some(card => card.id === payer.id), !kicked);
    if (index === 0) assert.equal(final.players[String(3-seat)].hand_count, kicked ? 0 : 1);
    if (index === 1) assert.equal(actor.battlefield.find(card => card.name === name).power, kicked ? 5 : 3);
    if (index === 2) assert.equal(final.players[String(3-seat)].battlefield.some(card => card.id === target.id), !kicked);
    const sum = pool => Object.values(pool).reduce((a, b) => a + b, 0);
    assert.equal(sum(owner.mana_pool) - sum(actor.mana_pool), index === 0 ? 3 : index === 1 ? 4 : 2);
    console.log(`PASS seat ${seat}: ${kicked ? 'kicked' : 'base'} ${name}, exact resources, stack/choice refresh and resolution`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
