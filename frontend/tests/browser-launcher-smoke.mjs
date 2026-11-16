import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

export function smokeConfig(argv, environment) {
  assert.equal(argv.length, 2, 'Expected --create|--restore and an absolute checkpoint');
  assert.ok(['--create', '--restore'].includes(argv[0]), 'Unknown smoke phase');
  assert.ok(path.isAbsolute(argv[1]) && path.resolve(argv[1]) === argv[1], 'Absolute checkpoint required');
  const url = new URL(environment.MTG_LAUNCHER_ORIGIN || 'http://127.0.0.1:15173');
  assert.ok(url.protocol === 'http:' && url.hostname === '127.0.0.1'
    && Number(url.port) >= 1024 && url.pathname === '/' && !url.search && !url.hash
    && !url.username && !url.password, 'Expected a single loopback launcher origin');
  return {phase: argv[0].slice(2), checkpoint: argv[1], origin: url.origin};
}

export function assertProductionAssets(resources, origin) {
  let count = 0;
  for (const resource of resources) {
    const url = new URL(resource.name);
    assert.ok(!url.pathname.includes('/@vite/') && !url.pathname.includes('@react-refresh'),
      'Vite development assets are not launcher acceptance');
    if (['script', 'link', 'css'].includes(resource.initiatorType)) {
      assert.equal(url.origin, origin, 'Static asset origin differs from launcher');
      if (url.pathname.startsWith('/assets/')) count++;
    }
  }
  assert.ok(count > 0, 'No production bundle assets observed');
  return count;
}

export function createObserver(origin) {
  let badPaths = 0, runtimeErrors = 0, matchRead = false, legalMoves = false, actionPost = false;
  let firstAction = null, actionSeen = false;
  const handler = async () => {}; // No Fetch interception is enabled by this smoke.
  handler.observeBrowserEvent = message => {
    if (message.method === 'Runtime.exceptionThrown'
      || message.method === 'Runtime.consoleAPICalled' && message.params?.type === 'error') runtimeErrors++;
    if (message.method !== 'Network.requestWillBeSent' || !['Fetch', 'XHR'].includes(message.params?.type)) return;
    const request = message.params.request;
    const url = new URL(request.url);
    if (url.origin !== origin || !url.pathname.startsWith('/api/') && !url.pathname.startsWith('/card-images/')) {
      badPaths++; return;
    }
    if (request.method === 'GET' && /^\/api\/matches\/[^/]+$/.test(url.pathname)) matchRead = true;
    if (request.method === 'GET' && /^\/api\/matches\/[^/]+\/legal-moves$/.test(url.pathname)) legalMoves = true;
    if (request.method === 'POST' && /^\/api\/matches\/[^/]+\/action$/.test(url.pathname)) {
      actionPost = true;
      if (!actionSeen) {
        actionSeen = true;
        const headers = Object.fromEntries(Object.entries(request.headers ?? {})
          .filter(([name]) => ['idempotency-key', 'x-match-revision'].includes(name.toLowerCase()))
          .map(([name, value]) => [name.toLowerCase(), value]));
        try { firstAction = {body: JSON.parse(request.postData), headers}; }
        catch { firstAction = null; }
      }
    }
  };
  return {handler,
    check(requireAction) {
      assert.equal(badPaths, 0, 'Unexpected App API origin/path');
      assert.equal(runtimeErrors, 0, 'Unexpected browser runtime error');
      assert.ok(matchRead, 'App match restore read was not observed');
      assert.ok(legalMoves, 'App legal-move read was not observed');
      if (requireAction) assert.ok(actionPost, 'No real App action POST was observed');
      return {matchRead, legalMoves, actionPost, runtimeErrors};
    },
    receipt() {
      assert.ok(firstAction && typeof firstAction.headers['idempotency-key'] === 'string'
        && firstAction.headers['idempotency-key'].length > 0
        && typeof firstAction.headers['x-match-revision'] === 'string'
        && /^\d+$/.test(firstAction.headers['x-match-revision']),
        'UI action receipt headers/body unavailable');
      return structuredClone(firstAction);
    }};
}

export function assertRestoredState(expected, actual) {
  assert.deepEqual(actual, expected, 'Full saved match changed across launcher refresh/restart');
}

export async function runSmoke(options) {
  const {openBrowser, waitForApiState} = await import('./browser-driver.mjs');
  const {phase, checkpoint, origin} = options;
  if (phase === 'create') assert.equal(existsSync(checkpoint), false, 'Checkpoint already exists');
  let expected = phase === 'restore' ? JSON.parse(await readFile(checkpoint, 'utf8')) : null;
  const browser = await openBrowser(`${origin}/`);
  const {evaluate, waitFor, click, command, reload, close, onIntercept} = browser;
  const observer = createObserver(origin);
  onIntercept(observer.handler);
  await command('Network.enable', {maxPostDataSize: 2097152});
  await command('Runtime.enable');
  let state, mid;
  async function read(route) {
    const response = await fetch(`${origin}/api${route}`, {signal: AbortSignal.timeout(15000)});
    assert.equal(response.status, 200, 'Unexpected launcher API status');
    return response.json();
  }
  async function post(route, body, headers = {}) {
    return fetch(`${origin}/api${route}`, {method: 'POST', signal: AbortSignal.timeout(15000),
      headers: {'Content-Type': 'application/json', ...headers}, body: JSON.stringify(body)});
  }
  async function visible() {
    await waitFor(`document.querySelector('.battlefield')?.dataset.matchId === ${JSON.stringify(mid)}
      && document.querySelector('.battlefield')?.dataset.matchRevision === '${state.revision}'
      && !document.body.innerText.includes('Match operation pending')`);
  }
  async function commitUI(trigger) {
    const before = state.revision;
    await trigger();
    state = await waitForApiState(`${origin}/api/matches/${mid}`, value => value.revision > before);
    assert.equal(state.revision, before+1, 'One UI intent must commit exactly once');
    await visible();
  }
  async function press(label) { await commitUI(() => click(label)); }
  try {
    await reload();
    assert.equal((await read('/health')).ok, true);
    assert.ok((await read('/decks')).length >= 2, 'Fresh app bootstrap did not supply decks');
    const media = await evaluate(`fetch('/card-images/generic-token-creature.svg').then(async r =>
      ({status: r.status, type: r.headers.get('content-type'), svg: (await r.text()).includes('<svg')}))`);
    assert.equal(media.status, 200); assert.ok(media.type.startsWith('image/svg+xml') && media.svg);
    for (const route of ['/api/not-a-route', '/assets/not-a-bundle.js']) {
      assert.equal((await fetch(origin+route, {headers: {Accept: 'text/html'}, signal: AbortSignal.timeout(15000)})).status, 404);
    }
    if (phase === 'create') {
      const payload = {deck_a: [{card_name: 'Island', quantity: 60}],
        deck_b: [{card_name: 'Island', quantity: 60}], controller_a: 'human', controller_b: 'human',
        mode: 'human_vs_human', seed: 97531};
      const started = await post('/matches/start', payload, {'Idempotency-Key': 'launcher-browser-start'});
      assert.equal(started.status, 200);
      state = await started.json(); mid = state.id;
      assert.equal(state.revision, 0);
      await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(mid)}); localStorage.removeItem('mtg.pendingStart');`);
      await reload(); await visible();
      for (let seat = 0; seat < 2; seat++) await press('Keep Hand');
      assert.equal(state.pregame_pending, false);
      let land, seat;
      for (let step = 0; step < 12; step++) {
        const menu = await read(`/matches/${mid}/legal-moves`);
        assert.equal(menu.revision, state.revision);
        land = menu.moves.find(move => move.type === 'play_land'); seat = menu.player_id;
        if (land) break;
        assert.ok(menu.moves.some(move => move.type === 'pass_priority'), 'No bounded opening continuation');
        await press('Pass Priority');
      }
      assert.ok(land, 'No legal opening land was offered');
      const selector = `[data-hand-card-id="${land.card_id}"]`;
      await waitFor(`[...document.querySelector(${JSON.stringify(selector)})?.querySelectorAll('button') ?? []].some(b => b.textContent.trim().startsWith('Play Land Island') && !b.disabled)`);
      await commitUI(() => evaluate(`(() => {
        const box = document.querySelector(${JSON.stringify(selector)});
        const button = [...box.querySelectorAll('button')].find(b => b.textContent.trim().startsWith('Play Land Island') && !b.disabled);
        if (!button) throw new Error('Missing selected legal land control');
        button.click();
      })()`));
      assert.ok(state.players[String(seat)].battlefield.some(card => card.id === land.card_id));
      const before = state;
      await reload(); await visible();
      state = await read(`/matches/${mid}`);
      assertRestoredState(before, state);
      const receipt = observer.receipt();
      const retry = await post(`/matches/${mid}/action`, receipt.body, receipt.headers);
      assert.equal(retry.status, 200); assertRestoredState(state, await retry.json());
      expected = {schema: 1, scope: 'fresh canonical all-Island opening', state, payload, receipt,
                  land: {id: land.card_id, seat}};
      await writeFile(checkpoint, JSON.stringify(expected)+'\n', {flag: 'wx', mode: 0o600});
    } else {
      assert.equal(expected.schema, 1);
      assert.equal(expected.scope, 'fresh canonical all-Island opening');
      state = expected.state; mid = state.id;
      assert.equal(await evaluate("localStorage.getItem('mtg.activeMatch')"), mid);
      await visible();
      assertRestoredState(state, await read(`/matches/${mid}`));
      const retry = await post(`/matches/${mid}/action`, expected.receipt.body, expected.receipt.headers);
      assert.equal(retry.status, 200); assertRestoredState(state, await retry.json());
      const start = await post('/matches/start', expected.payload, {'Idempotency-Key': 'launcher-browser-start'});
      assert.equal(start.status, 200); assertRestoredState(state, await start.json());
      const stale = await post(`/matches/${mid}/action`, {player_id: 1, action: {type: 'pass_priority'}},
        {'Idempotency-Key': 'launcher-browser-stale', 'X-Match-Revision': '0'});
      assert.equal(stale.status, 409); assert.equal((await stale.json()).detail.code, 'stale_revision');
      assertRestoredState(state, await read(`/matches/${mid}`));
    }
    const assets = await evaluate("performance.getEntriesByType('resource').map(e => ({name: e.name, initiatorType: e.initiatorType}))");
    assertProductionAssets(assets, origin);
    observer.check(phase === 'create');
    console.log(`PASS launcher ${phase}: built same-origin App/API/media, exact saved state and durable request key`);
  } finally { await close(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  await runSmoke(smokeConfig(process.argv.slice(2), process.env));
}
