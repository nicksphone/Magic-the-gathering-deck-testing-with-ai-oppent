import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Baloth Gorger', 'Citanul Woodreaders', 'Torch Slinger', 'Mold Shambler'];
for (const seat of [1, 2]) for (const index of [0, 1, 2, 3]) for (const kicked of [false, true]) {
  const response = await fetch(`${api}/fixture?face_kind=permanent_kicker_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const name = names[index];
  const target = fixture.players[String(3-seat)].battlefield[0];
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  const read = async () => (await fetch(`${api}/matches/${fixture.id}`)).json();
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
    await waitFor(ready(`Cast ${name}`));
    await click(`Cast ${name}`);
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 1)()`);
    await command('Page.reload');
    for (let pass = 0; pass < 2; pass++) {
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      if (pass === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).players['${seat}'].battlefield.some(card => card.name === '${name}'))()`);
    if (kicked && index >= 2) {
      await waitFor("document.body.innerText.includes('Choose Trigger Target')");
      await command('Page.reload');
      await waitFor("document.body.innerText.includes('Choose Trigger Target')");
      await click(target.name);
    }
    if (kicked && index > 0) {
      for (let pass = 0; pass < 2; pass++) {
        await waitFor(ready('Pass Priority'));
        await click('Pass Priority');
        if (pass === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
      }
    }
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 0)()`);
    const final = await read();
    const creature = final.players[String(seat)].battlefield.find(card => card.name === name);
    if (index === 0) assert.equal(creature.power, kicked ? 7 : 4);
    if (index === 1) assert.equal(final.players[String(seat)].hand.length, kicked ? 2 : 0);
    if (index >= 2) assert.equal(final.players[String(3-seat)].battlefield.some(card => card.id === target.id), !kicked);
    console.log(`PASS seat ${seat}: ${kicked ? 'kicked' : 'base'} ${name}, entry and restored ETB choice`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
