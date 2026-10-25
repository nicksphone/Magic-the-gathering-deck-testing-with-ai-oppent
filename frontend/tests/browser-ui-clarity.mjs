import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

const frontend = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15174';
const browser = await openBrowser(frontend + '/tests/ui-clarity.html');
const {evaluate, waitFor, click, command, close} = browser;
const labels = {creature: 'Creature target', permanent: 'Permanent target', etb: 'Untargeted ETB',
  attack: 'Attack draft', block: 'Block draft'};
async function reset(scenario, seat) {
  await click('Fixture seat ' + seat);
  await click('Reset ' + labels[scenario]);
  await waitFor(`window.fixtureScenario === ${JSON.stringify(scenario)} && window.fixtureSeat === ${seat} && window.fixtureActions?.length === 0`);
}
async function selectTarget(id) {
  await evaluate(`(() => {const select = document.getElementById('cast-target-spell');
    if (!select || ![...select.options].some(option => option.value === ${JSON.stringify(id)})) throw Error('Target not offered');
    select.value = ${JSON.stringify(id)}; select.dispatchEvent(new Event('change', {bubbles: true}));})()`);
  await waitFor("!document.querySelector('.cast-readiness-guidance')");
}
async function noPrematureCommit(seat) {
  assert.equal(await evaluate('window.fixtureActions.length'), 0);
  assert.equal(await evaluate('window.fixtureState.priority_player'), seat);
  assert.equal(await evaluate('window.fixtureState.revision'), 7);
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(button => button.textContent.trim() === 'Pass Priority').disabled"), false);
}
try {
  await waitFor("window.fixtureState && document.querySelector('[data-testid=fixture-ready]')");
  for (const seat of [1, 2]) {
    for (const scenario of ['creature', 'permanent']) {
      await reset(scenario, seat);
      assert.equal(await evaluate("[...document.querySelectorAll('button')].find(button => button.textContent.trim().startsWith('Cast Protocol removal')).disabled"), false);
      await click('Cast Protocol removal');
      await waitFor("document.activeElement?.id === 'cast-target-spell'");
      await noPrematureCommit(seat);
      assert.match(await evaluate("document.querySelector('.cast-readiness-guidance').textContent"), /Choose .*target before casting\./);
      assert.equal(await evaluate("document.activeElement.getAttribute('aria-describedby')"), 'cast-target-help-spell');
      const target = scenario === 'permanent' ? 'target-artifact' : 'target-creature';
      assert.deepEqual(await evaluate("[...document.getElementById('cast-target-spell').options].map(option => option.value)"),
        scenario === 'permanent' ? ['', 'target-creature', 'target-artifact'] : ['', 'target-creature']);
      await selectTarget(target);
      await click('Cast Protocol removal');
      await waitFor('window.fixtureActions.length === 1');
      assert.deepEqual(await evaluate('window.fixtureActions[0].action.targets'), {target_card_id: target});
      assert.equal(await evaluate('window.fixtureActions[0].player_id'), seat);
      await click('Replace offered targets');
      await waitFor("document.querySelector('.cast-readiness-guidance')");
      await click('Cast Protocol removal');
      await waitFor("document.activeElement?.id === 'cast-target-spell'");
      assert.equal(await evaluate('window.fixtureActions.length'), 1, 'Stale target never dispatches');
      await click('Clear offered targets');
      await waitFor("!document.getElementById('cast-target-spell')");
      await click('Cast Protocol removal');
      await waitFor("document.activeElement?.id === 'cast-target-help-spell'");
      assert.equal(await evaluate('window.fixtureActions.length'), 1, 'Empty offers never dispatch');
    }
    await reset('etb', seat);
    await click('Cast Protocol ETB creature');
    await waitFor('window.fixtureActions.length === 1');
    assert.deepEqual(await evaluate('window.fixtureActions[0].action.targets'), {});
    await reset('attack', seat);
    await click('Click to attack');
    await waitFor("window.fixtureDraft.attackers.includes('attacker') && document.querySelector('.combat-draft-status')?.textContent.includes('selected, not submitted')");
    await noPrematureCommit(seat);
    assert.deepEqual(await evaluate('window.fixtureState.attackers'), []);
    await click('Submit Attackers');
    await waitFor("window.fixtureActions[0]?.type === 'attack'");
    assert.deepEqual(await evaluate('window.fixtureActions[0].attackers'), ['attacker']);
    await reset('block', seat);
    await click('Click to block');
    await waitFor("window.fixtureDraft.selectedBlocker === 'blocker' && document.querySelector('.combat-draft-status')?.textContent.includes('click an attacker')");
    await noPrematureCommit(seat);
    await evaluate("document.querySelector('[data-card-id=incoming]').click()");
    await waitFor("window.fixtureDraft.blocks.incoming?.includes('blocker') && document.querySelector('.combat-draft-status')?.textContent.includes('drafted, not submitted')");
    await noPrematureCommit(seat);
    await click('Submit Blocks');
    await waitFor("window.fixtureActions[0]?.type === 'block'");
    assert.deepEqual(await evaluate('window.fixtureActions[0].blocks'), {incoming: ['blocker']});
  }
  await command('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: true});
  await reset('permanent', 1);
  await click('Cast Protocol removal');
  await waitFor("document.activeElement?.id === 'cast-target-spell'");
  assert.equal(await evaluate('innerWidth'), 390);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true, 'No page-wide mobile overflow');
  assert.equal(await evaluate("(() => {const box = document.querySelector('.cast-readiness-guidance').getBoundingClientRect(); return box.width > 0 && box.left >= 0 && box.right <= innerWidth + 1;})()"), true, 'Mobile guidance fits the viewport');
  assert.deepEqual(await evaluate("performance.getEntriesByType('resource').filter(entry => new URL(entry.name).pathname.startsWith('/api/')).map(entry => entry.name)"), []);
  console.log('PASS synthetic UI clarity: both seats, creature/permanent restrictions and dedup, target focus/dispatch/stale/empty/ETB, draft-before-submit attack/block, unchanged priority, mobile390; no engine/API/sandbox qualification');
} finally {
  await close();
}
