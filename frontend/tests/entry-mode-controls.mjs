import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { build } from 'esbuild';
import { parseLegalMoves } from '../src/api/match-contract.ts';

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
  for (const seat of [1, 2]) for (const options of [['mode-1', 'mode-2'], ['mode-2']]) {
    // Public protocol controls; backend paid execution is qualified separately.
    const move = { type: 'choose_mechanic', kind: 'entry_mode', player_id: seat,
      count: 1, label: 'Entry choice', options,
      option_labels: { 'mode-1': 'Remove counters from a creature', 'mode-2': 'Remove counters from an opponent' } };
    parseLegalMoves({ player_id: seat, revision: 0, moves: [move] });
    const before = JSON.stringify(move);
    const sent = [];
    const props = { decks: [], selectedA: null, selectedB: null, bestOf: 1,
      startMode: 'human_vs_human', difficulty: 'normal', autoplayDelayMs: 1000,
      responseCountdown: null, autoResponsePaused: false, match: null,
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
console.log('PASS entry-mode controls: both seats, explicit symbolic choices, offered-only options, no inferred choice, unknown-kind warning');
