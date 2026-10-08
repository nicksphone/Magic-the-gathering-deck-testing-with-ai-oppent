import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const states = [], dependencies = [];
let cursor = 0, effects = [];
const built = await build({entryPoints: [new URL('../src/components/Controls.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', built.outputFiles[0].text)(name => name === 'react' ? {
  ...React,
  useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = initial;
    return [states[index], value => {states[index] = typeof value === 'function' ? value(states[index]) : value;}];
  },
  useMemo: fn => fn(),
  useEffect(fn, deps) {
    const index = cursor++;
    if (!dependencies[index] || deps.some((value, i) => value !== dependencies[index][i])) effects.push(fn);
    dependencies[index] = deps;
  },
} : require(name), module, module.exports);

function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}
const submitted = [];
const move = {type: 'choose_mechanic', kind: 'discard', player_id: 1, options: ['card-a', 'card-b'], count: 1, min_count: 1};
const props = {decks: [], bestOf: 3, startMode: 'human_vs_human', humanSeat: 1,
  difficulty: 'master', autoplayDelayMs: 1000, responseCountdown: null, autoResponsePaused: false,
  match: {id: 1, game_number: 1, priority_player: 1}, legalMoves: [move],
  onChooseMechanic: (seat, action) => submitted.push({seat, action})};
function render() {
  cursor = 0; effects = [];
  module.exports.Controls(props);
  for (const effect of effects) effect();
  cursor = 0; effects = [];
  return nodes(module.exports.Controls(props));
}
function checkboxes(tree) {return tree.filter(node => node.type === 'input' && node.props.type === 'checkbox');}
function confirm(tree) {return tree.find(node => node.type === 'button' && node.props.children === 'Confirm Selection');}
for (const transition of ['match', 'game']) {
  let tree = render();
  checkboxes(tree)[0].props.onChange({target: {checked: true}});
  tree = render();
  assert.equal(checkboxes(tree)[0].props.checked, true);
  assert.equal(confirm(tree).props.disabled, false);
  // Identical offered IDs must not carry a human draft into a different game.
  props.match = {...props.match, [transition === 'match' ? 'id' : 'game_number']: 2};
  tree = render();
  assert.equal(checkboxes(tree).some(node => node.props.checked), false, `${transition} change must clear mechanic choices`);
  assert.equal(confirm(tree).props.disabled, true);
  assert.deepEqual(submitted, [], 'Rendering and draft resets never submit an action');
  checkboxes(tree)[1].props.onChange({target: {checked: true}});
  tree = render();
  confirm(tree).props.onClick();
  assert.deepEqual(submitted.pop(), {seat: 1, action: {type: 'choose_mechanic', card_ids: ['card-b']}});
  checkboxes(tree)[1].props.onChange({target: {checked: false}});
}
console.log('PASS actual Controls hook transitions: same-view draft retained, match/game reset, fresh explicit callback');
