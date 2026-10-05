import assert from 'node:assert/strict';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const name of ['Impulse', 'Anticipate', 'Memory Deluge', 'Dig Through Time']) {
    const response = await fetch(`${api}/fixture/opaque-selection?seat=${seat}&name=${encodeURIComponent(name)}`, { method: 'POST' });
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const id = fixture.match.id;
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const { evaluate, reload, waitFor, click, close } = browser;
    const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.disabled)`;
    try {
      await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(id)})`);
      await reload();
      await waitFor(ready(`Cast ${name}`));
      await click(`Cast ${name}`);
      let state = await waitForApiState(`${api}/matches/${id}`, state => state.stack.length === 1);
      for (let passes = 0; passes < 8 && !state.pending_mechanic_choice; passes++) {
        await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
        await waitFor(ready('Pass Priority'));
        const revision = state.revision;
        await click('Pass Priority');
        state = await waitForApiState(`${api}/matches/${id}`, state => state.revision > revision);
      }
      assert.equal(state.pending_mechanic_choice.kind, 'look_top_select_hand');
      const chosen = state.pending_mechanic_choice.options.slice(0, state.pending_mechanic_choice.count);
      await reload();
      await waitFor("document.body.innerText.includes('Select exactly') && document.querySelector('.block-panel label input') !== null");
      for (const cardId of chosen) {
        await evaluate(`(() => {
          const label = [...document.querySelectorAll('.block-panel label')].find(label => label.textContent.trim().startsWith(${JSON.stringify(fixture.labels[cardId])}) && !label.querySelector('input')?.checked);
          if (!label) throw new Error('Missing owned selection card'); label.querySelector('input').click();
        })()`);
      }
      await click('Confirm Selection');
      state = await waitForApiState(`${api}/matches/${id}`, state => state.pending_mechanic_choice?.kind !== 'look_top_select_hand');
      let expectedBottom;
      if (name !== 'Memory Deluge') {
        assert.equal(state.pending_mechanic_choice.kind, 'topdeck_bottom_order');
        const bottom = [...state.pending_mechanic_choice.options].reverse();
        expectedBottom = bottom;
        await reload();
        await waitFor("document.body.innerText.includes('Pick the bottom cards in order')");
        for (const cardId of bottom) {
          const index = state.pending_mechanic_choice.options.indexOf(cardId);
          await evaluate(`(() => {
            const button = document.querySelectorAll('.block-panel button')[${index}];
            if (!button || button.disabled || button.textContent.trim() !== ${JSON.stringify(fixture.labels[cardId])}) throw new Error('Missing ordered card option');
            button.click();
          })()`);
        }
        await click('Confirm Order');
      }
      state = await waitForApiState(`${api}/matches/${id}`, state => !state.pending_mechanic_choice && state.stack.length === 0);
      assert.ok(chosen.every(cid => state.players[String(seat)].hand.some(card => card.id === cid)));
      assert.ok(state.players[String(seat)].graveyard.some(card => card.id === fixture.spell_id));
      if (expectedBottom) {
        const response = await fetch(`${api}/fixture/opaque-selection-library/${id}?seat=${seat}`);
        assert.equal(response.status, 200);
        const { library } = await response.json();
        assert.deepEqual(library.slice(0, expectedBottom.length), expectedBottom);
      }
      assert.equal(state.log.filter(line => line.includes('draws a card')).length, 0);
      await reload();
      await waitFor(`document.body.innerText.includes('Priority: P${state.priority_player}')`);
      console.log(`PASS seat ${seat}: ${name} paid UI cast, inspected selection, ${name === 'Memory Deluge' ? 'random bottom' : 'deliberate bottom order'}, resolution and reload`);
    } finally { await close(); }
  }
}
