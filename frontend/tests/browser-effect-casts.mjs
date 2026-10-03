import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const decline of [false, true]) {
    const response = await fetch(`${api}/fixture?face_kind=effect_cast_${seat}`, { method: 'POST' });
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
    const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
    const passTwice = async () => {
      for (let i = 0; i < 2; i++) {
        await waitFor(ready('Pass Priority'));
        await click('Pass Priority');
        if (i === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
      }
    };
    try {
      await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
      await command('Page.reload');
      await waitFor(ready('Cast Torrential Gearhulk'));
      await click('Cast Torrential Gearhulk');
      await passTwice();
      await waitFor(ready('Lightning Bolt'));
      await command('Page.reload');
      await waitFor(ready('Lightning Bolt'));
      await click('Lightning Bolt');
      await passTwice();
      await waitFor(ready('Decline casting'));
      await command('Page.reload');
      await waitFor(ready('Decline casting'));
      if (decline) {
        await click('Decline casting');
      } else {
        await evaluate(`(() => {
          const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast Lightning Bolt'));
          const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.textContent === 'Target Player'));
          const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
          setter.call(select, '${3-seat}'); select.dispatchEvent(new Event('change', { bubbles: true }));
        })()`);
        await waitFor(ready('Cast Lightning Bolt'));
        await click('Cast Lightning Bolt');
        await passTwice();
      }
      await waitFor(`(async () => !(await (await fetch('${api}/matches/${fixture.id}')).json()).pending_mechanic_choice)()`);
      const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
      assert.equal(final.stack.length, 0);
      assert.equal(final.players[String(3-seat)].life, decline ? 20 : 17);
      const zone = decline ? 'graveyard' : 'exile';
      assert.ok(final.players[String(seat)][zone].some(card => card.name === 'Lightning Bolt'));
      console.log(`PASS seat ${seat}: Gearhulk target, reload, ${decline ? 'decline' : 'deliberate cast/target'} through App/API`);
    } finally {
      await evaluate("localStorage.removeItem('mtg.activeMatch')");
      await close();
    }
  }
}
