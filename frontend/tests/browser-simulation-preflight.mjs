import assert from "node:assert/strict";
import { openBrowser } from "./browser-driver.mjs";

const browser = await openBrowser("http://127.0.0.1:15173/tests/simulation-preflight.html");
const { evaluate, waitFor, click, command, close } = browser;

async function selectDeck(index, id) {
  await evaluate(`(() => {
    const select = document.querySelectorAll('.analytics > .row select')[${index}];
    select.value = ${JSON.stringify(String(id))};
    select.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
}

try {
  await waitFor("document.querySelector('.analytics > .row select') && window.fixturePreflights === 0");
  assert.equal(await evaluate("window.fixtureClientStartHeader"), "a".repeat(32));
  await selectDeck(0, 1);
  await selectDeck(1, 2);
  await click("Run 20 Matches");
  await waitFor("window.fixturePreflights === 1 && document.querySelector('[role=alert]')?.textContent.includes('Willbender')");
  assert.equal(await evaluate("window.fixtureStarts"), 0);
  await evaluate("document.querySelector('.analytics details summary').click()");
  await waitFor("document.querySelector('.analytics details').open");
  assert.ok((await evaluate("document.querySelector('.analytics details').innerText")).includes("your devotion to red and green"));
  assert.ok((await evaluate("document.querySelector('.analytics details').innerText")).includes("unsupported conditional static instruction"));
  await click("Run Anyway");
  await waitFor("window.fixtureStarts === 1");
  await waitFor("/^[0-9a-f]{32}$/.test(localStorage.getItem('mtg.activeSimulationJobId') ?? '')");
  console.log("PASS unsupported mechanics require review before starting a job");

  await command("Page.reload");
  await waitFor("document.querySelector('.analytics > .row select') && window.fixturePreflights === 0");
  await waitFor("window.fixturePolls > 0 && document.querySelector('.sim-status-pill')?.textContent === 'running'");
  assert.equal(await evaluate("window.fixtureStarts"), 0);
  await click("Cancel Run");
  await waitFor("window.fixtureCancels === 1 && document.querySelector('.sim-status-pill')?.textContent === 'canceled'");
  await waitFor("localStorage.getItem('mtg.activeSimulationJobId') === null");
  assert.ok((await evaluate("document.body.innerText")).includes("No partial results were published"));
  console.log("PASS refresh restores polling without starting a duplicate job, then Cancel Run works");

  await command("Page.reload");
  await waitFor("document.querySelector('.analytics > .row select') && window.fixturePreflights === 0");
  await selectDeck(0, 3);
  await selectDeck(1, 2);
  await click("Run 20 Matches");
  await waitFor("window.fixturePreflights === 1 && window.fixtureStarts === 1");
  assert.ok((await evaluate("document.body.innerText")).includes("not certified"));
  console.log("PASS ordinary matchup starts after one preflight click following cancellation");

  await click("Cancel Run");
  await waitFor("localStorage.getItem('mtg.activeSimulationJobId') === null");
  await evaluate("window.fixtureResponseLosses = 2");
  await click("Run 20 Matches");
  await waitFor("window.fixtureStarts === 2 && window.fixtureAttempts === 3 && localStorage.getItem('mtg.pendingSimulationStart') !== null");
  assert.ok((await evaluate("document.body.innerText")).includes("could not be recovered"));
  console.log("PASS accepted start with two lost responses retains one pending key");

  await command("Page.reload");
  await waitFor("window.fixtureAttempts === 1 && window.fixtureStarts === 0 && window.fixturePolls > 0");
  assert.equal(await evaluate("localStorage.getItem('mtg.pendingSimulationStart')"), null);
  assert.ok(await evaluate("/^[0-9a-f]{32}$/.test(localStorage.getItem('mtg.activeSimulationJobId') ?? '')"));
  console.log("PASS reload recovers the accepted simulator job without a duplicate start");

  await click("Cancel Run");
  await waitFor("localStorage.getItem('mtg.activeSimulationJobId') === null");
  await evaluate("window.fixtureWrongJobId = true");
  await selectDeck(0, 3);
  await selectDeck(1, 2);
  await evaluate("window.fixtureWrongJobId=false;window.fixtureCompleted=true");
  await click("Run 20 Matches");
  await waitFor("document.querySelector('.sim-status-pill')?.textContent === 'completed'");
  assert.ok(await evaluate("document.querySelector('.analytics-summary').textContent.includes('Win Rate: A 50%')"));
  assert.equal(await evaluate("localStorage.getItem('mtg.activeSimulationJobId')"),null);
  await evaluate("window.fixtureCompleted=false;window.fixtureFailed=true");
  await click("Run 20 Matches");
  await waitFor("document.body.innerText.includes('Deliberate UI test failure')");
  console.log('PASS styled simulator completion summary and explicit failure feedback (injected component fixtures, not actual simulation results)');
  await evaluate("window.fixtureFailed=false;window.fixtureWrongJobId=true");
  await selectDeck(0, 3);
  await selectDeck(1, 2);
  await click("Run 20 Matches");
  await waitFor("document.body.innerText.includes('different job ID')");
  assert.equal(await evaluate("localStorage.getItem('mtg.activeSimulationJobId')"), null);
  assert.ok(await evaluate("localStorage.getItem('mtg.pendingSimulationStart') !== null"));
  console.log("PASS mismatched start response cannot attach to another simulator job");
} finally {
  // The intentionally mismatched final fixture must not launch a real job in later tests.
  await evaluate("localStorage.removeItem('mtg.pendingSimulationStart'); localStorage.removeItem('mtg.activeSimulationJobId')");
  await close();
}
