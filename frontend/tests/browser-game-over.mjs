import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

// Serialized fixture mirrors the read-only report: game 1, turn 28, revision 894.
// Every API request is intercepted; this test never sends live match mutations.
const player = id => ({id, name: `Player ${id}`, life: id === 1 ? -4 : 20,
  library_count: 20, hand_count: 0, hand: [], battlefield: [], graveyard: [],
  graveyard_count: 0, exile: [], exile_count: 0, mana_pool: {}});
const fixture = (winner = 2, mode = 'player_vs_ai', complete = false) => ({
  id: 'game-over-fixture', revision: 894, game_number: 1, turn: 28,
  step: 'combat_damage', active_player: 2, priority_player: 2, winner,
  score: {'1': winner === 1 ? (complete ? 2 : 1) : 0, '2': winner === 2 ? (complete ? 2 : 1) : 0},
  best_of: 3, games_needed: 2, match_complete: complete, mode,
  controllers: {'1': mode === 'ai_vs_ai' ? 'ai' : 'human', '2': mode === 'human_vs_human' ? 'human' : 'ai'},
  next_play_draw_chooser: 1, players: {'1': player(1), '2': player(2)},
  pregame_pending: false, stack: [], log: [], attackers: [], blocks: {},
  sideboarding: {'1': {mainboard: [], sideboard: [], applied: false}},
});
const browser = await openBrowser('about:blank');
const frontend = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15173';
const backend = process.env.MTG_BACKEND_ORIGIN || 'http://127.0.0.1:10199';
const corsHeaders = [{name: 'Access-Control-Allow-Origin', value: frontend},
  {name: 'Access-Control-Allow-Methods', value: 'GET, POST, OPTIONS'},
  {name: 'Access-Control-Allow-Headers', value: '*'}];
const {command, evaluate, waitFor, click, close} = browser;
let state = fixture();
let moves = [];
let writes = [];
let unexpected = [];
let onAutoplay;
browser.onIntercept(async ({requestId, request}) => {
  if (request.method === 'OPTIONS') {
    await command('Fetch.fulfillRequest', {requestId, responseCode: 204, responseHeaders: corsHeaders});
    return;
  }
  const path = new URL(request.url).pathname.replace(/^\/api/, '');
  let body;
  if (request.method !== 'GET') {
    writes.push({path, body: request.postData && JSON.parse(request.postData)});
    if (path.endsWith('/autoplay')) state = onAutoplay?.() ?? state;
    else if (path.endsWith('/sideboard')) state = {...state, revision: state.revision + 1,
      sideboarding: {'1': {...state.sideboarding['1'], applied: true}}};
    else if (path.endsWith('/next-game')) state = {...fixture(null), revision: state.revision + 1,
      game_number: 2, controllers: {'1': 'human', '2': 'human'}};
    else unexpected.push(path);
    body = state;
  } else if (path === '/health') body = {ok: true};
  else if (['/matches', '/decks', '/decks/builtin', '/decks/expansion-top'].includes(path)) body = [];
  else if (path === '/diagnostics/runs') body = {runs: []};
  else if (path.endsWith('/legal-moves')) body = {player_id: 2, moves, revision: state.revision, can_auto_pass: true};
  else if (path === `/matches/${state.id}`) body = state;
  else {unexpected.push(path); body = [];}
  await command('Fetch.fulfillRequest', {requestId, responseCode: 200,
    responseHeaders: [{name: 'Content-Type', value: 'application/json'}, ...corsHeaders],
    body: Buffer.from(JSON.stringify(body)).toString('base64')});
});
const enabled = text => `[...document.querySelectorAll('button')].some(b => b.textContent.trim() === ${JSON.stringify(text)} && !b.matches(':disabled'))`;
const settle = () => new Promise(resolve => setTimeout(resolve, 2300));
async function load(next, legal = []) {
  state = next; moves = legal; writes = []; onAutoplay = undefined;
  await command('Page.navigate', {url: `${frontend}/`});
  try {await waitFor("document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session')");}
  catch (error) {throw new Error(`${error.message}\n${JSON.stringify(await evaluate('window.testErrors'))}`);}
}
try {
  await command('Page.enable');
  await command('Fetch.enable', {patterns: [{urlPattern: `${frontend}/api/*`}, {urlPattern: `${backend}/*`}]});
  await command('Page.addScriptToEvaluateOnNewDocument', {source: "window.testErrors = []; window.addEventListener('error', event => window.testErrors.push(event.error?.stack || event.message)); localStorage.setItem('mtg.activeMatch', 'game-over-fixture'); localStorage.removeItem('mtg.pendingStart');"});
  for (const winner of [1, 2, 0]) {
    // Even stale legal moves cannot reactivate a finished game.
    await load(fixture(winner), [{type: 'pass_priority'}]);
    await waitFor(`document.querySelector('.game-result')?.textContent.includes(${JSON.stringify(winner === 0 ? 'Draw' : `P${winner} wins`)})`);
    assert.match(await evaluate("document.querySelector('.game-result').textContent"), /Between games.*Series score:/s);
    for (const label of ['Pass Priority', 'Next Step', 'Auto-pass Until Response', 'AI Step x30', 'Resume automatic play']) {
      assert.equal(await evaluate(enabled(label)), false, label);
    }
    assert.equal(await evaluate(enabled('Apply Sideboard Swaps')), true);
    assert.equal(await evaluate(enabled('P1 Play First')), false, 'sideboarding must be confirmed first');
    assert.equal(await evaluate(enabled('P1 Draw First')), false, 'sideboarding must be confirmed first');
    assert.equal(await evaluate("document.querySelector('#table fieldset').disabled"), true);
    await settle();
    assert.equal(writes.length, 0, 'human games never auto-advance');
    console.log(`PASS winner ${winner}: game result, stopped actions, manual between-games controls`);
  }
  await load(fixture(2));
  assert.equal(await evaluate(enabled('P1 Play First')), false);
  assert.equal(await evaluate(enabled('P1 Draw First')), false);
  await click('Apply Sideboard Swaps');
  await waitFor("document.body.innerText.includes('Sideboard Applied')");
  assert.equal(await evaluate(enabled('P1 Play First')), true);
  assert.equal(await evaluate(enabled('P1 Draw First')), true);
  await click('P1 Draw First');
  await waitFor("!document.querySelector('.game-result')");
  assert.deepEqual(writes.map(write => write.path.split('/').at(-1)), ['sideboard', 'next-game']);
  assert.deepEqual(writes[1].body, {player_id: 1, play_first: false});
  console.log('PASS manual sideboard and play/draw start remain usable');

  await load(fixture(null));
  assert.equal(await evaluate("!!document.querySelector('.game-result')"), false, 'negative life alone does not end a game');
  onAutoplay = () => fixture(2);
  await click('Resume automatic play');
  await waitFor("!!document.querySelector('.game-result')");
  await settle();
  assert.equal(writes.length, 1, 'winner received during autoplay cancels further ticks');
  console.log('PASS active-to-ended transition cancels human autoplay');

  for (const winner of [1, 2]) {
    const ended = fixture(winner, 'player_vs_ai', true);
    ended.players['1'].life = 20;
    await load(ended);
    await waitFor("document.querySelector('.game-result')?.textContent.includes('Series complete')");
    assert.equal(await evaluate(enabled('P1 Play First')), false);
    await settle();
    assert.equal(writes.length, 0);
  }
  console.log('PASS human series completion and authoritative wins with positive life');

  await load(fixture(2, 'human_vs_human'));
  await settle();
  assert.equal(writes.length, 0);
  await load(fixture(2, 'ai_vs_ai'));
  onAutoplay = () => fixture(2, 'ai_vs_ai', true);
  assert.equal(await evaluate(enabled('AI Step x30')), true);
  await click('AI Step x30');
  await waitFor("document.querySelector('.game-result')?.textContent.includes('Series complete')");
  assert.equal(writes.length, 1);
  assert.equal(await evaluate(enabled('AI Step x30')), false);
  console.log('PASS paused AI series steps between games and disables steps at series completion');
  await load(fixture(2, 'ai_vs_ai'));
  onAutoplay = () => fixture(2, 'ai_vs_ai', true);
  await click('Resume automatic play');
  await waitFor("document.querySelector('.game-result')?.textContent.includes('Series complete')");
  await settle();
  assert.equal(writes.length, 1, 'AI series advances between games, stops at series completion');
  assert.equal(await evaluate("!!document.querySelector('.game-result a')"), false);
  assert.equal(await evaluate(enabled('Resume automatic play')), false);
  console.log('PASS AI series continuation and authoritative series completion');
  assert.deepEqual(unexpected, []);
  assert.deepEqual(await evaluate('window.testErrors'), []);
  assert.equal(await evaluate("!!document.querySelector('.operation-alert')"), false);
} finally {await close();}
