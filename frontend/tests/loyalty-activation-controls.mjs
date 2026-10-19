import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {writeFileSync} from 'node:fs';
import path from 'node:path';
import {build} from 'esbuild';
import {parseLegalMoves, parseMatchState} from '../src/api/match-contract.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = process.env.MTG_LOYALTY_UI_SOURCE || root;
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const fixture = path.join(root, 'frontend/tests/loyalty-activation-public-engine.py');
const runFixture = (args = [], input) => execFileSync(python, ['-B', fixture, ...args], {
  cwd: path.join(root, 'backend'), encoding: 'utf8', input,
  env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}, maxBuffer: 32 * 1024 * 1024,
});
const rows = JSON.parse(runFixture());
assert.equal(rows.length, 20);
const evidence = process.env.MTG_LOYALTY_ACTIVATION_EVIDENCE;
if (evidence) writeFileSync(path.join(evidence, 'paid-public-inputs.json'), JSON.stringify(rows));
const require = createRequire(import.meta.url);
const React = require('react');
const states = [], dependencies = [];
let cursor = 0, effects = [];
const adapter = {...React, useMemo: fn => fn(),
  useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = initial;
    return [states[index], value => {states[index] = typeof value === 'function' ? value(states[index]) : value;}];
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
const built = await build({entryPoints: [path.join(uiRoot, 'frontend/src/components/Battlefield.tsx')],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', built.outputFiles[0].text)(
  name => name === 'react' ? adapter : require(name), module, module.exports);
const {Battlefield} = module.exports;
globalThis.window = {addEventListener() {}, removeEventListener() {}};
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
const failures = [], submissions = [];
for (const row of rows) {
  try {
    states.length = dependencies.length = 0;
    const submitted = [];
    const props = {match: parseMatchState(row.state), actingPlayerId: row.seat,
      legalMoves: parseLegalMoves(row.legal).moves, onCardAction: (seat, action) => submitted.push({seat, action})};
    const label = `${row.publicMove.card_name}: ${row.publicMove.ability_label}`;
    let tree = render(props);
    const box = () => tree.find(node => node.type === 'div' && node.props.className === 'cast-card-box'
      && nodes(node).some(child => child.type === 'button' && text(child.props.children) === label));
    const button = () => nodes(box()).find(node => node.type === 'button' && text(node.props.children) === label);
    const selects = () => nodes(box()).filter(node => node.type === 'select');
    assert.ok(button(), 'The actually offered loyalty ability must render');
    assert.deepEqual(submitted, [], 'Rendering cannot infer or submit an action');
    if (row.publicMove.ability_x_cost) {
      const input = () => nodes(box()).find(node => node.type === 'input' && node.props.type === 'number');
      assert.ok(input(), 'The actual public X-cost ability needs an X input');
      assert.equal(input().props.min, 0);
      assert.equal(input().props.max, row.loyalty, 'Negative loyalty X is bounded by the actual source counters');
      assert.equal(input().props.value, 0);
      for (const invalid of [-1, 0.5, row.loyalty + 1]) {
        input().props.onChange({target: {value: String(invalid)}});
        tree = render(props);
        assert.equal(button().props.disabled, true, 'Invalid loyalty costs cannot be clicked');
        assert.deepEqual(submitted, []);
      }
      input().props.onChange({target: {value: String(row.expected.targets.x_value)}});
      tree = render(props);
      assert.equal(input().props.value, row.expected.targets.x_value);
      assert.equal(button().props.disabled, false);
    }
    const wanted = row.expected.targets.target_card_id;
    if (wanted) {
      const selector = selects().find(select => nodes(select).some(option => option.type === 'option' && option.props.value === wanted));
      assert.ok(selector, 'Every chosen canonical public permanent must be selectable');
      const options = nodes(selector).filter(node => node.type === 'option' && node.props.value);
      assert.equal(new Set(options.map(option => option.props.value)).size, options.length, 'Candidates are deduplicated by public ID');
      assert.equal(selector.props.value, '', 'Targets must not be automatically selected');
      selector.props.onChange({target: {value: wanted}});
      tree = render(props);
    }
    if (row.expected.targets.target_player) {
      const selector = selects().find(select => nodes(select).some(option => option.type === 'option' && option.props.value === row.expected.targets.target_player));
      assert.ok(selector, 'Existing player targets remain selectable');
      selector.props.onChange({target: {value: String(row.expected.targets.target_player)}});
      tree = render(props);
    }
    if (row.kind === 'nissa-decline') {
      const selector = selects().find(select => nodes(select).some(option => option.type === 'option' && option.props.value === row.ids.land));
      assert.ok(selector, 'Optional land targeting must retain an explicit decline');
      selector.props.onChange({target: {value: row.ids.land}});
      tree = render(props);
      selects()[0].props.onChange({target: {value: ''}});
      tree = render(props);
    }
    assert.deepEqual(submitted, [], 'Changing drafts cannot submit a choice');
    button().props.onClick();
    assert.equal(submitted.length, 1);
    // Undefined draft keys are omitted by the real JSON request boundary.
    const actual = JSON.parse(JSON.stringify(submitted[0]));
    assert.deepEqual(actual, {seat: row.seat, action: row.expected});
    submissions.push({id: row.id, ...actual});
    props.match = {...props.match, game_number: (props.match.game_number ?? 1) + 1};
    tree = render(props);
    assert.ok(selects().every(select => select.props.value === ''), 'New-game transitions clear old target drafts');
    const x = nodes(box()).find(node => node.type === 'input' && node.props.type === 'number');
    if (x) assert.equal(x.props.value, 0, 'New games clear old X drafts');
    assert.equal(submitted.length, 1, 'Draft reset cannot submit an action');
  } catch (error) {
    failures.push({id: row.id, message: error.message});
  }
}
console.log(JSON.stringify({phase: 'actual-source-handlers', cases: rows.length, passed: submissions.length, failures}));
assert.deepEqual(failures, [], 'Actual paid canonical loyalty announcements must be reachable');
if (evidence) writeFileSync(path.join(evidence, 'actual-handler-submissions.json'), JSON.stringify(submissions));
const verified = JSON.parse(runFixture(['--verify'], JSON.stringify({rows, submissions})));
assert.equal(verified.length, rows.length);
assert.ok(verified.every(row => row.passed));
if (evidence) writeFileSync(path.join(evidence, 'checked-backend-outcomes.json'), JSON.stringify(verified));
console.log(JSON.stringify({phase: 'actual-checked-backend-replay', cases: verified.length,
  receipts: verified.map(({id, actualCallback, passed}) => ({id, actualCallback, passed}))}));
