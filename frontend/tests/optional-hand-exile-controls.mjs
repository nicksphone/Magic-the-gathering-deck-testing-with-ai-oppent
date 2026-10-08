import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { build } from 'esbuild';
import { parseLegalMoves } from '../src/api/match-contract.ts';

const require = createRequire(import.meta.url);
const react = require('react');
let values, index;
const hooks = { ...react, useEffect() {}, useMemo: fn => fn(),
  useRef: value => ({ current: value }),
  useState(initial) {
    const slot = index++;
    if (!(slot in values)) values[slot] = typeof initial === 'function' ? initial() : initial;
    return [values[slot], next => { values[slot] = typeof next === 'function' ? next(values[slot]) : next; }];
  } };
const compiled = await build({ stdin: { contents: await readFile(new URL('../src/components/Battlefield.tsx', import.meta.url), 'utf8'),
  resolveDir: new URL('../src/components/', import.meta.url).pathname, loader: 'tsx' },
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: { 'import.meta.env.VITE_API_BASE_URL': "''" } });
const module = { exports: {} };
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(
  name => name === 'react' ? hooks : require(name), module, module.exports);
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value == null || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props?.children) : String(value);
}
for (const seat of [1, 2]) {
  const row = JSON.parse(await readFile(new URL(`./fixtures/march-public/march-public-view-v2-public-pitch-seat-${seat}.json`, import.meta.url)));
  const move = row.actual_cast_move;
  const option = move.cost_options.find(option => option.hand_exile_color);
  const legal = { player_id: seat, revision: 0, moves: [move] };
  parseLegalMoves(legal);
  for (const fields of [{hand_exile_color: null}, {hand_exile_color: 'C'},
    {hand_exile_generic_reduction: 0}, {hand_exile_generic_reduction: 1.5},
    {exile_card_ids: null}, {exile_card_ids: [option.exile_card_ids[0], option.exile_card_ids[0]]},
    {exile_card_ids: ['']}, {exile_card_ids: Array.from({length: 251}, (_, i) => String(i))}]) {
    assert.throws(() => parseLegalMoves({...legal, moves: [{...move,
      cost_options: move.cost_options.map(candidate => candidate === option ? {...option, ...fields} : candidate)}]}));
  }
  const player = hand => ({ life: 20, hand, battlefield: [], graveyard: [], exile: [],
    graveyard_count: 0, exile_count: 0, library_count: 30, mana_pool: {}, snow_mana_pool: {} });
  const match = { id: 'public-pitch', step: 'precombat_main', turn: 1, active_player: seat,
    priority_player: seat, controllers: {'1': 'human', '2': 'human'}, score: {'1': 0, '2': 0},
    stack: [], log: [], blocks: {}, players: {[seat]: player(row.actor_hand_views), [3-seat]: player([])} };
  values = []; const sent = [];
  const props = { match, legalMoves: [move], actingPlayerId: seat,
    onCardAction: (actor, action) => sent.push({actor, action}) };
  const render = () => { index = 0; return nodes(module.exports.Battlefield(props)); };
  const select = () => render().find(node => node.type === 'select' && node.props['aria-label'] === `Exile from hand for cost ${row.actor_hand_views[0].name}`);
  const cast = () => render().find(node => node.type === 'button' && text(node).startsWith(`Cast ${row.actor_hand_views[0].name}`));
  assert.ok(select(), 'actual optional hand-exile candidates need a deliberate selection control');
  assert.deepEqual(select().props.value, []);
  assert.deepEqual(nodes(select()).filter(node => node.type === 'option').map(node => node.props.value), option.exile_card_ids);
  cast().props.onClick();
  assert.deepEqual(sent.at(-1).action.cost_choice.exile_card_ids, [], 'zero cards is a valid deliberate option');
  const selected = [option.exile_card_ids[1], option.exile_card_ids[0]];
  select().props.onChange({target: {selectedOptions: selected.map(value => ({value}))}});
  cast().props.onClick();
  assert.equal(sent.at(-1).actor, seat);
  assert.deepEqual(sent.at(-1).action.cost_choice.exile_card_ids, selected);
  select().props.onChange({target: {selectedOptions: [{value: 'stale-or-foreign'}]}});
  assert.equal(cast().props.disabled, true);
  const ordinaryOption = {...option};
  delete ordinaryOption.hand_exile_color;
  delete ordinaryOption.hand_exile_generic_reduction;
  delete ordinaryOption.exile_card_ids;
  props.legalMoves = [{...move, cost_options: [ordinaryOption]}];
  parseLegalMoves({...legal, moves: props.legalMoves});
  assert.equal(select(), undefined, 'ordinary costs must not gain an exile control');
  cast().props.onClick();
  assert.equal(Object.hasOwn(sent.at(-1).action.cost_choice, 'exile_card_ids'), false);
}
console.log('PASS optional hand exile: actual both-seat public views, strict metadata, deliberate zero/reverse IDs and stale selection');
