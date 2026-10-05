import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const name of ['Forest', 'Bala Ged Recovery', 'Gravecrawler']) {
  const response = await fetch(`${api}/fixture/graveyard-permission?seat=${seat}&name=${encodeURIComponent(name)}`, {method: 'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const id = fixture.match.id;
  const {evaluate, waitFor, reload, click, close} = await openBrowser('http://127.0.0.1:15173/');
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
    await reload();
    const label = name === 'Gravecrawler' ? 'Cast Gravecrawler' : `Play Land ${name === 'Forest' ? 'Forest' : 'Bala Ged Sanctuary'}`;
    await click(label);
    let state = await waitForApiState(`${api}/matches/${id}`, state => name === 'Gravecrawler'
      ? state.stack.some(item => item.label === name)
      : state.players[String(seat)].battlefield.some(card => card.id === fixture.card_id));
    assert.ok(!state.players[String(seat)].graveyard.some(card => card.id === fixture.card_id));
    if (name !== 'Gravecrawler') {
      assert.equal(state.players[String(seat)].land_plays_remaining, 0);
      const land = state.players[String(seat)].battlefield.find(card => card.id === fixture.card_id);
      if (name === 'Bala Ged Recovery') assert.equal(land.tapped, true);
    }
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    state = await (await fetch(`${api}/matches/${id}`)).json();
    assert.ok(!state.players[String(seat)].graveyard.some(card => card.id === fixture.card_id));
    assert.ok(name === 'Gravecrawler' ? state.stack.some(item => item.label === name)
      : state.players[String(seat)].battlefield.some(card => card.id === fixture.card_id));
    console.log(`PASS seat ${seat}: real ${name} graveyard play, correct source and reload`);
  } finally { await close(); }
}
