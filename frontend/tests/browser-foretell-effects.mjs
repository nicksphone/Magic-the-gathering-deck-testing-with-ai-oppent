import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';
const { evaluate, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/tests/human-actions.html');
const ready = "document.querySelector('[data-testid=ready]')?.textContent === 'Ready'";
async function resolveSpell() {
  for (let pass = 0; pass < 2; pass++) {
    const count = await evaluate('window.fixtureActions.length');
    await click('Pass Priority');
    await waitFor(`window.fixtureActions.length > ${count} && ${ready}`);
  }
}
try {
  await waitFor(ready);
  for (const seat of [1, 2]) {
    for (const [index, x] of [[0, null], [1, 0], [1, 3]]) {
      await click(`Foretell Effect ${index} Seat ${seat} Fixture`);
      await waitFor(`window.fixtureState.priority_player === ${seat} && ${ready}`);
      assert.equal(await evaluate("Boolean(document.querySelector('input[placeholder=\"X value\"]'))"), index === 1);
      if (index === 1) {
        await evaluate(`(() => { const input = document.querySelector('input[placeholder="X value"]');
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '${x}');
          input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
        await waitFor(`document.querySelector('input[placeholder="X value"]').value === '${x}'`);
      }
      await click(`Cast Starnheim Unleashed (${index === 1 ? '{X}{X}{W}' : '{2}{W}{W}'})`);
      await waitFor(`window.fixtureState.stack.length === 1 && ${ready}`);
      assert.equal(await evaluate('window.fixtureActions.at(-1).player_id'), seat);
      if (index === 1) assert.equal(await evaluate('window.fixtureActions.at(-1).action.targets.x_value'), x);
      await resolveSpell();
      assert.equal(await evaluate(`window.fixtureState.players['${seat}'].battlefield.filter(c => c.name === 'Angel Warrior').length`), index === 1 ? x : 1);
      assert.equal(await evaluate(`window.fixtureState.players['${seat}'].battlefield.filter(c => c.name === 'Angel Warrior').every(c =>
        c.power === 4 && c.toughness === 4 && c.keywords.includes('flying') && c.keywords.includes('vigilance'))`), true);
    }
    await click(`Foretell Effect 2 Seat ${seat} Fixture`);
    await waitFor(`window.fixtureState.priority_player === ${seat} && ${ready}`);
    await evaluate(`(() => { const select = [...document.querySelectorAll('select')].find(s => [...s.options].some(o => o.textContent === 'Grizzly Bears'));
      if (!select) throw new Error('Missing removal target');
      select.value = [...select.options].find(o => o.textContent === 'Grizzly Bears').value;
      select.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await click('Cast Poison the Cup ({1}{B})');
    await waitFor(`window.fixtureState.stack.length === 1 && ${ready}`);
    await resolveSpell();
    assert.equal(await evaluate('window.fixtureState.pending_mechanic_choice.kind'), 'scry');
    assert.equal(await evaluate('window.fixtureState.pending_mechanic_choice.player_id'), seat);
    assert.equal(await evaluate(`window.fixtureState.players['${3-seat}'].graveyard.some(c => c.name === 'Grizzly Bears')`), true);
    await click('Confirm Selection');
    await waitFor(`window.fixtureState.pending_mechanic_choice?.kind !== 'scry' && ${ready}`);
    console.log(`PASS seat ${seat}: printed cost, foretold X cost, token stats and conditional removal/scry through UI/API`);
  }
} finally { await close(); }
