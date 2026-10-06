import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {manaShortcut} from '../src/components/manual-mana-shortcut.ts';

const backend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../backend');
const python=process.env.MTG_TEST_PYTHON;
assert.ok(python,'Use the external Python environment');
const options={cwd:backend,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}};
const rows=JSON.parse(execFileSync(python,['-c',`
import json
from tests.test_mana_executor_choices import position,add
from tests.test_mandatory_base_vectors import ROWS
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
cases=[('Island','U',None),('Forest','G',None),('Gyre Engineer','G',None),
 ('Gyre Engineer','G','sphere'),('Simic Growth Chamber','G',None),
 ('Simic Growth Chamber','C','sphere'),('Tropical Island','C','reflection-sphere'),
 ('Phyrexian Tower','B',None),('Bog Witch','B',None),('Graven Cairns','B',None)]
rows=[]
for seat in (1,2):
 for name,color,variant in cases:
  s=position(seat);c=add(s,name,seat)
  add(s,'Raging Goblin',seat);add(s,'Forest',seat,Zone.HAND)
  s.players[seat].mana_pool.update(B=1)
  if variant=='reflection-sphere':add(s,'Mana Reflection',seat)
  if variant:add(s,'Damping Sphere',seat)
  before=serialize_match_snapshot(s);moves=RulesEngine().legal_moves(s,seat)
  assert serialize_match_snapshot(s)==before
  rows.append(dict(seat=seat,name=name,color=color,variant=variant,land='Land' in c.types,source=c.id,moves=moves,snapshot=before))
print(json.dumps(rows))
`],options));
for(const row of rows) {
  const before=JSON.stringify(row);
  const action=manaShortcut(row.moves,row.source,row.color,row.land);
  assert.deepEqual(manaShortcut(row.moves,row.source,row.color,row.land),action);
  assert.equal(JSON.stringify(row),before);
  if(['Phyrexian Tower','Bog Witch','Graven Cairns','Tropical Island'].includes(row.name))assert.equal(action,null,'No implicit resource/hybrid payment or ambiguous final-color index');
  else if(['Gyre Engineer','Simic Growth Chamber'].includes(row.name)) {
    assert.ok(action,`${row.name} ${row.variant ?? 'plain'} seat ${row.seat}: expected offered shortcut`);
    assert.equal(action.type,'activate_mana_ability');
    assert.deepEqual(action.output_bundle,{G:1,U:1});
    assert.ok(['G','U'].includes(action.color),'Replacement C must not be a GU base anchor');
    action.output_bundle.G=9;
    assert.equal(JSON.stringify(row),before,'Shortcut vector never aliases the offered view');
    action.output_bundle.G=1;
  } else {
    assert.equal(action.type,'tap_land_for_mana','Unambiguous basic/modal legacy controls remain unchanged');
    assert.equal(action.output_bundle,undefined);
  }
  row.action=action;
}
const plain=rows[0];
const move=plain.moves.find(m=>m.type==='activate_mana_ability'&&m.card_id===plain.source);
assert.equal(manaShortcut([move,{...move,ability_index:99}],plain.source,'U',true),null,'No inferred ambiguous index');
assert.equal(manaShortcut([{...move,cost_text:'{X}, {T}'}],plain.source,'U',true),null,'Unsupported X metadata is not a payable control');
// These are negative metadata controls on a real view, not invented card Oracle.
const paid={...move,ability_index:99,cost_text:'{1}, {T}'};
assert.equal(manaShortcut([move,paid],plain.source,'U',false).type,'activate_mana_ability','A plain plus paid color collision uses the offered explicit plain index');
console.log(execFileSync(python,['-c',`
import json,sys
from game_state.serializers import deserialize_match_snapshot,serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
count=0
for row in json.load(sys.stdin):
 if row['action'] is None:continue
 state=deserialize_match_snapshot(row['snapshot']);before=serialize_match_snapshot(state)
 result=checked_action(state,RulesEngine(),row['seat'],row['action'])
 assert serialize_match_snapshot(state)==before
 expected={'C':1} if row['variant'] and row['land'] else {'G':1,'U':1} if row['name'] in ('Gyre Engineer','Simic Growth Chamber') else {row['color']:1}
 # Original B funding is unrelated to these free activations.
 expected['B']=1
 assert {k:v for k,v in result.players[row['seat']].mana_pool.items() if v}==expected
 count+=1
print('PASS',count,'canonical both-seat checked shortcut actions; mixed GU and SphereC explicit base vectors; basic/modal legacy unchanged; root purity')
`],{...options,input:JSON.stringify(rows)}).trim());
assert.equal(rows.length,20);
console.log('PASS 20 canonical shortcut views plus negative ambiguity/X controls, no payment defaults, deterministic independent vectors');
