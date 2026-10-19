import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { build } from 'esbuild';
import { parseLegalMoves, parseMatchState } from '../src/api/match-contract.ts';

const { rows } = JSON.parse(await readFile(new URL('./fixtures/spree-public/paid-views.json', import.meta.url)));
const require = createRequire(import.meta.url);
const react = require('react');
let values, index;
const hooks = { ...react, useEffect() {}, useMemo: fn => fn(), useRef: value => ({ current: value }),
  useState(initial) {
    const slot = index++;
    if (!(slot in values)) values[slot] = typeof initial === 'function' ? initial() : initial;
    return [values[slot], next => { values[slot] = typeof next === 'function' ? next(values[slot]) : next; }];
  } };
const compiled = await build({ entryPoints: [new URL('../src/components/Battlefield.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
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
  if (value == null || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props?.children) : String(value);
}
assert.equal(rows.length, 6);
const receipts = [];
for (const row of rows) {
  const move = row.actual_offered_move;
  const actor = row.casting_player;
  assert.notEqual(actor, row.fixture_seat);
  const match = { ...row.actual_public_serialized_match, revision: row.protocol_envelope.revision,
    controllers: row.protocol_envelope.controllers };
  const legal = { player_id: actor, revision: 0, moves: [move] };
  parseMatchState(match); parseLegalMoves(legal);
  const before = JSON.stringify({ match, legal });
  const modes = move.target_hints.modes;
  const chosen = row.selection === 2 ? modes : [modes[row.selection]];
  values = []; const sent = [];
  const props = { match, legalMoves: [move], actingPlayerId: actor,
    onCardAction: (seat, action) => sent.push({ seat, action: JSON.parse(JSON.stringify(action)) }) };
  const render = () => { index = 0; return nodes(module.exports.Battlefield(props)); };
  const cast = () => render().find(node => node.type === 'button' && text(node).startsWith(`Cast ${move.card_name}`));
  const select = label => render().find(node => node.type === 'select' && node.props['aria-label'] === label);
  assert.equal(cast().props.disabled, true);
  assert.deepEqual(select('Spell modes').props.value, []);
  assert.deepEqual(sent, [], 'Rendering must not infer a mode or target');
  select('Spell modes').props.onChange({ target: { selectedOptions: chosen.map(value => ({ value })) } });
  assert.equal(cast().props.disabled, true, 'Every selected mode needs its own deliberate target');
  const targets = {};
  for (const mode of chosen) {
    const id = row.actual_checked_action.targets.mode_targets?.[mode]?.target_stack_id
      ?? row.actual_checked_action.targets.target_stack_id;
    assert.ok(move.target_hints.mode_target_hints[mode].stack_targets.some(option => option.id === id));
    select(`Target for ${mode}`).props.onChange({ target: { value: id } });
    targets[mode] = { target_stack_id: id };
  }
  assert.equal(cast().props.disabled, false);
  const cost = move.target_hints.mode_base_mana_costs.base
    + chosen.map(mode => move.target_hints.mode_additional_mana_costs[mode]).join('');
  assert.ok(text(cast()).includes(`(${cost})`), 'Show selected costs without adding the preview minimum twice');
  cast().props.onClick();
  assert.deepEqual(sent, [{ seat: actor, action: { type: 'cast_spell', card_id: move.card_id,
    targets: { mode_texts: chosen, mode_targets: targets }, cost_choice: { id: 'base' },
    from_graveyard: move.from_graveyard } }]);
  receipts.push({ fixture_seat: row.fixture_seat, selection: row.selection, ...sent[0] });
  select(`Target for ${chosen[0]}`).props.onChange({ target: { value: 'stale-stack-id' } });
  assert.equal(cast().props.disabled, true);
  select('Spell modes').props.onChange({ target: { selectedOptions: [] } });
  assert.equal(cast().props.disabled, true);
  assert.equal(JSON.stringify({ match, legal }), before);
  for (const fields of [{ choose_one_or_more_modes: null }, { mode_base_mana_costs: null },
    { mode_additional_mana_costs: { [modes[0]]: 1 } }]) {
    assert.throws(() => parseLegalMoves({ ...legal, moves: [{ ...move,
      target_hints: { ...move.target_hints, ...fields } }] }));
  }
}
if (process.env.SPREE_UI_CALLBACK_EVIDENCE) {
  await writeFile(process.env.SPREE_UI_CALLBACK_EVIDENCE, JSON.stringify(receipts, null, 2));
}
console.log('PASS six actual Spree views: both actors, one/both modes, explicit per-mode targets, exact callback, prices, stale/reset and metadata controls (hook harness, not browser/API)');

const continuations = JSON.parse(await readFile(new URL('./fixtures/spree-public/continuations.json', import.meta.url)));
const controlCode = await build({ entryPoints: [new URL('../src/components/Controls.tsx', import.meta.url).pathname],
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  define: { 'import.meta.env.VITE_API_BASE_URL': "''" } });
const controlModule = { exports: {} };
new Function('require', 'module', 'exports', controlCode.outputFiles[0].text)(
  name => name === 'react' ? hooks : require(name), controlModule, controlModule.exports);
assert.equal(continuations.pending_rows.length, 8);
assert.equal(continuations.no_alternative_rows.length, 2);
for (const row of [...continuations.pending_rows, ...continuations.no_alternative_rows]) {
  const match = { ...row.actual_public_serialized_match, revision: row.protocol_envelope.revision,
    controllers: row.protocol_envelope.controllers };
  const legalMoves = row.actual_legal_moves;
  parseMatchState(match); parseLegalMoves({ player_id: row.casting_player, revision: 0, moves: legalMoves });
  const before = JSON.stringify({ match, legalMoves });
  const noop = () => {};
  const sent = [];
  values = []; index = 0;
  const tree = nodes(controlModule.exports.Controls({ match, legalMoves, actingPlayerId: row.casting_player,
    decks: [], selectedA: null, selectedB: null, startMode: 'human_vs_human', humanSeat: row.casting_player,
    difficulty: 'normal', bestOf: 1, startDisabled: true, autoplayDelayMs: 1000,
    responseCountdown: null, autoResponsePaused: false, setSelectedA: noop, setSelectedB: noop,
    setStartMode: noop, setHumanSeat: noop, setDifficulty: noop, setBestOf: noop, onStart: noop,
    onPassPriority: noop, onKeepHand: noop, onMulligan: noop, onNextStep: noop, onAutoplayTick: noop,
    setAutoplayDelayMs: noop, onSubmitBlocks: noop, onSubmitAttack: noop, onApplySideboard: noop,
    onNextGame: noop, onSetPriorityStops: noop, onChooseReplacement: noop, onChooseTriggerOrder: noop,
    onChooseTriggerTarget: noop, onChooseOptionalEffect: noop, onToggleAutoResponsePause: noop,
    onChooseMechanic: (seat, action) => sent.push({ seat, action }) }));
  assert.deepEqual(sent, [], 'Rendering must not choose keep or a replacement');
  const move = legalMoves.find(candidate => candidate.type === 'choose_mechanic');
  if (row.phase) {
    assert.equal(move.kind, row.phase === 'optional' ? 'copy_target' : 'spree_target_change');
    assert.equal(move.options.includes('keep'), row.phase === 'optional');
    assert.ok(!tree.some(node => node.props?.role === 'alert'));
    const panel = tree.find(node => node.type === 'div' && node.props.className === 'block-panel'
      && nodes(node.props.children).some(child => child.type === 'h3'
        && text(child) === `${move.label ?? 'Choose a draw replacement'} (P${move.player_id})`));
    assert.ok(panel);
    assert.ok(!nodes(panel).some(node => node.type === 'input' && node.props.type === 'checkbox'));
    for (const option of move.options) {
      const button = tree.find(node => node.type === 'button' && text(node) === (move.option_labels?.[option] ?? option));
      assert.ok(button, `Missing offered continuation ${option}`);
      button.props.onClick();
      assert.deepEqual(sent.pop(), { seat: row.casting_player,
        action: { type: 'choose_mechanic', card_ids: [option] } });
    }
  } else {
    assert.equal(match.pending_mechanic_choice, null);
    assert.equal(move, undefined);
  }
  assert.equal(JSON.stringify({ match, legalMoves }), before);
}
console.log('PASS eight actual copy/retarget continuation views and two actual no-alternative views: offered-only buttons, exact card_ids callback, both actors, no implicit choice (not browser/HTTP)');
