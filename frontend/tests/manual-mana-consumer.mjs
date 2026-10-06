import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {parseLegalMoves} from '../src/api/match-contract.ts';

const source=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
assert.ok(process.env.MTG_TEST_PYTHON);
const rows=JSON.parse(execFileSync(process.env.MTG_TEST_PYTHON,['-c',`
import json
from tests.test_mana_executor_choices import position,add
from game_state.state import Zone
from rules_engine.engine import RulesEngine
rows=[]
for seat in (1,2):
 for name,fragment in [('Phyrexian Tower','Sacrifice'),('Bog Witch','Discard'),('Graven Cairns','{B/R}'),('Flooded Grove','{G/U}')]:
  s=position(seat);c=add(s,name,seat)
  add(s,'Forest',seat,Zone.HAND);add(s,'Island',seat,Zone.HAND)
  add(s,'Raging Goblin',seat);add(s,'Raging Goblin',seat)
  s.players[seat].mana_pool.update(B=1,R=1,G=1)
  move=next(m for m in RulesEngine().legal_moves(s,seat) if m['type']=='activate_mana_ability' and m['card_id']==c.id and fragment in m['cost_text'])
  rows.append(dict(seat=seat,move=move,cards=[dict(id=cid,name=s.cards[cid].name) for cid in s.players[seat].hand+s.players[seat].battlefield]))
print(json.dumps(rows))
`],{cwd:path.join(source,'backend'),encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}}));
const compiled=await build({stdin:{contents:"import {createElement} from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {ManualManaOutput} from '../src/components/ManualManaOutput';export default p=>renderToStaticMarkup(createElement(ManualManaOutput,p));",resolveDir:path.join(source,'frontend/tests'),loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',packages:'external',jsx:'automatic'});
const module={exports:{}};
new Function('require','module','exports',compiled.outputFiles[0].text)(createRequire(import.meta.url),module,module.exports);
for(const row of rows) {
  const wire={player_id:row.seat,revision:0,moves:[row.move]};
  const frozen=JSON.stringify(wire);
  assert.equal(parseLegalMoves(wire),wire,'No alias normalization or invented wire fields');
  const html=module.exports.default({move:row.move,playerId:row.seat,cards:row.cards,onAction(){}});
  assert.match(html,/<fieldset disabled="">/);
  assert.equal((html.match(/ checked=/g)??[]).length,0,'No human flexible card default');
  assert.ok(!html.includes('>Auto</option>'));
  if(row.move.hybrid_symbols.length) assert.match(html,/Choose payment branch/);
  assert.equal(JSON.stringify(wire),frozen);
  for(const change of [
    {activation_costs:{...row.move.activation_costs,discard_cards:-1}},
    {required_choices:{...row.move.required_choices,payment_choices:'yes'}},
    {output_options:[{color:'C',output_bundle:{B:1,R:1}}],base_output_bundles:[{B:1,R:1}]},
    {output_options:[{color:'B',output_bundle:{B:100001}}],base_output_bundles:[{B:100001}]},
    {hybrid_symbols:[{symbol:'B/R',options:['B','R']}]},
  ]) assert.throws(()=>parseLegalMoves({...wire,moves:[{...row.move,...change}]}),/Invalid legal-moves/);
  const missing=module.exports.default({move:{...row.move,activation_costs:undefined},playerId:row.seat,cards:row.cards,onAction(){}});
  assert.match(missing,/Manual payment metadata is unavailable/);
}
assert.equal(rows.length,8);
console.log('PASS 8 canonical both-seat mana consumers: unchanged wire choices, explicit empty drafts, complete BASE vectors, malformed contract rejection, unavailable metadata warnings');
