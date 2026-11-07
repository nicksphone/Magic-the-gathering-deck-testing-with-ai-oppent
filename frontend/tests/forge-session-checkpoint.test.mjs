// Labelled synthetic transport/UI contracts only: no backend, database or native game.
import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build, stop} from 'esbuild';
import {fixture, uuid} from './forge-session-fixtures.mjs';

after(stop);
const require = createRequire(import.meta.url);
const cap = 'a'.repeat(64), sessionKey = 'mtg.forge.session';
const deck = {id: 1, name: 'SYNTHETIC checkpoint deck', mainboard: [{quantity: 60, card_name: 'Island'}], sideboard: []};
const identity = () => new Map([[sessionKey, JSON.stringify({session_id: uuid(9), capability: cap})]]);
const paused = (status = 'suspended', sequence = 4) => ({...fixture(), status, sequence, question: null});
const settle = () => new Promise(resolve => setImmediate(resolve));
const posts = h => h.calls.filter(c => c.init.method === 'POST');
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  return value && typeof value === 'object' ? [value, ...nodes(value.props?.children)] : [];
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value == null || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props?.children) : String(value);
}
let apiBuild, componentBuild;
const api = () => apiBuild ??= build({entryPoints: [new URL('../src/api/forge.ts', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'esm', define: {'import.meta.env': '{}'}})
  .then(result => import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`));

// Same hooks/esbuild seam as the original session fixtures; only fetch and timers are synthetic.
async function harness(reply, entries = identity()) {
  const slots = [], effects = [], cleanups = new Map(), calls = [], timers = new Map(), active = [];
  let index = 0, timerId = 0;
  const storage = {getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value),
    removeItem: key => entries.delete(key)};
  const hooks = {
    useState(initial) {const i = index++; if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
      return [slots[i], value => {slots[i] = typeof value === 'function' ? value(slots[i]) : value;}];},
    useRef(initial) {const i = index++; if (!(i in slots)) slots[i] = {current: initial}; return slots[i];},
    useEffect(fn, deps) {const i = index++; if (!slots[i] || deps.some((d, j) => d !== slots[i][j])) {
      slots[i] = deps; effects.push({i, fn});}},
  };
  componentBuild ??= build({entryPoints: [new URL('../src/components/ForgeGame.tsx', import.meta.url).pathname],
    bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
    loader: {'.css': 'empty'}, define: {'import.meta.env': '{}'}}).then(result => result.outputFiles[0].text);
  const module = {exports: {}};
  const fetcher = async (url, init) => {
    calls.push({url, init});
    const value = url.endsWith('/status') ? {available: true} : await reply(url, init);
    return value instanceof Response ? value : new Response(JSON.stringify(value));
  };
  new Function('require', 'module', 'exports', 'localStorage', 'fetch', 'window', await componentBuild)(
    name => name === 'react' ? {...require('react'), ...hooks} : require(name), module, module.exports, storage,
    fetcher, {setTimeout(fn) {timers.set(++timerId, fn); return timerId;}, clearTimeout(id) {timers.delete(id);}});
  const props = {deckA: deck, deckB: deck, humanSeat: 1, disabled: false,
    onActiveChange(value) {active.push(value); return true;}};
  const h = {calls, entries, storage, timers, active, props,
    render() {index = 0; return module.exports.ForgeGame(props);},
    button(label) {const node = nodes(h.render()).find(n => n.type === 'button' && text(n.props.children) === label);
      assert.ok(node, `Missing button ${label}`); return node.props;},
    choice() {return nodes(h.render()).find(n => n.type === module.exports.ForgeChoices)?.props;},
    async flush() {for (let pass = 0; pass < 3; pass++) {h.render();
      for (const {i, fn} of effects.splice(0)) {cleanups.get(i)?.(); cleanups.set(i, fn());}
      await settle();}},
    async tick() {const pending = [...timers.values()]; timers.clear(); for (const fn of pending) fn(); await h.flush();},
    cleanup() {for (const cleanup of cleanups.values()) cleanup?.();},
  };
  return h;
}

test('checkpoint statuses retain the strict eleven-field envelope and never release a choice', async () => {
  const {parseForgeSnapshot, canAnswerForge, makeForgeAnswer} = await api();
  for (const status of ['suspended', 'restoring']) {
    const s = paused(status);
    assert.deepEqual(parseForgeSnapshot(s), s);
    assert.equal(Object.keys(s).length, 11);
    assert.equal(canAnswerForge(s), false);
    assert.throws(() => makeForgeAnswer(s, [uuid(2)], 'forbidden'), /selection/);
    for (const mutate of [v => {v.question = fixture().question;}, v => {v.checkpoint = {};},
      v => {v.info.command = 'private';}, v => {v.path = 'private';},
      v => {v.result = {outcomes: [], turns: 1, draw: true, win_condition: 'SYNTHETIC'};}]) {
      const bad = paused(status); mutate(bad);
      assert.throws(() => parseForgeSnapshot(bad), /Invalid Forge/);
    }
  }
});

test('checkpoint and resume send exact authorized bodies with bounded save deadline', async t => {
  const {createForgeClient} = await api(), calls = [], deadlines = [];
  const timeout = AbortSignal.timeout.bind(AbortSignal);
  t.mock.method(AbortSignal, 'timeout', ms => {deadlines.push(ms); return timeout(ms);});
  const client = createForgeClient('/api', async (url, init) => {
    calls.push({url, init}); return new Response(JSON.stringify(paused(url.endsWith('/resume') ? 'restoring' : 'suspended')));
  });
  const save = {sequence: 3, request_id: uuid(1), action_id: 'save-1'};
  const resume = {sequence: 4, action_id: 'resume-1'};
  assert.equal((await client.checkpoint(uuid(9), cap, save)).status, 'suspended');
  assert.equal((await client.resume(uuid(9), cap, resume)).status, 'restoring');
  assert.deepEqual(calls.map(c => c.url), [`/api/forge/sessions/${uuid(9)}/checkpoint`, `/api/forge/sessions/${uuid(9)}/resume`]);
  assert.deepEqual(calls.map(c => JSON.parse(c.init.body)), [save, resume]);
  assert.deepEqual(deadlines, [30000, 15000]);
  for (const {url, init} of calls) {
    assert.equal(init.method, 'POST'); assert.equal(init.headers.Authorization, `Bearer ${cap}`);
    assert.equal(init.cache, 'no-store'); assert.equal(init.redirect, 'error');
    assert.equal(init.referrerPolicy, 'no-referrer'); assert.ok(!url.includes(cap));
  }
});

test('checkpoint commands reject extra browser fields and invalid versions before transport', async () => {
  const {createForgeClient} = await api(); let calls = 0;
  const client = createForgeClient('/api', async () => {calls++; return new Response(JSON.stringify(paused()));});
  for (const method of ['checkpoint', 'resume']) {
    const body = method === 'checkpoint' ? {sequence: 3, request_id: uuid(1), action_id: 'save'} : {sequence: 4, action_id: 'resume'};
    for (const extra of [{command: 'private'}, {path: 'private'}, {checkpoint: {}}, {sequence: -1},
      {sequence: true}, {action_id: ''}, {action_id: '../private'},
      ...(method === 'checkpoint' ? [{request_id: 'old-token'}] : [{request_id: uuid(1)}])]) {
      await assert.rejects(client[method](uuid(9), cap, {...body, ...extra}), /Invalid/);
    }
  }
  assert.equal(calls, 0);
});

test('checkpoint clients reject malformed or foreign snapshots and never retry lost delivery', async () => {
  const {createForgeClient} = await api();
  for (const method of ['checkpoint', 'resume']) {
    const body = method === 'checkpoint' ? {sequence: 3, request_id: uuid(1), action_id: 'save'} : {sequence: 4, action_id: 'resume'};
    for (const response of [{...paused(), private_journal: []}, {...paused(), session_id: uuid(10)}, {...paused(), sequence: true}]) {
      const client = createForgeClient('/api', async () => new Response(JSON.stringify(response)));
      await assert.rejects(client[method](uuid(9), cap, body), /Invalid Forge/);
    }
    let attempts = 0;
    const lost = createForgeClient('/api', async () => {attempts++; throw Error('SYNTHETIC response lost');});
    await assert.rejects(lost[method](uuid(9), cap, body), /Reconnect/);
    assert.equal(attempts, 1);
  }
});

test('save is explicit, fences concurrent actions, and reports saved only after suspended response', async t => {
  let next = fixture(), finish;
  const h = await harness((url, init) => init.method === 'GET' ? next : new Promise(resolve => {finish = resolve;}));
  t.after(() => h.cleanup()); await h.flush();
  assert.equal(posts(h).length, 0);
  assert.equal(h.button('Save and pause').disabled, false);
  assert.equal(h.button('Resume saved game').disabled, true);
  const save = h.button('Save and pause').onClick, pending = save();
  await h.flush();
  assert.equal(h.button('Save and pause').disabled, true);
  assert.equal(h.choice().disabled, true);
  assert.doesNotMatch(text(h.render()), /Saved and paused/);
  await save(); await h.choice().onAnswer([uuid(2)]);
  assert.equal(posts(h).length, 1);
  const command = JSON.parse(posts(h)[0].init.body);
  assert.deepEqual(Object.keys(command).sort(), ['action_id', 'request_id', 'sequence']);
  assert.equal(command.sequence, 3); assert.equal(command.request_id, uuid(1)); assert.match(command.action_id, /^[a-f0-9]{32}$/);
  next = paused(); finish(next); await pending; await h.flush();
  assert.match(text(h.render()), /Saved and paused/);
  assert.equal(h.choice(), undefined);
  assert.equal(h.button('Resume saved game').disabled, false);
  assert.deepEqual(JSON.parse(h.entries.get(sessionKey)), {session_id: uuid(9), capability: cap});
  assert.ok(!h.active.includes(false), 'Save must not release the Python mutation fence');
  assert.doesNotMatch(text(h.render()), new RegExp(cap));
});

test('save requires a current answerable pending question and obeys the parent fence', async t => {
  for (const change of [s => {s.status = 'starting'; s.question = null;}, s => {s.question = null;},
    s => {s.last_answer = {action_id: 'pending', request_id: uuid(1), status: 'uncertain', reason: null};},
    s => {s.last_answer = {action_id: 'pending', request_id: uuid(1), status: 'processing', reason: null};}]) {
    const next = fixture(); change(next);
    const h = await harness(() => next); t.after(() => h.cleanup()); await h.flush();
    assert.equal(h.button('Save and pause').disabled, true);
    await h.button('Save and pause').onClick(); assert.equal(posts(h).length, 0);
  }
  const h = await harness(() => fixture()); t.after(() => h.cleanup()); await h.flush();
  h.props.disabled = true;
  assert.equal(h.button('Save and pause').disabled, true);
  await h.button('Save and pause').onClick(); assert.equal(posts(h).length, 0);
});

test('an uncertain answer cannot be checkpointed after reconnect to its unchanged question', async t => {
  const h = await harness((_url, init) => {
    if (init.method === 'POST') throw Error('SYNTHETIC answer response lost'); return fixture();
  });
  t.after(() => h.cleanup()); await h.flush();
  await h.choice().onAnswer([uuid(2)]); await h.flush();
  assert.equal(h.button('Save and pause').disabled, true);
  await h.button('Save and pause').onClick(); assert.equal(posts(h).length, 1);
});

test('reload reads a suspended save without resuming and retains the native handle', async t => {
  const {hasForgeSession} = await api(), entries = identity();
  for (let mount = 0; mount < 2; mount++) {
    const h = await harness(() => paused(), entries); t.after(() => h.cleanup()); await h.flush();
    assert.ok(h.calls.every(c => c.init.method === 'GET'));
    assert.equal(h.button('Save and pause').disabled, true);
    assert.equal(h.button('Resume saved game').disabled, false);
    assert.equal(h.timers.size, 0, 'Suspended GET must neither spawn nor poll a worker');
    assert.ok(!h.active.includes(false)); assert.equal(entries.size, 1);
    const original = globalThis.localStorage;
    try {globalThis.localStorage = h.storage; assert.equal(hasForgeSession(), true);}
    finally {if (original === undefined) delete globalThis.localStorage; else globalThis.localStorage = original;}
    assert.match(text(h.render()), /unsaved progress after the last save is not guaranteed/i);
    assert.doesNotMatch(text(h.render()), /Cold app restore is not supported/);
    h.cleanup();
  }
});

test('explicit resume polls restoring and exposes only a fresh verified choice on the same session', async t => {
  let next = paused();
  const h = await harness((url, init) => {
    if (init.method === 'GET') return next;
    if (url.endsWith('/resume')) return next = paused('restoring', 5);
    assert.ok(url.endsWith('/answer')); return next;
  });
  t.after(() => h.cleanup()); await h.flush();
  await h.button('Resume saved game').onClick(); await h.flush();
  assert.equal(h.render().props['data-forge-status'], 'restoring');
  assert.equal(h.button('Resume saved game').disabled, true); assert.equal(h.button('Save and pause').disabled, true);
  await h.button('Resume saved game').onClick(); assert.equal(posts(h).length, 1);
  const resume = JSON.parse(posts(h)[0].init.body);
  assert.deepEqual(Object.keys(resume).sort(), ['action_id', 'sequence']); assert.equal(resume.sequence, 4);
  assert.ok(h.timers.size > 0); assert.equal(h.choice(), undefined);
  assert.match(text(h.render()), /restoring/i);
  next = fixture(); next.sequence = 6; next.question.request_id = uuid(6);
  next.question.choices = [{token: uuid(7), display: 'button_ok'}];
  await h.tick();
  assert.equal(h.choice().disabled, false); assert.equal(h.choice().snapshot.question.request_id, uuid(6));
  assert.equal(h.render().props['data-forge-session'], uuid(9));
  await h.choice().onAnswer([uuid(7)]); await h.flush();
  const answer = JSON.parse(posts(h)[1].init.body);
  assert.deepEqual(answer.tokens, [uuid(7)]); assert.equal(answer.request_id, uuid(6)); assert.equal(answer.sequence, 6);
  assert.ok(h.calls.filter(c => c.url.includes('/sessions/')).every(c => c.init.headers.Authorization === `Bearer ${cap}`));
  assert.ok(!h.active.includes(false)); assert.equal(h.entries.size, 1);
});

test('reload during restoring only polls, without another resume or old-token choice', async t => {
  let next = paused('restoring', 5);
  const h = await harness(() => next); t.after(() => h.cleanup()); await h.flush();
  assert.equal(h.button('Resume saved game').disabled, true);
  assert.equal(h.button('Save and pause').disabled, true); assert.equal(h.choice(), undefined);
  assert.ok(h.timers.size > 0);
  next = fixture(); next.sequence = 6; next.question.request_id = uuid(6);
  await h.tick(); assert.equal(h.choice().snapshot.question.request_id, uuid(6));
  assert.equal(posts(h).length, 0);
});

test('lost checkpoint or resume delivery reconnects authoritatively without resending', async t => {
  for (const resume of [false, true]) {
    let next = resume ? paused() : fixture(), reconnect;
    const h = await harness((_url, init) => {
      if (init.method === 'POST') {next = resume ? paused('restoring', 5) : paused(); throw Error('SYNTHETIC lost control response');}
      return posts(h).length ? new Promise(resolve => {reconnect = resolve;}) : next;
    });
    t.after(() => h.cleanup()); await h.flush();
    const label = resume ? 'Resume saved game' : 'Save and pause';
    await h.button(label).onClick(); await h.flush();
    assert.equal(h.button(label).disabled, true);
    assert.match(text(h.render()), /Reconnect/); assert.equal(posts(h).length, 1);
    await h.button(label).onClick(); assert.equal(posts(h).length, 1);
    reconnect(next); await h.flush();
    assert.equal(h.render().props['data-forge-status'], resume ? 'restoring' : 'suspended');
    assert.equal(posts(h).length, 1); assert.ok(!h.active.includes(false));
  }
});

test('a running save response never claims a successful save and reconnect never retries it', async t => {
  const h = await harness(() => fixture()); t.after(() => h.cleanup()); await h.flush();
  await h.button('Save and pause').onClick(); await h.flush();
  assert.doesNotMatch(text(h.render()), /Saved and paused/);
  h.button('Reconnect native session').onClick(); await h.flush();
  assert.equal(posts(h).length, 1); assert.equal(h.render().props['data-forge-status'], 'running');
});

test('malformed, wrong-session and wrong-actor control responses cannot replace the authorized view', async t => {
  for (const resume of [false, true]) for (const mutate of [s => {s.private_journal = [];},
    s => {s.session_id = uuid(10);}, s => {s.actor_id = 19; s.state.actor_id = 19;}]) {
    const original = resume ? paused() : fixture(), bad = paused(resume ? 'restoring' : 'suspended', 5); mutate(bad);
    const h = await harness((_url, init) => init.method === 'POST' ? bad : original);
    t.after(() => h.cleanup()); await h.flush();
    await h.button(resume ? 'Resume saved game' : 'Save and pause').onClick(); await h.flush();
    assert.equal(h.render().props['data-forge-status'], resume ? 'suspended' : 'running');
    assert.equal(h.render().props['data-forge-session'], uuid(9));
    assert.equal(h.render().props['data-forge-sequence'], resume ? 4 : 3);
    assert.equal(posts(h).length, 1); assert.equal(h.entries.size, 1);
  }
});

test('a read begun before saving cannot regress a suspended snapshot or unlock controls', async t => {
  let reads = 0, finishRead, next = fixture();
  const h = await harness((_url, init) => {
    if (init.method === 'POST') return next = paused();
    if (++reads === 2) return new Promise(resolve => {finishRead = resolve;});
    return next;
  });
  t.after(() => h.cleanup()); await h.flush(); await h.tick();
  await h.button('Save and pause').onClick(); await h.flush();
  finishRead(fixture()); await h.flush();
  assert.equal(h.render().props['data-forge-status'], 'suspended');
  assert.equal(h.button('Save and pause').disabled, true); assert.equal(h.choice(), undefined);
  assert.equal(posts(h).length, 1);
});
