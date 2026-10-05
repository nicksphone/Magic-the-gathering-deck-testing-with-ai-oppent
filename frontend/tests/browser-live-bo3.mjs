import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const backend = 'http://127.0.0.1:10199';
async function deck(name) {
  const response = await fetch(`${backend}/decks/builtin/${encodeURIComponent(name)}`);
  if (!response.ok) throw new Error(`Could not load ${name}: ${response.status}`);
  const { deck_text } = await response.json();
  return deck_text.trim().split('\n').map(line => {
  const [, quantity, card_name] = line.trim().match(/^(\d+) (.+)$/) ?? [];
  if (!quantity) throw new Error(`Invalid built-in deck line: ${line}`);
  return { quantity: Number(quantity), card_name };
  });
}
const started = await fetch(`${backend}/matches/start`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    deck_a: await deck('Mono Red Aggro'), deck_b: await deck('Burn'),
    controller_a: 'ai', controller_b: 'ai', mode: 'ai_vs_ai', best_of: 3, seed: 73,
  }),
});
if (!started.ok) throw new Error(`Could not start BO3: ${started.status} ${await started.text()}`);
let state = await started.json();
const browser = await openBrowser('http://127.0.0.1:15173/');
const { evaluate, waitFor, click, command, close } = browser;

try {
  await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(state.id)})`);
  await command('Page.reload');
  await waitFor("document.querySelector('.battlefield') && [...document.querySelectorAll('button')].some(b => b.textContent === 'Resume automatic play')");
  const observed = new Set([1]);
  // Budget priority actions across up to three games, not fifty game turns.
  // The retained seed-73 game three finished seven actions beyond the old 1500.
  const maxActionTicks = 3000;
  const ticksPerBatch = 30;
  for (let batch = 0; batch < maxActionTicks / ticksPerBatch && !state.match_complete; batch++) {
    const revision = state.revision;
    await click('AI Step x30');
    const deadline = Date.now() + 15000;
    do {
      await new Promise(resolve => setTimeout(resolve, 100));
      state = await (await fetch(`${backend}/matches/${state.id}`)).json();
    } while (state.revision <= revision && Date.now() < deadline);
    assert.ok(state.revision > revision, `AI Step x30 did not advance revision ${revision}`);
    await waitFor(`document.querySelector('.battlefield')?.dataset.matchRevision === '${state.revision}' && [...document.querySelectorAll('button')].some(b => b.textContent === 'AI Step x30' && b.disabled === ${state.match_complete}) && !document.querySelector('[role=alert]')`);
    observed.add(state.game_number);
    if ((batch + 1) % 10 === 0 || state.match_complete) {
      console.log(JSON.stringify({ event: 'browser_bo3_progress', batches: batch + 1,
        action_budget: maxActionTicks, game: state.game_number, turn: state.turn,
        score: state.score, complete: state.match_complete }));
    }
  }
  assert.equal(state.match_complete, true, `BO3 did not finish: game ${state.game_number}, turn ${state.turn}`);
  assert.equal(Math.max(...Object.values(state.score)), 2);
  assert.deepEqual([...observed].sort(), Array.from({ length: state.game_number }, (_, index) => index + 1));
  await waitFor("document.querySelector('.sideboard-panel')?.innerText.includes('Match Complete')");
  console.log('PASS full natural AI BO3 progresses through the UI and finishes after automatic game transitions');
} finally { await close(); }
