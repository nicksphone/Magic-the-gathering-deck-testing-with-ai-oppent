import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build, stop} from 'esbuild';
import {parseLegalMoves} from '../src/api/match-contract.ts';

// Generated once from immutable091 + reviewed backend cc98, real paid casts,
// legal_moves and serialize_match. Only public BF id/name and choice fields
// are retained. Remaining rendering props are protocol-only presentation
// defaults: this is not an HTTP, browser, or naturally played-game fixture.
const rows = [{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-037","p2-001"],"player_id":1,"type":"choose_mechanic"}],"phase":"paid-spell-two-distinct-same-name-options","public_battlefields":{"1":[{"id":"p1-037","name":"Sol Ring"}],"2":[{"id":"p2-001","name":"Sol Ring"}]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-037","p2-001"],"player_id":1},"seat":1},{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":[],"player_id":1,"type":"choose_mechanic"}],"phase":"paid-spell-no-eligible-permanent","public_battlefields":{"1":[],"2":[]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":[],"player_id":1},"seat":1},{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-013","p2-001"],"player_id":1,"type":"choose_mechanic"}],"phase":"real-two-copy-roster-first","public_battlefields":{"1":[{"id":"p1-013","name":"Sol Ring"}],"2":[{"id":"p2-001","name":"Sol Ring"}]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-013","p2-001"],"player_id":1},"seat":1},{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-013","p2-001"],"player_id":1,"type":"choose_mechanic"}],"phase":"real-two-copy-roster-second","public_battlefields":{"1":[{"id":"p1-013","name":"Sol Ring"}],"2":[{"id":"p2-001","name":"Sol Ring"}]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-013","p2-001"],"player_id":1},"seat":1},{"legal_moves":[],"phase":"real-two-copy-roster-completed","public_battlefields":{"1":[{"id":"p1-013","name":"Sol Ring"},{"id":"p1-006","name":"Sol Ring"},{"id":"p1-037","name":"Sculpting Steel"}],"2":[{"id":"p2-001","name":"Sol Ring"}]},"public_choice":null,"seat":1},{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-006","p2-052"],"player_id":2,"type":"choose_mechanic"}],"phase":"paid-spell-two-distinct-same-name-options","public_battlefields":{"1":[{"id":"p1-006","name":"Sol Ring"}],"2":[{"id":"p2-052","name":"Sol Ring"}]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-006","p2-052"],"player_id":2},"seat":2},{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":[],"player_id":2,"type":"choose_mechanic"}],"phase":"paid-spell-no-eligible-permanent","public_battlefields":{"1":[],"2":[]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":[],"player_id":2},"seat":2},{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-006","p2-024"],"player_id":2,"type":"choose_mechanic"}],"phase":"real-two-copy-roster-first","public_battlefields":{"1":[{"id":"p1-006","name":"Sol Ring"}],"2":[{"id":"p2-024","name":"Sol Ring"}]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-006","p2-024"],"player_id":2},"seat":2},{"legal_moves":[{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-006","p2-024"],"player_id":2,"type":"choose_mechanic"}],"phase":"real-two-copy-roster-second","public_battlefields":{"1":[{"id":"p1-006","name":"Sol Ring"}],"2":[{"id":"p2-024","name":"Sol Ring"}]},"public_choice":{"count":1,"kind":"entry_copy","label":"You may choose an artifact to copy as this permanent enters","min_count":0,"options":["p1-006","p2-024"],"player_id":2},"seat":2},{"legal_moves":[],"phase":"real-two-copy-roster-completed","public_battlefields":{"1":[{"id":"p1-006","name":"Sol Ring"}],"2":[{"id":"p2-024","name":"Sol Ring"},{"id":"p2-001","name":"Sol Ring"},{"id":"p2-052","name":"Sculpting Steel"}]},"public_choice":null,"seat":2}];
const require = createRequire(import.meta.url);
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const runtime = require('react/jsx-runtime');
const original = {jsx: runtime.jsx, jsxs: runtime.jsxs};
const buttons = [];
const built = await build({entryPoints: [new URL('../src/components/Controls.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', built.outputFiles[0].text)(require, module, module.exports);
for (const key of ['jsx', 'jsxs']) runtime[key] = (type, props, ...args) => {
  if (type === 'button') buttons.push(props);
  return original[key](type, props, ...args);
};
after(async () => { Object.assign(runtime, original); stop(); await globalThis[Symbol.for('mtg.build.guard')]?.closed(); });
const text = value => Array.isArray(value) ? value.map(text).join('')
  : value && typeof value === 'object' ? text(value.props?.children)
  : value == null || typeof value === 'boolean' ? '' : String(value);
const rowFor = (seat, phase) => structuredClone(rows.find(row => row.seat === seat && row.phase === phase));
function render(row, move = row.legal_moves[0]) {
  if (move) parseLegalMoves({player_id: row.seat, revision: 0, moves: [move]});
  const sent = [];
  const props = {decks: [], selectedA: null, selectedB: null, bestOf: 1, startMode: 'human_vs_human',
    humanSeat: row.seat, difficulty: 'normal', autoplayDelayMs: 1000, responseCountdown: null,
    autoResponsePaused: false, match: {id: 'entry-copy-public-projection', step: 'precombat_main',
      priority_player: row.seat, pending_mechanic_choice: row.public_choice,
      controllers: {'1': 'human', '2': 'human'},
      players: Object.fromEntries(Object.entries(row.public_battlefields).map(([seat, battlefield]) => [seat, {battlefield}]))},
    legalMoves: move ? [move] : [], onChooseMechanic: (seat, action) => sent.push({seat, action})};
  buttons.length = 0;
  const html = renderToStaticMarkup(React.createElement(module.exports.Controls, props));
  return {html, sent, buttons: [...buttons], target: id => buttons.find(button => button['data-entry-copy-id'] === id),
    decline: () => buttons.find(button => text(button.children) === 'Enter without copying')};
}

for (const seat of [1, 2]) {
  const phase = 'paid-spell-two-distinct-same-name-options';
  test(`P${seat} actual public entry-copy offer is supported without inferring a selection`, () => {
    const row = rowFor(seat, phase), before = JSON.stringify(row), ui = render(row);
    assert.equal(row.legal_moves[0].kind, 'entry_copy');
    assert.equal(Object.hasOwn(row.legal_moves[0], 'option_labels'), false);
    assert.equal(ui.html.includes('Unsupported mechanic choice:'), false);
    assert.equal(ui.html.includes('Confirm Selection'), false);
    assert.deepEqual(ui.sent, []); assert.equal(JSON.stringify(row), before);
  });
  test(`P${seat} duplicate printed names keep both real BF IDs and exact one-click callbacks`, () => {
    const row = rowFor(seat, phase), ui = render(row), move = row.legal_moves[0];
    assert.equal(move.options.length, 2); assert.equal(new Set(move.options).size, 2);
    for (const id of move.options) {
      const permanent = Object.values(row.public_battlefields).flat().find(card => card.id === id);
      const button = ui.target(id); assert.ok(button && !button.disabled);
      assert.ok(text(button.children).includes(permanent.name)); assert.ok(text(button.children).includes(id));
      button.onClick(); assert.deepEqual(ui.sent.pop(), {seat, action: {type: 'choose_mechanic', card_ids: [id]}});
      assert.deepEqual(ui.sent, []);
    }
  });
  test(`P${seat} explicit decline emits empty card_ids, never a guessed choice_id`, () => {
    const ui = render(rowFor(seat, phase)); assert.ok(ui.decline()); assert.deepEqual(ui.sent, []);
    ui.decline().onClick(); assert.deepEqual(ui.sent, [{seat, action: {type: 'choose_mechanic', card_ids: []}}]);
  });
  test(`P${seat} actual no-eligible-permanent offer still permits deliberate decline`, () => {
    const row = rowFor(seat, 'paid-spell-no-eligible-permanent'), ui = render(row);
    assert.deepEqual(row.legal_moves[0].options, []); assert.ok(ui.decline());
    assert.equal(ui.buttons.filter(button => button['data-entry-copy-id'] !== undefined).length, 0);
    ui.decline().onClick(); assert.deepEqual(ui.sent, [{seat, action: {type: 'choose_mechanic', card_ids: []}}]);
  });
  test(`P${seat} real two-copy roster requires another explicit choice and then removes controls`, () => {
    const first = rowFor(seat, 'real-two-copy-roster-first'), second = rowFor(seat, 'real-two-copy-roster-second');
    let ui = render(first); assert.deepEqual(ui.sent, []);
    const id = first.legal_moves[0].options[0]; assert.ok(ui.target(id)); ui.target(id).onClick();
    assert.deepEqual(ui.sent, [{seat, action: {type: 'choose_mechanic', card_ids: [id]}}]);
    ui = render(second); assert.deepEqual(ui.sent, []); assert.ok(ui.decline()); ui.decline().onClick();
    assert.deepEqual(ui.sent, [{seat, action: {type: 'choose_mechanic', card_ids: []}}]);
    const complete = rowFor(seat, 'real-two-copy-roster-completed'); assert.equal(complete.public_choice, null);
    ui = render(complete); assert.equal(ui.decline(), undefined); assert.deepEqual(ui.sent, []);
  });
  test(`P${seat} stale offered ID absent from public battlefield cannot dispatch`, () => {
    const row = rowFor(seat, phase), id = row.legal_moves[0].options[0];
    for (const player of Object.keys(row.public_battlefields)) row.public_battlefields[player] = row.public_battlefields[player].filter(card => card.id !== id);
    const ui = render(row), button = ui.target(id); assert.ok(button && button.disabled);
    button.onClick(); assert.deepEqual(ui.sent, []); assert.ok(ui.decline());
  });
  test(`P${seat} protocol-only unknown target ID is disabled rather than invented`, () => {
    const row = rowFor(seat, phase), move = {...row.legal_moves[0], options: ['not-on-the-public-battlefield']};
    const ui = render(row, move), button = ui.target(move.options[0]); assert.ok(button && button.disabled);
    button.onClick(); assert.deepEqual(ui.sent, []);
  });
  test(`P${seat} unsupported-kind warning remains unchanged`, () => {
    const row = rowFor(seat, phase), ui = render(row, {...row.legal_moves[0], kind: '__unknown_entry_copy_protocol__'});
    assert.ok(ui.html.includes('Unsupported mechanic choice:')); assert.equal(ui.decline(), undefined);
    assert.deepEqual(ui.sent, []);
  });
  test(`P${seat} protocol-only mandatory choice cannot acquire an optional decline`, () => {
    const row = rowFor(seat, phase), ui = render(row, {...row.legal_moves[0], min_count: 1});
    assert.equal(ui.decline(), undefined); assert.deepEqual(ui.sent, []);
  });
}

for (const kind of ['copy_target', 'spree_target_change']) {
  test(`existing ${kind} controls keep their exact labelled single-click payload`, async () => {
    const {readFile} = await import('node:fs/promises');
    const old = JSON.parse(await readFile(new URL('./fixtures/spree-public/continuations.json', import.meta.url)));
    const row = old.pending_rows.find(row => row.actual_legal_moves.some(move => move.kind === kind));
    assert.ok(row);
    const move = row.actual_legal_moves.find(move => move.kind === kind);
    const ui = render({seat: row.casting_player, legal_moves: [move], public_choice: row.actual_public_serialized_match.pending_mechanic_choice,
      public_battlefields: Object.fromEntries(Object.entries(row.actual_public_serialized_match.players).map(([seat, player]) => [seat, player.battlefield]))}, move);
    assert.equal(ui.decline(), undefined); assert.deepEqual(ui.sent, []);
    for (const id of move.options) {
      const button = ui.buttons.find(button => text(button.children) === (move.option_labels?.[id] ?? id));
      assert.ok(button); button.onClick();
      assert.deepEqual(ui.sent.pop(), {seat: row.casting_player, action: {type: 'choose_mechanic', card_ids: [id]}});
    }
  });
}
