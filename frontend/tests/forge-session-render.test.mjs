import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {build, stop} from 'esbuild';
import {fixture, uuid} from './forge-session-fixtures.mjs';

after(stop);
const require = createRequire(import.meta.url);
function nodes(v) {
  if (Array.isArray(v)) return v.flatMap(nodes);
  return v && typeof v === 'object' ? [v, ...nodes(v.props?.children)] : [];
}
function text(v) {
  if (Array.isArray(v)) return v.map(text).join('');
  if (v == null || typeof v === 'boolean') return '';
  return typeof v === 'object' ? text(v.props?.children) : String(v);
}
function button(tree, label) {
  const found = nodes(tree).find(n => n.type === 'button' && text(n.props.children) === label);
  assert.ok(found, `Missing button ${label}`); return found.props;
}
const settle = () => new Promise(resolve => setImmediate(resolve));
const deck = {id: 1, name: 'SYNTHETIC selected deck', mainboard: [{quantity: 60, card_name: 'Island'}], sideboard: []};

async function harness(name, props, entries = new Map(), reply = () => fixture()) {
  const calls = [], effects = [], cleanups = [], slots = [], timers = new Map();
  let index = 0;
  const storage = {getItem: k => entries.get(k) ?? null, setItem: (k,v) => entries.set(k,v), removeItem: k => entries.delete(k)};
  const hooks = {
    useState(initial) { const i = index++; if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
      return [slots[i], v => {slots[i] = typeof v === 'function' ? v(slots[i]) : v;}]; },
    useRef(initial) { const i = index++; if (!(i in slots)) slots[i] = {current: initial}; return slots[i]; },
    useCallback: fn => fn,
    useEffect(fn, deps) { const i = index++; if (!slots[i] || !deps || deps.some((d,j) => d !== slots[i][j])) {slots[i] = deps; effects.push(fn);} },
  };
  const fetcher = async (url, init) => {
    calls.push({url, init});
    const value = url.endsWith('/status') ? {available: true} : await reply(url, init);
    return new Response(JSON.stringify(value), {status: 200});
  };
  const built = await build({entryPoints: [new URL('../src/components/ForgeGame.tsx', import.meta.url).pathname],
    bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
    loader: {'.css': 'empty'}, define: {'import.meta.env': '{}'}});
  const module = {exports: {}};
  const window = {setTimeout(fn) {const id = timers.size + 1; timers.set(id,fn); return id;}, clearTimeout(id) {timers.delete(id);}};
  new Function('require','module','exports','localStorage','fetch','window',built.outputFiles[0].text)(
    n => n === 'react' ? {...require('react'), ...hooks} : require(n), module, module.exports, storage, fetcher, window);
  return {
    calls, entries, exports: module.exports,
    render() { index = 0; return module.exports[name](props); },
    async effects() { for (const fn of effects.splice(0)) {const cleanup = fn(); if (cleanup) cleanups.push(cleanup);} await settle(); },
    cleanup() {for (const fn of cleanups.splice(0)) fn();},
  };
}

test('native scalar choice buttons submit only the clicked opaque token and never default', async () => {
  const answers = [], s = fixture();
  const h = await harness('ForgeChoices', {snapshot: s, disabled: false, onAnswer: tokens => answers.push(tokens)});
  const tree = h.render(); assert.deepEqual(answers, []);
  button(tree, 'Pass').onClick(); assert.deepEqual(answers, [[uuid(3)]]);
  assert.match(text(tree), /Choose a native action/);
  assert.doesNotMatch(text(tree), /cast succeeded|cast successful/i);
});

test('multi/order selection starts empty, respects counts and offers explicit reordering', async () => {
  const answers = [], s = fixture(); s.question.kind = 'order'; s.question.min = s.question.max = 2;
  const h = await harness('ForgeChoices', {snapshot: s, disabled: false, onAnswer: tokens => answers.push(tokens)});
  assert.equal(button(h.render(), 'Submit native selection').disabled, true);
  let checks = nodes(h.render()).filter(n => n.type === 'input');
  assert.ok(checks.every(n => n.props.checked === false));
  checks[0].props.onChange(); h.render(); checks = nodes(h.render()).filter(n => n.type === 'input');
  checks[1].props.onChange();
  let tree = h.render(); assert.equal(button(tree, 'Submit native selection').disabled, false);
  button(tree, 'Move selection 2 up').onClick(); tree = h.render();
  button(tree, 'Submit native selection').onClick();
  assert.deepEqual(answers, [[uuid(3), uuid(2)]]);
  s.question.min = 0;
  const optional = await harness('ForgeChoices', {snapshot: s, disabled: false, onAnswer: tokens => answers.push(tokens)});
  button(optional.render(), 'Submit native selection').onClick(); assert.deepEqual(answers.at(-1), []);
});

test('native board renders native identities, own hand, public stack, life and phase without Python projection', async () => {
  const h = await harness('ForgeBoard', {snapshot: fixture()});
  // Use React's real server renderer for the complete board subtree.
  const {renderToStaticMarkup} = require('react-dom/server');
  const html = renderToStaticMarkup(h.render());
  assert.match(html, /SYNTHETIC Island/); assert.match(html, /Native AI/);
  assert.match(html, /MAIN1/); assert.match(html, /20/); assert.match(html, /Stack/);
  assert.match(html, /53/); assert.doesNotMatch(html, /python-id|play_land/);
});

test('native creature cards show returned power and toughness, not guessed combat stats', async () => {
  const s = fixture(), card = s.state.players[0].zones.Hand.visible_cards[0];
  card.face.type = 'Artifact Creature - SYNTHETIC'; card.face.power = -1; card.face.toughness = 5;
  const h = await harness('ForgeBoard', {snapshot: s});
  const html = require('react-dom/server').renderToStaticMarkup(h.render());
  assert.match(html, /Power \/ toughness: -1 \/ 5/);
});

test('StrictMode mount/remount only reads; saved session reconnects with its original capability', async () => {
  const entries = new Map([['mtg.forge.session', JSON.stringify({session_id: uuid(9), capability: 'a'.repeat(64)})]]);
  for (let i = 0; i < 2; i++) {
    const h = await harness('ForgeGame', {deckA: deck, deckB: deck, humanSeat: 1, disabled: false, onActiveChange: () => true}, entries);
    h.render(); await h.effects(); h.render(); await h.effects(); h.cleanup();
    assert.ok(h.calls.length > 0); assert.ok(h.calls.every(c => c.init.method === 'GET'));
    const get = h.calls.find(c => c.url.includes('/sessions/'));
    assert.ok(get); assert.equal(get.init.headers.Authorization, `Bearer ${'a'.repeat(64)}`);
    assert.equal(entries.size, 1);
  }
});

test('lost start response recovers only by explicit click with identical start intent', async () => {
  let post = 0; const active = [];
  const h = await harness('ForgeGame', {deckA: deck, deckB: deck, humanSeat: 2, disabled: false,
    onActiveChange: value => {active.push(value); return true;}}, new Map(), (_url, init) => {
    if (init.method === 'POST' && ++post === 1) throw Error('lost response'); return fixture();
  });
  h.render(); await h.effects();
  button(h.render(), 'Open native table').onClick(); h.render(); await h.effects();
  await button(h.render(), 'Start native single game').onClick(); await settle();
  assert.equal(active[0], true);
  assert.equal(h.calls.filter(c => c.init.method === 'POST').length, 1);
  assert.ok(h.entries.has('mtg.forge.pendingStart'));
  await button(h.render(), 'Recover native start').onClick(); await settle();
  const starts = h.calls.filter(c => c.init.method === 'POST');
  assert.equal(starts.length, 2); assert.equal(starts[0].init.body, starts[1].init.body);
  assert.equal(starts[0].init.headers.Authorization, starts[1].init.headers.Authorization);
  assert.equal(starts[0].init.headers['Idempotency-Key'], starts[1].init.headers['Idempotency-Key']);
  assert.ok(h.entries.has('mtg.forge.session')); assert.ok(!h.entries.has('mtg.forge.pendingStart'));
  h.cleanup();
});

test('legacy default mount makes no Forge requests until explicit opt-in', async () => {
  const h = await harness('ForgeGame', {deckA: deck, deckB: deck, humanSeat: 1, disabled: false, onActiveChange: () => true});
  h.render(); await h.effects(); assert.deepEqual(h.calls, []);
  button(h.render(), 'Open native table').onClick(); h.render(); await h.effects();
  assert.deepEqual(h.calls.map(c => [c.url, c.init.method]), [['/api/forge/status', 'GET']]);
  h.cleanup();
});

test('native entry labels experimental single-game scope, actual AI and Forge attribution', async () => {
  const h = await harness('ForgeGame', {deckA: deck, deckB: deck, humanSeat: 1, disabled: false, onActiveChange: () => true});
  const content = text(h.render());
  for (const label of ['Experimental', 'Default Forge heuristic', 'Master', 'Single game', 'open decklists',
    'No BO3 or cold app restore', 'Powered by Forge Team / Card-Forge']) assert.ok(content.includes(label), `Missing ${label}`);
  h.cleanup();
});

test('stored sideboards do not disable native start and the UI explains their omission', async () => {
  const withSideboard = {...deck, sideboard: [{quantity: 15, card_name: 'Counterspell'}]};
  const before = JSON.stringify(withSideboard);
  const h = await harness('ForgeGame', {deckA: withSideboard, deckB: withSideboard, humanSeat: 1, disabled: false, onActiveChange: () => true});
  button(h.render(), 'Open native table').onClick(); h.render(); await h.effects();
  const tree = h.render();
  assert.equal(button(tree, 'Start native single game').disabled, false);
  assert.ok(text(tree).includes('Sideboards are not used in this single-game preview; saved decklists are unchanged.'));
  await button(tree, 'Start native single game').onClick();
  const body = JSON.parse(h.calls.find(c => c.init.method === 'POST').init.body);
  assert.deepEqual(Object.keys(body).sort(), ['deck_a','deck_b','human_seat','name_a','name_b']);
  assert.equal(JSON.stringify(withSideboard), before);
  h.cleanup();
});

test('uncertain answer is not resent; a new question remains usable while the parent is processing', async () => {
  const entries = new Map([['mtg.forge.session', JSON.stringify({session_id: uuid(9), capability: 'a'.repeat(64)})]]);
  let next = fixture();
  const h = await harness('ForgeGame', {deckA: deck, deckB: deck, humanSeat: 1, disabled: false, onActiveChange: () => true}, entries,
    (_url, init) => { if (init.method === 'POST') throw Error('lost answer'); return next; });
  h.render(); await h.effects();
  const choice = () => nodes(h.render()).find(n => n.type === h.exports.ForgeChoices);
  await choice().props.onAnswer([uuid(2)]); await h.effects();
  assert.equal(choice().props.disabled, true);
  await choice().props.onAnswer([uuid(2)]);
  assert.equal(h.calls.filter(c => c.init.method === 'POST').length, 1);
  next = fixture(); next.sequence = 5; next.question.request_id = uuid(6);
  next.last_answer = {action_id: 'old-parent', request_id: uuid(1), status: 'processing', reason: null};
  button(h.render(), 'Reconnect native session').onClick(); h.render(); await h.effects();
  assert.equal(choice().props.disabled, false);
  await choice().props.onAnswer([uuid(3)]);
  assert.equal(h.calls.filter(c => c.init.method === 'POST').length, 2);
  const container = h.render();
  assert.equal(container.props['data-forge-session'], uuid(9));
  assert.equal(container.props['data-forge-sequence'], 5);
  assert.ok(!text(container).includes('a'.repeat(64)));
  h.cleanup();
});

test('a late GET after explicit close cannot resurrect the native session or board', async () => {
  const entries = new Map([['mtg.forge.session', JSON.stringify({session_id: uuid(9), capability: 'a'.repeat(64)})]]);
  const active = []; let resolveRead;
  const h = await harness('ForgeGame', {deckA: deck, deckB: deck, humanSeat: 1, disabled: false,
    onActiveChange: value => {active.push(value); return true;}}, entries, (_url, init) => {
    if (init.method === 'GET') return new Promise(resolve => {resolveRead = resolve;});
    const s = fixture(); s.status = 'aborted'; s.question = null; s.sequence = 4; return s;
  });
  h.render(); await h.effects();
  await button(h.render(), 'Close native session').onClick();
  resolveRead(fixture()); await settle();
  assert.equal(entries.size, 0); assert.equal(active.at(-1), false);
  assert.equal(nodes(h.render()).filter(n => n.type === h.exports.ForgeBoard).length, 0);
  assert.equal(h.render().props['data-forge-session'], '');
  h.cleanup();
});

test('App gates legacy mutation/start/autoplay and hides Python board during native activation', () => {
  const source = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
  assert.match(source, /nativeActiveRef/);
  for (const name of ['mutateMatch','startMatch','resumeMatch']) {
    const start = source.indexOf(`${name} =` ) >= 0 ? source.indexOf(`${name} =`) : source.indexOf(`function ${name}(`);
    assert.ok(start >= 0); assert.match(source.slice(start, start + 400), /nativeActiveRef\.current/);
  }
  assert.match(source, /<ForgeGame/);
  assert.match(source, /disabled=\{nativeActive \|\| mutationPending \|\| restoring\}/);
  assert.match(source, /!nativeActive && match/);
  assert.ok((source.match(/nativeActiveRef\.current/g) ?? []).length >= 9);
  assert.match(source, /match \|\| nativeActive \? "workspace-match"/);
  assert.match(source, /nativeActive \? <section[^>]*aria-label="Paused Python table"/);
  assert.match(source, /href="#forge-native-choice"/);
});
