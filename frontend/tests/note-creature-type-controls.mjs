import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { parseLegalMoves, parseMatchState } from '../src/api/match-contract.ts';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
assert.ok(process.env.MTG_TEST_PYTHON, 'Declare the guarded Python fixture runner');
const rows = JSON.parse(execFileSync(process.env.MTG_TEST_PYTHON, ['-c', `
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent / 'qualification/native-next-cast/tests'))
from test_native_next_creature_entry import source_ready, choose_type
from game_state.serializers import serialize_match, serialize_match_snapshot
from rules_engine.move_generator import legal_moves
rows=[]
for seat in (1,2):
 state,source=source_ready(seat,'Long List of the Ents')
 for player in state.players.values():
  for color in 'WUBRGC':
   player.mana_pool.setdefault(color,0)
 before=serialize_match_snapshot(state)
 moves=legal_moves(state,seat)
 assert serialize_match_snapshot(state)==before
 assert not legal_moves(state,3-seat)
 move=next(m for m in moves if m.get('kind')=='note_creature_type')
 assert 'creature-type:elf' in move['options']
 view=serialize_match(state,look_players={seat})
 view.update(controllers={'1':'human','2':'human'},revision=0)
 assert not any(k in move for k in ('record','resolving_item','history_key'))
 state=choose_type(state,seat,'elf')
 assert state.pending_mechanic_choice is None
 assert state.pending_entry_counters[-1]['__native_next_cast']['filter']=='elf'
 rows.append(dict(seat=seat,state=view,move=move))
print(json.dumps(rows))
`], { cwd: path.join(source, 'backend'), encoding: 'utf8',
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } }));

const compiled = await build({ entryPoints: [path.join(source, 'frontend/src/components/Controls.tsx')],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: { 'import.meta.env.VITE_API_BASE_URL': "''" } });
const require = createRequire(import.meta.url);
const module = { exports: {} };
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
const { createElement } = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const runtime = require('react/jsx-runtime');
const original = { jsx: runtime.jsx, jsxs: runtime.jsxs };
const buttons = [];
// Observe real rendered handlers without changing component or React hook behavior.
for (const key of ['jsx', 'jsxs']) runtime[key] = (type, props, ...args) => {
  if (type === 'button') buttons.push(props);
  return original[key](type, props, ...args);
};
const noop = () => {};
try {
  for (const row of rows) {
    parseMatchState(row.state);
    parseLegalMoves({ player_id: row.seat, revision: 0, moves: [row.move] });
    const wire = JSON.stringify(row);
    const actions = [];
    buttons.length = 0;
    const props = { match: row.state, legalMoves: [row.move], actingPlayerId: row.seat,
      decks: [], selectedA: null, selectedB: null, setSelectedA: noop, setSelectedB: noop,
      startMode: 'human_vs_human', setStartMode: noop, difficulty: 'normal', setDifficulty: noop,
      bestOf: 1, setBestOf: noop, onStart: noop, startDisabled: true, onPassPriority: noop,
      onKeepHand: noop, onMulligan: noop, onNextStep: noop, onAutoplayTick: noop,
      autoplayDelayMs: 1000, setAutoplayDelayMs: noop, onSubmitBlocks: noop, onSubmitAttack: noop,
      onApplySideboard: noop, onNextGame: noop, onSetPriorityStops: noop, onChooseReplacement: noop,
      onChooseTriggerOrder: noop, onChooseTriggerTarget: noop, onChooseOptionalEffect: noop,
      onChooseMechanic: (seat, action) => actions.push({ seat, action }), responseCountdown: null,
      autoResponsePaused: false, onToggleAutoResponsePause: noop };
    const html = renderToStaticMarkup(createElement(module.exports.Controls, props));
    assert.ok(!html.includes('Unsupported mechanic choice:'), 'Native type-note needs a control');
    assert.equal(actions.length, 0, 'Rendering must not infer or submit a type');
    const button = buttons.find(b => b.children === row.move.option_labels['creature-type:elf']);
    assert.ok(button && !button.disabled, 'The offered Elf choice is reachable');
    button.onClick();
    assert.deepEqual(actions, [{ seat: row.seat,
      action: { type: 'choose_mechanic', choice_id: 'creature-type:elf' } }]);
    assert.equal(JSON.stringify(row), wire, 'No mutation or normalization of actor view');
    assert.ok(!html.includes('history_key') && !html.includes('resolving_item'));
    const unknown = renderToStaticMarkup(createElement(module.exports.Controls,
      { ...props, legalMoves: [{ ...row.move, kind: '__unknown_type_note__' }] }));
    assert.ok(unknown.includes('Unsupported mechanic choice:'), 'Unknown kinds remain fail-closed');
  }
} finally {
  Object.assign(runtime, original);
}
assert.equal(rows.length, 2);
console.log('PASS both-seat native type-note views: explicit choice_id callback, no inferred choice, privacy and unknown-kind warning');
