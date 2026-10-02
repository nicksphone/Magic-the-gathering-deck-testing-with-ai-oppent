import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
const response = await fetch(`${backend}/fixture/combat-coverage-decks`, { method: 'POST' });
assert.equal(response.status, 200);
const decks = await response.json();
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, waitFor, click, close } = browser;
try {
  await waitFor(`Boolean(document.querySelector('.analytics > .row select option[value="${decks.a}"]'))`);
  for (const [index, id] of [[0, decks.a], [1, decks.b]]) {
    await evaluate(`(() => {
      const select = document.querySelectorAll('.analytics > .row select')[${index}];
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
      setter.call(select, ${JSON.stringify(String(id))});
      select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
  }
  await click('Run 20 Matches');
  await waitFor("[...document.querySelectorAll('[role=alert]')].some(node => node.textContent.includes(\"Collective Restraint\") && node.textContent.includes('unsupported combat payment'))");
  await waitFor("[...document.querySelectorAll('button')].some(node => node.textContent.includes('Run Anyway (Exploratory)'))");
  const count = await (await fetch(`${backend}/fixture/simulation-job-count`)).json();
  assert.equal(count.jobs, decks.jobs);
  console.log('PASS canonical combat-tax warning reaches real App/preflight without admitting a simulator job');
} finally { await close(); }
