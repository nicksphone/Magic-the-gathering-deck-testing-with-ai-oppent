import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const kind of ['channel', 'counter_payment']) {
    const response = await fetch(`${api}/fixture?face_kind=${kind}_${seat}`, { method: 'POST' });
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const { evaluate, command, waitFor, click, close } = browser;
    const name = kind === 'channel' ? 'Colossal Skyturtle' : 'Mirrorshell Crab';
    const source = fixture.players[String(seat)].hand.find(card => card.name === name);
    try {
      await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
      await command('Page.reload');
      await waitFor(`document.body.innerText.includes('Activate ${name}')`);
      const target = kind === 'channel'
        ? fixture.players[String(seat)].graveyard.find(card => card.name === 'Lightning Bolt').id
        : fixture.stack[0].id;
      await evaluate(`(() => {
        const option = [...document.querySelectorAll('select option')].find(option => option.value === ${JSON.stringify(target)});
        if (!option) throw new Error('Missing legal target');
        option.parentElement.value = option.value;
        option.parentElement.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await click(`Activate ${name}`);
      const get = async () => (await fetch(`${api}/matches/${fixture.id}`)).json();
      await waitFor(`!document.body.innerText.includes('Activate ${name}')`);
      await waitFor(`(async () => {
        const state = await (await fetch('${api}/matches/${fixture.id}')).json();
        return state.players['${seat}'].graveyard.some(card => card.id === ${JSON.stringify(source.id)})
          && state.stack.length === ${kind === 'channel' ? 1 : 2};
      })()`);
      let state = await get();
      assert.ok(state.players[String(seat)].graveyard.some(card => card.id === source.id));
      assert.equal(state.stack.length, kind === 'channel' ? 1 : 2);
      const readyToPass = "[...document.querySelectorAll('button')].some(button => button.textContent.trim() === 'Pass Priority' && !button.matches(':disabled'))";
      await waitFor(readyToPass);
      await click('Pass Priority');
      await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
      await waitFor(readyToPass);
      await click('Pass Priority');
      if (kind === 'counter_payment') {
        await waitFor("document.body.innerText.includes('Decline payment')");
        await command('Page.reload');
        await waitFor("document.body.innerText.includes('Decline payment')");
        state = await get();
        assert.equal(state.pending_mechanic_choice.player_id, 3-seat);
        await click('Decline payment');
        await waitFor("!document.body.innerText.includes('Decline payment')");
        await waitFor(`(async () => {
          const state = await (await fetch('${api}/matches/${fixture.id}')).json();
          return !state.pending_mechanic_choice && state.stack.length === 0;
        })()`);
        state = await get();
        assert.equal(state.players[String(3-seat)].mana_pool.C, 3);
      } else {
        await waitFor("document.querySelector('.hand-row')?.textContent.includes('Lightning Bolt')");
        state = await get();
        assert.ok(state.players[String(seat)].hand.some(card => card.id === target));
      }
      assert.equal(state.stack.length, 0);
      console.log(`PASS seat ${seat}: ${kind} through App, authoritative action and snapshot reload`);
    } finally {
      await evaluate("localStorage.removeItem('mtg.activeMatch')");
      await close();
    }
  }
}
