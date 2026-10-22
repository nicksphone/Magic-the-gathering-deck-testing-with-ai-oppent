import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const React = require('react');
const ts = require('typescript');
const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src');
let cursor = 0;
const states = [];
const hooks = {...React,
  useMemo: callback => callback(),
  useEffect() {},
  useRef: initial => ({current: initial}),
  useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial;
    return [states[index], value => {states[index] = typeof value === 'function' ? value(states[index]) : value;}];
  },
};
const modules = new Map();
function load(filename) {
  if (modules.has(filename)) return modules.get(filename).exports;
  const module = {exports: {}};
  modules.set(filename, module);
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const imports = name => {
    if (name === 'react') return hooks;
    if (name.startsWith('.')) {
      const base = path.resolve(path.dirname(filename), name);
      if (base === path.join(directory, 'api/client')) return {
        resolveCardMediaUrl: url => url,
        api: new Proxy({}, {get() {throw Error('Rendering cannot start an API operation');}}),
      };
      const dependency = (path.extname(base) ? [base] : ['.ts', '.tsx'].map(extension => base + extension)).find(fs.existsSync);
      assert.ok(dependency, `Missing actual component dependency: ${name}`);
      return load(dependency);
    }
    assert.ok(['react-dom', 'react/jsx-runtime'].includes(name));
    return require(name);
  };
  vm.runInNewContext(`(function(require,module,exports){${compiled}\n})`)(imports, module, module.exports);
  return module.exports;
}
const {Battlefield} = load(path.join(directory, 'components/Battlefield.tsx'));

function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}
const name = 'Selection probe';
const target = {id: 'target', name: 'Offered target'};
const cases = [
  ['creature target', `Target for ${name}`, {target_hints: {creature_targets: [target]}}],
  ['alternative target', `Target for ${name}`, {target_hints: {
    single_target_alternative: true, player_targets: [{id: 2, name: 'Opponent'}], creature_targets: [target],
  }}],
  ['X value', `X value for ${name}`, {target_hints: {requires_x_value: true, x_value_max: 5}}],
  ['stack target', `Stack target for ${name}`, {target_hints: {stack_targets: [{id: 'stack', label: 'Offered spell'}]}}],
  ['casting cost', `Casting cost for ${name}`, {cost_options: [{id: 'normal', label: 'Normal', mana_cost: '{1}'}]}],
  ['spell face', `Spell face for ${name}`, {target_hints: {face_names: ['First face', 'Second face']}}, {card_faces: [
    {name: 'First face', mana_cost: '{1}', oracle_text: 'Target creature.'},
    {name: 'Second face', mana_cost: '{2}', oracle_text: 'Target creature.'},
  ]}],
  ['loyalty player target', `Loyalty player target for ${name}`, {type: 'activate_loyalty', ability_index: 0,
    ability_label: 'Choose target player', target_hints: {player_targets: [{id: 2, name: 'Opponent'}]}}],
  ['loyalty permanent target', `Loyalty permanent target for ${name}`, {type: 'activate_loyalty', ability_index: 0,
    ability_label: 'Choose target permanent', target_hints: {permanent_targets: [target]}}],
  ['equip target', `Equip target for ${name}`, {type: 'equip', targets: [target]}],
];

function fixture(seat, move, extra = {}) {
  const card = {id: 'source', name, owner: seat, controller: seat, mana_cost: '{1}',
    oracle_text: 'Target creature.', types: ['Creature'], counters: {}, ...extra};
  const player = {name: 'Player', life: 20, battlefield: [], hand: [], graveyard: [], exile: [],
    mana_pool: {}, library_count: 40, land_plays_remaining: 1};
  const match = {id: 'accessible-table', revision: 1, turn: 2, step: 'precombat_main',
    active_player: seat, priority_player: seat, winner: null, controllers: {'1': 'human', '2': 'human'},
    players: {'1': {...player, hand: seat === 1 ? [card] : []}, '2': {...player, hand: seat === 2 ? [card] : []}}, stack: []};
  const submitted = [];
  return {submitted, props: {match, actingPlayerId: seat,
    legalMoves: [{type: 'cast_spell', card_id: card.id, card_name: card.name, ...move}],
    onCardAction: (...args) => submitted.push(args)}};
}
function render(props) {
  cursor = 0;
  return nodes(Battlefield(props));
}

for (const seat of [1, 2]) for (const [kind, label, move, extra] of cases) {
  test(`${kind} has an explicit accessible name in human seat ${seat}`, () => {
    states.length = 0;
    const {props, submitted} = fixture(seat, move, extra);
    const before = JSON.stringify(props);
    const fields = render(props).filter(node => ['input', 'select', 'textarea'].includes(node.type));
    assert.ok(fields.some(field => field.props['aria-label'] === label), `Missing accessible name: ${label}`);
    assert.ok(fields.every(field => String(field.props['aria-label'] ?? '').trim()), 'Every rendered field must be named');
    assert.deepEqual(submitted, [], 'Rendering cannot infer or submit an action');
    assert.equal(JSON.stringify(props), before);
  });
}

test('naming the target does not change selection values or deliberate cast payload', () => {
  states.length = 0;
  const {props, submitted} = fixture(1, cases[0][2]);
  let tree = render(props);
  const picker = () => tree.find(node => node.type === 'select' && node.props['aria-label'] === `Target for ${name}`);
  assert.ok(picker(), 'The actual target picker must be identifiable by name');
  assert.equal(picker().props.value, '');
  assert.deepEqual(nodes(picker()).filter(node => node.type === 'option').map(node => node.props.value), ['', 'target']);
  picker().props.onChange({target: {value: 'target'}});
  tree = render(props);
  assert.equal(picker().props.value, 'target');
  assert.deepEqual(submitted, []);
  tree.find(node => node.type === 'button' && nodes(node).some(child => String(child.props?.children).includes('Cast '))).props.onClick();
  assert.equal(submitted.length, 1);
  assert.equal(submitted[0][0], 1);
  assert.equal(submitted[0][1].type, 'cast_spell');
  assert.equal(submitted[0][1].card_id, 'source');
  assert.equal(submitted[0][1].targets.target_card_id, 'target');
});
