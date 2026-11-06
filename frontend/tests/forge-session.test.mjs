import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {build, stop} from 'esbuild';

import {fixture, uuid} from './forge-session-fixtures.mjs';

after(stop);
let built;
const api = () => built ??= build({entryPoints: [new URL('../src/api/forge.ts', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'esm', define: {'import.meta.env.VITE_API_BASE_URL': '"/api"'}})
  .then(result => import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`));
test('strict native snapshot accepts the authorized schema, not Python state or private envelopes', async () => {
  const {parseForgeSnapshot} = await api();
  assert.deepEqual(parseForgeSnapshot(fixture()), fixture());
  for (const mutate of [s => {s.private_journal = [];}, s => {delete s.info;}, s => {s.sequence = true;},
    s => {s.question.actor_id = 19;}, s => {s.state.actor_id = 19;},
    s => {s.state.players[1].player_id = 8;}, s => {s.question.min = 3;},
    s => {s.question.choices[1].token = s.question.choices[0].token;},
    s => {s.info.argv = ['/secret'];}, s => {s.state.players[0].zones.Hand.visible_cards[0].private = 'secret';},
    s => {s.question.choices[0].display = {type: 'play_land', card_id: 'python-id'};},
    s => {s.status = 'completed';}, s => {s.result = {outcomes: [], turns: 1, draw: false, win_condition: 'AllOpponentsLost'};}]) {
    const value = fixture(); mutate(value);
    assert.throws(() => parseForgeSnapshot(value), /Invalid Forge/);
  }
});

function metadata() {
  return {input: 'InputSelectCardsFromList', generation: 1, priority_epoch: 2, revision: 3, actor: 8,
    chosen: [fixture().state.players[0].zones.Hand.visible_cards[0], {player_id: 19, name: 'Native AI'}]};
}
test('native input metadata preserves chosen cards and players without requiring the selection minimum yet', async () => {
  const {parseForgeSnapshot} = await api();
  const s = fixture(); s.info.selection = {...metadata(), min: 3, max: 4};
  s.info.stack_selection = {...metadata(), input: 'InputSelectStack', chosen: [s.state.stack[0]]};
  assert.deepEqual(parseForgeSnapshot(s), s);
  for (const key of ['selection', 'stack_selection']) {
    s.info[key].chosen = [];
    assert.deepEqual(parseForgeSnapshot(s), s);
  }
});
test('malformed nested selection metadata fails in the parser with a clean error', async () => {
  const {parseForgeSnapshot} = await api();
  for (const key of ['selection','stack_selection']) {
    const valid = key === 'selection' ? {...metadata(), min: 0, max: 3} : {...metadata(), chosen: [fixture().state.stack[0]]};
    const variants = [null, [], 'bad', {}, {...valid, extra: true}, {...valid, chosen: null}, {...valid, chosen: {}},
      {...valid, chosen: [null]}, {...valid, chosen: [true]}, {...valid, chosen: ['card-id']},
      {...valid, chosen: [{card_id: 42}]}, {...valid, chosen: [{player_id: 19, name: 0}]},
      {...valid, chosen: [{hidden: false}]}, {...valid, chosen: Array(1001).fill(valid.chosen[0])},
      {...valid, actor: 19}, {...valid, actor: true}, {...valid, input: {}},
      ...['generation','priority_epoch','revision'].flatMap(field => [-1, true, 0.5, '1', null, Number.MAX_SAFE_INTEGER + 1]
        .map(value => ({...valid, [field]: value}))),
      ...Object.keys(valid).map(field => {const missing = {...valid}; delete missing[field]; return missing;})];
    if (key === 'selection') variants.push({...valid, min: -1}, {...valid, max: true}, {...valid, min: 4, max: 3}, {...valid, max: 1});
    for (const value of variants) {
      const s = fixture(); s.info[key] = value;
      assert.throws(() => parseForgeSnapshot(s), error => error instanceof Error && !(error instanceof TypeError)
        && /Invalid Forge/.test(error.message), `${key} malformed metadata must be rejected before rendering`);
    }
  }
});
test('option labels match the complete numeric choice domain without blocking unlabelled numeric choices', async () => {
  const {parseForgeSnapshot, forgeChoiceLabel} = await api();
  const s = fixture(); s.question.kind = 'showOptionDialog';
  s.question.choices = [{token: uuid(2), display: 1}, {token: uuid(3), display: 0}];
  s.info.labels = ['First', 'Second'];
  assert.deepEqual(parseForgeSnapshot(s), s);
  assert.equal(forgeChoiceLabel(s.question.choices[0].display, s.info), 'Second');
  for (const labels of [null, {}, ['Only one'], ['First','Second','Extra'], ['First',42]]) {
    assert.throws(() => parseForgeSnapshot({...s, info: {...s.info, labels}}), /Invalid Forge/);
  }
  for (const index of [-1, 2, 0.5, true, '1', 0]) {
    const bad = structuredClone(s); bad.question.choices[0].display = index;
    assert.throws(() => parseForgeSnapshot(bad), /Invalid Forge/);
  }
  delete s.info.labels; s.question.choices[0].display = -5;
  assert.deepEqual(parseForgeSnapshot(s), s);
});

test('native replies validate offered UUIDs, bounds, explicit empties and preserve order', async () => {
  const {makeForgeAnswer} = await api();
  const s = fixture();
  assert.deepEqual(makeForgeAnswer(s, [uuid(2)], 'action-1'), {request_id: uuid(1), tokens: [uuid(2)], sequence: 3, action_id: 'action-1'});
  for (const tokens of [[], [uuid(8)], [uuid(2),uuid(2)], [uuid(2),uuid(3)]]) {
    assert.throws(() => makeForgeAnswer(s, tokens, 'action-1'), /native selection/);
  }
  s.question.kind = 'order'; s.question.min = s.question.max = 2;
  assert.deepEqual(makeForgeAnswer(s, [uuid(3),uuid(2)], 'order-1').tokens, [uuid(3),uuid(2)]);
  s.question.min = 0;
  assert.deepEqual(makeForgeAnswer(s, [], 'empty-1').tokens, []);
});

test('receipts never imply a cast; an outstanding parent does not block a new question', async () => {
  const {parseForgeSnapshot, canAnswerForge, newerForgeSnapshot} = await api();
  for (const status of ['submitted','processing','processed','rejected','uncertain']) {
    const s = fixture(); s.last_answer = {action_id: 'a', request_id: uuid(7), status, reason: null};
    assert.ok(canAnswerForge(parseForgeSnapshot(s)));
    s.last_answer.request_id = s.question.request_id;
    assert.equal(canAnswerForge(s), status === 'rejected');
  }
  const current = fixture(), old = fixture(); old.sequence--;
  assert.equal(newerForgeSnapshot(current, old), current);
  const foreign = fixture(); foreign.session_id = uuid(10);
  assert.throws(() => newerForgeSnapshot(current, foreign), /session/);
  const wrongActor = fixture(); wrongActor.actor_id = 19;
  assert.throws(() => newerForgeSnapshot(current, wrongActor), /actor/);
});

test('capabilities stay in protected headers; GETs do not mutate and POST is never retried', async () => {
  const {createForgeClient} = await api();
  const calls = [], cap = 'a'.repeat(64);
  const client = createForgeClient('/api', async (url, init) => {
    calls.push({url, init});
    return new Response(JSON.stringify(url.endsWith('/status') ? {available: true} : fixture()), {status: 200});
  });
  assert.deepEqual(await client.status(), {available: true});
  await client.get(uuid(9), cap); await client.answer(uuid(9), cap, {request_id: uuid(1), tokens: [uuid(2)], sequence: 3, action_id: 'a'});
  await client.close(uuid(9), cap);
  assert.deepEqual(calls.map(c => c.init.method), ['GET','GET','POST','DELETE']);
  for (const {url, init} of calls) {
    assert.ok(!url.includes(cap)); assert.equal(init.cache, 'no-store');
    assert.equal(init.redirect, 'error');
  }
  assert.equal(calls[0].init.headers.Authorization, undefined);
  assert.equal(calls[1].init.headers.Authorization, `Bearer ${cap}`);
  let count = 0;
  const unavailable = createForgeClient('/api', async () => {count++; throw new Error(cap);});
  await assert.rejects(unavailable.answer(uuid(9), cap, {}), error => !String(error).includes(cap));
  assert.equal(count, 1);
});

test('lost start recovery retains the exact body, key and capability in private storage only', async () => {
  const {prepareForgeStart, readForgeSaved, rememberForgeSession, clearForgeSaved, createForgeClient} = await api();
  const entries = new Map(), storage = {getItem: k => entries.get(k) ?? null,
    setItem: (k,v) => entries.set(k,v), removeItem: k => entries.delete(k)};
  entries.set('mtg.activeMatch', 'legacy-match');
  const deck = {name: 'Selected deck', mainboard: [{quantity: 60, card_name: 'Island'}], sideboard: []};
  const intent = prepareForgeStart(storage, deck, deck, 2);
  assert.match(intent.capability, /^[0-9a-f]{64}$/);
  assert.equal(intent.payload.human_seat, 1);
  assert.deepEqual(readForgeSaved(storage).pending, intent);
  const calls = [];
  const client = createForgeClient('/api', async (url, init) => {calls.push({url,init}); return new Response(JSON.stringify(fixture()));});
  await client.start(intent); await client.start(readForgeSaved(storage).pending);
  assert.equal(calls[0].init.body, calls[1].init.body);
  assert.equal(calls[0].init.headers['Idempotency-Key'], calls[1].init.headers['Idempotency-Key']);
  rememberForgeSession(storage, fixture().session_id, intent.capability);
  assert.equal(readForgeSaved(storage).pending, null);
  assert.equal(readForgeSaved(storage).session.capability, intent.capability);
  clearForgeSaved(storage);
  assert.deepEqual([...entries], [['mtg.activeMatch', 'legacy-match']]);
  assert.throws(() => prepareForgeStart(storage, {...deck, mainboard: [{quantity: 60, card_name: '[Sideboard]\n60 Island'}]}, deck, 1), /deck/);
  assert.throws(() => prepareForgeStart({...storage, setItem() {throw Error('blocked');}}, deck, deck, 1), /storage/);
});

test('saved 60-card mains with stored sideboards export only copied mains without changing any saved bytes', async () => {
  const {prepareForgeStart, createForgeClient} = await api();
  const a = {id: 11, name: 'Saved A', source: 'user', archetype_guess: 'SYNTHETIC',
    mainboard: [{quantity: 36, card_name: 'Island'}, {quantity: 24, card_name: 'Forest'}],
    sideboard: [{quantity: 15, card_name: 'Counterspell'}]};
  const b = {...a, id: 12, name: 'Saved B', mainboard: [{quantity: 60, card_name: 'Mountain'}],
    sideboard: [{quantity: 15, card_name: 'Pyroblast'}]};
  const originalBytes = Buffer.from(JSON.stringify([a,b]));
  const sideboardBytes = Buffer.from(JSON.stringify([a.sideboard,b.sideboard]));
  for (const saved of [a,b]) {
    for (const rows of [saved.mainboard,saved.sideboard]) {rows.forEach(Object.freeze); Object.freeze(rows);}
    Object.freeze(saved);
  }
  const entries = new Map(), storage = {getItem: k => entries.get(k) ?? null,
    setItem: (k,v) => entries.set(k,v), removeItem: k => entries.delete(k)};
  const intent = prepareForgeStart(storage, a, b, 1);
  assert.deepEqual(intent.payload, {deck_a: a.mainboard, deck_b: b.mainboard, name_a: a.name, name_b: b.name, human_seat: 0});
  assert.notEqual(intent.payload.deck_a, a.mainboard);
  assert.notEqual(intent.payload.deck_a[0], a.mainboard[0]);
  let body;
  const client = createForgeClient('/api', async (_url, init) => {body = JSON.parse(init.body); return new Response(JSON.stringify(fixture()));});
  await client.start(intent);
  assert.deepEqual(body, intent.payload);
  assert.deepEqual(Object.keys(body).sort(), ['deck_a','deck_b','human_seat','name_a','name_b']);
  assert.deepEqual(Buffer.from(JSON.stringify([a,b])), originalBytes);
  assert.deepEqual(Buffer.from(JSON.stringify([a.sideboard,b.sideboard])), sideboardBytes);
  assert.ok(!JSON.stringify(body).includes('Counterspell') && !JSON.stringify(body).includes('Pyroblast'));
});

test('a corrupt pending record cannot discard a valid saved native capability', async () => {
  const {readForgeSaved} = await api();
  const identity = {session_id: uuid(9), capability: 'a'.repeat(64)};
  const entries = new Map([['mtg.forge.session', JSON.stringify(identity)], ['mtg.forge.pendingStart', '{broken']]);
  assert.deepEqual(readForgeSaved({getItem: k => entries.get(k) ?? null}), {session: identity, pending: null});
});

test('protected responses bind the requested session; read cancellation retains its deadline', async () => {
  const {createForgeClient} = await api();
  const foreign = fixture(); foreign.session_id = uuid(10);
  const calls = [], client = createForgeClient('/api', async (_url, init) => {
    calls.push(init); return new Response(JSON.stringify(foreign));
  });
  const controller = new AbortController();
  await assert.rejects(client.get(uuid(9), 'a'.repeat(64), controller.signal), /session/);
  assert.notEqual(calls[0].signal, controller.signal, 'Combine cancellation with the bounded read deadline');
  controller.abort(); assert.equal(calls[0].signal.aborted, true);
});
