import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
const names = ['Wheel of Fortune', 'Windfall', 'Dark Deal', 'Incendiary Command', 'Chandra Ablaze', 'Windfall'];
for (const seat of [1, 2]) for (const [index, name] of names.entries()) {
  const response = await fetch(`${api}/fixture?face_kind=wheel_${index}_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.disabled)`;
  const read = async () => (await fetch(`${api}/matches/${fixture.id}`)).json();
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    const label = index === 4 ? `${name}: -2:` : `Cast ${name}`;
    if (index === 3) {
      await waitFor("Boolean(document.querySelector('select[aria-label=\"Spell modes\"]'))");
      await evaluate(`(() => {
        const select = document.querySelector('select[aria-label="Spell modes"]');
        for (const option of select.options) option.selected = option.value.startsWith('Each player') || option.value.includes('damage to target player');
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await waitFor("Boolean(document.querySelector('select[aria-label^=\"Target for\"]'))");
      await evaluate(`(() => {
        const select = document.querySelector('select[aria-label^="Target for"]');
        select.value = 'player:${3-seat}'; select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await waitFor(ready(label)); await click(label);
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 1)()`);
    await command('Page.reload');
    for (let pass = 0; pass < 2; pass++) {
      await waitFor(ready('Pass Priority')); await click('Pass Priority');
      if (!pass) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    if (index === 5) for (const pid of [seat, 3-seat]) {
      await waitFor(`(async () => { const state = await (await fetch('${api}/matches/${fixture.id}')).json(); return state.pending_mechanic_choice?.player_id === ${pid}; })()`);
      await command('Page.reload');
      await waitFor(ready('Stinkweed Imp'));
      assert.equal((await read()).pending_mechanic_choice.player_id, pid);
      await click('Stinkweed Imp');
    }
    await waitFor(`(async () => { const state = await (await fetch('${api}/matches/${fixture.id}')).json(); return !state.pending_mechanic_choice && state.stack.length === 0; })()`);
    const final = await read();
    const amounts = [[7, 7], [5, 5], [2, 4], [3, 5], [3, 3], [6, 6]][index];
    assert.equal(final.players[String(seat)].hand.length, amounts[0]);
    assert.equal(final.players[String(3-seat)].hand.length, amounts[1]);
    assert.equal(final.discards_this_turn[String(seat)], index === 5 ? 4 : 3);
    assert.equal(final.discards_this_turn[String(3-seat)], index === 5 ? 6 : 5);
    const maro = final.players[String(seat)].battlefield.find(card => card.name === 'Maro');
    assert.ok(maro);
    assert.equal(maro.power, amounts[0]); assert.equal(maro.toughness, amounts[0]);
    if (index === 4) assert.equal(final.players[String(seat)].battlefield.find(card => card.name === name).loyalty, 3);
    else assert.equal(final.players[String(seat)].graveyard.some(card => card.name === name), true);
    if (index === 3) assert.equal(final.players[String(3-seat)].life, 16);
    console.log(`PASS seat ${seat}: ${name}, exact simultaneous counts, effective Maro stats${index === 5 ? ', both owned draw choices and reload' : ''}`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')"); await close();
  }
}
