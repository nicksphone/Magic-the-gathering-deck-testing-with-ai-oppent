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
  await selectDeck(0, 1);
  await selectDeck(1, 2);
  await click("Run 20 Matches");
  await waitFor("window.fixturePreflights === 1 && document.querySelector('[role=alert]')?.textContent.includes('Willbender')");
  assert.equal(await evaluate("window.fixtureStarts"), 0);
  await click("Run Anyway");
  await waitFor("window.fixtureStarts === 1");
  console.log("PASS unsupported mechanics require review before starting a job");

  await command("Page.reload");
  await waitFor("document.querySelector('.analytics > .row select') && window.fixturePreflights === 0");
  await selectDeck(0, 3);
  await selectDeck(1, 2);
  await click("Run 20 Matches");
  await waitFor("window.fixturePreflights === 1 && window.fixtureStarts === 1");
  assert.ok((await evaluate("document.body.innerText")).includes("not certified"));
  console.log("PASS ordinary matchup starts after one preflight click");
} finally {
  await close();
}
