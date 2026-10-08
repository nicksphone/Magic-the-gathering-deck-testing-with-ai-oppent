import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {parseLegalMoves, parseMatchState} from '../src/api/match-contract.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = process.env.MTG_TEST_PYTHON || path.join(root, 'backend/.venv/bin/python');
const rows = JSON.parse(execFileSync(python, [path.join(root, 'frontend/tests/keeper-energy-engine.py')], {
  cwd: path.join(root, 'backend'), encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'},
}));
assert.equal(rows.length, 6);
const require = createRequire(import.meta.url);
const React = require('react');
const built = await build({entryPoints: [path.join(root, 'frontend/src/components/Controls.tsx')],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', built.outputFiles[0].text)(name => name === 'react'
  ? {...React, useState: initial => [initial, () => {}], useMemo: fn => fn(), useEffect: () => {}} : require(name), module, module.exports);
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
const failures = [];
for (const row of rows) {
  const match = parseMatchState(row.state);
  const legal = parseLegalMoves(row.legal);
  const move = legal.moves[0];
  const submitted = [];
  const props = {decks: [], bestOf: 1, startMode: 'human_vs_human', humanSeat: row.seat,
    difficulty: 'master', autoplayDelayMs: 1000, responseCountdown: null, autoResponsePaused: false,
    match, legalMoves: legal.moves, onChooseMechanic: (seat, action) => submitted.push({seat, action})};
  const tree = module.exports.Controls(props);
  if (text(tree).includes('Unsupported mechanic choice:')) {
    failures.push(`${move.kind} seat${row.seat} options=${move.options.join(',')}`);
    continue;
  }
  const buttons = nodes(tree).filter(node => node.type === 'button');
  for (const option of move.options) {
    const button = buttons.find(node => move.kind === 'legend_keeper'
      ? node.props['data-legend-keeper-id'] === option : text(node.props.children) === move.option_labels[option]);
    assert.ok(button, `Every actual offered ${move.kind} option must be reachable`);
    if (move.kind === 'legend_keeper') {
      const card = Object.values(match.players).flatMap(player => player.battlefield).find(card => card.id === option);
      assert.ok(text(button.props.children).includes(option), 'Identically named legends keep distinct public IDs');
      assert.ok(text(button.props.children).includes(`${card.power}/${card.toughness}`), 'Keeper choices display actual public characteristics');
      assert.ok(text(button.props.children).includes(card.tapped ? 'Tapped' : 'Untapped'));
    }
    assert.equal(Boolean(button.props.disabled), false);
    button.props.onClick();
    assert.deepEqual(submitted.at(-1), {seat: row.seat, action: move.kind === 'legend_keeper'
      ? {type: 'choose_mechanic', card_ids: [option]} : {type: 'choose_mechanic', choice_id: option}});
  }
  assert.equal(submitted.length, move.options.length, 'No default choice is submitted while rendering');
  if (move.kind === 'exchange_energy_payment' && !move.options.includes('pay')) {
    assert.equal(buttons.some(node => text(node.props.children) === move.option_labels.pay), false, 'Unaffordable payment is not fabricated');
  }
  const hidden = module.exports.Controls({...props, legalMoves: []});
  assert.equal(nodes(hidden).some(node => node.props?.['data-legend-keeper-id']), false, 'No offered keeper cannot expose a card action');
}
assert.deepEqual(failures, [], 'Actual backend continuations cannot stop at unsupported UI controls');
const unknown = module.exports.Controls({decks: [], bestOf: 1, startMode: 'human_vs_human', humanSeat: 1,
  difficulty: 'master', autoplayDelayMs: 1000, responseCountdown: null, autoResponsePaused: false,
  match: null, legalMoves: [{type: 'choose_mechanic', kind: 'future_unknown_choice', player_id: 1, options: ['do_not_guess'], count: 1}]});
assert.ok(text(unknown).includes('Unsupported mechanic choice: future_unknown_choice'));
console.log('PASS six canonical paid continuation views: both-seat keeper selections, energy pay/decline/unaffordability, exact callbacks and unknown-choice warning');
