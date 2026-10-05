import assert from 'node:assert/strict';
import {openBrowser, waitForApiState} from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const name of ['Dig Through Time', 'Siege Wurm', 'Reverse Engineer']) {
  const response = await fetch(`${api}/fixture/cast-resources?seat=${seat}&name=${encodeURIComponent(name)}`, {method: 'POST'});
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const id = fixture.match.id;
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const {evaluate, waitFor, reload, click, close} = browser;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
    await reload();
    await waitFor(`document.querySelector(${JSON.stringify(`[aria-label="Automatic resources ${name}"]`)}) !== null`);
    await evaluate(`document.querySelector(${JSON.stringify(`[aria-label="Automatic resources ${name}"]`)}).click()`);
    for (const kind of ['delve', 'convoke', 'improvise']) for (const row of fixture.choices[kind]) {
      const cid = typeof row === 'string' ? row : row.card_id;
      await evaluate(`document.querySelector(${JSON.stringify(`input[data-resource-kind="${kind}"][data-resource-card="${cid}"]`)}).click()`);
      if (kind === 'convoke') await evaluate(`(() => {
        const select = document.querySelector(${JSON.stringify(`[data-convoke-card="${cid}"]`)});
        select.value = ${JSON.stringify(row.pay_as)}; select.dispatchEvent(new Event('change', {bubbles: true}));
      })()`);
    }
    await click(`Cast ${name}`);
    let state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 1);
    assert.equal(state.stack[0].label, name);
    const receipt = await (await fetch(`${api}/fixture/casting-payment/${id}`)).json();
    assert.equal(receipt.source_card_id, fixture.spell_id);
    assert.deepEqual(receipt.resources, fixture.choices);
    assert.equal(receipt.mana_spent, name === 'Siege Wurm' ? 0 : 2);
    for (const cid of fixture.choices.delve) assert.ok(state.players[String(seat)].exile.some(card => card.id === cid));
    for (const row of fixture.choices.convoke) assert.ok(state.players[String(seat)].battlefield.find(card => card.id === row.card_id).tapped);
    for (const cid of fixture.choices.improvise) assert.ok(state.players[String(seat)].battlefield.find(card => card.id === cid).tapped);
    await reload();
    await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    state = await (await fetch(`${api}/matches/${id}`)).json();
    assert.equal(state.stack[0].label, name);
    assert.deepEqual(await (await fetch(`${api}/fixture/casting-payment/${id}`)).json(), receipt);
    console.log(`PASS seat ${seat}: deliberate ${name} resource selection, real cast, mana-spent accounting and reload`);
  } finally {await close();}
}
