import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {build} from 'esbuild';
import {parseLegalMoves, parseMatchState} from '../src/api/match-contract.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = process.env.MTG_BOUNDED_UI_SOURCE || root;
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const fixture = path.join(root, 'frontend/tests/bounded-target-engine.py');
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
  const submitted = [];
  const props = {match, legalMoves: legal.moves, actingPlayerId: row.seat,
    onCardAction: (seat, action) => submitted.push({seat, action})};
  let tree = render(props);
  const picker = () => tree.find(node => node.type === 'select' && node.props.multiple);
  const button = () => tree.find(node => node.type === 'button'
    && text(node.props.children).startsWith('Cast Force of Vigor'));
  assert.ok(picker(), 'Actual canonical bounded removal needs a multi-target picker');
  const offered = nodes(picker()).filter(node => node.type === 'option').map(node => node.props.value);
  assert.equal(offered.length, 3);
  assert.deepEqual(submitted, [], 'Rendering never chooses or submits a target');
  assert.equal(button().props.disabled, false, 'The initial deliberate cast may choose zero targets');
  button().props.onClick();
  const empty = submitted.pop();
  assert.deepEqual(empty.action.targets, {}, 'No target is inferred for an untouched draft');
  packets.push(structuredClone({...empty, snapshot: row.snapshot, offered}));
  const choose = ids => {
    picker().props.onChange({target: {selectedOptions: ids.map(value => ({value}))}});
    tree = render(props);
  };
  choose(offered);
  assert.equal(button().props.disabled, true, 'Three targets cannot be cast with an offered maximum of two');
  for (const ids of [[offered[0], offered[0]], ['unknown-object']]) {
    choose(ids);
    assert.equal(button().props.disabled, true, 'Duplicate or unoffered target drafts cannot be cast');
  }
  for (const ids of [[], [offered[2]], [offered[1], offered[0]]]) {
    choose(ids);
    assert.equal(button().props.disabled, false, 'Zero/one/two deliberate targets remain legal');
    assert.deepEqual(picker().props.value, ids, 'The control displays the current target draft');
    button().props.onClick();
    const packet = submitted.pop();
    assert.equal(packet.seat, row.seat);
    assert.deepEqual(packet.action.targets.target_card_ids, ids);
    assert.equal(packet.action.targets.target_card_id, undefined);
    packets.push(structuredClone({...packet, snapshot: row.snapshot, offered}));
  }
  const draft = states.find(state => state?.[row.source]?.target_card_ids);
  draft[row.source].target_card_id = offered[2];
  choose([offered[0]]);
  button().props.onClick();
  assert.equal(submitted.pop().action.targets.target_card_id, undefined,
    'Editing a bounded draft removes a stale single-target announcement');
  props.match = {...match, game_number: (match.game_number ?? 1) + 1};
  tree = render(props);
  assert.deepEqual(picker().props.value, [], 'New games clear old target drafts');
  assert.deepEqual(submitted, [], 'Draft resets do not submit an action');
}
const results = JSON.parse(execFileSync(python, ['-B', fixture, 'execute'], {
  ...options, input: JSON.stringify(packets),
}));
assert.equal(results.length, 8);
assert.ok(results.every(row => row.resolved));
console.log('PASS both-seat actual public bounded targets: zero/one/two execution, limit/duplicate/unknown drafts, stale scalar cleanup and game reset');
