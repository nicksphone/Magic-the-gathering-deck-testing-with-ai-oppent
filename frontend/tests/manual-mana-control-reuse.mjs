import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
assert.ok(process.env.MTG_TEST_PYTHON, 'Declare the external Python environment');
const rows = JSON.parse(execFileSync(process.env.MTG_TEST_PYTHON, ['-c', `
import json
from tests.test_activation_payment_choices import position
from tests.test_contextual_cost_prohibitions import canonical
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
out=[]
for seat in (1,2):
 for kind in ('discard','sacrifice'):
  state,source,candidates,key=position(seat,kind)
  foreign=canonical(state,'viscera-seer',3-seat,Zone.HAND if kind=='discard' else Zone.BATTLEFIELD)
  before=serialize_match_snapshot(state)
  move=next(m for m in RulesEngine().legal_moves(state,seat) if m['type']=='activate_ability' and m['card_id']==source.id)
  assert serialize_match_snapshot(state)==before
  assert set(move['payment_options'][key])=={c.id for c in candidates}
  own=state.players[seat]
  cards=[dict(id=cid,name=state.cards[cid].name) for cid in own.hand+own.battlefield]
  out.append(dict(seat=seat,kind=kind,move=move,cards=cards,candidate_ids=[c.id for c in candidates],foreign_id=foreign.id))
print(json.dumps(out))
`], {cwd: path.join(source, 'backend'), encoding: 'utf8',
  env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));
const compiled = await build({stdin: {
  contents: "import {createElement} from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {PermanentActions} from '../src/components/PermanentActions';export default p=>renderToStaticMarkup(createElement(PermanentActions,p));",
  resolveDir: path.join(source, 'frontend/tests'), loader: 'tsx',
}, bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic'});
const module = {exports: {}};
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(createRequire(import.meta.url), module, module.exports);
for (const row of rows) {
  const html = module.exports.default({moves: [row.move], playerId: row.seat, cards: row.cards, onAction() {}});
  assert.equal((html.match(/type="checkbox"/g) ?? []).length, 2);
  assert.equal((html.match(/ checked=/g) ?? []).length, 0, 'No flexible resource selected for the human');
  for (const id of row.candidate_ids) assert.ok(html.includes(id));
  assert.ok(!html.includes(row.foreign_id), 'Opponent resource must never become a payment option');
  assert.match(html, /<button disabled="">Activate /);
}
assert.equal(rows.length, 4);
console.log('PASS 4 canonical both-seat reusable ability dialogs: actor-only candidates, no preselected flexible resources, incomplete payment disabled');
