import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { parseLegalMoves, parseMatchState } from '../src/api/match-contract.ts';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(source, 'backend/.venv/bin/python');
const baseline = process.env.MTG_MECHANIC_BASELINE;
const baselineCode = baseline
  ? execFileSync('git', ['show', `${baseline}:frontend/src/components/Controls.tsx`], { cwd: source, encoding: 'utf8' })
  : await readFile(path.join(source, 'frontend/src/components/Controls.tsx'), 'utf8');
async function compile(code) {
  const compiled = await build({ stdin: { contents: code, resolveDir: path.join(source, 'frontend/src/components'), loader: 'tsx' },
    bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
    define: { 'import.meta.env.VITE_API_BASE_URL': "''" } });
  const module = { exports: {} };
  new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(createRequire(import.meta.url), module, module.exports);
  return module.exports.Controls;
}
const current = await compile(await readFile(path.join(source, 'frontend/src/components/Controls.tsx'), 'utf8'));
const old = await compile(baselineCode);
const require = createRequire(import.meta.url);
const { createElement } = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const rows = JSON.parse(execFileSync(python, ['-c', `
import json,ast
from pathlib import Path
from tests.test_surveil_mill import board,add
from game_state.state import Zone
from game_state.serializers import serialize_match
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
rows=[]
for seat in (1,2):
 state=board(seat)
 add(state,'Otherworldly Gaze',seat,Zone.HAND)
 for name in ('Mind Stone','Grizzly Bears','Island'):add(state,name,seat,Zone.LIBRARY)
 state.players[seat].mana_pool.update(U=1)
 rules=RulesEngine()
 cast=next(m for m in rules.legal_moves(state,seat) if m['type']=='cast_spell')
 state=checked_action(state,rules,seat,{'type':'cast_spell','card_id':cast['card_id']})
 for _ in range(2):state=checked_action(state,rules,state.priority_player,{'type':'pass_priority'})
 assert state.pending_mechanic_choice['kind']=='surveil'
 view=serialize_match(state,look_players={seat});view.update(controllers={'1':'human','2':'human'},revision=0)
 rows.append(dict(seat=seat,state=view,legal=dict(player_id=seat,revision=0,moves=rules.legal_moves(state,seat))))
# Inventory only explicit pending-kind comparisons in the actual dispatcher.
# This prevents the four runtime kinds missing from TS from silently regressing.
kinds=set()
for file in ('keyword_actions.py','engine.py'):
 for node in ast.walk(ast.parse((Path('rules_engine')/file).read_text())):
  if not isinstance(node,ast.Compare):continue
  left=ast.unparse(node.left)
  if left not in ("pending['kind']", "state.pending_mechanic_choice['kind']"):continue
  for value in node.comparators:
   values=value.elts if isinstance(value,(ast.Set,ast.Tuple,ast.List)) else [value]
   kinds.update(v.value for v in values if isinstance(v,ast.Constant) and isinstance(v.value,str))
print(json.dumps(dict(rows=rows,kinds=sorted(kinds))))
`], { cwd: path.join(source, 'backend'), env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8' }));
const types = await readFile(path.join(source, 'frontend/src/types/index.ts'), 'utf8');
const typedKinds = [...types.match(/kind\?: ([^;]+);/)[1].matchAll(/"([a-z_]+)"/g)].map(match => match[1]);
const kinds = [...new Set([...typedKinds, ...rows.kinds])];
const noop = () => {};
function props(row, moves) {
  return { match: row.state, legalMoves: moves, actingPlayerId: row.seat, decks: [], selectedA: null, selectedB: null,
    setSelectedA: noop, setSelectedB: noop, startMode: 'human_vs_human', setStartMode: noop, difficulty: 'normal',
    setDifficulty: noop, bestOf: 1, setBestOf: noop, onStart: noop, startDisabled: true, onPassPriority: noop,
    onKeepHand: noop, onMulligan: noop, onNextStep: noop, onAutoplayTick: noop, autoplayDelayMs: 1000,
    setAutoplayDelayMs: noop, onSubmitBlocks: noop, onSubmitAttack: noop, onApplySideboard: noop, onNextGame: noop,
    onSetPriorityStops: noop, onChooseReplacement: noop, onChooseTriggerOrder: noop, onChooseTriggerTarget: noop,
    onChooseOptionalEffect: noop, onChooseMechanic: noop, responseCountdown: null, autoResponsePaused: false,
    onToggleAutoResponsePause: noop };
}
const render = (component, p) => renderToStaticMarkup(createElement(component, p));
for (const row of rows.rows) {
  parseMatchState(row.state); parseLegalMoves(row.legal);
  const real = props(row, row.legal.moves);
  assert.equal(render(current, real), render(old, real), 'Actual canonical surveil markup unchanged');
  // Protocol seam variants, not fabricated card positions or mechanism certification.
  for (const kind of kinds) {
    const p = props(row, [{ type: 'choose_mechanic', kind, player_id: row.seat, options: [], count: 0 }]);
    assert.equal(render(current, p), render(old, p), `Existing ${kind} control markup must not change`);
  }
  for (const kind of ['__unknown_mechanic__', '', undefined, null, 1, {}]) for (const options of [[], ['__none__']]) {
    const wire = { ...row.legal, moves: [{ type: 'choose_mechanic', kind, player_id: row.seat, options, count: options.length }] };
    parseLegalMoves(wire); // Forward-compatible parser; renderer owns truthful capability warning.
    const html = render(current, props(row, wire.moves));
    assert.ok(html.includes('role="alert"') && html.includes('Unsupported mechanic choice:'));
    assert.ok(!html.includes('Confirm Selection') && !html.includes('Assign Damage') && !html.includes('Confirm Order'));
    assert.ok(!html.includes('>__none__</button>'), 'Sentinel cannot bypass unknown-kind guard');
  }
}
console.log(`PASS both seats: real canonical surveil parity, ${kinds.length} existing kind control-markup parity, 24 unknown/missing/non-string/sentinel warning cases`);
