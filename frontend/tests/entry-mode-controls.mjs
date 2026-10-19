import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';
import { build } from 'esbuild';
import { parseLegalMoves, parseMatchState } from '../src/api/match-contract.ts';

const rows = JSON.parse(await readFile(new URL('./fixtures/entry-mode-public/paid-views.json', import.meta.url)));
assert.equal(rows.length, 4);
assert.deepEqual(rows.map(row => [row.seat, row.mode]), [[1, 'creature'], [1, 'player'], [2, 'creature'], [2, 'player']]);

const require = createRequire(import.meta.url);
const { createElement } = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const runtime = require('react/jsx-runtime');
const original = { jsx: runtime.jsx, jsxs: runtime.jsxs };
const buttons = [];
const compiled = await build({ entryPoints: [new URL('../src/components/Controls.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: { 'import.meta.env.VITE_API_BASE_URL': "''" } });
const module = { exports: {} };
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
// Observe actual rendered callbacks without replacing React hooks or the component.
for (const key of ['jsx', 'jsxs']) runtime[key] = (type, props, ...args) => {
  if (type === 'button') buttons.push(props);
  return original[key](type, props, ...args);
};
try {
  for (const row of rows) for (const options of [row.move.options, [row.chosen]]) {
    const { seat } = row;
    parseMatchState(row.state);
    // Original paid views plus a protocol-only offered-single-mode boundary.
    const move = { ...row.move, options };
    parseLegalMoves({ player_id: seat, revision: 0, moves: [move] });
    const before = JSON.stringify(move);
    const sent = [];
    const props = { decks: [], selectedA: null, selectedB: null, bestOf: 1,
      startMode: 'human_vs_human', difficulty: 'normal', autoplayDelayMs: 1000,
      responseCountdown: null, autoResponsePaused: false, match: row.state,
      legalMoves: [move], onChooseMechanic: (player, action) => sent.push({ player, action }) };
    buttons.length = 0;
    const html = renderToStaticMarkup(createElement(module.exports.Controls, props));
    assert.ok(!html.includes('Unsupported mechanic choice:'));
    assert.ok(!html.includes('Confirm Selection'), 'Modes must not submit card_ids');
    assert.deepEqual(sent, [], 'Rendering must not choose a default mode');
    for (const id of options) {
      const button = buttons.find(button => button.children === move.option_labels[id]);
      assert.ok(button && !button.disabled, 'Every offered mode is reachable');
      button.onClick();
      assert.deepEqual(sent.at(-1), { player: seat, action: { type: 'choose_mechanic', choice_id: id } });
    }
    for (const id of Object.keys(move.option_labels).filter(id => !options.includes(id))) {
      assert.ok(!buttons.some(button => button.children === move.option_labels[id]), 'Unprovided modes are not invented');
    }
    assert.equal(JSON.stringify(move), before);
    const unknown = renderToStaticMarkup(createElement(module.exports.Controls,
      { ...props, legalMoves: [{ ...move, kind: '__unknown_entry_mode__' }] }));
    assert.ok(unknown.includes('Unsupported mechanic choice:'));
  }
} finally {
  Object.assign(runtime, original);
}
console.log('PASS paid entry-mode views: both seats and modes, explicit callbacks, offered-only options, no inferred choice, unknown-kind warning');
