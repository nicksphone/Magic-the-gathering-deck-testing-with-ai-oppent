import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';
import {visibleCardPoint} from './visible-card-point.mjs';

const frontend = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15179';
const browser = await openBrowser(frontend + '/tests/ui-clarity.html');
const {evaluate, waitFor, click, command, close, uiInput} = browser;
const selector = '.card[data-combat-role="attacker"]';
try {
  await waitFor('window.fixtureState');
  for (const height of [437, 493]) {
    await command('Emulation.setDeviceMetricsOverride', {width: 780, height, deviceScaleFactor: 1, mobile: false});
    await click('Reset Attack draft');
    await waitFor("window.fixtureScenario === 'attack' && window.fixtureActions.length === 0 && window.fixtureDraft.attackers.length === 0");
    // Expand only the DOM geometry; the third card retains the real React handler.
    await evaluate(`(() => {const node = document.querySelector(${JSON.stringify(selector)});
      for (let i = 0; i < 2; i++) {const clone = node.cloneNode(true);
        clone.removeAttribute('data-combat-role'); clone.removeAttribute('data-card-id');
        node.parentElement.insertBefore(clone, node);}})()`);
    const point = await evaluate('(' + visibleCardPoint.toString() + ')(' + JSON.stringify(selector) + ')');
    assert.equal(await evaluate(`(() => {const node = document.querySelector(${JSON.stringify(selector)});
      const hit = document.elementFromPoint(${point.x}, ${point.y});
      return !!hit && node.contains(hit) && !hit.closest('button,input,select,a,summary,.combat-toolbar,.turn-command-bar,.table-navigation');})()`), true);
    if (uiInput) await uiInput.clickAt(point);
    else {
      await command('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
      await command('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
    }
    await waitFor("window.fixtureDraft.attackers.length === 1");
    assert.deepEqual(await evaluate('window.fixtureDraft.attackers'), ['attacker']);
    assert.deepEqual(await evaluate('window.fixtureActions'), [], 'A pointer selection must not submit an empty attack');
    console.log('PASS synthetic three-card native pointer at 780x' + height + ': one draft toggle, no submission');
    // Fully cover the synthetic page to prove refusal, never a JS-click fallback.
    await evaluate("(() => {const cover = document.createElement('div'); cover.id = 'point-proof-cover'; cover.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#123'; document.body.append(cover);})()");
    await assert.rejects(() => evaluate('(' + visibleCardPoint.toString() + ')(' + JSON.stringify(selector) + ')'), /No unobscured/);
    await evaluate("document.getElementById('point-proof-cover').remove()");
    // Reload removes the geometry-only clones before the next viewport case.
    await browser.reload();
    await waitFor('window.fixtureState');
  }
} finally {
  await close();
}
