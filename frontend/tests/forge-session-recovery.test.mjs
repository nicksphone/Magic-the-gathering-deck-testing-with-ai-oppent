// Synthetic HTTP/UI recovery contracts only; no app server, database or native game.
import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build, stop} from 'esbuild';
import {fixture, uuid} from './forge-session-fixtures.mjs';

after(stop);
const require = createRequire(import.meta.url);
const deck = {id: 1, name: 'SYNTHETIC deck', mainboard: [{quantity: 60, card_name: 'Island'}], sideboard: []};
const cap = 'a'.repeat(64);
const sessionKey = 'mtg.forge.session', pendingKey = 'mtg.forge.pendingStart';
const settle = () => new Promise(resolve => setImmediate(resolve));
const reject = (status, code) => new Response(JSON.stringify({detail: {code, message: 'SYNTHETIC rejection'}}), {status});
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  return value && typeof value === 'object' ? [value, ...nodes(value.props?.children)] : [];
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value == null || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props?.children) : String(value);
}
let componentBuild, apiBuild;
async function api() {
  apiBuild ??= build({entryPoints: [new URL('../src/api/forge.ts', import.meta.url).pathname], bundle: true,
    write: false, platform: 'node', format: 'esm', define: {'import.meta.env': '{}'}})
    .then(result => import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`));
  return apiBuild;
}
async function harness(reply, entries = new Map()) {
  const slots = [], effects = [], cleanups = new Map(), calls = [], active = [], timers = new Map();
  let index = 0;
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
    const result = url.endsWith('/status') ? {available: true} : await reply(url, init, storage);
    return result instanceof Response ? result : new Response(JSON.stringify(result));
  };
  new Function('require', 'module', 'exports', 'localStorage', 'fetch', 'window', await componentBuild)(
    name => name === 'react' ? {...require('react'), ...hooks} : require(name), module, module.exports, storage,
    fetcher, {setTimeout(fn) {const id = timers.size + 1; timers.set(id, fn); return id;}, clearTimeout(id) {timers.delete(id);}});
  const h = {calls, active, entries, storage,
    render() {index = 0; return module.exports.ForgeGame({deckA: deck, deckB: deck, humanSeat: 1, disabled: false,
      onActiveChange(value) {active.push(value); return true;}});},
    button(label) {const value = nodes(h.render()).find(n => n.type === 'button' && text(n.props.children) === label);
      assert.ok(value, `Missing button ${label}`); return value.props;},
    choice() {return nodes(h.render()).find(n => n.type === module.exports.ForgeChoices)?.props;},
    async flush() {for (let pass = 0; pass < 3; pass++) {h.render();
      for (const {i, fn} of effects.splice(0)) {cleanups.get(i)?.(); cleanups.set(i, fn());}
      await settle();}},
    cleanup() {for (const cleanup of cleanups.values()) cleanup?.();},
  };
  return h;
}
const identity = () => new Map([[sessionKey, JSON.stringify({session_id: uuid(9), capability: cap})]]);
const posts = h => h.calls.filter(call => call.init.method === 'POST');
async function open(h) {await h.flush(); h.button('Open native table').onClick(); await h.flush();}

test('a definitive stale-sequence reject unlocks only after authoritative reconnect, without resending', async t => {
  let reads = 0, resolveRead;
  const authoritative = fixture(); authoritative.sequence = 4;
  authoritative.last_answer = {action_id: 'parent', request_id: uuid(7), status: 'processed', reason: null};
  const h = await harness((_url, init) => init.method === 'POST' ? reject(409, 'stale_question')
    : reads++ === 0 ? fixture() : new Promise(resolve => {resolveRead = resolve;}), identity());
  t.after(() => h.cleanup()); await h.flush();
  await h.choice().onAnswer([uuid(2)]); await h.flush();
  assert.equal(h.choice().disabled, true, 'Do not unlock before the reconnect finishes');
  assert.equal(posts(h).length, 1);
  resolveRead(authoritative); await h.flush();
  assert.equal(h.choice().disabled, false, 'A pre-write rejection must not fence the unchanged question');
  assert.equal(posts(h).length, 1, 'Reconnect must not resend the answer');
});

test('a definitive reject does not clear or fence a newer authoritative question', async t => {
  let next = fixture();
  const h = await harness((_url, init) => init.method === 'POST' ? reject(409, 'stale_question') : next, identity());
  t.after(() => h.cleanup()); await h.flush();
  next = fixture(); next.sequence = 5; next.question.request_id = uuid(6);
  await h.choice().onAnswer([uuid(2)]); await h.flush();
  assert.equal(h.choice().snapshot.question.request_id, uuid(6));
  assert.equal(h.choice().disabled, false);
  assert.equal(posts(h).length, 1);
});

test('lost answers and ambiguous HTTP errors remain fenced after reconnect to the same question', async t => {
  for (const status of [null, 408, 429, 500, 503, 404, 409, 422]) {
    const h = await harness((_url, init) => {
      if (init.method !== 'POST') return fixture();
      if (status === null) throw Error('SYNTHETIC lost response');
      return reject(status, status === 409 ? 'action_conflict' : 'stale_question');
    }, identity());
    t.after(() => h.cleanup()); await h.flush();
    await h.choice().onAnswer([uuid(2)]); await h.flush();
    h.button('Reconnect native session').onClick(); await h.flush();
    assert.equal(h.choice().disabled, true, `Ambiguous status ${status} must stay fenced`);
    assert.equal(posts(h).length, 1);
  }
});

test('fresh start rejects unsafe upstream names before storing any intent', async () => {
  const {prepareForgeStart} = await api();
  for (const bad of ['[Control]', 'bad\u2028name', 'bad\u2029name', 'bad\tname', 'bad\x7fname', '\ud800']) {
    for (const cardName of [false, true]) {
      const entries = new Map(), storage = {getItem: key => entries.get(key) ?? null,
        setItem: (key, value) => entries.set(key, value), removeItem: key => entries.delete(key)};
      const invalid = cardName ? {...deck, mainboard: [{quantity: 60, card_name: bad}]} : {...deck, name: bad};
      assert.throws(() => prepareForgeStart(storage, invalid, deck, 1), /deck|name/i);
      assert.equal(entries.size, 0, 'Unsafe names must not create a persisted pending start');
    }
  }
});

test('a definite prelaunch 422 clears its own pending intent and releases the Python fence', async t => {
  const h = await harness(() => reject(422, 'invalid_deck'));
  t.after(() => h.cleanup()); await open(h);
  await h.button('Start native single game').onClick(); await h.flush();
  assert.equal(h.entries.has(pendingKey), false);
  assert.equal(h.entries.has(sessionKey), false);
  assert.deepEqual(h.active, [true, false]);
  assert.equal(h.button('Start native single game').disabled, false);
  assert.match(text(h.render()), /reject.*before|before.*launch|not.*created/i);
  assert.equal(posts(h).length, 1);
});

test('unknown start delivery retains exact recovery body, key and capability until explicit recovery', async t => {
  for (const status of [null, 408, 429, 500, 503, 409, 404, 422]) {
    let attempts = 0;
    const h = await harness((_url, init) => {
      if (init.method !== 'POST') return fixture();
      if (++attempts > 1) return fixture();
      if (status === null) throw Error('SYNTHETIC lost start');
      return reject(status, status === 409 ? 'start_conflict' : status === 422 ? 'unknown_start' : 'invalid_deck');
    });
    t.after(() => h.cleanup()); await open(h);
    await h.button('Start native single game').onClick(); await h.flush();
    const saved = h.entries.get(pendingKey);
    assert.ok(saved, `Ambiguous status ${status} must preserve start recovery`);
    assert.deepEqual(h.active, [true]); assert.equal(posts(h).length, 1);
    await h.button('Recover native start').onClick(); await h.flush();
    assert.equal(posts(h).length, 2);
    assert.equal(posts(h)[0].init.body, posts(h)[1].init.body);
    assert.equal(posts(h)[0].init.headers.Authorization, posts(h)[1].init.headers.Authorization);
    assert.equal(posts(h)[0].init.headers['Idempotency-Key'], posts(h)[1].init.headers['Idempotency-Key']);
    assert.equal(h.entries.has(pendingKey), false); assert.ok(h.entries.has(sessionKey));
  }
});

test('a rejected old start cannot discard a different pending intent or an existing session', async t => {
  for (const existingSession of [false, true]) {
    let replacement;
    const h = await harness((_url, _init, storage) => {
      const intent = JSON.parse(storage.getItem(pendingKey));
      replacement = {...intent, key: 'other-start', capability: 'b'.repeat(64)};
      storage.setItem(pendingKey, JSON.stringify(replacement));
      if (existingSession) storage.setItem(sessionKey, JSON.stringify({session_id: uuid(9), capability: cap}));
      return reject(422, 'invalid_deck');
    });
    t.after(() => h.cleanup()); await open(h);
    await h.button('Start native single game').onClick(); await h.flush();
    assert.deepEqual(JSON.parse(h.entries.get(pendingKey)), replacement);
    assert.equal(h.entries.has(sessionKey), existingSession);
    assert.deepEqual(h.active, [true]);
  }
});

test('HTTP rejection classification does not echo server private messages', async () => {
  const {createForgeClient, ForgeHttpError} = await api();
  const client = createForgeClient('/api', async () => new Response(JSON.stringify({detail: {
    code: 'stale_question', message: 'PRIVATE operator path'}}), {status: 409}));
  await assert.rejects(client.answer(uuid(9), cap, {}), error => error instanceof ForgeHttpError
    && error.code === 'stale_question' && !error.message.includes('PRIVATE'));
});
