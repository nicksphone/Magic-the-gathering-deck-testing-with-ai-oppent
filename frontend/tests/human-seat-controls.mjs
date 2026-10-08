import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';

const require = createRequire(import.meta.url);
const {createElement} = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const runtime = require('react/jsx-runtime');
const original = {jsx: runtime.jsx, jsxs: runtime.jsxs};
const compiled = await build({entryPoints: [new URL('../src/components/Controls.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', compiled.outputFiles[0].text)(require, module, module.exports);
const selects = [];
for (const key of ['jsx', 'jsxs']) runtime[key] = (type, props, ...args) => {
  if (type === 'select') selects.push(props);
  return original[key](type, props, ...args);
};
try {
  for (const humanSeat of [1, 2]) for (const startMode of ['player_vs_ai', 'human_vs_human', 'ai_vs_ai']) {
    const chosen = [];
    selects.length = 0;
    const html = renderToStaticMarkup(createElement(module.exports.Controls, {
      decks: [], selectedA: null, selectedB: null, bestOf: 3, startMode, humanSeat,
      setHumanSeat: value => chosen.push(value), difficulty: 'master', autoplayDelayMs: 1000,
      responseCountdown: null, autoResponsePaused: false, match: null, legalMoves: [],
    }));
    const control = selects.find(props => props['aria-label'] === 'Human seat');
    assert.deepEqual(chosen, [], 'Rendering cannot choose a different seat');
    if (startMode !== 'player_vs_ai') {
      assert.equal(control, undefined);
      continue;
    }
    assert.ok(control, 'Player vs AI must expose both human seats');
    assert.equal(control.value, humanSeat);
    assert.ok(html.includes('Seat 1 (Deck A)') && html.includes('Seat 2 (Deck B)'));
    for (const value of ['1', '2']) {
      control.onChange({currentTarget: {value}});
      assert.equal(chosen.at(-1), Number(value));
    }
    const before = chosen.length;
    for (const value of ['', '0', '3', '2.5', 'ai']) control.onChange({currentTarget: {value}});
    assert.equal(chosen.length, before, 'Unoffered seats are not coerced');
  }
} finally {Object.assign(runtime, original);}
console.log('PASS actual Human seat controls: both seats, offered-only callbacks, mode boundaries and no default mutation');
