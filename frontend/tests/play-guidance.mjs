import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';

const helper = new URL('../src/components/play-guidance.ts', import.meta.url);
assert.ok(existsSync(helper), 'RED: getPlayGuidance implementation is not present');
const {getPlayGuidance} = await import(helper);
const anchors = ['#match-controls', '#table', '#automatic-play-toggle',
  '#your-hand', '#attack-declaration', '#block-declaration', '#opening-hand-choice'];
let cases = 0;
const hidden = () => {throw Error('Guidance must not inspect hidden cards, deck names, or callbacks');};
function move(type, fields = {}) {
  return Object.freeze(Object.defineProperties({type, ...fields}, {
    card_name: {get: hidden}, card_view: {get: hidden}, inspected_cards: {get: hidden},
    targets: {get: hidden}, options: {get: hidden}, callback: {get: hidden},
  }));
}
function state(seat = 1, fields = {}) {
  return Object.freeze(Object.defineProperties({
    id: 'synthetic-public-state', winner: null, match_complete: false,
    mode: 'player_vs_ai', controllers: Object.freeze({[seat]: 'human', [3 - seat]: 'ai'}),
    priority_player: seat, active_player: seat, step: 'precombat_main',
    stack: Object.freeze([]), ...fields,
  }, {players: {get: hidden}, deck_names: {get: hidden}, log: {get: hidden}}));
}
function check(label, match, moves, actor, paused, title, href, detail) {
  const result = getPlayGuidance(match, Object.freeze(moves), actor, paused);
  assert.deepEqual(Object.keys(result).sort(), ['detail', 'href', 'linkLabel', 'title']);
  for (const value of Object.values(result)) assert.equal(typeof value, 'string');
  assert.ok(anchors.includes(result.href), label + ': navigation only');
  assert.match(result.title, title, label);
  if (href) assert.equal(result.href, href, label);
  if (detail) assert.match(result.detail, detail, label);
  assert.ok(result.linkLabel.length > 0);
  cases++;
  return result;
}

// All inputs below are synthetic public-metadata protocol vectors, not game evidence.
check('lobby', null, [], 1, false, /Choose.*matchup/i, '#match-controls', /deck.*seat/i);
for (const seat of [1, 2]) {
  check('series complete', state(seat, {match_complete: true}), [], seat, false,
    /Series complete/, '#table', /result/i);
  check('game won', state(seat, {winner: seat}), [], seat, true,
    /Game over/, '#match-controls', /between.games/i);
  check('drawn game', state(seat, {winner: 0}), [], seat, false,
    /Game drawn/, '#match-controls');
  check('human opening hand precedes pause', state(seat, {pregame_pending: true}), [], seat, true,
    /You.*opening hand/, '#opening-hand-choice', /keep.*redraw/i);
  for (const paused of [false, true]) {
    const aiState = state(seat, {pregame_pending: true,
      pending_mechanic_choice: {kind: 'opening_hand', player_id: 3 - seat}});
    const ai = check('actual actor is AI before pending', aiState, [move('choose_mechanic')], 3 - seat,
      paused, paused ? /Automatic play is paused/ : /AI/, paused ? '#automatic-play-toggle' : '#table');
    assert.doesNotMatch([ai.title, ai.detail, ai.linkLabel].join(' '), /\byou(?:r)?\b/i);
    const aiOnly = check('AI vs AI', state(seat, {mode: 'ai_vs_ai', controllers: {'1': 'ai', '2': 'ai'},
      pending_trigger_order: {current_controller: seat, phase: 'targets'}}), [], seat, paused,
    paused ? /Automatic play is paused/ : /AI/);
    assert.doesNotMatch([aiOnly.title, aiOnly.detail, aiOnly.linkLabel].join(' '), /\byou(?:r)?\b/i);
  }
  const pending = [
    [{pending_mechanic_choice: {kind: 'discard', player_id: seat}}, 'choose_mechanic', /choice is required/],
    [{pending_mechanic_choice: {kind: 'synthetic_unsupported_kind', player_id: seat}}, 'choose_mechanic', /choice is required/],
    [{pending_replacement_choice: {event: 'synthetic_event', player_id: seat, options: []}}, 'choose_replacement', /event happens/],
    [{pending_trigger_order: {current_controller: seat}}, 'choose_trigger_order', /order of effects/],
    [{pending_trigger_order: {current_controller: seat, phase: 'targets'}}, 'choose_trigger_target', /choose a target/],
    [{pending_trigger_order: {current_controller: seat, phase: 'optional'}}, 'choose_optional_effect', /accept or decline/],
  ];
  for (const [fields, type, title] of pending) {
    check('public pending field precedes pause', state(seat, fields), [], seat, true, title, '#match-controls');
    check('actual offered pending move', state(seat), [move(type)], seat, true, title, '#match-controls');
  }
  check('opening-hand subchoice links to the actual choice panel',
    state(seat, {pregame_pending: true, pending_mechanic_choice: {kind: 'mulligan_bottom', player_id: seat}}),
    [move('choose_mechanic')], seat, false, /choice is required/, '#match-controls');
  check('attack offer', state(seat), [move('attack')], seat, true, /select attackers/, '#attack-declaration', /submit/i);
  check('block offer', state(seat), [move('block')], seat, true, /assign blockers/, '#block-declaration', /submit/i);
  for (const type of ['cast_spell', 'activate_ability', 'activate_loyalty', 'activate_mana_ability']) {
    check('offered cast/ability', state(seat), [move(type)], seat, true, /offered plays/,
      type === 'cast_spell' ? '#your-hand' : '#table');
  }
  check('offered land', state(seat), [move('play_land')], seat, true, /land play/, '#your-hand');
  const stack = Object.freeze([Object.freeze(Object.defineProperty({id: 'public-effect'}, 'label', {get: hidden}))]);
  check('human stack response', state(seat, {stack}), [move('cast_spell'), move('pass_priority')], seat, false,
    /effect is waiting/, '#your-hand', /offered response/i);
  check('stack pass', state(seat, {stack}), [move('pass_priority')], seat, false,
    /effect is waiting/, '#match-controls', /both players.*pass/i);
  const unavailable = check('stack without offered actions', state(seat, {stack}), [], seat, false,
    /effect is waiting/, '#match-controls');
  assert.doesNotMatch(unavailable.detail, /Pass Priority|cast a spell|activate an ability/i);
  const pass = check('pass only', state(seat), [move('pass_priority')], seat, true,
    /take no action/, '#match-controls', /not.*end.*turn/i);
  assert.match(pass.detail, /Pass Priority/);
  for (const step of ['declare_attackers', 'declare_blockers', 'untap']) {
    check('phase is not a legal-action offer', state(seat, {step}), [], seat, false,
      /No action is offered/, '#match-controls');
  }
  check('unsupported move is not a fabricated play', state(seat), [move('synthetic_unknown_action')], seat, false,
    /No guided action/, '#match-controls', /review/i);
  for (const fields of [
    {mode: 'human_vs_human', controllers: {'1': 'human', '2': 'human'}},
    {controllers: undefined},
    {mode: 'ai_vs_ai', controllers: {[seat]: 'human', [3 - seat]: 'ai'}},
  ]) {
    const named = check('no assumed personal seat', state(seat, fields), [move('play_land')], seat, false,
      new RegExp('Player ' + seat), '#your-hand');
    assert.doesNotMatch([named.title, named.detail, named.linkLabel].join(' '), /\byou(?:r)?\b/i);
  }
}
console.log('PASS ' + cases + ' play-guidance synthetic protocol cases; both seats, actual controllers/pending fields, public-only reads, no callbacks or gameplay');
