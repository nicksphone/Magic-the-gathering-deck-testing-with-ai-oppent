import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import {build} from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const built = await build({entryPoints: [new URL('../src/components/Controls.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const module = {exports: {}};
new Function('require', 'module', 'exports', built.outputFiles[0].text)(name => name === 'react'
  ? {...React, useState: initial => [initial, () => {}], useMemo: fn => fn(), useEffect: () => {}}
  : require(name), module, module.exports);

const source = await readFile(new URL('./browser-human-actions.mjs', import.meta.url), 'utf8');
const start = source.indexOf('async function chooseCopyOption(optionId) {');
const end = source.indexOf('\nasync function assignDamage(', start);
assert.ok(start >= 0 && end > start, 'The browser must use the current one-click copy choice controls');
const helper = source.slice(start, end);
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props?.children)];
}

for (const seat of [1, 2]) {
  const submitted = [];
  const choice = {type: 'choose_mechanic', kind: 'copy_target', player_id: seat,
    options: ['keep', 'target_player:1', 'target_card_id:bear'], count: 1, min_count: 1,
    option_labels: {keep: 'Keep original target', 'target_player:1': 'Player A', 'target_card_id:bear': 'Grizzly Bears'}};
  const tree = nodes(module.exports.Controls({decks: [], bestOf: 1, startMode: 'human_vs_human',
    humanSeat: seat, difficulty: 'master', autoplayDelayMs: 1000, responseCountdown: null,
    autoResponsePaused: false, match: {id: 1, revision: 1, priority_player: seat,
      pending_mechanic_choice: choice}, legalMoves: [choice],
    onChooseMechanic: (player_id, action) => submitted.push({player_id, action})}));
  const panel = nodes(tree.find(node => node.props.className === 'block-panel'));
  assert.ok(panel.length);
  assert.ok(!panel.some(node => node.type === 'input' && node.props.type === 'checkbox'));
  assert.ok(!panel.some(node => node.type === 'button' && node.props.children === 'Confirm Selection'));
  const choose = vm.runInNewContext(`(${helper})`, {assert,
    evaluate: async expression => {
      assert.equal(expression, 'window.fixtureState.pending_mechanic_choice');
      return choice;
    },
    click: async label => {
      const button = panel.find(node => node.type === 'button' && node.props.children === label);
      assert.ok(button, `No actual offered button for ${label}`);
      button.props.onClick();
    }});
  for (const id of choice.options) {
    await choose(id);
    assert.deepEqual(submitted.at(-1), {player_id: seat, action: {type: 'choose_mechanic', card_ids: [id]}});
  }
  assert.equal(submitted.length, 3, 'Each deliberate button sends exactly one choice');
  await assert.rejects(choose('target_player:9'));
  choice.kind = 'discard';
  await assert.rejects(choose('keep'));
  assert.equal(submitted.length, 3, 'Invalid or stale choices never submit');
}
console.log('PASS actual Controls copy buttons and browser helper: both seats, keep/retarget, one action, stale choices rejected');
