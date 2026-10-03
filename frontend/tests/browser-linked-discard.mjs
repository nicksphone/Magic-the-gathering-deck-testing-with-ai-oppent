import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const [index, name] of ['Rites of Spring', 'Tolarian Winds', 'Dangerous Wager'].entries()) {
  const response = await fetch(`${api}/fixture?face_kind=linked_discard_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(ready(`Cast ${name}`)); await click(`Cast ${name}`);
    for (let pass = 0; pass < 2; pass++) {
      await waitFor(ready('Pass Priority')); await click('Pass Priority');
      if (!pass) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    const label = index === 0 ? 'Choose any number of cards to discard' : 'Choose cards to discard';
    await waitFor(`document.body.innerText.includes(${JSON.stringify(label)})`);
    await command('Page.reload');
    await waitFor(`document.body.innerText.includes(${JSON.stringify(label)})`);
    assert.equal(await evaluate(ready('Confirm Selection')), index === 0);
    await evaluate(`(() => {
      const panel = [...document.querySelectorAll('.block-panel')].find(panel => panel.textContent.includes(${JSON.stringify(label)}));
      const boxes = [...panel.querySelectorAll('input[type="checkbox"]')];
      if (boxes.length !== 3) throw new Error('Wrong owned discard choices');
      boxes.slice(0, ${index === 0 ? 2 : 3}).forEach(box => box.click());
    })()`);
    await waitFor(ready('Confirm Selection')); await click('Confirm Selection');
    if (index === 0) {
      await waitFor("document.body.innerText.includes('Search your library (you may fail to find a matching card)')");
      await command('Page.reload');
      await waitFor("document.body.innerText.includes('Search your library (you may fail to find a matching card)')");
      const state = await (await fetch(`${api}/matches/${fixture.id}`)).json();
      assert.equal(state.pending_mechanic_choice.count, 2);
      await evaluate(`(() => {
        const panel = [...document.querySelectorAll('.block-panel')].find(panel => panel.textContent.includes('Search your library'));
        const boxes = [...panel.querySelectorAll('input[type="checkbox"]')];
        if (boxes.length !== 4) throw new Error('Wrong basic-land search choices');
        boxes[0].click();
      })()`);
      await waitFor(ready('Confirm Selection')); await click('Confirm Selection');
    }
    await waitFor(`(async () => { const state = await (await fetch('${api}/matches/${fixture.id}')).json(); return !state.pending_mechanic_choice && state.stack.length === 0; })()`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.equal(final.players[String(seat)].hand.length, index === 1 ? 3 : 2);
    assert.equal(final.players[String(3-seat)].hand.length, fixture.players[String(3-seat)].hand.length);
    if (!index) assert.equal(final.log.filter(line => line.includes('shuffles their library')).length, 1);
    assert.equal(final.players[String(seat)].graveyard.some(card => card.name === name), true);
    console.log(`PASS seat ${seat}: ${name}, actual cast, owned discard/search, choice reload and linked result`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')"); await close();
  }
}

for (const seat of [1, 2]) {
  const response = await fetch(`${api}/fixture?face_kind=linked_copy_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    for (const actor of [3-seat, seat]) {
      for (let pass = 0; pass < 2; pass++) {
        await waitFor(ready('Pass Priority')); await click('Pass Priority');
        if (!pass) await waitFor(`document.body.innerText.includes('Priority: P${3-actor}')`);
      }
      await waitFor("document.body.innerText.includes('Choose cards to discard')");
      await command('Page.reload');
      await waitFor("document.body.innerText.includes('Choose cards to discard')");
      const state = await (await fetch(`${api}/matches/${fixture.id}`)).json();
      assert.equal(state.pending_mechanic_choice.player_id, actor);
      assert.equal(state.pending_mechanic_choice.count, actor === seat ? 3 : 2);
      await evaluate(`(() => {
        const panel = [...document.querySelectorAll('.block-panel')].find(panel => panel.textContent.includes('Choose cards to discard'));
        [...panel.querySelectorAll('input[type="checkbox"]')].forEach(box => box.click());
      })()`);
      await waitFor(ready('Confirm Selection')); await click('Confirm Selection');
      await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).pending_mechanic_choice === null)()`);
    }
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.equal(final.players[String(seat)].hand.length, 3);
    assert.equal(final.players[String(3-seat)].hand.length, 2);
    assert.equal(final.stack.length, 0);
    console.log(`PASS original seat ${seat}: opposing-controller copy discards/draws its own hand, pending reload and original resolution`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')"); await close();
  }
}
