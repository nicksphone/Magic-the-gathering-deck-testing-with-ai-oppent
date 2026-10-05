import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { parseLegalMoves, parseMatchState } from '../src/api/match-contract.ts';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(source, 'backend/.venv/bin/python');
// Generate views from the real backend and pinned canonical records, not fake
// UI-only cards or preselected targets. No App/API methods are replaced.
const rows = JSON.parse(execFileSync(python, ['-c', `
import json
from tests.test_suspend_lifecycle import setup,ready,CARDS
from tests.test_ai_recurring_engines import add
from game_state.serializers import serialize_match
from rules_engine.engine import RulesEngine
out=[]
for seat in (1,2):
 for case in ('hand','creature-hand','pending','no-target','unpayable'):
  state,cid=setup(seat,'Errant Ephemeron' if case=='creature-hand' else 'Rift Bolt')
  if case=='no-target':
   for owner in (1,2):add(state,'Ivory Mask',owner,cards=CARDS)
  if case in ('pending','no-target'):state=ready(state,seat,cid)
  if case=='unpayable':state.players[seat].mana_pool.clear()
  view=serialize_match(state,look_players={1,2})
  view.update(controllers={'1':'human','2':'human'},revision=0)
  out.append(dict(seat=seat,case=case,cid=cid,state=view,moves=dict(player_id=seat,revision=0,moves=RulesEngine().legal_moves(state,seat))))
print(json.dumps(out))
`], { cwd: path.join(source, 'backend'), env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8' }));

const compiled = await build({ stdin: {
  contents: "import {createElement} from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {Battlefield} from '../src/components/Battlefield';export default props=>renderToStaticMarkup(createElement(Battlefield,props));",
  resolveDir: path.join(source, 'frontend/tests'), loader: 'tsx',
}, bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: { 'import.meta.env.VITE_API_BASE_URL': "''" } });
const module = { exports: {} };
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(createRequire(import.meta.url), module, module.exports);
const render = module.exports.default;
const castButton = /<button\b[^>]*>\s*Cast Rift Bolt/;
for (const row of rows) {
  parseMatchState(row.state); parseLegalMoves(row.moves);
  const props = { match: row.state, legalMoves: row.moves.moves, actingPlayerId: row.seat, onCardAction() {} };
  const html = render(props);
  assert.ok(!html.includes('No control is implemented'), row.case);
  if (row.case.endsWith('hand')) {
    const move = row.moves.moves.find(move => move.type === 'suspend');
    assert.ok(html.includes(`Suspend ${move.card_name} (${move.mana_cost}; ${move.time_counters} time counter`));
    for (const fields of [{ time_counters: 0 }, { time_counters: 1.5 }, { time_counters: '1' },
      { mana_cost: 'pay life' }, { mana_cost: '{X}' }, { card_id: '' }]) {
      assert.throws(() => parseLegalMoves({ ...row.moves, moves: [{ ...move, ...fields }] }), /legal-moves/);
    }
  } else if (row.case === 'unpayable') assert.ok(!html.includes('>Suspend '));
  else {
    assert.ok(html.includes('suspend-cast-panel') && html.includes('Decline suspended casting'));
    const move = row.moves.moves.find(move => move.kind === 'suspend_cast');
    for (const fields of [{ player_id: 3-row.seat }, { options: ['cast'] }, { count: 0 }]) {
      assert.throws(() => parseLegalMoves({ ...row.moves, moves: [{ ...move, ...fields }] }), /legal-moves/);
    }
    if (row.case === 'no-target') {
      assert.ok(html.includes('No legal cast is available'));
      assert.ok(!castButton.test(html));
    } else assert.ok(castButton.test(html));
    const foreign = render({ ...props, actingPlayerId: 3-row.seat });
    assert.ok(!foreign.includes('suspend-cast-panel') && !castButton.test(foreign));
    const ai = render({ ...props, match: { ...row.state, controllers: { ...row.state.controllers, [row.seat]: 'ai' } } });
    assert.ok(!ai.includes('suspend-cast-panel') && !castButton.test(ai));
  }
  const card = row.state.players[String(row.seat)].hand[0];
  if (card) assert.throws(() => parseMatchState({ ...row.state, players: { ...row.state.players,
    [row.seat]: { ...row.state.players[String(row.seat)], hand: [{ ...card, suspended: 'yes' }] } } }), /card view/);
}
console.log('PASS 10 canonical backend-rendered Suspend UI states, choice-owner/AI guards and strict wire contracts');
