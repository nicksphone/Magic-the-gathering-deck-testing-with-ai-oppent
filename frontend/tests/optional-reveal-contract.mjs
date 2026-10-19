import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseLegalMoves,parseMatchState} from '../src/api/match-contract.ts';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const python=process.env.MTG_TEST_PYTHON || path.join(root,'backend/.venv/bin/python');
const rows=JSON.parse(execFileSync(python,['-c',`import json
from tests.test_optional_reveal_transform import pending,ENGINE
from game_state.serializers import serialize_match
rows=[]
for seat in (1,2):
 s,_,_=pending(seat)
 view=serialize_match(s);view.update(revision=0,controllers={'1':'human','2':'human'})
 rows.append({'seat':seat,'state':view,'legal':{'player_id':seat,'revision':0,'moves':ENGINE.legal_moves(s,seat)}})
print(json.dumps(rows))`],{cwd:path.join(root,'backend'),encoding:'utf8'}));
for(const row of rows){
 parseMatchState(row.state);parseLegalMoves(row.legal);
 const original=row.legal.moves[0];
 for(const patch of [{player_id:3-row.seat},{count:0},{options:['reveal']},{options:['reveal','reveal']},
  {inspected_cards:[]},{inspected_cards:[{}]},{option_labels:{reveal:42,decline:'Decline'}}])
  assert.throws(()=>parseLegalMoves({...row.legal,moves:[{...original,...patch}]}),/legal.moves/i);
 assert.deepEqual(Object.keys(row.state.pending_mechanic_choice).sort(),['count','kind','label','player_id']);
}
console.log('PASS both-seat canonical optional reveal contracts, private status, malformed view rejection');
