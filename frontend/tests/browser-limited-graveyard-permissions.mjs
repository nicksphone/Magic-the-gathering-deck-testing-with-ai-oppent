import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const source of ['Lurrus of the Dream-Den', 'Gisa and Geralf', 'Muldrotha, the Gravetide']) {
  const response = await fetch(`${api}/fixture/limited-graveyard-permission?seat=${seat}&source=${encodeURIComponent(source)}`, {method: 'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json(), id = fixture.match.id;
  const {evaluate, waitFor, reload, click, close} = await openBrowser('http://127.0.0.1:15173/');
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
    await reload();
    const label = JSON.stringify('Graveyard cast - ' + source);
    const casts = source === 'Muldrotha, the Gravetide' ? 2 : 1;
    for (let casting = 0; casting < casts; casting++) {
    await waitFor(`[...document.querySelectorAll('select option')].some(option => option.textContent.includes(${label}))`);
    await evaluate(`(() => {
      const option = [...document.querySelectorAll('select option')].find(option => option.textContent.includes(${label}));
      const select = option.parentElement; select.value = option.value; select.dispatchEvent(new Event('change', {bubbles:true}));
    })()`);
    await click(`Cast ${fixture.name}`);
    await waitForApiState(`${api}/matches/${id}`, state => state.stack.some(item => item.label === fixture.name));
    await reload();
    for (let index = 0; index < 2; index++) {
      const before = await (await fetch(`${api}/matches/${id}`)).json();
      await click('Pass Priority');
      await waitForApiState(`${api}/matches/${id}`, state => state.priority_player !== before.priority_player || state.stack.length === 0);
    }
    await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 0);
    await reload();
    }
    const state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 0);
    for (const id of fixture.card_ids.slice(0, casts)) assert.ok(state.players[String(seat)].battlefield.some(card => card.id === id));
    assert.ok(state.players[String(seat)].graveyard.some(card => card.id === fixture.card_ids[casts]));
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    const legal = await (await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`)).json();
    assert.ok(!legal.moves.some(move => move.type === 'cast_spell' && move.card_id === fixture.card_ids[casts]));
    console.log(`PASS seat ${seat}: choose ${source} permission, actual cast/resolve, reload and exhausted allowance`);
  } finally { await close(); }
}
