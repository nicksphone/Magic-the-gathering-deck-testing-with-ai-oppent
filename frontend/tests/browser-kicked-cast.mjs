import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Risen Riptide', 'Roost of Drakes', 'Vine Gecko', 'Roost of Drakes'];
for (const seat of [1, 2]) for (const index of [0, 1, 2, 3]) for (const kicked of [false, true]) {
  const response = await fetch(`${api}/fixture?face_kind=kicked_cast_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const name = index === 3 ? 'Roost of Drakes' : 'Burst Lightning';
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
    if (index !== 3) await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast ${name}'));
      const target = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.textContent.includes('Player ${seat === 1 ? 'B' : 'A'}')));
      target.value = [...target.options].find(option => option.textContent.includes('Player ${seat === 1 ? 'B' : 'A'}')).value;
      target.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(ready(`Cast ${name}`));
    await click(`Cast ${name}`);
    const announced = kicked && index < 3 ? 2 : 1;
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === ${announced})()`);
    await command('Page.reload');
    const resolutions = kicked ? 2 : 1;
    for (let resolution = 0; resolution < resolutions; resolution++) {
      for (let pass = 0; pass < 2; pass++) {
        await waitFor(ready('Pass Priority'));
        await click('Pass Priority');
        if (pass === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
      }
      const remaining = resolution === resolutions - 1 ? 0 : 1;
      await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === ${remaining})()`);
    }
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    const cards = final.players[String(seat)].battlefield;
    const payoff = cards.find(card => card.name === names[index]);
    if (index === 0) assert.equal(payoff.power, kicked ? 5 : 0);
    if (index === 2) assert.equal(payoff.counters['+1/+1'] ?? 0, kicked ? 1 : 0);
    if (index === 1 || index === 3) assert.equal(cards.filter(card => card.name === 'Drake').length, Number(kicked));
    const sum = pool => Object.values(pool).reduce((a, b) => a + b, 0);
    assert.equal(sum(fixture.players[String(seat)].mana_pool) - sum(final.players[String(seat)].mana_pool),
      index === 3 ? (kicked ? 4 : 1) : (kicked ? (index === 2 ? 4 : 5) : 1));
    console.log(`PASS seat ${seat}: ${kicked ? 'kicked' : 'base'} ${names[index]} ${index === 3 ? 'entry' : 'cast payoff'}, restored stack and exact mana`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
