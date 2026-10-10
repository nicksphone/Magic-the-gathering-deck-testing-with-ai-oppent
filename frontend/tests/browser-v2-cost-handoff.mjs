import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = (await readFile(new URL('./browser-ui-v2-costs.mjs', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '');
const checkpoint = new Error('Actual script reached the bounded protocol checkpoint');

// Synthetic DOM/CDP/API protocol only: run the unchanged script, not a game engine.
function protocol({ action = false, oldPending = false, mismatch, status = 200,
  idleError, restoreError } = {}) {
  const events = [], scheduled = [], storage = new Map([['mtg.activeMatch', 'old']]);
  const view = { id: 'old', revision: 9, pending: oldPending, restoring: false, cast: false };
  const player = seat => ({ hand: [{ id: `paid-${seat}`, name: 'Island' }],
    battlefield: [{ id: `bear-${seat}`, name: 'Grizzly Bears' }],
    graveyard: [], mana_pool: { B: 1 } });
  const state = { id: 'published', revision: 0, stack: [],
    players: { 1: player(1), 2: player(2) } };
  let closed = false, posts = 0, startedCastWait = false, apiReads = 0;
  const selected = { value: '', options: [{ value: 'paid-1', textContent: 'Island', selected: false }],
    dispatchEvent() {}, closest: () => box };
  const target = { value: '', options: [{ value: 'bear-2', textContent: 'Target Grizzly Bears' }],
    dispatchEvent() {} };
  const cost = { value: '', options: [{ value: 'base_discard', textContent: 'Discard' }], dispatchEvent() {} };
  const box = { textContent: 'Cast Bone Shards', querySelectorAll: () => [cost, selected, target] };
  const castButton = { textContent: 'Cast Bone Shards',
    get disabled() { return !selected.options[0].selected; } };
  const document = {
    body: { get innerText() { return [view.pending && 'Match operation pending',
      view.restoring && 'Restoring saved session', view.cast && 'Cast Bone Shards'].filter(Boolean).join(' '); } },
    querySelector(selector) {
      if (selector === '.battlefield' || selector === '[data-match-revision]') {
        return { dataset: { matchId: view.id, matchRevision: String(view.revision) } };
      }
      if (selector.startsWith('select[aria-label=')) return selected;
      throw new Error(`Unexpected protocol selector: ${selector}`);
    },
    querySelectorAll(selector) {
      if (selector === 'button') return [castButton, { textContent: 'Resume automatic play' }];
      if (selector === '.hand-card') return [box];
      throw new Error(`Unexpected protocol selector: ${selector}`);
    },
  };
  const context = vm.createContext({ document, Event: class {}, localStorage: {
    setItem(key, value) { storage.set(key, value); events.push(`storage:${value}`); },
    getItem(key) { return storage.get(key); },
  } });
  const commit = () => {
    view.id = state.id;
    view.revision = state.revision;
    view.cast = state.stack.length === 0;
    storage.set('mtg.activeMatch', state.id);
    events.push(`view/legal/storage:${state.revision}`);
    scheduled.push(() => { view.pending = false; events.push('mutation-idle'); });
  };
  if (oldPending) scheduled.push(() => {
    view.pending = false;
    storage.set('mtg.activeMatch', 'old');
    events.push('old-view/legal/storage');
  });
  const browser = {
    async evaluate(expression) {
      if (expression.includes('dataset.matchRevision')) events.push(`sample:${view.revision}:${view.pending}`);
      return vm.runInContext(expression, context);
    },
    async waitFor(expression) {
      if (expression.includes('Match operation pending') && idleError) throw idleError;
      if (expression === "document.body.innerText.includes('Cast Bone Shards')") {
        startedCastWait = true;
        if (!action && vm.runInContext(expression, context)) throw checkpoint;
      }
      for (let poll = 0; poll < 8; poll++) {
        if (vm.runInContext(expression, context)) return;
        if (!scheduled.length) throw new Error('Protocol readiness failed: ' + expression);
        scheduled.shift()();
      }
      throw new Error('Protocol readiness did not settle');
    },
    async reload() {
      // An already acknowledged old action finishes before the new document reads storage.
      if (oldPending && scheduled.length) scheduled.shift()();
      if (restoreError) throw restoreError;
      const id = storage.get('mtg.activeMatch');
      view.restoring = true;
      scheduled.push(() => {
        view.id = mismatch === 'rendered-id' ? 'other' : id;
        view.revision = mismatch === 'revision' ? 1 : 0;
        view.cast = id === 'published';
        if (mismatch === 'stored-id') storage.set('mtg.activeMatch', 'other');
        view.restoring = false;
        if (mismatch === 'pending') view.pending = true;
        events.push('restored');
      });
    },
    async click(label) {
      // Like the real driver's click(), await the enabled control before dispatch.
      while (view.pending && scheduled.length) scheduled.shift()();
      assert.equal(view.pending, false);
      state.revision++;
      state.stack = label === 'Cast Bone Shards' || state.revision === 2 ? [{}] : [];
      view.pending = true;
      events.push(`action/API:${state.revision}`);
      scheduled.push(commit);
    },
    async close() { closed = true; },
  };
  const program = vm.runInNewContext(`(async () => { ${source}\n})()`, {
    assert, openBrowser: async () => browser,
    process: { env: { MTG_BROWSER_ORIGIN: 'http://protocol.invalid' } },
    fetch: async (_url, options) => {
      assert.equal(options.method, 'POST');
      posts++;
      events.push(`fixture:${view.pending}`);
      return { status, json: async () => structuredClone(state) };
    },
    waitForApiState: async (_url, predicate) => {
      apiReads++;
      assert.equal(predicate(state), true);
      if (state.stack.length === 0) {
        events.push(`final-API:${view.pending}:${view.revision}`);
        throw checkpoint;
      }
      return structuredClone(state);
    },
    console: { log() {} },
  });
  return { program, events, view, storage, get closed() { return closed; },
    get posts() { return posts; }, get startedCastWait() { return startedCastWait; },
    get apiReads() { return apiReads; } };
}

test('old acknowledged mutation commits before publishing the next fixture', async () => {
  const p = protocol({ oldPending: true });
  await assert.rejects(p.program, error => error === checkpoint);
  assert.ok(p.events.indexOf('old-view/legal/storage') < p.events.indexOf('fixture:false'));
  assert.equal(p.storage.get('mtg.activeMatch'), 'published');
  assert.equal(p.view.id, 'published');
  assert.equal(p.posts, 1);
  assert.equal(p.closed, true);
});

test('clean fixture restoration reaches the original cast readiness check', async () => {
  const p = protocol();
  await assert.rejects(p.program, error => error === checkpoint);
  assert.equal(p.startedCastWait, true);
  assert.equal(p.posts, 1);
  assert.equal(p.closed, true);
});

for (const mismatch of ['stored-id', 'rendered-id', 'revision', 'pending']) {
  test(`fixture readiness rejects ${mismatch} before entering gameplay`, async () => {
    const p = protocol({ mismatch });
    await assert.rejects(p.program, /Protocol readiness failed/);
    assert.equal(p.startedCastWait, false);
    assert.equal(p.posts, 1, 'Never replay a fixture write to hide a mismatch');
    assert.equal(p.closed, true);
  });
}

test('unresolved previous mutation preserves its error without publishing', async () => {
  const error = new Error('Old mutation failed to settle');
  const p = protocol({ idleError: error });
  await assert.rejects(p.program, observed => observed === error);
  assert.equal(p.posts, 0);
  assert.equal(p.closed, true);
});

test('failed fixture POST is neither retried nor followed by reload', async () => {
  const p = protocol({ status: 500 });
  await assert.rejects(p.program, error => error.code === 'ERR_ASSERTION');
  assert.equal(p.posts, 1);
  assert.ok(!p.events.includes('restored'));
  assert.equal(p.closed, true);
});

test('reload failure remains primary and closes the owned target', async () => {
  const error = new Error('Reload protocol failed');
  const p = protocol({ restoreError: error });
  await assert.rejects(p.program, observed => observed === error);
  assert.equal(p.posts, 1);
  assert.equal(p.closed, true);
});

test('sample revision only after prior cast and legal-move/view/storage commit', async () => {
  const p = protocol({ action: true });
  await assert.rejects(p.program, error => error === checkpoint);
  assert.deepEqual(p.events.filter(event => event.startsWith('sample:')), ['sample:1:false', 'sample:2:false']);
  assert.equal(p.apiReads, 2, 'Run the original server stack predicates without retries');
  assert.equal(p.closed, true);
});

test('early final server acknowledgement is not a rendered action/idle receipt', async () => {
  const p = protocol({ action: true });
  await assert.rejects(p.program, error => error === checkpoint);
  assert.ok(p.events.includes('final-API:false:3'));
  assert.equal(p.view.pending, false);
  assert.equal(p.view.revision, 3);
  assert.equal(p.closed, true);
});
