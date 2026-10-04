import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  const response = await fetch(`${backend}/fixture?face_kind=bestow_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const host = fixture.players[String(seat)].battlefield.find(card => card.name === 'Grizzly Bears');
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, reload, waitFor, click, close } = browser;
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await reload();
    await waitFor("Boolean(document.querySelector('.hand-row option[value=bestow]'))");
    await evaluate(`(() => {
      const select = document.querySelector('.hand-row option[value=bestow]').parentElement;
      select.value = 'bestow'; select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(`Boolean(document.querySelector('.hand-row option[value="${host.id}"]'))`);
    assert.ok(await evaluate("[...document.querySelectorAll('.hand-row button')].some(button => button.textContent.includes('Cast Leafcrown Dryad ({3}{G})'))"));
    await evaluate(`(() => {
      const select = document.querySelector('.hand-row option[value="${host.id}"]').parentElement;
      select.value = ${JSON.stringify(host.id)}; select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await click('Cast Leafcrown Dryad');
    await waitFor("document.body.textContent.includes('Leafcrown Dryad') && !document.querySelector('.hand-row option[value=bestow]')");
    let state = await waitForApiState(`${backend}/matches/${fixture.id}`,
      state => state.stack.some(item => item.label.includes('Leafcrown Dryad')));
    assert.equal(state.players[String(seat)].mana_pool.G, 0);
    assert.ok(state.stack.length);
    for (let step = 0; step < 8 && state.stack.length; step += 1) {
      const priorRevision = state.revision;
      await click('Pass Priority');
      state = await waitForApiState(`${backend}/matches/${fixture.id}`, state => state.revision > priorRevision);
      await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
    }
    assert.equal(state.stack.length, 0);
    const aura = state.players[String(seat)].battlefield.find(card => card.name === 'Leafcrown Dryad');
    assert.ok(aura.bestowed);
    assert.equal(aura.attached_to, host.id);
    assert.equal(state.players[String(seat)].battlefield.find(card => card.id === host.id).power, 4);
    await reload();
    await waitFor("document.body.textContent.includes('Leafcrown Dryad')");
    console.log(`PASS seat ${seat}: choose Bestow, announce target, pay four, resolve Aura and reload through App/API`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
