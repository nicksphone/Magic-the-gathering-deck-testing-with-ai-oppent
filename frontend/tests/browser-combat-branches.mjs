import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) {
  const response = await fetch(`${backend}/fixture?face_kind=combat_branches_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const browser = await openBrowser('http://127.0.0.1:15173/');
  const { evaluate, command, waitFor, click, close } = browser;
  const getState = async () => (await fetch(`${backend}/matches/${fixture.id}`)).json();
  try {
    await waitFor("document.querySelector('.saved-games') !== null && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor("Boolean(document.querySelector('[aria-label=\"Attack with Gorm the Great\"]'))");
    await click('Attack all eligible');
    await waitFor("Boolean(document.querySelector('[aria-label=\"Attack payment 1 for Gorm the Great\"]'))");
    assert.equal(await evaluate("[...document.querySelectorAll('button')].find(node => node.textContent.trim() === 'Submit Attackers').disabled"), true);
    async function choose(branch) {
      await evaluate(`(() => {
        const select = document.querySelector('[aria-label="Attack payment 1 for Gorm the Great"]');
        Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(select, ${JSON.stringify(branch)});
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await choose('W');
    const before = await getState();
    await click('Submit Attackers');
    await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('attack costs'))");
    assert.equal((await getState()).revision, before.revision);
    await choose('P');
    await click('Submit Attackers');
    await waitFor("!document.querySelector('[aria-label=\"Attack payment 1 for Gorm the Great\"]')");
    const paid = await getState();
    assert.equal(paid.players[String(seat)].life, 18);
    assert.equal(paid.attackers.length, 1);
    for (let i = 0; i < 4 && (await getState()).step !== 'declare_blockers'; i++) {
      const previous = (await getState()).revision;
      await click('Pass Priority');
      for (let attempt = 0; attempt < 100 && (await getState()).revision === previous; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      await waitFor("[...document.querySelectorAll('button')].some(node => node.textContent.trim() === 'Pass Priority' && !node.disabled)");
    }
    await waitFor("[...document.querySelectorAll('h3')].some(node => node.textContent === 'Declare Blockers')");
    async function selectBlockers(count) {
      await evaluate(`(() => {
        const panel = [...document.querySelectorAll('.block-panel')].find(node => node.querySelector('h3')?.textContent === 'Declare Blockers');
        const select = panel.querySelector('select');
        [...select.options].forEach((option, index) => option.selected = index < ${count});
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    const blocking = await getState();
    await selectBlockers(1);
    await click('Submit Blocks');
    await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes('requirements'))");
    assert.equal((await getState()).revision, blocking.revision);
    await selectBlockers(2);
    await click('Submit Blocks');
    await waitFor("[...document.querySelectorAll('h3')].every(node => node.textContent !== 'Declare Blockers')");
    assert.equal((await getState()).blocks[paid.attackers[0]].length, 2);
    console.log(`PASS seat ${seat}: deliberate Phyrexian choice, atomic unaffordable retry and minimum blocker requirements via App/API`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
