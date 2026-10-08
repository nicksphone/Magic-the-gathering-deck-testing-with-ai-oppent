import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { parseLegalMoves, parseMatchState } from '../src/api/match-contract.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const rows = JSON.parse(execFileSync(python, ['-c', `
import sys,json
def deny(event,args):
 if event.startswith(('sqlite3.','socket.')) or event in ('subprocess.Popen','os.system','os.fork','os.posix_spawn'):
  raise AssertionError('pure UI fixture denied '+event)
sys.addaudithook(deny)
sys.path.insert(0,'../audit/brainstorm')
from test_brainstorm_desired import position,brainstorm,add,act,RULES
from game_state.state import Zone
from game_state.serializers import serialize_match
rows=[]
for seat in (1,2):
 state=position(seat)
 for player in state.players.values(): player.snow_mana_pool.clear()
 add(state,'Counterspell',seat,Zone.HAND)
 state,_=brainstorm(state,seat)
 moves=RULES.legal_moves(state,seat)
 move=next(m for m in moves if m.get('kind')=='hand_top_order')
 chosen=[move['options'][1],move['options'][0]]
 resolved=act(state,seat,{'type':'choose_mechanic','card_ids':chosen})
 assert resolved.players[seat].library[-2:]==list(reversed(chosen))
 view=serialize_match(state,look_players={seat})
 view.update(controllers={'1':'human','2':'human'},revision=0)
 rows.append(dict(seat=seat,state=view,legal=dict(player_id=seat,revision=0,moves=moves),chosen=chosen))
print(json.dumps(rows))
`], { cwd: path.join(root, 'backend'), env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8' }));

const require = createRequire(import.meta.url);
const realReact = require('react');
let values, index;
const hooks = { ...realReact, useEffect() {}, useMemo: fn => fn(),
  useState(initial) {
    const slot = index++;
    if (!(slot in values)) values[slot] = typeof initial === 'function' ? initial() : initial;
    return [values[slot], next => { values[slot] = typeof next === 'function' ? next(values[slot]) : next; }];
  } };
const compiled = await build({ stdin: { contents: await readFile(path.join(root, 'frontend/src/components/Controls.tsx'), 'utf8'),
  resolveDir: path.join(root, 'frontend/src/components'), loader: 'tsx' }, bundle: true, write: false,
  platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
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
  if (value === null || value === undefined || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props?.children) : String(value);
}
for (const row of rows) {
  parseMatchState(row.state); parseLegalMoves(row.legal);
  values = []; const sent = [];
  const props = { match: row.state, legalMoves: row.legal.moves, actingPlayerId: row.seat,
    decks: [], selectedA: null, selectedB: null, bestOf: 1, startMode: 'human_vs_human',
    difficulty: 'normal', autoplayDelayMs: 1000, responseCountdown: null, autoResponsePaused: false,
    onChooseMechanic: (seat, action) => sent.push({ seat, action }) };
  const render = () => { index = 0; return nodes(module.exports.Controls(props)); };
  const button = label => render().find(node => node.type === 'button' && text(node) === label);
  const move = row.legal.moves.find(move => move.kind === 'hand_top_order');
  assert.ok(!render().some(node => node.props?.role === 'alert' && text(node).includes('Unsupported mechanic')));
  assert.ok(render().some(node => text(node).includes('topmost first')));
  assert.equal(button('Confirm Order')?.props.disabled, true);
  // Select in deliberate reverse option order; IDs must not be sorted or inferred.
  for (const id of row.chosen) {
    button(move.option_labels[id]).props.onClick();
    assert.equal(button(move.option_labels[id]).props.disabled, true);
  }
  assert.equal(button('Confirm Order').props.disabled, false);
  button('Confirm Order').props.onClick();
  assert.deepEqual(sent, [{ seat: row.seat, action: { type: 'choose_mechanic', card_ids: row.chosen } }]);
  button('Reset Order').props.onClick();
  assert.equal(button('Confirm Order').props.disabled, true);
  assert.equal(sent.length, 1);
}
console.log('PASS both seats: canonical paid Brainstorm view, deliberate topmost-first selection, exact actor/ordered IDs, reset and cardinality');
