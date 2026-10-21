import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {parseLegalMoves, parseMatchState} from '../src/api/match-contract.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const rows = JSON.parse(execFileSync(python, ['-B', '-c', `
import json
from game_state.serializers import serialize_match,serialize_match_snapshot
from rules_engine.action_validation import ActionRejected,checked_action
from rules_engine.engine import RulesEngine
from tests.variable_suspend_support import NAMES,position
out=[]
for seat in (1,2):
 for name in NAMES:
  state,cid=position(name,seat)
  for player in state.players.values():
   player.mana_pool={**dict.fromkeys('WUBRGC',0),**player.mana_pool}
  view=serialize_match(state,look_players={1,2})
  view.update(controllers={'1':'human','2':'human'},revision=0)
  moves=RulesEngine().legal_moves(state,seat)
  offer=next(m for m in moves if m['type']=='suspend' and m['card_id']==cid)
  cast_moves=[m for m in moves if m['type']=='cast_spell' and m['card_id']==cid]
  assert offer['choice_schema']['x_value']==dict(type='integer',required=True,minimum=1,maximum=3)
  before=serialize_match_snapshot(state)
  for x in (None,0,4,1.5):
   action=dict(type='suspend',card_id=cid)
   if x is not None:action['x_value']=x
   try:checked_action(state,RulesEngine(),seat,action)
   except ActionRejected:pass
   else:raise AssertionError('Invalid suspend X was admitted')
   assert serialize_match_snapshot(state)==before
  action=dict(type='suspend',card_id=cid,x_value=2)
  state=checked_action(state,RulesEngine(),seat,action)
  assert state.cards[cid].counters['time']==2 and cid in state.players[seat].exile
  out.append(dict(seat=seat,cid=cid,name=name,state=view,offer=offer,castMoves=cast_moves,expected=action))
print(json.dumps(out))
`], {cwd: path.join(root, 'backend'), encoding: 'utf8',
  env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));

const require = createRequire(import.meta.url);
const React = require('react');
const states = [];
let cursor = 0;
const adapter = {...React, useMemo: fn => fn(), useEffect() {},
  useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = initial;
    return [states[index], value => {states[index] = typeof value === 'function' ? value(states[index]) : value;}];
  },
  useRef(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = {current: initial};
    return states[index];
  },
};
const compiled = await build({entryPoints: [path.join(root, 'frontend/src/components/Battlefield.tsx')],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(
  name => name === 'react' ? adapter : require(name), module, module.exports);
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
for (const row of rows) {
  const legal = {player_id: row.seat, revision: 0, moves: [row.offer]};
  assert.equal(parseLegalMoves(legal), legal, 'The real variable-Suspend offer must remain usable');
  const rule = row.offer.choice_schema.x_value;
  for (const fields of [{minimum: 0}, {minimum: 1.5}, {maximum: 0}, {maximum: '3'},
    {maximum: Number.MAX_SAFE_INTEGER + 1}, {required: false}, {type: 'number'}]) {
    assert.throws(() => parseLegalMoves({...legal, moves: [{...row.offer,
      choice_schema: {x_value: {...rule, ...fields}}}]}), /legal-moves/);
  }
  for (const fields of [{choice_schema: null}, {choice_schema: {}}, {time_counters: 2},
    {time_counters_variable: false}, {mana_cost: '{X}{Q}'}]) {
    assert.throws(() => parseLegalMoves({...legal, moves: [{...row.offer, ...fields}]}), /legal-moves/);
  }
  {
    states.length = 0;
    const submitted = [];
    const props = {match: parseMatchState(row.state), actingPlayerId: row.seat,
      legalMoves: [...legal.moves, ...row.castMoves],
      onCardAction: (seat, action) => submitted.push({seat, action})};
    const render = () => {cursor = 0; return nodes(module.exports.Battlefield(props));};
    let tree = render();
    const button = () => tree.find(node => node.type === 'button' && text(node.props.children).startsWith(`Suspend ${row.name} (`));
    const input = () => tree.find(node => node.type === 'input' && node.props['aria-label'] === `Suspend X for ${row.name}`);
    assert.ok(input(), 'The actual variable-Suspend hand offer needs an explicit X input');
    assert.equal(input().props.min, 1);
    assert.equal(input().props.max, 3);
    assert.equal(input().props.step, 1);
    assert.equal(input().props.value, '');
    assert.equal(button().props.disabled, true, 'Do not infer a minimum or a previous cast draft');
    for (const invalid of ['', '0', '4', '1.5']) {
      input().props.onChange({target: {value: invalid}});
      tree = render();
      assert.equal(button().props.disabled, true);
      assert.deepEqual(submitted, []);
    }
    input().props.onChange({target: {value: '2'}});
    tree = render();
    assert.equal(button().props.disabled, false);
    button().props.onClick();
    assert.deepEqual(submitted, [{seat: row.seat, action: row.expected}]);
  }
}
console.log(`PASS ${rows.length} real bounded Suspend offers, invalid/missing X, explicit X=2 dispatch and paid engine outcome`);
