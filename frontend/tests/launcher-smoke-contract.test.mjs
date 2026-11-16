import assert from 'node:assert/strict';
import test from 'node:test';
import {existsSync} from 'node:fs';

async function subject() {
  const url = new URL('./browser-launcher-smoke.mjs', import.meta.url);
  assert.ok(existsSync(url), 'Launcher browser scenario is missing');
  return import(url.href);
}

const origin = 'http://127.0.0.1:15173';
const event = (url, method = 'GET') => ({method: 'Network.requestWillBeSent',
  params: {type: 'Fetch', request: {url, method}}});

function evidence(observer, action = true) {
  for (const path of ['/api/health', '/api/decks', '/api/matches/unit', '/api/matches/unit/legal-moves',
                      '/card-images/generic-token-creature.svg']) {
    observer.handler.observeBrowserEvent(event(origin + path));
  }
  if (action) observer.handler.observeBrowserEvent(event(origin + '/api/matches/unit/action', 'POST'));
}

test('smoke configuration requires a phase, private checkpoint path and loopback origin', async () => {
  const {smokeConfig} = await subject();
  assert.deepEqual(smokeConfig(['--create', '/tmp/checkpoint.json'], {}),
    {phase: 'create', checkpoint: '/tmp/checkpoint.json', origin});
  assert.equal(smokeConfig(['--restore', '/tmp/checkpoint.json'], {}).phase, 'restore');
  for (const args of [[], ['--create'], ['--other', '/tmp/x'], ['--create', 'relative.json'], ['--create', '/tmp/x', 'extra']]) {
    assert.throws(() => smokeConfig(args, {}));
  }
  for (const bad of ['https://example.com', 'http://127.0.0.1:15173/api', 'http://user@127.0.0.1:15173', 'http://0.0.0.0:15173']) {
    assert.throws(() => smokeConfig(['--create', '/tmp/x'], {MTG_LAUNCHER_ORIGIN: bad}));
  }
});

test('only real same-origin App requests satisfy the create-phase evidence', async () => {
  const {createObserver} = await subject();
  const observer = createObserver(origin); evidence(observer);
  assert.deepEqual(observer.check(true), {matchRead: true, legalMoves: true, actionPost: true, runtimeErrors: 0});
});

for (const [label, url] of [['old direct backend', 'http://127.0.0.1:10199/matches/unit'],
                           ['missing API mount', origin + '/matches/unit']]) {
  test(`${label} is rejected rather than silently accepted`, async () => {
    const {createObserver} = await subject();
    const observer = createObserver(origin); evidence(observer);
    observer.handler.observeBrowserEvent(event(url));
    assert.throws(() => observer.check(true), /origin\/path/);
  });
}

test('missing legal-move reads and missing UI mutations fail', async () => {
  const {createObserver} = await subject();
  const empty = createObserver(origin);
  empty.handler.observeBrowserEvent(event(origin + '/api/matches/unit'));
  assert.throws(() => empty.check(false), /legal/);
  const noAction = createObserver(origin); evidence(noAction, false);
  assert.throws(() => noAction.check(true), /action/);
  assert.equal(noAction.check(false).actionPost, false);
});

for (const method of ['Runtime.exceptionThrown', 'Runtime.consoleAPICalled']) {
  test(`${method} cannot be hidden by successful requests`, async () => {
    const {createObserver} = await subject();
    const observer = createObserver(origin); evidence(observer);
    observer.handler.observeBrowserEvent({method, params: {type: 'error'}});
    assert.throws(() => observer.check(true), /runtime/);
  });
}

test('production assets are required; Vite development assets are refused', async () => {
  const {assertProductionAssets} = await subject();
  const good = [{name: origin + '/assets/index-unit.js', initiatorType: 'script'},
                {name: origin + '/assets/index-unit.css', initiatorType: 'link'}];
  assert.equal(assertProductionAssets(good, origin), 2);
  assert.throws(() => assertProductionAssets([], origin), /bundle/);
  assert.throws(() => assertProductionAssets([...good, {name: origin + '/@vite/client', initiatorType: 'script'}], origin), /development/);
  assert.throws(() => assertProductionAssets([{name: 'http://127.0.0.1:15174/assets/x.js', initiatorType: 'script'}], origin), /origin/);
});

test('restore comparison preserves every field and revision', async () => {
  const {assertRestoredState} = await subject();
  const before = {id: 'unit', revision: 7, players: {'1': {life: 20}}, log: ['unit']};
  assert.doesNotThrow(() => assertRestoredState(before, structuredClone(before)));
  for (const changed of [{...before, revision: 8}, {...before, log: []},
    {...before, players: {'1': {life: 19}}}]) assert.throws(() => assertRestoredState(before, changed));
});


test('only the first UI action receipt is retained, with no unrelated headers', async () => {
  const {createObserver} = await subject();
  const observer = createObserver(origin);
  const action = event(origin+'/api/matches/unit/action', 'POST');
  action.params.request.headers = {'Idempotency-Key': 'unit-first', 'X-Match-Revision': '0', Authorization: 'unit-not-forwarded'};
  action.params.request.postData = JSON.stringify({player_id: 1, action: {type: 'keep_hand'}});
  observer.handler.observeBrowserEvent(action);
  observer.handler.observeBrowserEvent({...action, params: {...action.params, request: {...action.params.request,
    headers: {'Idempotency-Key': 'unit-second', 'X-Match-Revision': '1'}}}});
  assert.deepEqual(observer.receipt(), {body: {player_id: 1, action: {type: 'keep_hand'}},
    headers: {'idempotency-key': 'unit-first', 'x-match-revision': '0'}});
});

test('missing first action metadata cannot be replaced by an easier later receipt', async () => {
  const {createObserver} = await subject();
  const observer = createObserver(origin);
  observer.handler.observeBrowserEvent(event(origin+'/api/matches/unit/action', 'POST'));
  const later = event(origin+'/api/matches/unit/action', 'POST');
  later.params.request.headers = {'Idempotency-Key': 'unit-second', 'X-Match-Revision': '1'};
  later.params.request.postData = JSON.stringify({player_id: 2, action: {type: 'keep_hand'}});
  observer.handler.observeBrowserEvent(later);
  assert.throws(() => observer.receipt(), /headers\/body/);
});


test('runner is valid Bash and launches the actual script with explicit owned DB/origin', async () => {
  const {spawnSync} = await import('node:child_process');
  const {mkdtempSync, mkdirSync, writeFileSync, readFileSync} = await import('node:fs');
  const {tmpdir} = await import('node:os');
  const {join} = await import('node:path');
  const {fileURLToPath} = await import('node:url');
  const runner = fileURLToPath(new URL('./run-launcher-smoke.sh', import.meta.url));
  assert.equal(spawnSync('bash', ['-n', runner]).status, 0);
  const directory = mkdtempSync(join(tmpdir(), 'mtg-launcher-wiring-'));
  mkdirSync(join(directory, 'source/scripts'), {recursive: true});
  mkdirSync(join(directory, 'logs'));
  writeFileSync(join(directory, 'source/scripts/start-local.sh'),
    'printf "%s\\n" "$MTG_LOCAL_PYTHON" "$MTG_LOCAL_PORT" "$MTG_DATABASE_PATH" "$PWD" > "$RECORD"\n');
  const script = 'source "$RUNNER"; work="$CASE"; source_root="$CASE/source"; python_bin="$CASE/venv with spaces/bin/python"; launcher_port=15173; database="$CASE/state.db"; start_launcher; wait "$launcher_pid"';
  const result = spawnSync('bash', ['-c', script], {env: {PATH: process.env.PATH, RUNNER: runner, CASE: directory,
    RECORD: join(directory, 'record')}, encoding: 'utf8', timeout: 5000});
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readFileSync(join(directory, 'record'), 'utf8').trim().split('\n'),
    [join(directory, 'venv with spaces/bin/python'), '15173', join(directory, 'state.db'), join(directory, 'source')]);
});


test('frontend installation includes build tooling even under production omit settings', async () => {
  const {spawnSync} = await import('node:child_process');
  const {mkdtempSync, mkdirSync, writeFileSync, readFileSync} = await import('node:fs');
  const {tmpdir} = await import('node:os');
  const {join} = await import('node:path');
  const {fileURLToPath} = await import('node:url');
  const runner = fileURLToPath(new URL('./run-launcher-smoke.sh', import.meta.url));
  const directory = mkdtempSync(join(tmpdir(), 'mtg-launcher-install-'));
  for (const path of ['source/frontend', 'logs', 'bin']) mkdirSync(join(directory, path), {recursive: true});
  writeFileSync(join(directory, 'bin/npm'), '#!/bin/sh\nprintf "%s\\n" "$@" > "$RECORD"\n', {mode: 0o700});
  const result = spawnSync('bash', ['-c', 'source "$RUNNER"; work="$CASE"; source_root="$CASE/source"; install_frontend'],
    {env: {PATH: join(directory, 'bin') + ':' + process.env.PATH, RUNNER: runner, CASE: directory,
      RECORD: join(directory, 'record'), NODE_ENV: 'production', npm_config_omit: 'dev'}, encoding: 'utf8', timeout: 5000});
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readFileSync(join(directory, 'record'), 'utf8').trim().split('\n'),
    ['ci', '--include=dev', '--no-audit', '--no-fund']);
});
