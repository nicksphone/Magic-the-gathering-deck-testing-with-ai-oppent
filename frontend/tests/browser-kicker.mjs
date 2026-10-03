import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Burst Lightning', 'Into the Roil', 'Gift of Growth', 'Fight with Fire'];
for (const seat of [1, 2]) for (const free of [false, true]) for (const index of [1, 2, 3]) for (const kicked of [false, true]) {
  const response = await fetch(`${api}/fixture?face_kind=kicker_${index}_${seat}_${Number(free)}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const name = names[index];
  const target = fixture.players[String(name === 'Gift of Growth' ? seat : 3-seat)].battlefield[0];
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(`document.body.innerText.includes('Cast ${name}')`);
    await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast ${name}'));
      const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === 'kicker'));
      select.value = '${kicked ? 'kicker' : 'base'}'; select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    if (name === 'Fight with Fire' && kicked) {
      await waitFor("document.body.innerText.includes('Damage Distribution')");
      await evaluate(`(() => {
        const input = document.querySelector('input[aria-label="Damage to Player ${seat === 1 ? 'B' : 'A'} for ${name}"]');
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(input, '10'); input.dispatchEvent(new Event('input', { bubbles: true }));
      })()`);
    } else {
      if (name === 'Fight with Fire') assert.equal(await evaluate("document.body.innerText.includes('Damage Distribution')"), false);
      await evaluate(`(() => {
        const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast ${name}'));
        const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === ${JSON.stringify(target.id)}));
        select.value = ${JSON.stringify(target.id)}; select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await waitFor(ready(`Cast ${name}`));
    await click(`Cast ${name}`);
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 1)()`);
    await command('Page.reload');
    await waitFor(ready('Pass Priority'));
    for (let pass = 0; pass < 2; pass++) {
      await click('Pass Priority');
      if (pass === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 0)()`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    if (name === 'Into the Roil') {
      assert.ok(final.players[String(3-seat)].hand.some(card => card.id === target.id));
      assert.equal(final.players[String(seat)].hand.length, Number(kicked));
    } else if (name === 'Gift of Growth') {
      const creature = final.players[String(seat)].battlefield.find(card => card.id === target.id);
      assert.equal(creature.tapped, false);
      assert.equal(creature.power, kicked ? 6 : 4);
    } else {
      assert.equal(final.players[String(3-seat)].life, kicked ? 10 : 20);
    }
    console.log(`PASS seat ${seat}: ${free ? 'free' : 'normal'} ${kicked ? 'kicked' : 'base'} ${name}, branch targets/effects and pending reload`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
