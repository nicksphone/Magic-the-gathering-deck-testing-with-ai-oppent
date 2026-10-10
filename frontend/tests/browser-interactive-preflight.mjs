import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { finished } from 'node:stream/promises';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import { openBrowser } from './browser-driver.mjs';

const evidence = process.env.MTG_UI_EVIDENCE;
assert.ok(evidence, 'Set MTG_UI_EVIDENCE to local test scratch');
await mkdir(evidence, { recursive: true });
const frontendPort = Number(process.env.MTG_PREFLIGHT_FRONTEND_PORT ?? 15187);
const browserPort = Number(process.env.MTG_PREFLIGHT_BROWSER_PORT ?? 19387);
process.env.MTG_FRONTEND_ORIGIN = `http://127.0.0.1:${frontendPort}`;
process.env.MTG_BROWSER_ORIGIN = `http://127.0.0.1:${browserPort}`;
const server = await createServer({
  configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [react()],
  server: { host: '127.0.0.1', port: frontendPort, strictPort: true, watch: null },
});
const profile = await mkdtemp(`${tmpdir()}/mtg-interactive-preflight-browser-`);
const chromeLog = createWriteStream(`${evidence}/chromium.log`);
const chromium = spawn(process.env.CHROMIUM_BINARY ?? '/snap/bin/chromium', [
  '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run', '--disable-background-networking', '--enable-automation',
  `--remote-debugging-port=${browserPort}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: ['ignore', 'pipe', 'pipe'] });
const chromiumClosed = new Promise(resolve => chromium.once('close', resolve));
chromium.stdout.pipe(chromeLog, { end: false }); chromium.stderr.pipe(chromeLog, { end: false });
console.log(`Test PID ${process.pid}; Chromium PID ${chromium.pid}; frontend ${process.env.MTG_FRONTEND_ORIGIN}; isolated profile ${profile}`);
let browser;
const results = [];
const failures = [];
try {
  await server.listen();
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { ready = (await fetch(`${process.env.MTG_BROWSER_ORIGIN}/json/version`)).ok; } catch { /* Browser startup. */ }
    if (ready) break;
    if (chromium.exitCode !== null) throw new Error('Isolated Chromium exited during startup');
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(ready, 'Isolated Chromium did not start');
  browser = await openBrowser('about:blank');
  const launched = await browser.command('Browser.getBrowserCommandLine');
  assert.ok(launched.arguments.includes(`--user-data-dir=${profile}`), 'Refuse storage operations on a browser profile not owned by this test');
  await browser.command('Page.navigate', { url: `${process.env.MTG_FRONTEND_ORIGIN}/tests/interactive-preflight.html` });
  const { evaluate, waitFor, click, command, reload } = browser;
  const acknowledge = () => evaluate("document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]').click()");
  async function select(label, value) {
    await evaluate(`(() => { const s=document.querySelector(${JSON.stringify(`select[aria-label="${label}"]`)}); if(!s || s.matches(':disabled')) throw Error('Missing/enabled selector'); s.value=${JSON.stringify(String(value))}; s.dispatchEvent(new Event('change',{bubbles:true})); })()`);
  }
  async function fresh(pending = null) {
    await waitFor('window.interactiveFixture !== undefined');
    assert.equal(await evaluate('window.interactiveFixture.blockedFetches'), 0, 'No live API access allowed');
    await evaluate(`localStorage.clear(); sessionStorage.clear(); ${pending ? `localStorage.setItem('mtg.pendingStart',${JSON.stringify(JSON.stringify(pending))});` : ''}`);
    await reload();
    await waitFor("window.interactiveFixture && document.querySelector('select[aria-label=\"Deck A\"]')?.options.length === 4 && !document.querySelector('fieldset')?.disabled");
  }
  async function pair(a = 1, b = 2) { await select('Deck A', a); await select('Deck B', b); }
  async function review(bestOf = 3) {
    await click(`Start Best-of-${bestOf} Match`);
    await waitFor("document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]') && !document.body.innerText.includes('Checking known rules gaps')");
  }
  async function capture(name, mobile = false) {
    await command('Emulation.setDeviceMetricsOverride', { width: mobile ? 390 : 1440, height: mobile ? 844 : 1000, deviceScaleFactor: 1, mobile });
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true, 'No horizontal overflow');
    await evaluate("document.querySelector('[aria-label=\"Interactive match support preflight\"]').scrollIntoView({block:'start'})");
    const shot = await command('Page.captureScreenshot', { format: 'png' });
    await writeFile(`${evidence}/${name}.png`, Buffer.from(shot.data, 'base64'));
  }
  const passed = label => { results.push(label); console.log(`PASS ${label}`); };

  await fresh(); await pair();
  assert.equal(await evaluate("document.querySelector('select[aria-label=\"AI difficulty\"]').value"), 'master');
  await evaluate("window.interactiveFixture.holdPreflight=true; (() => { const b=[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Start Best-of-3')); b.click(); b.click(); })()");
  await waitFor('window.interactiveFixture.preflights.length === 1');
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  assert.deepEqual(await evaluate('window.interactiveFixture.preflights[0].a'), [{ quantity: 60, card_name: 'Island' }, { quantity: 1, card_name: 'Willbender' }]);
  await select('Match length', 5);
  await evaluate('window.interactiveFixture.resolvePreflight(); window.interactiveFixture.holdPreflight=false');
  await waitFor("document.body.innerText.includes('stale preflight was discarded')");
  assert.equal(await evaluate("!!document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]')"), false);
  passed('double-click performs one preflight; changed config discards its delayed response; sideboard cards included');

  await review(5);
  const gapsText = await evaluate("document.querySelector('[aria-label=\"Interactive match support preflight\"]').innerText");
  for (const text of ['Deck A: Willbender', 'morph', 'Deck B: Xenagos, God of Revels', "as long as your devotion to red and green is less than seven, xenagos isn't a creature", 'condition: your devotion to red and green is less than seven', 'reasons: unsupported conditional static predicate', 'index: none']) assert.ok(gapsText.includes(text), text);
  assert.equal(await evaluate("document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]').checked"), false);
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Start Best-of-5')).matches(':disabled')"), true);
  await capture('known-gaps-desktop'); await capture('known-gaps-mobile', true);
  await acknowledge();
  for (const [label, value] of [['Deck B', 3], ['Match mode', 'human_vs_human'], ['AI difficulty', 'strong'], ['Deck A', 3]]) {
    await select(label, value);
    await waitFor("!document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]')");
    await review(5); await acknowledge();
  }
  await evaluate("window.interactiveFixture.decks[2].sideboard.push({quantity:1,card_name:'Willbender'}); document.querySelector('a[href=\"#lab-tools\"]').click()");
  await click('Refresh Decks');
  await waitFor("!document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]')");
  await review(5); await acknowledge();
  await evaluate('window.interactiveFixture.decks[2].mainboard[0].quantity=61');
  await click('Refresh Decks');
  await waitFor("!document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]')");
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  passed('exact mechanic/clause/condition/reason display and acknowledgement invalidation on both decks, mode, difficulty and same-ID mainboard/sideboard edits');

  await fresh(); await pair();
  await evaluate('window.interactiveFixture.preflightError=true');
  await click('Start Best-of-3 Match');
  await waitFor("document.querySelector('[role=alert]')?.textContent.includes('Fixture coverage offline')");
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  assert.equal(await evaluate("localStorage.getItem('mtg.pendingStart')"), null);
  await evaluate('window.interactiveFixture.preflightError=false; window.interactiveFixture.holdPreflight=true');
  await click('Start Best-of-3 Match'); await waitFor('window.interactiveFixture.preflights.length === 2');
  await select('Deck A', 3); await select('Deck A', 1);
  await evaluate('window.interactiveFixture.resolvePreflight(true); window.interactiveFixture.holdPreflight=false');
  await waitFor("document.body.innerText.includes('stale preflight error was discarded')");
  assert.equal(await evaluate('!!document.querySelector("[role=alert]")'), false);
  await review();
  passed('preflight failure blocks creation; stale failure after change-away-and-back does not authorize or poison the new setup');

  await fresh(); await pair(); await evaluate('window.interactiveFixture.emptyGaps=true'); await review();
  assert.ok(await evaluate("document.body.innerText.includes('No known unsupported gaps were reported') && document.body.innerText.includes('not certification')"));
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Start Best-of-3')).matches(':disabled')"), true);
  await acknowledge(); await acknowledge();
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Start Best-of-3')).matches(':disabled')"), true);
  await acknowledge(); await evaluate('window.interactiveFixture.holdStart=true');
  await evaluate("(() => { const b=[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Start Best-of-3')); b.click(); b.click(); })()");
  await waitFor('window.interactiveFixture.requests.length === 1');
  assert.equal(await evaluate('window.interactiveFixture.created'), 1);
  assert.equal(await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart')).review.exploratoryAcknowledged"), true);
  await evaluate('window.interactiveFixture.releaseStart(); window.interactiveFixture.holdStart=false');
  await waitFor("!!document.querySelector('.battlefield') && !localStorage.getItem('mtg.pendingStart') && !document.querySelector('fieldset').disabled");
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 1);
  await review();
  assert.equal(await evaluate('window.interactiveFixture.created'), 1, 'A second ordinary start must perform a fresh review, not create');
  passed('empty-gap result is not certification; checkbox is deliberate/revocable; double write creates one receipt; next ordinary start checks afresh');

  await fresh(); await pair(); await review(); await acknowledge();
  await evaluate("sessionStorage.setItem('interactiveFixture.losses','2')");
  await click('Start Best-of-3 Match');
  await waitFor("document.querySelector('[role=alert]')?.textContent.includes('outcome is uncertain') && !document.querySelector('fieldset').disabled");
  const original = await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart'))");
  const lostRequests = await evaluate('window.interactiveFixture.requests');
  assert.equal(lostRequests.length, 2); assert.equal(lostRequests[0].key, lostRequests[1].key);
  assert.deepEqual(lostRequests[0].payload, lostRequests[1].payload);
  assert.equal(await evaluate('window.interactiveFixture.created'), 1);
  await reload();
  await waitFor("document.querySelector('.battlefield') && !localStorage.getItem('mtg.pendingStart')");
  assert.equal(await evaluate('window.interactiveFixture.created'), 1);
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 3);
  assert.equal(await evaluate('window.interactiveFixture.preflights.length'), 0);
  assert.deepEqual(await evaluate('window.interactiveFixture.requests[2]'), { key: original.key, payload: original.payload });
  passed('two lost accepted responses retain original reviewed payload/key; StrictMode reload recovers the same receipt without a new start or changed intent');

  const legacy = { key: 'b'.repeat(32), payload: { ...original.payload, deck_a_id: 3, deck_a: [{ quantity: 60, card_name: 'Mountain' }], deck_a_sideboard: [], mode: 'human_vs_human', controller_b: 'human', best_of: 7 } };
  await fresh(legacy); await pair();
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  assert.ok(await evaluate("document.body.innerText.includes('Original pending start') && document.body.innerText.includes('best-of-7')"));
  await click('Recover pending match start');
  await waitFor("document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]')");
  assert.deepEqual(await evaluate('window.interactiveFixture.preflights[0].a'), legacy.payload.deck_a);
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  await acknowledge(); await click('Recover pending match start');
  await waitFor('window.interactiveFixture.requests.length === 1 && document.querySelector(".battlefield")');
  assert.deepEqual(await evaluate('window.interactiveFixture.requests[0]'), legacy);
  passed('legacy pending start never auto-creates; manual check/acknowledgement recovers original config with same key despite different current selectors');

  await fresh({ ...original, review: { ...original.review, signature: 'tampered' } });
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  assert.ok(await evaluate("document.body.innerText.includes('no acknowledged support review')"));
  await click('Recover pending match start');
  await waitFor("document.querySelector('[aria-label=\"Acknowledge exploratory interactive match\"]')");
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  passed('tampered persisted review fails closed without losing the uncertain key/payload');

  await fresh(); await pair(); await review(); await acknowledge();
  await evaluate('window.interactiveFixture.rejectStart=true'); await click('Start Best-of-3 Match');
  await waitFor("document.querySelector('[role=alert]')?.textContent.includes('Fixture rejected start')");
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 1);
  assert.equal(await evaluate('window.interactiveFixture.created'), 0);
  assert.equal(await evaluate("localStorage.getItem('mtg.pendingStart')"), null);
  passed('definite 4xx rejection clears pending intent and does not automatically retry');

  await fresh(); await pair(); await review(); await acknowledge();
  await evaluate(`localStorage.setItem('mtg.pendingStart',${JSON.stringify(JSON.stringify(legacy))})`);
  await click('Start Best-of-3 Match');
  await waitFor("document.body.innerText.includes('An existing pending start was found')");
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 0);
  assert.equal(await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart')).key"), legacy.key);
  assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Start Best-of-3')).matches(':disabled')"), true);
  passed('newly persisted foreign intent is held for explicit recovery, never silently rebound or overwritten by the current setup');

  await fresh(); await pair(); await review(); await acknowledge();
  await evaluate('window.interactiveFixture.holdStart=true');
  await click('Start Best-of-3 Match'); await waitFor('window.interactiveFixture.requests.length === 1');
  await evaluate(`localStorage.setItem('mtg.pendingStart',${JSON.stringify(JSON.stringify(legacy))}); window.interactiveFixture.releaseStart(); window.interactiveFixture.holdStart=false`);
  await waitFor('document.querySelector(".battlefield") && !document.querySelector("fieldset").disabled');
  assert.equal(await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart')).key"), legacy.key);
  assert.equal(await evaluate('window.interactiveFixture.created'), 1);
  passed('completed creation clears only its own pending key and preserves a foreign record written while its response was in flight');

  await fresh(); await pair(); await review(); await acknowledge();
  await evaluate("sessionStorage.setItem('interactiveFixture.losses','2')");
  await click('Start Best-of-3 Match');
  await waitFor("document.querySelector('[role=alert]')?.textContent.includes('outcome is uncertain') && !document.querySelector('fieldset').disabled");
  const uncertainKey = await evaluate('window.interactiveFixture.requests[0].key');
  await evaluate(`localStorage.setItem('mtg.pendingStart',${JSON.stringify(JSON.stringify(legacy))})`);
  await click('Recover pending match start');
  await waitFor("document.querySelector('[role=alert]')?.textContent.includes('Another window changed the stored pending start')");
  assert.equal(await evaluate('window.interactiveFixture.requests.length'), 2);
  assert.equal(await evaluate("JSON.parse(localStorage.getItem('mtg.pendingStart')).key"), legacy.key);
  await evaluate("localStorage.removeItem('mtg.pendingStart')");
  await click('Recover pending match start');
  await waitFor('window.interactiveFixture.requests.length === 3 && document.querySelector(".battlefield")');
  assert.equal(await evaluate('window.interactiveFixture.requests[2].key'), uncertainKey);
  assert.equal(await evaluate('window.interactiveFixture.created'), 1);
  passed('conflicting persisted intent blocks recovery without overwriting it or losing the original in-memory idempotency key');

  await fresh(); await pair(); await review(); await acknowledge();
  await evaluate("window.fixtureOriginalSetItem=Storage.prototype.setItem; Storage.prototype.setItem=function(key,value){if(key==='mtg.pendingStart')throw Error('Fixture storage disabled');return window.fixtureOriginalSetItem.call(this,key,value)}; sessionStorage.setItem('interactiveFixture.losses','2')");
  await click('Start Best-of-3 Match');
  await waitFor("document.querySelector('[role=alert]')?.textContent.includes('Keep this window open')");
  assert.equal(await evaluate('window.interactiveFixture.created'), 1);
  assert.equal(await evaluate("localStorage.getItem('mtg.pendingStart')"), null);
  await click('Recover pending match start');
  await waitFor('window.interactiveFixture.requests.length === 3 && document.querySelector(".battlefield")');
  assert.equal(await evaluate('window.interactiveFixture.created'), 1);
  assert.equal(await evaluate('window.interactiveFixture.requests.every(row=>row.key===window.interactiveFixture.requests[0].key)'), true);
  await evaluate('Storage.prototype.setItem=window.fixtureOriginalSetItem');
  passed('unavailable persistence is explicit; in-memory recovery retains same key and avoids duplicate creation');
  assert.equal(await evaluate('window.interactiveFixture.blockedFetches'), 0);
  await writeFile(`${evidence}/browser-results.json`, JSON.stringify({ results, liveBackendAccess: false, fixtureOnly: true }, null, 2));
} catch (error) {
  failures.push(error);
} finally {
  for (const cleanup of [
    async () => { if (browser) await browser.close(); },
    () => server.close(),
    async () => {
      chromium.kill('SIGTERM');
      await chromiumClosed;
      const logFinished = finished(chromeLog, { cleanup: true });
      chromeLog.end();
      await logFinished;
      await rm(profile, { recursive: true });
    },
  ]) {
    try { await cleanup(); } catch (error) { failures.push(error); }
  }
}
if (failures.length === 1) throw failures[0];
if (failures.length > 1) throw new AggregateError(failures, 'Interactive preflight and cleanup failures', { cause: failures[0] });
