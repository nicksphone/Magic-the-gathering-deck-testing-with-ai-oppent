import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { openBrowser, waitForApiState } from './browser-driver.mjs';

const api = process.env.MTG_BACKEND_ORIGIN;
const ui = process.env.MTG_FRONTEND_ORIGIN;
const evidence = process.env.MTG_UI_EVIDENCE;
for (const origin of [api, ui, process.env.MTG_BROWSER_ORIGIN]) {
  assert.ok(origin && new URL(origin).hostname === '127.0.0.1');
  assert.ok(!['10199', '15173', '19222'].includes(new URL(origin).port));
}
assert.ok(evidence);
await mkdir(evidence, { recursive: true });
const started = Date.now();
const results = [];
async function json(route, method = 'GET') {
  const response = await fetch(api + route, { method, signal: AbortSignal.timeout(15000) });
  assert.equal(response.status, 200, route);
  return response.json();
}
// Each check owns a fresh tab. Faults alter wire fields only, never canonical cards.
async function check(seat, name, run, route = `/fixture/table?seat=${seat}&crowded=false`) {
  const b = await openBrowser(ui);
  const posts = [];
  let interceptError;
  let fault;
  const interceptions = [];
  b.onIntercept(event => {
    const work = (async () => {
      if (event.request.method === 'POST') {
        assert.ok(event.networkId, 'Actual POST needs its real Network request ID');
        const { postData } = await b.command('Network.getRequestPostData', { requestId: event.networkId });
        assert.ok(typeof postData === 'string' && postData.length > 0);
        posts.push({ url: event.request.url, method: event.request.method, body: postData });
      }
      if (fault && event.request.method === 'GET' && event.request.url.includes('/legal-moves')) {
        const value = await json(new URL(event.request.url).pathname + new URL(event.request.url).search);
        const changed = fault(structuredClone(value));
        interceptions.push({ actual: value, injected: changed });
        await b.command('Fetch.fulfillRequest', { requestId: event.requestId, responseCode: 200,
          responseHeaders: [{ name: 'Content-Type', value: 'application/json' },
            { name: 'Access-Control-Allow-Origin', value: ui }],
          body: Buffer.from(JSON.stringify(changed)).toString('base64') });
      } else await b.command('Fetch.continueRequest', { requestId: event.requestId });
    })();
    work.catch(error => { interceptError = error; });
  });
  try {
    // Shared origin storage survives tab closure. Finish any previous restore
    // before enabling interception, so navigation cannot cancel a paused read.
    await b.waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session')");
    await b.evaluate("localStorage.removeItem('mtg.activeMatch');localStorage.removeItem('mtg.pendingStart')");
    await b.reload();
    await b.waitFor("document.querySelector('.saved-games') && !document.querySelector('.battlefield') && !document.body.innerText.includes('Restoring saved session')");
    await b.command('Network.enable');
    await b.command('Fetch.enable', { patterns: [{ urlPattern: api + '/matches/*', requestStage: 'Request' }] });
    await b.waitFor("document.querySelector('.saved-games') && !document.body.innerText.includes('Restoring saved session')");
    const state = await json(route, 'POST');
    const before = await json(`/matches/${state.id}`);
    const load = async transform => {
      fault = transform;
      await b.evaluate(`localStorage.setItem('mtg.activeMatch',${JSON.stringify(state.id)})`);
      await b.reload();
      await b.waitFor("!document.body.innerText.includes('Restoring saved session') && (document.querySelector('.battlefield') || document.querySelector('[role=alert]'))");
      if (interceptError) throw interceptError;
    };
    await run({ b, state, before, posts, load });
    if (interceptError) throw interceptError;
    results.push({ seat, name, status: 'PASS', posts: posts.length });
    console.log(`PASS seat ${seat} ${name}`);
  } catch (error) {
    results.push({ seat, name, status: 'RED', error: error.stack, posts: posts.length });
    console.error(`RED seat ${seat} ${name}: ${error.message}`);
  } finally {
    await writeFile(`${evidence}/${seat}-${name}.json`, JSON.stringify({ posts, interceptions, intercept_error: interceptError?.stack }, null, 2));
    await writeFile(`${evidence}/${seat}-${name}-body.txt`, await b.evaluate('document.body.innerText').catch(() => 'Unavailable'));
    const image = await b.command('Page.captureScreenshot', { format: 'png' }).catch(() => null);
    if (image) await writeFile(`${evidence}/${seat}-${name}.png`, Buffer.from(image.data, 'base64'));
    await b.close();
  }
}
for (const seat of [1, 2]) {
  await check(seat, 'canonical-action-response-privacy', async ({ b, state, load, posts }) => {
    await load();
    const moves = await json(`/matches/${state.id}/legal-moves`);
    assert.equal(moves.player_id, seat);
    const card = state.players[String(seat)].hand.find(c => c.name === 'Grizzly Bears');
    assert.ok(moves.moves.some(m => m.type === 'cast_spell' && m.card_id === card.id));
    assert.equal(await b.evaluate(`document.querySelector('.player .seat-label').textContent.includes('P${seat}')`), true);
    assert.equal(await b.evaluate("document.querySelectorAll('.opponent .hand-card').length"), 0);
    for (const foreign of state.players[String(3-seat)].hand) {
      assert.equal(await b.evaluate(`document.body.innerHTML.includes(${JSON.stringify(foreign.id)})`), false);
      assert.equal(JSON.stringify(moves).includes(foreign.id), false);
    }
    assert.equal(await b.evaluate("document.body.innerText.includes('No control is implemented')"), false);
    await b.click('Cast Grizzly Bears');
    const cast = await waitForApiState(`${api}/matches/${state.id}`, s => s.stack.length === 1);
    await b.waitFor("document.body.innerText.includes('Stack objects: 1') && [...document.querySelectorAll('button')].some(e=>e.textContent==='Pass Priority'&&!e.matches(':disabled'))");
    assert.equal(await b.evaluate("document.body.innerText.includes('Priority held for human response')"), true);
    assert.ok((await json(`/matches/${state.id}/legal-moves`)).moves.some(m => m.type === 'pass_priority'));
    assert.equal(cast.priority_player, seat);
    assert.equal(posts.length, 1);
    await b.reload();
    await b.waitFor("document.body.innerText.includes('Stack objects: 1') && !document.body.innerText.includes('Restoring saved session')");
    assert.equal((await json(`/matches/${state.id}`)).revision, cast.revision);
    assert.equal(posts.length, 1, 'Reload must not resubmit');
  });
  await check(seat, 'canonical-pending-choice', async ({ b, state, load, posts }) => {
    await load();
    await b.click('Cast Otherworldly Gaze');
    await waitForApiState(`${api}/matches/${state.id}`, s => s.stack.length === 1);
    for (let i = 0; i < 2; i++) {
      const before = (await json(`/matches/${state.id}`)).revision;
      await b.click('Pass Priority');
      await waitForApiState(`${api}/matches/${state.id}`, s => s.revision > before);
      await b.waitFor(`document.querySelector('[data-match-revision]').dataset.matchRevision!==${JSON.stringify(String(before))}`);
    }
    const pending = await waitForApiState(`${api}/matches/${state.id}`, s => s.pending_mechanic_choice?.kind === 'surveil');
    const legal = await json(`/matches/${state.id}/legal-moves`);
    assert.equal(legal.player_id, seat);
    const move = legal.moves.find(m => m.type === 'choose_mechanic' && m.kind === 'surveil');
    assert.equal(move.player_id, seat);
    assert.equal(move.options.length, 3);
    const foreign = await json(`/matches/${state.id}/legal-moves?player_id=${3-seat}`);
    assert.deepEqual(foreign.moves, [], 'Only choice owner receives private inspected options');
    for (const id of move.options) assert.equal(JSON.stringify(foreign).includes(id), false);
    await b.waitFor("document.body.innerText.includes('Choose any cards for your graveyard')");
    assert.equal(await b.evaluate("document.body.innerText.includes('No control is implemented')"), false);
    assert.equal(await b.evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent==='Pass Priority').matches(':disabled')"), true);
    const chosen = move.options[0];
    await b.evaluate(`(() => {const label=[...document.querySelectorAll('.block-panel label')].find(e=>e.querySelector('input[type=checkbox]')&&e.textContent.includes(${JSON.stringify(move.option_labels[chosen])}));if(!label)throw new Error('Missing actual inspected choice');label.querySelector('input').click();})()`);
    assert.deepEqual(await json(`/matches/${state.id}`), pending, 'Draft selection is read-only');
    await b.click('Confirm Selection');
    await waitForApiState(`${api}/matches/${state.id}`, s => s.pending_mechanic_choice?.kind === 'surveil_top_order');
    await b.waitFor("document.body.innerText.includes('Pick the remaining cards in order')");
    const ordering = (await json(`/matches/${state.id}/legal-moves`)).moves.find(m => m.kind === 'surveil_top_order');
    for (const id of ordering.options) await b.click(ordering.option_labels[id]);
    await b.click('Confirm Order');
    const done = await waitForApiState(`${api}/matches/${state.id}`, s => !s.pending_mechanic_choice);
    assert.ok(done.players[String(seat)].graveyard.some(c => c.id === chosen));
    assert.equal(posts.length, 5, 'One cast, two passes, one partition, one order');
    assert.deepEqual(JSON.parse(posts[3].body).action, { type: 'choose_mechanic', card_ids: [chosen] });
    assert.equal(JSON.parse(posts[3].body).player_id, seat);
  }, `/fixture?face_kind=surveil_${seat}`);
  for (const corruption of ['bad-seat', 'bad-revision', 'bad-moves', 'bad-mana-index']) {
    await check(seat, corruption, async ({ b, state, before, posts, load }) => {
      await load(value => {
        if (corruption === 'bad-mana-index') {
          const move = value.moves.find(m => m.type === 'activate_mana_ability');
          assert.ok(move, 'Corrupt an actual offered canonical mana ability, not a made-up move');
          move.ability_index = -1;
          return value;
        }
        return { ...value, ...({ 'bad-seat': { player_id: 3 },
          'bad-revision': { revision: -1 }, 'bad-moves': { moves: {} } }[corruption]) };
      });
      assert.equal(await b.evaluate("[...document.querySelectorAll('[role=alert]')].some(e=>e.textContent.includes('Invalid legal-moves response'))"), true);
      assert.equal(await b.evaluate("document.querySelector('.battlefield')===null"), true);
      assert.equal(posts.length, 0);
      assert.deepEqual(await json(`/matches/${state.id}`), before);
    });
  }
  await check(seat, 'unknown-action-warning', async ({ b, state, before, posts, load }) => {
    await load(value => ({ ...value, moves: [{ type: '__diagnostic_unknown_action__' }] }));
    assert.equal(await b.evaluate("[...document.querySelectorAll('[role=alert]')].some(e=>e.textContent.includes('No control is implemented for legal action: __diagnostic_unknown_action__'))"), true);
    assert.equal(posts.length, 0);
    assert.deepEqual(await json(`/matches/${state.id}`), before);
  });
  await check(seat, 'unknown-mechanic-fail-visible', async ({ b, state, before, posts, load }) => {
    // Synthetic protocol fault: no claim this mechanic exists in Oracle or engine.
    await load(value => ({ ...value, moves: [{ type: 'choose_mechanic',
      kind: '__diagnostic_unknown_mechanic__', player_id: seat, options: [], count: 0 }] }));
    assert.equal(posts.length, 0);
    assert.deepEqual(await json(`/matches/${state.id}`), before);
    const visible = await b.evaluate("[...document.querySelectorAll('[role=alert]')].some(e=>/unsupported|unknown|No control|Invalid legal-moves/i.test(e.textContent))");
    const confirm = await b.evaluate("[...document.querySelectorAll('button')].some(e=>e.textContent==='Confirm Selection'&&!e.matches(':disabled'))");
    if (confirm) {
      await b.click('Confirm Selection');
      await b.waitFor("[...document.querySelectorAll('[role=alert]')].some(e=>e.textContent.length>0) && !document.body.innerText.includes('Match operation pending')");
      assert.equal(posts.length, 1, 'Capture actual invalid-choice POST, not a simulated callback');
      assert.deepEqual(await json(`/matches/${state.id}`), before, 'Engine rejection preserves state');
    }
    assert.equal(visible, true, `Unknown mechanic must fail visibly; enabled generic confirmation=${confirm}`);
    assert.equal(confirm, false, 'Unknown mechanism must not offer generic POST control');
  });
}
const red = results.filter(row => row.status === 'RED');
await writeFile(`${evidence}/results.json`, JSON.stringify({ scope: 'test-only UI action diagnostics',
  elapsed_ms: Date.now()-started, passed: results.length-red.length, red: red.length, results,
  limits: 'Existing canonical table and surveil fixtures only. Unknown type/kind probes are synthetic wire faults, not card support claims. No full shared gate.' }, null, 2));
if (red.length) process.exitCode = 1;
