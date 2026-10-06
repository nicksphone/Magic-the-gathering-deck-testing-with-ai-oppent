import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {formatManaVector, legacyManaOutput} from '../src/components/manual-mana-output.ts';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON;
assert.ok(python, 'Declare an external Python environment; never install dependencies for this gate');
const rows = JSON.parse(execFileSync(python, ['-c', `
import json
from tests.test_additive_mana import position,add,aura
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
out=[]
for seat in (1,2):
 for scenario in ('plain','fixed-trigger','replacement-trigger','two-trigger-mana'):
  state=position(seat)
  source=add(state,'Island',seat)
  if scenario!='plain':aura(state,'Overgrowth' if scenario=='two-trigger-mana' else 'Wild Growth',3-seat,source)
  if scenario=='replacement-trigger':add(state,'Mana Reflection',seat)
  before=serialize_match_snapshot(state)
  move=next(m for m in RulesEngine().legal_moves(state,seat) if m['type']=='activate_mana_ability' and m['card_id']==source.id)
  assert serialize_match_snapshot(state)==before
  paid=checked_action(state,RulesEngine(),seat,dict(type='activate_mana_ability',card_id=source.id,ability_index=move['ability_index'],color='U'))
  assert serialize_match_snapshot(state)==before
  pool={c:n for c,n in paid.players[seat].mana_pool.items() if n}
  out.append(dict(seat=seat,scenario=scenario,move=move,pool=pool))
print(json.dumps(out))
`], {cwd: path.join(source, 'backend'), encoding: 'utf8',
  env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));

const expected = {'plain': '1 U', 'fixed-trigger': '1 U + 1 G',
  'replacement-trigger': '2 U + 1 G', 'two-trigger-mana': '1 U + 2 G'};
const compiled = await build({stdin: {
  contents: "import {createElement} from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {ManualManaOutput} from '../src/components/ManualManaOutput';export default p=>renderToStaticMarkup(createElement(ManualManaOutput,p));",
  resolveDir: path.join(source, 'frontend/tests'), loader: 'tsx',
}, bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic'});
const module = {exports: {}};
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(createRequire(import.meta.url), module, module.exports);
for (const row of rows) {
  const before = JSON.stringify(row);
  const display = legacyManaOutput(row.move, 'U');
  assert.equal(display.total, expected[row.scenario]);
  assert.equal(display.total, formatManaVector(row.pool));
  assert.equal(display.effective, row.scenario === 'replacement-trigger' ? '2 U' : '1 U');
  assert.equal(Boolean(display.warning), row.scenario !== 'plain');
  const html = module.exports.default({move: {...row.move, output_options: undefined, base_output_bundles: undefined}, playerId: row.seat, cards: [], onAction() {}});
  assert.ok(html.includes(`Add projected ${expected[row.scenario]}`), 'Legacy control shows the whole checked vector');
  assert.ok(!html.includes('disabled=""'), 'Canonical plain tap remains available');
  assert.equal(JSON.stringify(row), before);
}
assert.equal(rows.length, 8);
for (const vector of [null, [], {}, {U: 0}, {S: 1}, {U: -1}, {U: 1.5}, {U: '1'}, {U: Infinity}]) {
  assert.equal(formatManaVector(vector), null);
}
assert.equal(formatManaVector({G: 2, U: 1, W: 0}), '1 U + 2 G');
assert.equal(legacyManaOutput({outputs: {U: 1, G: 1}}, 'U').total, '1 U');
assert.equal(legacyManaOutput({outputs: {U: 1}, output_bundles: {U: {U: 1, invalid: 2}}}, 'U').total, null);
console.log('PASS 8 canonical both-seat vectors match actual checked mana receipts; alternatives, replacement/trigger distinction and invalid-vector guards');
