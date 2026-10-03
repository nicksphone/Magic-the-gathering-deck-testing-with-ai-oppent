import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  for (const kind of ['legend_graveyard', 'legend_search']) {
    const response = await fetch(`${api}/fixture?face_kind=${kind}_${seat}`, { method: 'POST' });
    assert.equal(response.status, 200);
    const fixture = await response.json();
    const name = kind === 'legend_graveyard' ? 'Takenuma, Abandoned Mire' : 'Boseiju, Who Endures';
    const browser = await openBrowser('http://127.0.0.1:15173/');
    const { evaluate, command, waitFor, click, close } = browser;
    const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
    const get = async () => (await fetch(`${api}/matches/${fixture.id}`)).json();
    try {
      await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
      await command('Page.reload');
      await waitFor(ready(`Activate ${name}`));
      if (kind === 'legend_search') {
        const target = fixture.players[String(3-seat)].battlefield.find(card => card.name === 'Mind Stone');
        await evaluate(`(() => {
          const option = [...document.querySelectorAll('select option')].find(option => option.value === ${JSON.stringify(target.id)});
          option.parentElement.value = option.value; option.parentElement.dispatchEvent(new Event('change', { bubbles: true }));
        })()`);
      }
      await click(`Activate ${name}`);
      await waitFor(`!document.body.innerText.includes('Activate ${name}')`);
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      if (kind === 'legend_search') {
        await waitFor(ready('Search library'));
        assert.equal((await get()).pending_mechanic_choice.player_id, 3-seat);
        await command('Page.reload');
        await waitFor(ready('Search library'));
        await click('Search library');
        await waitFor("[...document.querySelectorAll('.block-panel label')].some(label => label.textContent.includes('Forest'))");
      } else {
        await waitFor("document.body.innerText.includes('Choose a graveyard card to return')");
        await command('Page.reload');
        await waitFor("document.body.innerText.includes('Choose a graveyard card to return')");
      }
      const selectedName = kind === 'legend_search' ? 'Forest' : 'Ugin, the Spirit Dragon';
      await evaluate(`(() => {
        const label = [...document.querySelectorAll('.block-panel label')].find(label => label.textContent.includes(${JSON.stringify(selectedName)}));
        if (!label) throw new Error('Missing owned resolution choice'); label.querySelector('input').click();
      })()`);
      await waitFor(ready('Confirm Selection'));
      await click('Confirm Selection');
      await waitFor("!document.body.innerText.includes('Confirm Selection')");
      const final = await get();
      assert.equal(final.pending_mechanic_choice, null);
      assert.equal(final.stack.length, 0);
      const returned = kind === 'legend_search'
        ? final.players[String(3-seat)].battlefield : final.players[String(seat)].hand;
      assert.ok(returned.some(card => card.name === selectedName));
      if (kind === 'legend_graveyard') assert.equal(final.log.filter(line => line.includes(' mills ')).length, 3);
      console.log(`PASS seat ${seat}: ${kind}, owned resolution choice and pending reload through App/API`);
    } finally {
      await evaluate("localStorage.removeItem('mtg.activeMatch')");
      await close();
    }
  }
}
