import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  const response = await fetch(`${api}/fixture?face_kind=surveil_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, command, waitFor, click, close } = browser;
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  const get = async () => (await fetch(`${api}/matches/${fixture.id}`)).json();
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(ready('Cast Otherworldly Gaze'));
    await click('Cast Otherworldly Gaze');
    for (let i = 0; i < 2; i++) {
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      if (i === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    await waitFor("document.body.innerText.includes('Choose any cards for your graveyard')");
    await command('Page.reload');
    await waitFor("document.body.innerText.includes('Choose any cards for your graveyard')");
    await evaluate(`(() => {
      const label = [...document.querySelectorAll('.block-panel label')].find(label => label.textContent.includes('Island'));
      if (!label) throw new Error('Missing owned inspected card'); label.querySelector('input').click();
    })()`);
    await waitFor(ready('Confirm Selection'));
    await click('Confirm Selection');
    await waitFor("document.body.innerText.includes('Order the remaining cards')");
    await command('Page.reload');
    await waitFor("document.body.innerText.includes('Order the remaining cards')");
    await click('Mind Stone');
    await click('Grizzly Bears');
    await waitFor(ready('Confirm Order'));
    await click('Confirm Order');
    for (let i = 0; i < 2; i++) {
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      if (i === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    await waitFor("!document.body.innerText.includes('Confirm Order')");
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 0)()`);
    const final = await get();
    assert.equal(final.pending_mechanic_choice, null);
    assert.equal(final.stack.length, 0);
    assert.ok(final.players[String(seat)].graveyard.some(card => card.name === 'Island'));
    assert.ok(final.players[String(seat)].graveyard.some(card => card.name === 'Otherworldly Gaze'));
    assert.equal(final.players[String(seat)].battlefield.find(card => card.name === 'Dimir Spybug').counters['+1/+1'], 1);
    assert.equal(final.log.filter(line => line.includes(' surveils ')).length, 1);
    console.log(`PASS seat ${seat}: private surveil partition/top order, refresh and payoff through App/API`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
