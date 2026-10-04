import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const [index, name] of ["Kaervek's Spite", 'Sickening Dreams'].entries()) {
  const response = await fetch(`${api}/fixture?face_kind=variable_cost_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(`document.body.innerText.includes(${JSON.stringify(`Cast ${name}`)})`);
    if (index === 0) {
      await waitFor("document.body.innerText.includes('sacrifice all permanents you control') && document.body.innerText.includes('discard your entire hand')");
      await evaluate(`(() => {
        const select = document.querySelector('select[aria-label="Player target"]');
        if (!select) throw new Error('Missing player target');
        select.value = '${3-seat}'; select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    } else {
      await evaluate(`(() => {
        const input = document.querySelector('input[placeholder="X value"]');
        if (!input || input.max !== '3') throw new Error('Missing bounded resource X');
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '2');
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await waitFor(`Boolean(document.querySelector('select[aria-label="Discard for cost ${name}"]'))`);
      assert.equal(await evaluate(ready(`Cast ${name}`)), false);
      const ids = fixture.players[String(seat)].hand.filter(card => card.name !== name).slice(0, 2).map(card => card.id);
      await evaluate(`(() => {
        const select = document.querySelector('select[aria-label="Discard for cost ${name}"]');
        [...select.options].forEach(option => option.selected = ${JSON.stringify(ids)}.includes(option.value));
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await waitFor(ready(`Cast ${name}`));
    await click(`Cast ${name}`);
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 1)()`);
    await command('Page.reload');
    await waitFor(ready('Pass Priority'));
    for (let pass = 0; pass < 2; pass++) {
      await waitFor(ready('Pass Priority')); await click('Pass Priority');
      if (!pass) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 0)()`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.equal(final.players[String(seat)].hand.length, index === 0 ? 0 : 1);
    assert.equal(final.players[String(seat)].life, index === 0 ? 20 : 18);
    assert.equal(final.players[String(3-seat)].life, index === 0 ? 15 : 18);
    assert.equal(final.players[String(seat)].battlefield.length, index === 0 ? 0 : 2);
    console.log(`PASS seat ${seat}: ${name}, deliberate payment, stack reload and actual resolution`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')"); await close();
  }
}
