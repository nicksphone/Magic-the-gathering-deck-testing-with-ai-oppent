import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {build} from 'esbuild';
import {parseLegalMoves, parseMatchState} from '../src/api/match-contract.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = process.env.MTG_ORDERED_UI_SOURCE || root;
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const fixture = path.join(root, 'frontend/tests/ordered-target-engine.py');
const options = {cwd: path.join(root, 'backend'), encoding: 'utf8',
  env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}};
const rows = JSON.parse(execFileSync(python, ['-B', fixture], options));
const require = createRequire(import.meta.url);
const React = require('react');
const states = [], dependencies = [];
let cursor = 0, effects = [];
const adapter = {...React, useMemo: fn => fn(),
  useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = initial;
    return [states[index], value => {
      states[index] = typeof value === 'function' ? value(states[index]) : value;
    }];
  },
  useRef(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = {current: initial};
    return states[index];
  },
  useEffect(fn, deps) {
    const index = cursor++;
    if (!dependencies[index] || deps.some((value, i) => value !== dependencies[index][i])) effects.push(fn);
    dependencies[index] = deps;
  },
};
globalThis.window = {addEventListener() {}, removeEventListener() {}};
const built = await build({entryPoints: [path.join(uiRoot, 'frontend/src/components/Battlefield.tsx')],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', built.outputFiles[0].text)(
  name => name === 'react' ? adapter : require(name), module, module.exports);
const Battlefield = module.exports.Battlefield;
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value === null || value === undefined || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props?.children) : String(value);
}
function render(props) {
  cursor = 0; effects = [];
  Battlefield(props);
  for (const effect of effects) effect();
  cursor = 0; effects = [];
  return nodes(Battlefield(props));
}
const packets = [];
for (const row of rows) {
  states.length = dependencies.length = 0;
  const match = parseMatchState(row.state), legal = parseLegalMoves(row.legal);
  const name = row.kind === 'ghostly' ? 'Ghostly Flicker' : 'Agony Warp';
  const submitted = [];
  const props = {match, legalMoves: legal.moves, actingPlayerId: row.seat,
    onCardAction: (seat, action) => submitted.push({seat, action})};
  let tree = render(props);
  const picker = index => tree.find(node => node.type === 'select'
    && node.props['aria-label'] === `Target ${index + 1} for ${name}`);
  const button = () => tree.find(node => node.type === 'button'
    && text(node.props.children).startsWith(`Cast ${name}`));
  assert.equal(button().props.disabled, true, 'No target is inferred for an untouched draft');
  assert.deepEqual(submitted, []);
  for (const index of [0, 1]) {
    assert.ok(picker(index), 'Each target must be explicitly selectable');
    const offered = nodes(picker(index)).filter(node => node.type === 'option' && node.props.value)
      .map(node => node.props.value);
    assert.deepEqual(new Set(offered), new Set(row.offered), 'Use every server-offered target, including noncreatures');
    assert.ok(!text(tree).includes('undefined'), 'Target labels must not invent counter or pump effects');
  }
  const choose = (index, value) => {
    picker(index).props.onChange({target: {value}});
    tree = render(props);
  };
  choose(0, row.offered[0]);
  assert.equal(button().props.disabled, true, 'One target cannot satisfy an exact two-target announcement');
  choose(1, 'unoffered-object');
  assert.equal(button().props.disabled, true);
  choose(1, row.offered[0]);
  assert.equal(button().props.disabled, row.kind === 'ghostly', 'Distinct spells forbid duplicates; instance spells permit them');
  if (row.kind === 'ghostly') {
    assert.equal(nodes(picker(1)).find(node => node.type === 'option'
      && node.props.value === row.offered[0]).props.disabled, true);
  }
  const selections = row.kind === 'ghostly'
    ? [[row.offered[2], row.offered[1]], [row.offered[0], row.offered[2]], [row.offered[1], row.offered[0]]]
    : [[row.offered[0], row.offered[0]], [row.offered[1], row.offered[0]]];
  for (const ids of selections) {
    choose(0, ids[0]); choose(1, ids[1]);
    assert.equal(button().props.disabled, false, 'A complete valid draft can be submitted');
    assert.deepEqual([picker(0).props.value, picker(1).props.value], ids);
    button().props.onClick();
    const packet = submitted.pop();
    assert.equal(packet.seat, row.seat);
    assert.deepEqual(packet.action.targets.target_card_ids, ids, 'Selection order is preserved');
    assert.equal(packet.action.targets.target_card_id, undefined);
    packets.push(structuredClone({...row, ...packet}));
  }
  const draft = states.find(state => state?.[row.source]?.target_card_ids);
  draft[row.source].target_card_id = row.offered[0];
  choose(0, row.offered[1]); choose(1, row.offered[0]);
  button().props.onClick();
  assert.equal(submitted.pop().action.targets.target_card_id, undefined, 'Editing removes a stale scalar target');
  choose(1, '');
  assert.equal(button().props.disabled, true, 'Clearing a target disables submission');
  props.match = {...match, game_number: (match.game_number ?? 1) + 1};
  tree = render(props);
  assert.deepEqual([picker(0).props.value, picker(1).props.value], ['', '']);
  assert.equal(button().props.disabled, true);
  assert.deepEqual(submitted, [], 'Resetting a game does not submit a draft');
}
const results = JSON.parse(execFileSync(python, ['-B', fixture, 'execute'], {
  ...options, input: JSON.stringify(packets),
}));
assert.equal(results.length, 16);
assert.ok(results.every(row => row.resolved));
console.log('PASS actual public exact-two permanent and ordered creature-instance controls, both seats, foreign owners, native payment/resolution and snapshot restoration');
