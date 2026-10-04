import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';
const { evaluate, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/tests/human-actions.html');
try {
  await waitFor("document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  for (const seat of [1, 2]) {
    await click(`Foretell Seat ${seat} Fixture`);
    await waitFor(`window.fixtureState?.priority_player === ${seat} && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'`);
    await click('Foretell Behold the Multiverse ({2})');
    await waitFor(`window.fixtureState.players['${seat}'].exile.some(c => c.name === 'Behold the Multiverse') && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'`);
    assert.equal(await evaluate('window.fixtureActions.at(-1).player_id'), seat);
    assert.equal(await evaluate('window.fixtureActions.at(-1).action.type'), 'foretell');
    assert.equal(await evaluate('window.fixtureState.stack.length'), 0);
    assert.equal(await evaluate('window.fixtureState.priority_player'), seat);
    assert.equal(await evaluate(`window.fixtureState.players['${seat}'].hand.some(c => c.name === 'Behold the Multiverse')`), false);
    console.log(`PASS human seat ${seat} Foretell control submits the special action and exposes authorized exile view`);
  }
} finally { await close(); }
