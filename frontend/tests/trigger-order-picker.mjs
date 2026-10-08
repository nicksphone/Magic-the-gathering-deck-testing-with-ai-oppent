import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const require = createRequire(import.meta.url);
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
async function compile(file, imports = require) {
  const built = await build({entryPoints: [new URL(file, import.meta.url).pathname], bundle: true,
    write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
    define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
  const module = {exports: {}};
  new Function('require', 'module', 'exports', built.outputFiles[0].text)(imports, module, module.exports);
  return module.exports;
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const rows = JSON.parse(execFileSync(python, [path.join(root, 'frontend/tests/trigger-order-engine.py')], {
  cwd: path.join(root, 'backend'), encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'},
}));
const ids = rows[0].move.trigger_order;
const labels = rows[0].move.trigger_labels;
const {Controls} = await compile('../src/components/Controls.tsx');
for (const {seat, move} of rows) {
  const html = renderToStaticMarkup(React.createElement(Controls, {
    decks: [], selectedA: null, selectedB: null, bestOf: 1, startMode: 'human_vs_human', humanSeat: seat,
    difficulty: 'master', autoplayDelayMs: 1000, responseCountdown: null, autoResponsePaused: false,
    match: {id: 1, priority_player: seat, pending_trigger_order: {current_controller: seat, event: 'enters_battlefield'}},
    legalMoves: [move],
  }));
  assert.ok(html.includes('Choose triggers from bottom to top'), 'Large groups need arbitrary ordering, not just the single enumerated order');
}
const controlled = await compile('../src/components/Controls.tsx', name => name === 'react'
  ? {...React, useState: initial => [initial, () => {}], useMemo: fn => fn(), useEffect: () => {}} : require(name));
const base = {decks: [], bestOf: 1, startMode: 'human_vs_human', humanSeat: 1,
  difficulty: 'master', autoplayDelayMs: 1000, responseCountdown: null, autoResponsePaused: false,
  match: {id: 1, revision: 1, pending_trigger_order: {current_controller: 1}},
  legalMoves: [rows[0].move]};
function pickerElement(props) {
  const found = [];
  function walk(node) {
    if (Array.isArray(node)) return node.forEach(walk);
    if (!node || typeof node !== 'object') return;
    if (typeof node.type === 'function' && node.type.name === 'TriggerOrderPicker') found.push(node);
    walk(node.props?.children);
  }
  walk(controlled.Controls(props));
  return found[0];
}
const firstKey = pickerElement(base).key;
for (const changes of [
  {match: {...base.match, id: 2}},
  {match: {...base.match, revision: 2}},
  {match: {...base.match, pending_trigger_order: {current_controller: 2}}},
  {legalMoves: [{...rows[0].move, trigger_order: [...ids].reverse()}]},
]) assert.notEqual(pickerElement({...base, ...changes}).key, firstKey, 'Changed match/controller/group remounts the draft');
assert.equal(pickerElement({...base, legalMoves: []}), undefined, 'No offered choice cannot expose a picker');
assert.equal(pickerElement({...base, legalMoves: [{...rows[0].move, trigger_order: ids.slice(0, 6)}]}), undefined,
  'Existing small-group order buttons stay unchanged');
// Exercise the compiled component's real event callbacks with a deterministic hook store.
// This is not a mounted-browser or React lifecycle certificate.
let selected = [];
const {TriggerOrderPicker} = await compile('../src/components/TriggerOrderPicker.tsx', name => name === 'react'
  ? {...React, useState: () => [selected, value => {selected = typeof value === 'function' ? value(selected) : value;}]} : require(name));
const submitted = [];
const props = {ids, labels, onChoose: order => submitted.push(order)};
function buttons() {
  const tree = TriggerOrderPicker(props);
  const result = [];
  function walk(node) {
    if (Array.isArray(node)) return node.forEach(walk);
    if (!node || typeof node !== 'object') return;
    if (node.type === 'button') result.push(node.props);
    walk(node.props?.children);
  }
  walk(tree);
  return result;
}
function button(label) {return buttons().find(p => p.children === label);}
assert.equal(button('Submit trigger order').disabled, true);
button('Submit trigger order').onClick();
assert.deepEqual(submitted, [], 'Incomplete callbacks cannot submit even if invoked directly');
for (const id of [...ids].reverse()) {
  const pick = buttons().find(p => p['data-trigger-id'] === id);
  assert.equal(pick.disabled, false);
  pick.onClick();
  // A stale event callback must not duplicate a trigger.
  pick.onClick();
}
assert.deepEqual(selected, [...ids].reverse());
assert.equal(button('Submit trigger order').disabled, false);
button('Submit trigger order').onClick();
assert.deepEqual(submitted, [[...ids].reverse()]);
button('Undo last trigger').onClick();
assert.equal(selected.length, 6);
assert.equal(button('Submit trigger order').disabled, true);
button('Reset trigger order').onClick();
assert.deepEqual(selected, []);
assert.deepEqual(submitted, [[...ids].reverse()], 'Editing never submits implicitly');
console.log('PASS actual Controls both-seat large-group admission and compiled picker complete/reverse/duplicate/undo/reset callbacks');
