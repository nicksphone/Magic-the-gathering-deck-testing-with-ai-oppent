import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Eject the Warp Core', 'Final Flourish', 'Hypnotic Cloud', 'Stomped by the Foot', "Vayne's Treachery"];
for (const seat of [1, 2]) for (const [index, name] of names.entries()) for (const kicked of [false, true]) {
  const response = await fetch(`${api}/fixture?face_kind=kicker_golden_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const discard = name === 'Hypnotic Cloud';
  const owner = fixture.players[String(seat)];
  const payer = owner.battlefield.find(card => card.name === (seat === 1 ? 'Darksteel Relic' : 'Grizzly Bears'));
  const target = fixture.players[String(3-seat)].battlefield.find(card => card.name === 'Baloth Gorger');
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(`document.body.innerText.includes(${JSON.stringify(`Cast ${name}`)})`);
    await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes(${JSON.stringify(`Cast ${name}`)}));
      const cost = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === 'kicker'));
      cost.value = '${kicked ? 'kicker' : 'base'}'; cost.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    if (kicked && !discard) {
      const selector = `select[aria-label="Sacrifice for cost ${name}"]`;
      await waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)}))`);
      assert.equal(await evaluate(ready(`Cast ${name}`)), false);
      await evaluate(`(() => {
        const select = document.querySelector(${JSON.stringify(selector)});
        const values = [...select.options].filter(option => option.value).map(option => option.value);
        if (!values.includes(${JSON.stringify(payer.id)})) throw new Error('Missing eligible payer');
        [...select.options].forEach(option => option.selected = option.value === ${JSON.stringify(payer.id)});
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes(${JSON.stringify(`Cast ${name}`)}));
      const matches = option => ${discard ? `option.textContent.includes('Player ${seat === 1 ? 'B' : 'A'}')` : `option.value === ${JSON.stringify(target.id)}`};
      const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(matches));
      select.value = [...select.options].find(matches).value;
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
    if (discard) {
      await waitFor("document.body.innerText.includes('Choose cards to discard')");
      await command('Page.reload');
      await waitFor("document.body.innerText.includes('Choose cards to discard')");
      await evaluate(`(() => {
        const panel = [...document.querySelectorAll('.block-panel')].find(panel => panel.textContent.includes('Choose cards to discard'));
        [...panel.querySelectorAll('input[type="checkbox"]')].slice(0, ${kicked ? 3 : 1}).forEach(input => input.click());
      })()`);
      await waitFor(ready('Confirm Selection'));
      await click('Confirm Selection');
    }
    await waitFor(`(async () => { const state = await (await fetch('${api}/matches/${fixture.id}')).json(); return state.stack.length === 0 && !state.pending_mechanic_choice; })()`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    const actor = final.players[String(seat)];
    if (discard) assert.equal(final.players[String(3-seat)].hand_count, kicked ? 0 : 2);
    else {
      assert.equal(actor.battlefield.some(card => card.id === payer.id), !kicked);
      assert.equal(final.players[String(3-seat)].battlefield.some(card => card.id === target.id), !kicked);
      if (!kicked) assert.equal(final.players[String(3-seat)].battlefield.find(card => card.id === target.id).toughness, 2);
    }
    const sum = pool => Object.values(pool).reduce((a, b) => a + b, 0);
    assert.equal(sum(owner.mana_pool) - sum(actor.mana_pool), 2 + (discard && kicked ? 4 : 0));
    console.log(`PASS seat ${seat}: ${kicked ? 'kicked' : 'base'} ${name}, payment, reload, owned choices and effective result`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
