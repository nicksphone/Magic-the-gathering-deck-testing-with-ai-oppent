import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const frontend = process.env.MTG_TARGET_FRONTEND
  ? pathToFileURL(process.env.MTG_TARGET_FRONTEND + '/') : new URL('../', import.meta.url);
const require = createRequire(new URL('package.json', frontend));
const ts = require('typescript');
const helperUrl = new URL('src/components/target-readiness.ts', frontend);
// Keep the genuine baseline callback runnable before the new helper exists.
let singleCardTargetReady;
if (existsSync(helperUrl)) ({singleCardTargetReady} = await import(helperUrl));
const battlefield = ts.createSourceFile('Battlefield.tsx',
  readFileSync(new URL('src/components/Battlefield.tsx', frontend), 'utf8'),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let cast;
function visit(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === 'castAction') {
    assert.equal(cast, undefined, 'Exactly one shared cast callback');
    cast = node;
  }
  ts.forEachChild(node, visit);
}
visit(battlefield);
assert.ok(cast, 'Test the actual shared cast callback, not a substitute');
const castCode = ts.transpileModule(cast.getText(battlefield),
  {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
const creature = {id: 'creature-1', name: 'Protocol creature'};
const hints = {action_has_target_text: true, creature_targets: [creature],
  choice_schema: {target_card_id: {type: 'string', required: false},
    replacement_source_id: {type: 'string', required: false}}};
const normal = {id: 'normal', label: 'Normal', mana_cost: '{B}', pay_life: 0,
  discard_cards: 0, sacrifice_creatures: 0};
let checks = 0;
function check(actual, expected, message) {
  assert.deepEqual(actual, expected, message);
  checks++;
}
function click({seat = 1, selected, rootHints = hints, costHints, costId = 'normal',
  selectAvailable = true, hintAvailable = true,
  costOptions = [{...normal, ...(costHints === undefined ? {} : {target_hints: costHints})}]} = {}) {
  const sent = [], focused = [];
  const context = {targets: {'spell-1': selected === undefined ? {} : {target_card_id: selected}},
    castMoves: [{type: 'cast_spell', card_id: 'spell-1', target_hints: rootHints, cost_options: costOptions}],
    costChoice: {'spell-1': costId}, hybridChoice: {}, costCards: {}, resourceChoices: {},
    onCardAction: (...args) => sent.push(args), viewerSeat: seat, singleCardTargetReady,
    document: {getElementById(id) {
      if (id === 'cast-target-spell-1' && !selectAvailable) return null;
      if (id === 'cast-target-help-spell-1' && !hintAvailable) return null;
      return {focus() {focused.push(id);}};
    }}};
  const callback = new Function(...Object.keys(context), castCode + '\nreturn castAction;')(...Object.values(context));
  const before = JSON.stringify(context.targets);
  callback('spell-1');
  check(JSON.stringify(context.targets), before, 'Readiness never chooses or replaces a target');
  return {sent, focused};
}

// Synthetic public-metadata vectors; no backend, HTTP, browser, or game execution.
for (const seat of [1, 2]) {
  const missing = click({seat});
  check(missing.sent, [], 'Missing target must not dispatch the actual cast callback');
  check(missing.focused, ['cast-target-spell-1'], 'Missing target focuses its own select');
  const stale = click({seat, selected: 'gone-creature'});
  check(stale.sent, [], 'A formerly offered target must not dispatch');
  check(stale.focused, ['cast-target-spell-1'], 'Stale target focuses its own select');
  const offered = click({seat, selected: creature.id});
  check(offered.sent.length, 1, 'An explicitly chosen offered target follows the normal cast route');
  check(offered.sent[0][0], seat, 'The acting seat is unchanged');
  check(offered.sent[0][1].targets, {target_card_id: creature.id}, 'The exact chosen ID is preserved');
  check(offered.focused, [], 'Valid casting does not steal focus');
}
assert.equal(typeof singleCardTargetReady, 'function');
const unavailable = click({rootHints: {...hints, creature_targets: []}, selectAvailable: false});
check(unavailable.sent, [], 'An empty offer pool never dispatches');
check(unavailable.focused, ['cast-target-help-spell-1'], 'An absent target select focuses the inline guidance');
const unmounted = click({selectAvailable: false, hintAvailable: false});
check(unmounted.sent, [], 'A removed select/help still refuses without throwing');
for (const selected of [undefined, null, '', 'gone-creature', 1, {}, ['creature-1']]) {
  check(singleCardTargetReady(hints, selected), false, 'Only an offered ID is ready');
}
check(singleCardTargetReady(hints, creature.id), true, 'Offered creature ID is ready');
check(singleCardTargetReady(undefined, undefined), undefined, 'Absent hints do not invent a target requirement');
check(singleCardTargetReady({...hints, creature_targets: []}, creature.id), false, 'Changed offers invalidate an old selection');
// Actual public hint shapes from the rejected pilot casts, with synthetic IDs.
const restricted = {...hints, target_restrictions: {allowed_types: ['Creature']}};
check(click({rootHints: restricted}).sent, [], 'Restriction metadata does not bypass required target guidance');
const permanent = {id: 'permanent-1', name: 'Protocol permanent'};
const permanentHints = {...hints, permanent_targets: [permanent],
  target_restrictions: {exclude_types: ['Land'], mana_value_max: 3}};
check(click({rootHints: permanentHints}).sent, [], 'The witnessed permanent-target cast also requires a choice');
check(click({rootHints: permanentHints, selected: permanent.id}).sent.length, 1,
  'An offered noncreature permanent is a valid explicit choice');
check(singleCardTargetReady({action_has_target_text: true, permanent_targets: [permanent]}, permanent.id), true,
  'A permanent-only single-card offer is supported without inventing creature candidates');
for (const flag of [false, undefined]) {
  const passive = {...hints, action_has_target_text: flag};
  check(singleCardTargetReady(passive, undefined), undefined, 'Untargeted/ETB hint pools are not cast requirements');
  check(click({rootHints: passive}).sent.length, 1, 'Untargeted/ETB casting is unchanged');
}
const excluded = [
  {up_to_target_count: 1}, {up_to_target_count: 2}, {modes: ['mode']},
  {available_modes: ['mode']}, {choose_two_modes: true}, {choose_one_or_more_modes: true},
  {mode_target_hints: {}}, {mode_additional_mana_costs: {}}, {linked_target_pairs: []},
  {required_distinct_target_count: 2}, {required_target_instance_count: 2},
  {ordered_creature_modifiers: []}, {ordered_counter_amounts: []},
  {single_target_alternative: true}, {supports_divide: true}, {divide_max_targets: 2},
  ...['player_targets', 'planeswalker_targets', 'aura_targets',
    'land_targets', 'artifact_targets', 'enchantment_targets', 'noncreature_permanent_targets',
    'graveyard_card_targets', 'graveyard_creature_targets', 'graveyard_permanent_targets',
    'stack_targets'].map(key => ({[key]: []})),
  {choice_schema: {target_card_ids: {type: 'array'}}},
  {choice_schema: {mode_text: {type: 'string'}}},
  {choice_schema: {hybrid_choices: {type: 'array'}}},
];
for (const group of excluded) {
  const complex = {...hints, ...group};
  check(singleCardTargetReady(complex, undefined), undefined, 'Complex/optional groups stay with existing guards');
  check(click({rootHints: complex}).sent.length, 1, 'The new shared guard does not intercept complex groups');
}
check(click({rootHints: {...hints, action_has_target_text: false}, costHints: hints}).sent, [],
  'Selected cost hints can require a target when root hints do not');
check(click({costHints: {...hints, action_has_target_text: false}}).sent.length, 1,
  'Selected cost hints can suppress a passive root target pool');
check(click({selected: creature.id, costHints: {...hints, creature_targets: [{id: 'new-creature', name: 'New'}]}}).sent, [],
  'Cost-specific offers, not root offers, decide whether an ID is stale');
check(click({costOptions: [{...normal, target_hints: hints},
  {...normal, id: 'other', target_hints: {...hints, action_has_target_text: false}}], costId: 'other'}).sent.length, 1,
  'The explicitly selected cost is honored');

const {parseLegalMoves} = await import(new URL('src/api/match-contract.ts', frontend));
for (const costSpecific of [false, true]) {
  const response = value => ({player_id: 1, revision: 0, moves: [{
    type: 'cast_spell', ...(costSpecific ? {cost_options: [{...normal, target_hints: value}]} : {target_hints: value}),
  }]});
  for (const flag of [false, true, undefined]) {
    const value = response({...hints, action_has_target_text: flag});
    check(parseLegalMoves(value), value, 'Optional boolean flags are preserved, not inferred');
  }
  for (const flag of [null, 0, 1, 'true', 'false', [], {}]) {
    assert.throws(() => parseLegalMoves(response({...hints, action_has_target_text: flag})), /legal-moves/);
    checks++;
  }
}
const source = battlefield.text;
assert.match(source, /id=\{targetSelectId\}/, 'The guarded target select has the focus ID');
assert.match(source, /aria-describedby=\{missingCardTarget \? targetHelpId : undefined\}/);
assert.match(source, /id=\{targetHelpId\}[^>]*>Choose a target before casting\./);
checks += 3;
console.log('PASS ' + checks + ' target-readiness protocol checks; actual shared cast callback; no DOM/backend/game execution');
