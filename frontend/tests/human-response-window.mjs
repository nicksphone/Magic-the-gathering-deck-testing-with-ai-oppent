import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

// Evaluate the actual App prerequisite, not a duplicate of its policy.
const file = ts.createSourceFile('App.tsx', readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8'),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let initializer;
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(file) === 'humanResponseWindowActive') {
    assert.equal(initializer, undefined, 'The response guard must be unique');
    initializer = node.initializer;
  }
  ts.forEachChild(node, visit);
}
visit(file);
assert.ok(initializer, 'The actual response guard must exist');
const keys = ['match', 'restoring', 'mutationPending', 'autoProgressPaused', 'legalPlayerId', 'legalMoves', 'canAutoPass'];
const expression = ts.createPrinter().printNode(ts.EmitHint.Expression, initializer, file);
const evaluate = new Function(...keys, `return (${expression});`);
const base = {
  match: { mode: 'player_vs_ai', controllers: { 1: 'human', 2: 'ai' },
    pregame_pending: false, match_complete: false, winner: null, stack: [{ id: 'view-only-stack' }] },
  restoring: false, mutationPending: false, autoProgressPaused: false,
  legalPlayerId: 1, legalMoves: [{ type: 'pass_priority' }], canAutoPass: false,
};
let checked = 0;
const failures = [];
function check(value, expected, label) {
  const actual = evaluate(...keys.map(key => value[key]));
  if (actual !== expected) failures.push({ label, expected, actual });
  checked++;
}
for (const humanSeat of [1, 2]) {
  const state = structuredClone(base);
  state.match.controllers = { 1: humanSeat === 1 ? 'human' : 'ai', 2: humanSeat === 2 ? 'human' : 'ai' };
  for (const priority of [1, 2]) {
    state.legalPlayerId = priority;
    check(state, priority === humanSeat, `Human seat ${humanSeat}, priority ${priority}`);
    check(JSON.parse(JSON.stringify(state)), priority === humanSeat, 'Restored public controller map');
  }
  state.legalPlayerId = humanSeat;
  for (const key of ['restoring', 'mutationPending', 'autoProgressPaused', 'canAutoPass']) {
    check({ ...state, [key]: true }, false, key);
  }
  for (const change of [
    { pregame_pending: true }, { match_complete: true }, { winner: humanSeat }, { stack: [] },
    { mode: 'human_vs_human' }, { mode: 'ai_vs_ai' }, { controllers: {} }, { controllers: undefined },
  ]) check({ ...state, match: { ...state.match, ...change } }, false, JSON.stringify(change));
  check({ ...state, legalMoves: [] }, false, 'No legal priority pass');
  check({ ...state, match: null }, false, 'No active match');
}
assert.deepEqual(failures, [], 'All actual App response-guard cases must pass');
console.log(`PASS ${checked} actual App response-guard checks; both seats, restore and pending-state boundaries`);
