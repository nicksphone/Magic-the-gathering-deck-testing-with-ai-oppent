import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';
const { evaluate, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/tests/human-actions.html');
const ready = "document.querySelector('[data-testid=ready]')?.textContent === 'Ready'";
try {
  await waitFor(ready);
  for (const seat of [1, 2]) {
    await click(`Foretell Created 0 Seat ${seat} Fixture`);
    await waitFor(`window.fixtureState.pending_mechanic_choice?.kind === 'foretell_from_hand' && ${ready}`);
    await evaluate(`(() => { const label = [...document.querySelectorAll('label')].find(l =>
      l.textContent.includes('Behold the Multiverse') && l.querySelector('input[type=checkbox]'));
      if (!label) throw new Error('Missing effect-created Foretell selection');
      label.querySelector('input').click(); })()`);
    await click('Confirm Selection');
    await waitFor(`!window.fixtureState.pending_mechanic_choice && ${ready}`);
    assert.equal(await evaluate('window.fixtureActions.at(-1).player_id'), seat);
    assert.equal(await evaluate(`window.fixtureState.players['${seat}'].exile.some(c => c.foretell_order != null)`), true);
    assert.equal(await evaluate('window.fixtureActions.at(-1).action.card_ids.length'), 1);

    await click(`Foretell Created 1 Seat ${seat} Fixture`);
    await waitFor(`window.fixtureState.stack.length === 1 && ${ready}`);
    for (let pass = 0; pass < 2; pass++) {
      const count = await evaluate('window.fixtureActions.length');
      await click('Pass Priority');
      await waitFor(`window.fixtureActions.length > ${count} && ${ready}`);
    }
    assert.equal(await evaluate(`window.fixtureState.players['${seat}'].battlefield.some(c => c.name === 'The Foretold Soldier')`), false);
    assert.equal(await evaluate(`window.fixtureState.players['${seat}'].exile.some(c => c.foretell_order != null)`), true);
  }
  console.log('PASS: both seats select effect-created Foretell cards and resolve damage-triggered self-exile.');
} finally {
  await close();
}
