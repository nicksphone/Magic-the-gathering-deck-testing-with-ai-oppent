import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {build} from 'esbuild';

const raw = JSON.parse(readFileSync(new URL('../../backend/tests/fixtures/human_flow_audit/canonical.json', import.meta.url)));
const compiled = await build({stdin: {
  contents: "import {createElement} from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {Battlefield} from '../src/components/Battlefield';export default p=>renderToStaticMarkup(createElement(Battlefield,p));",
  resolveDir: new URL('.', import.meta.url).pathname, loader: 'tsx',
}, bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
define: {'import.meta.env.VITE_API_BASE_URL': 'undefined'}});
const module = {exports: {}};
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(createRequire(import.meta.url), module, module.exports);
const render = module.exports.default;
function props(seat, name, moves) {
  const card = {...raw[name], id: 'own-cycle-card', types: [name === 'Shark Typhoon' ? 'Enchantment' : 'Instant']};
  const player = () => ({life: 20, mana_pool: {}, battlefield: [], hand: [], graveyard: [], exile: [],
    library_count: 2, hand_count: 0, graveyard_count: 0, exile_count: 0});
  const players = {1: player(), 2: player()};
  players[seat].hand = [card]; players[seat].hand_count = 1;
  players[3-seat].hand = [{...raw['Grizzly Bears'], id: 'private-opponent-card', types: ['Creature']}];
  return {match: {id: 'cycling-control-unit', players, controllers: {1: 'human', 2: 'human'},
    priority_player: seat, active_player: seat, step: 'precombat_main', turn: 1, revision: 0,
    winner: null, stack: [], attackers: [], blocks: {}}, legalMoves: moves, onCardAction() {}};
}
let cases = 0;
for (const seat of [1, 2]) for (const castable of [false, true]) for (const values of [[0], [0, 1, 2], [2]]) {
  const moves = values.map(x_value => ({type: 'cycle_card', card_id: 'own-cycle-card', x_value, mana_cost: `{${x_value + 1}}{U}`}));
  if (castable) moves.push({type: 'cast_spell', card_id: 'own-cycle-card', mana_cost: '{5}{U}'});
  const html = render(props(seat, 'Shark Typhoon', moves));
  const select = html.match(/<select aria-label="Cycling X for Shark Typhoon"[^>]*>(.*?)<\/select>/)?.[1];
  assert.ok(select, 'Both hand branches expose offered cycling X');
  assert.deepEqual([...select.matchAll(/value="(\d+)"/g)].map(m => Number(m[1])), values);
  assert.match(select, new RegExp(`value="${values[0]}" selected=""`));
  assert.ok(!html.includes('private-opponent-card'));
  assert.equal((html.match(/>\s*Cycle Shark Typhoon/g) ?? []).length, 1);
  cases++;
}
for (const seat of [1, 2]) {
  const html = render(props(seat, 'Renewed Faith', [{type: 'cycle_card', card_id: 'own-cycle-card', mana_cost: '{1}{W}'}]));
  assert.ok(html.includes('Cycle Renewed Faith'));
  assert.ok(!html.includes('Cycling X for'));
  const unavailable = render(props(seat, 'Shark Typhoon', []));
  assert.ok(!unavailable.includes('Cycling X for') && !unavailable.includes('Cycle Shark Typhoon'));
  cases += 2;
}
console.log(`PASS ${cases} cycling-control renders: both seats/branches, offered zero/bounds, fixed costs, unavailable action, private hand`);
