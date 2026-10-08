import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {build} from 'esbuild';
import {parseLegalMoves, parseMatchState} from '../src/api/match-contract.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = process.env.MTG_LOYALTY_UI_SOURCE || root;
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const rows = JSON.parse(execFileSync(python, ['-B', path.join(root, 'frontend/tests/loyalty-public-engine.py')], {
  cwd: path.join(root, 'backend'), encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'},
}));
assert.equal(rows.length, 6);
const require = createRequire(import.meta.url);
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const states = [], dependencies = [];
let cursor = 0, effects = [];
async function compile(component, hooks = false) {
  const built = await build({entryPoints: [path.join(uiRoot, `frontend/src/components/${component}.tsx`)],
    bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
    define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
  const module = {exports: {}};
  const adapter = {...React, useMemo: fn => fn(),
    useState(initial) {
      const index = cursor++;
      if (!(index in states)) states[index] = initial;
      return [states[index], value => {states[index] = typeof value === 'function' ? value(states[index]) : value;}];
    },
    useEffect(fn, deps) {
      const index = cursor++;
      if (!dependencies[index] || deps.some((value, i) => value !== dependencies[index][i])) effects.push(fn);
      dependencies[index] = deps;
    },
  };
  new Function('require', 'module', 'exports', built.outputFiles[0].text)(
    name => hooks && name === 'react' ? adapter : require(name), module, module.exports);
  return module.exports[component];
}
const Controls = await compile('Controls', true);
const Battlefield = await compile('Battlefield');
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
  Controls(props);
  for (const effect of effects) effect();
  cursor = 0; effects = [];
  return nodes(Controls(props));
}
const failures = [];
for (const row of rows) {
  const match = parseMatchState(row.state);
  const submitted = [];
  if (row.kind === 'emblem') {
    for (const viewer of [1, 2]) {
      const html = renderToStaticMarkup(React.createElement(Battlefield, {
        match, actingPlayerId: viewer, legalMoves: [], onCardAction: (...args) => submitted.push(args),
      }));
      if (!html.includes(`aria-label="Player ${row.seat} emblems"`)) {
        failures.push(`Missing public emblem seat${row.seat} viewer${viewer}`);
        continue;
      }
      for (const emblem of match.emblems) {
        assert.ok(html.includes(emblem.name));
        assert.ok(html.includes(emblem.oracle_text.replaceAll('&', '&amp;').replaceAll('"', '&quot;')),
          'Public emblem rules must be readable without activating or targeting it');
        assert.equal(emblem.zone, 'command');
      }
      assert.deepEqual(submitted, [], 'Viewing emblems cannot submit a card action');
    }
    continue;
  }
  const legal = parseLegalMoves(row.legal);
  const move = legal.moves.find(move => move.type === 'choose_mechanic');
  assert.equal(move.kind, row.kind);
  states.length = dependencies.length = 0;
  const props = {decks: [], bestOf: 1, startMode: 'human_vs_human', humanSeat: row.seat,
    difficulty: 'master', autoplayDelayMs: 1000, responseCountdown: null, autoResponsePaused: false,
    match, legalMoves: legal.moves, onChooseMechanic: (seat, action) => submitted.push({seat, action})};
  let tree = render(props);
  if (tree.some(node => text(node).includes('Unsupported mechanic choice:'))) {
    failures.push(`Missing ${move.kind} seat${row.seat}`);
    continue;
  }
  assert.deepEqual(submitted, [], 'Rendering never infers a choice');
  if (move.kind === 'loyalty_attachment') {
    for (const option of move.options) {
      const button = tree.find(node => node.type === 'button' && text(node.props.children) === move.option_labels[option]);
      assert.ok(button, 'Every actually offered attachment must be reachable');
      button.props.onClick();
      assert.deepEqual(submitted.at(-1), {seat: row.seat, action: {type: 'choose_mechanic', choice_id: option}});
    }
    assert.equal(submitted.length, move.options.length);
  } else {
    const confirm = () => tree.find(node => node.type === 'button' && node.props.children === 'Confirm Selection');
    assert.equal(confirm().props.disabled, false, 'An explicit zero selection must be legal');
    assert.ok(tree.some(node => text(node) === `Select up to ${move.count} card(s).`));
    confirm().props.onClick();
    assert.deepEqual(submitted.pop(), {seat: row.seat, action: {type: 'choose_mechanic', card_ids: []}});
    const checkboxes = () => nodes(tree.find(node => node.type === 'div'
      && node.props.className === 'block-panel' && nodes(node).includes(confirm())))
      .filter(node => node.type === 'input' && node.props.type === 'checkbox');
    assert.equal(checkboxes().length, move.options.length);
    const selected = [2, 0, 1];
    for (const index of selected) {
      checkboxes()[index].props.onChange({target: {checked: true}});
      tree = render(props);
    }
    assert.equal(confirm().props.disabled, false);
    confirm().props.onClick();
    assert.deepEqual(submitted.pop(), {seat: row.seat,
      action: {type: 'choose_mechanic', card_ids: selected.map(index => move.options[index])}});
    for (let index = 0; index <= move.count; index++) {
      if (!checkboxes()[index].props.checked) checkboxes()[index].props.onChange({target: {checked: true}});
      tree = render(props);
    }
    assert.equal(confirm().props.disabled, true, 'More than the announced maximum cannot be confirmed');
    props.match = {...match, game_number: (match.game_number ?? 1) + 1};
    tree = render(props);
    assert.ok(checkboxes().every(node => !node.props.checked), 'New games clear old selection drafts');
    assert.deepEqual(submitted, [], 'Draft transitions cannot submit an action');
  }
}
assert.deepEqual(failures, [], 'Actual paid public loyalty views must have reachable UI');
const state = rows.find(row => row.kind === 'emblem').state;
const emblem = state.emblems[0];
for (const emblems of [null, {}, [null], [{...emblem, controller: 3}], [{...emblem, owner: '1'}],
  [{...emblem, zone: 'battlefield'}], [{...emblem, name: null}], [emblem, emblem]]) {
  assert.throws(() => parseMatchState({...state, emblems}), /emblem/);
}
assert.equal(parseMatchState({...state, emblems: []}).emblems.length, 0);
const legacy = {...state}; delete legacy.emblems;
assert.equal(parseMatchState(legacy), legacy, 'Older snapshots without public emblems remain readable');
console.log('PASS both-seat actual paid loyalty card/attachment choices, explicit zero/subset drafts, public emblems and strict legacy-compatible response contract');
