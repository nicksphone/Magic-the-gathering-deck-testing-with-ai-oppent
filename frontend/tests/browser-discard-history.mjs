import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const [index, name] of ['Daretti, Scrap Savant', 'Cathartic Pyre', 'Change of Fortune'].entries()) {
  const response = await fetch(`${api}/fixture?face_kind=discard_history_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    const label = index ? `Cast ${name}` : `${name}: +2:`;
    await waitFor(ready(label));
    if (index === 1) await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast ${name}'));
      const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value.startsWith('Discard up to')));
      select.value = [...select.options].find(option => option.value.startsWith('Discard up to')).value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(ready(label)); await click(label);
    for (let pass = 0; pass < 2; pass++) {
      await waitFor(ready('Pass Priority')); await click('Pass Priority');
    }
    await waitFor("document.body.innerText.includes('Choose cards to discard') || document.body.innerText.includes('Choose any number of cards to discard')");
    await command('Page.reload');
    await waitFor("document.body.innerText.includes('Choose cards to discard') || document.body.innerText.includes('Choose any number of cards to discard')");
    const pending = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.equal(pending.pending_mechanic_choice.player_id, seat);
    assert.equal(pending.pending_mechanic_choice.count, 2);
    await evaluate(`(() => {
      const panel = [...document.querySelectorAll('.block-panel')].find(panel => panel.textContent.includes('cards to discard'));
      [...panel.querySelectorAll('input[type="checkbox"]')].slice(0, 2).forEach(box => box.click());
    })()`);
    await waitFor(ready('Confirm Selection')); await click('Confirm Selection');
    await waitFor(`(async () => { const state = await (await fetch('${api}/matches/${fixture.id}')).json(); return !state.pending_mechanic_choice && state.stack.length === 0; })()`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.equal(final.players[String(seat)].hand.length, 3);
    assert.equal(final.players[String(3-seat)].hand.length, fixture.players[String(3-seat)].hand.length);
    assert.equal(final.discards_this_turn[String(seat)], index === 2 ? 3 : 2);
    if (!index) assert.equal(final.players[String(seat)].battlefield.find(card => card.name === name).loyalty, 5);
    else assert.equal(final.players[String(seat)].graveyard.some(card => card.name === name), true);
    console.log(`PASS seat ${seat}: ${name}, actual modal/loyalty/cast action, owned choice reload and exact history`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')"); await close();
  }
}
