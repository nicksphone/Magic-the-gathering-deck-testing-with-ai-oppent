import assert from "node:assert/strict";
import { parseLegalMoves, parseMatchState, parseSavedMatches } from "../src/api/match-contract.ts";

const mountain = { id: "mountain-1", name: "Mountain", tapped: false, types: ["Land"], power: null, toughness: null, card_faces: [] };
const state = {
  id: "match-1", step: "precombat_main", turn: 1, active_player: 1, priority_player: 1,
  score: { 1: 0, 2: 0 }, stack: [], log: [], blocks: { attacker: ["blocker-a", "blocker-b"] },
  players: {
    1: { life: 20, hand: [mountain], battlefield: [], graveyard: [], graveyard_count: 0, exile: [], exile_count: 0 },
    2: { life: 20, hand: [], battlefield: [], graveyard: [], graveyard_count: 0, exile: [], exile_count: 0 },
  },
};
assert.equal(parseMatchState(state), state);
for (const remaining of [-1, 1.5, '1', null]) {
  assert.throws(() => parseMatchState({...state,players:{...state.players,1:{...state.players[1],land_plays_remaining:remaining}}}), /land allowance/);
}
assert.equal(parseMatchState({...state,players:{...state.players,1:{...state.players[1],land_plays_remaining:0}}}).id,state.id);
for (const fields of [{ was_foretold: 'yes' }, { foretell_order: -1 }, { foretold_turn: 1.5 }]) {
  assert.throws(() => parseMatchState({ ...state, players: { ...state.players,
    1: { ...state.players[1], hand: [{ ...mountain, ...fields }] } } }), /card view/);
}
assert.equal(parseMatchState({ ...state, players: { ...state.players,
  1: { ...state.players[1], hand: [{ ...mountain, was_foretold: true, foretell_order: 2, foretold_turn: 1 }] } } }).id, state.id);
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1],
  hand: [{ ...mountain, printed_power: "*", printed_toughness: "1+*" }] } } }).id, state.id);
for (const printed_power of [1, {}, [], true]) {
  assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1],
    hand: [{ ...mountain, printed_power }] } } }), /card view/);
}
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1],
  hand: [{ ...mountain, keyword_counts: { exalted: 2 } }] } } }).id, state.id);
for (const keyword_counts of [{ exalted: 0 }, { decayed: -1 }, { exalted: "2" }, { exalted: 0.5 }, []]) {
  assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1],
    hand: [{ ...mountain, keyword_counts }] } } }), /card view/);
}
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], counters: { experience: 4, poison: 2 } } } }).id, state.id);
for (const counters of [{ experience: -1 }, { energy: 0.5 }, { experience: "4" }, { "bad label": 2 }, []]) {
  assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 2: { ...state.players[2], counters } } }), /counters/);
}
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], battlefield: [{ ...mountain, effect_warnings: ["Unsupported attached condition"] }] } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], battlefield: [{ ...mountain, effect_warnings: [42] }] } } }), /card view/);
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], mana_pool: { U: 2 }, snow_mana_pool: { U: 1 } } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], mana_pool: { U: 1 }, snow_mana_pool: { U: 2 } } } }), /snow mana pool/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], mana_pool: { U: 1 }, snow_mana_pool: { U: -1 } } } }), /snow mana pool/);
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], battlefield: [{ ...mountain, mana_source_colors: ["G"] }] } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], battlefield: [{ ...mountain, mana_source_colors: ["green"] }] } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], battlefield: [{ ...mountain, mana_source_amounts: { C: -1 } }] } } }), /card view/);
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, colors: ["W"] }] } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, colors: ["white"] }] } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, blocks: { attacker: "blocker-a" } }), /blocks must map/);
assert.throws(() => parseMatchState({ ...state, attack_bands: [["attacker"], "blocker-a"] }), /attack bands must/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, power: undefined }] } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 2: undefined } }), /player 2/);
assert.throws(() => parseMatchState({ ...state, mulligan_bottomed: { 1: 8 } }), /mulligan_bottomed/);
assert.throws(() => parseMatchState({ ...state, mulligan_bottomed: { 3: 1 } }), /mulligan_bottomed/);
assert.throws(() => parseMatchState({ ...state, mulligan_count: { 1: -1 } }), /mulligan_count/);
assert.equal(parseMatchState({ ...state, mulligan_bottomed: { 1: 1, 2: 0 } }).mulligan_bottomed["1"], 1);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], graveyard: undefined } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], graveyard: [mountain] } } }), /card view/);
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], graveyard: [mountain], graveyard_count: 1 } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], exile: undefined } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], exile: [mountain], exile_count: 0 } } }), /card view/);
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], exile: [], exile_count: 1 } } }).id, state.id);
assert.equal(parseMatchState({ ...state, sideboarding: { 1: { mainboard: [{ card_name: "Island", quantity: 60 }], sideboard: [], applied: false } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, sideboarding: { 1: { mainboard: [], sideboard: "Island", applied: false } } }), /sideboarding inventory/);
const aiChoice = { ...state, controllers: { 1: "human", 2: "ai" }, pending_mechanic_choice: { kind: "search_library", player_id: 2, label: "AI is making a choice" } };
assert.equal(parseMatchState(aiChoice), aiChoice);
assert.throws(() => parseMatchState({ ...aiChoice, pending_mechanic_choice: { ...aiChoice.pending_mechanic_choice, options: ["hidden-card"] } }), /pending mechanic choice/);
const legal = { player_id: 1, revision: 0, moves: [{ type: "play_land", card_id: mountain.id, card_view: mountain }] };
for (const field of ['type_line', 'base_type_line']) {
  assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, [field]: 42 }] } } }), /card view/);
}
const castCosts = { id: 'base_discard', discard_cards: 1, sacrifice_creatures: 0, discard_card_ids: ['fodder'] };
for (const flag of ['discard_x', 'discard_all', 'sacrifice_all']) {
  assert.equal(parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts, [flag]: true }] }] }).moves.length, 1);
  for (const value of [1, 'true', null]) {
    assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts, [flag]: value }] }] }), /legal-moves response/);
  }
}
assert.equal(parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [castCosts] }] }).moves.length, 1);
assert.equal(parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts,
  additional_cost_group: 'base', discard_cards: 2, discard_card_ids: ['first', 'second'] }] }] }).moves.length, 1);
assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts,
  additional_cost_group: 5 }] }] }), /legal-moves response/);
assert.equal(parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts,
  kicked: true, kicker_base_id: 'base', target_hints: { supports_divide: true } }] }] }).moves.length, 1);
for (const bad of [{ kicked: 1 }, { kicker_base_id: 1 }, { target_hints: [] }]) {
  assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts, ...bad }] }] }), /legal-moves response/);
}
for (const bad of [{ discard_card_ids: [1] }, { sacrifice_card_ids: ['same', 'same'] }, { discard_cards: -1 }]) {
  assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts, ...bad }] }] }), /legal-moves response/);
}
assert.equal(parseLegalMoves(legal), legal);
assert.throws(() => parseLegalMoves({ ...legal, player_id: 99 }), /legal-moves response/);
assert.throws(() => parseLegalMoves({ ...legal, revision: "0" }), /legal-moves response/);
assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: "cast_spell", card_view: { name: "Broken" } }] }), /legal-moves response/);
assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: "choose_mechanic", options: "not a list" }] }), /legal-moves response/);
assert.equal(parseLegalMoves({ ...legal, moves: [{ type: "choose_mechanic", kind: "search_library", count: 1, min_count: 1, options: ["forest"] }] }).moves[0].min_count, 1);
assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: "choose_mechanic", kind: "search_library", count: 1, min_count: 2, options: ["forest"] }] }), /legal-moves response/);
const saved = [{ id: "match-1", mode: "human_vs_human", turn: 1, game_number: 1, revision: 0, players: ["Player A", "Player B"] }];
assert.equal(parseSavedMatches(saved), saved);
assert.throws(() => parseSavedMatches([{ ...saved[0], id: null }]), /saved-matches response/);
assert.throws(() => parseSavedMatches([{ ...saved[0], players: "Player A" }]), /saved-matches response/);
assert.throws(() => parseSavedMatches([{ ...saved[0], revision: -1 }]), /saved-matches response/);
console.log("PASS live match response contract cases");

const restricted = { color: "C", amount: 2, snow: false, rule: { cast_types: ["Artifact"], activate_types: ["Artifact"] } };
function withLots(lots, pool = { C: 2 }, snow = { C: 0 }) {
  return { ...state, players: { ...state.players, 1: { ...state.players[1], mana_pool: pool, snow_mana_pool: snow, restricted_mana_pool: lots } } };
}
assert.equal(parseMatchState(withLots([restricted])).id, state.id);
assert.equal(parseMatchState(withLots([{ ...restricted, rule: { unsupported: true } }])).id, state.id);
assert.throws(() => parseMatchState(withLots([{ ...restricted, amount: -1 }])), /restricted mana pool/);
assert.throws(() => parseMatchState(withLots([{ ...restricted, rule: { cast_types: ["Anything"], activate_types: [] } }])), /restricted mana pool/);
assert.throws(() => parseMatchState(withLots([restricted, restricted])), /restricted mana pool/);
assert.throws(() => parseMatchState(withLots([{ ...restricted, snow: true }])), /restricted mana pool/);
assert.throws(() => parseMatchState(withLots([restricted], { C: 2 }, { C: 2 })), /restricted mana pool/);
console.log("PASS restricted-mana quantity, purpose and snow-provenance contracts");
assert.equal(parseMatchState({ ...state, discards_this_turn: { 1: 3, 2: 0 } }).discards_this_turn[1], 3);
for (const history of [{ 1: -1, 2: 0 }, { 1: 1.5, 2: 0 }, { 1: 0 }, { 1: 0, 2: 0, 99: 1 }]) {
  assert.throws(() => parseMatchState({ ...state, discards_this_turn: history }), /discard history/);
}
console.log("PASS optional public discard-history contract");
const manaMove = {type: 'activate_mana_ability', card_id: 'nykthos', ability_index: 1,
  cost_text: '{2}, {T}', outputs: {G: 3, U: 0}};
assert.equal(parseLegalMoves({player_id: 2, revision: 1, moves: [manaMove]}).moves[0], manaMove);
for (const invalid of [{...manaMove, ability_index: -1}, {...manaMove, cost_text: 2},
  {...manaMove, outputs: {G: -1}}, {...manaMove, outputs: {X: 3}}, {...manaMove, outputs: {G: 1.5}}]) {
  assert.throws(() => parseLegalMoves({player_id: 2, revision: 1, moves: [invalid]}), /legal-moves/);
}
console.log('PASS indexed mana ability contracts, zero output and invalid costs/colors/counts');

const modifierHints = {required_target_instance_count: 2,
  ordered_creature_modifiers: [{power: -3, toughness: 0, keywords: []}, {power: 0, toughness: -3, keywords: []}]};
const modifierMove = {type: 'cast_spell', target_hints: modifierHints};
assert.equal(parseLegalMoves({player_id: 1, revision: 1, moves: [modifierMove]}).moves[0], modifierMove);
for (const fields of [{required_target_instance_count: 0}, {required_target_instance_count: 1},
  {required_target_instance_count: 2.5}, {required_target_instance_count: '2'},
  {required_target_instance_count: 251}, {required_distinct_target_count: 2},
  {ordered_creature_modifiers: []}, {ordered_creature_modifiers: [{power: -3, toughness: 0, keywords: []}]},
  {ordered_creature_modifiers: [{power: -3, toughness: 0}, {power: 0, toughness: -3, keywords: []}]},
  {ordered_creature_modifiers: [{power: '-3', toughness: 0, keywords: []}, {power: 0, toughness: -3, keywords: []}]}]) {
  for (const costSpecific of [false, true]) {
    const badHints = {...modifierHints, ...fields};
    const move = costSpecific ? {type: 'cast_spell', cost_options: [{id: 'base', discard_cards: 0,
      sacrifice_creatures: 0, target_hints: badHints}]} : {type: 'cast_spell', target_hints: badHints};
    assert.throws(() => parseLegalMoves({player_id: 1, revision: 1, moves: [move]}), /legal-moves/);
  }
}
console.log('PASS ordered modifier target-instance and cost-specific contracts');

const linkedPairs = [
  {primary_kind: 'player', primary_id: 2, primary_name: 'Player B', creature_id: 'creature', creature_name: 'Torrential Gearhulk',
    targets: {target_player: 2, target_card_id: 'creature'}},
  {primary_kind: 'planeswalker', primary_id: 'walker', primary_name: 'Ugin, the Spirit Dragon', creature_id: 'creature', creature_name: 'Torrential Gearhulk',
    targets: {target_card_ids: ['walker', 'creature']}},
];
const linkedMove = {type: 'cast_spell', target_hints: {linked_target_pairs: linkedPairs}};
assert.equal(parseLegalMoves({player_id: 1, revision: 1, moves: [linkedMove]}).moves[0], linkedMove);
for (const pair of [{...linkedPairs[0], primary_id: 3}, {...linkedPairs[0], targets: {target_player: 1, target_card_id: 'creature'}},
  {...linkedPairs[0], targets: {target_player: 2}}, {...linkedPairs[1], targets: {target_card_ids: ['creature', 'walker']}},
  {...linkedPairs[1], targets: {target_player: 2, target_card_ids: ['walker', 'creature']}},
  {...linkedPairs[1], targets: {target_card_ids: ['walker', 'creature', 'third']}},
  {...linkedPairs[0], targets: {...linkedPairs[0].targets, amount: 99}}]) {
  for (const costSpecific of [false, true]) {
    const badHints = {linked_target_pairs: [pair]};
    const move = costSpecific ? {type: 'cast_spell', cost_options: [{id: 'base', discard_cards: 0, sacrifice_creatures: 0, target_hints: badHints}]}
      : {type: 'cast_spell', target_hints: badHints};
    assert.throws(() => parseLegalMoves({player_id: 1, revision: 1, moves: [move]}), /legal-moves/);
  }
}
console.log('PASS linked target pair shape, ordering, exclusivity and cost-specific contracts');

const activationPayment = {pay_life: 0, discard_cards: 1, sacrifice_creatures: 0,
  discard_card_ids: ['one', 'two'], sacrifice_card_ids: [], fixed_discard_card_ids: [], fixed_sacrifice_card_ids: []};
const paymentPacket = payment => ({player_id: 2, revision: 3, moves: [{type: 'activate_ability', payment_options: payment}]});
assert.equal(parseLegalMoves(paymentPacket(activationPayment)).moves[0].payment_options.discard_cards, 1);
for (const payment of [{...activationPayment, discard_cards: -1}, {...activationPayment, discard_cards: '1'},
  {...activationPayment, discard_card_ids: ['one', 'one']}, {...activationPayment, sacrifice_card_ids: null},
  {...activationPayment, fixed_discard_card_ids: [1]}, {...activationPayment, fixed_sacrifice_card_ids: ['']},
  {...activationPayment, fixed_discard_card_ids: ['foreign']}, {...activationPayment, discard_cards: 3},
  {...activationPayment, fixed_discard_card_ids: ['one', 'two']}]) {
  assert.throws(() => parseLegalMoves(paymentPacket(payment)), /legal-moves/);
}
console.log('PASS activated resource payment count, candidate and mandatory-source contracts');

for (const can_auto_pass of [true, false]) {
  assert.equal(parseLegalMoves({player_id: 1, revision: 0, moves: [], can_auto_pass}).can_auto_pass, can_auto_pass);
}
for (const can_auto_pass of [null, 1, 'true', {}]) {
  assert.throws(() => parseLegalMoves({player_id: 1, revision: 0, moves: [], can_auto_pass}), /legal-moves/);
}
assert.equal(parseLegalMoves({player_id: 1, revision: 0, moves: []}).can_auto_pass, undefined);
console.log('PASS authoritative automatic-priority flag and conservative legacy-server compatibility');

const combat = {type:'block', attackers:[{id:'a',name:'Attacker'}], blockers:[{id:'b',name:'Blocker'}],
  legal_blocks:{b:['a']}, blocker_capacities:{b:1}};
const packet = move => ({player_id:2,revision:0,moves:[move]});
assert.equal(parseLegalMoves(packet(combat)).moves[0].blocker_capacities.b, 1);
assert.equal(parseLegalMoves(packet({...combat,blocker_capacities:{b:null}})).moves[0].blocker_capacities.b, null);
for (const value of [{...combat,legal_blocks:{b:['outsider']}}, {...combat,legal_blocks:{outsider:['a']}},
  {...combat,legal_blocks:{b:['a','a']}}, {...combat,blocker_capacities:{b:0}},
  {...combat,blocker_capacities:{b:'2'}}, {...combat,blocker_capacities:{b:1.5}},
  {type:'attack',options:['hero'],banding_attackers:['outsider']}]) {
  assert.throws(() => parseLegalMoves(packet(value)), /legal-moves/);
}
assert.deepEqual(parseLegalMoves(packet({type:'attack',options:['hero'],banding_attackers:['hero']})).moves[0].banding_attackers, ['hero']);
console.log('PASS authoritative banding, blocker-target and finite/unlimited capacity contracts');
const graveyardLand = {type: 'play_land', card_id: 'land', from_graveyard: true,
  graveyard_permission_key: '1:source:0:0:Land', graveyard_permission_name: 'Muldrotha, the Gravetide'};
assert.equal(parseLegalMoves(packet(graveyardLand)).moves[0].graveyard_permission_key, graveyardLand.graveyard_permission_key);
for (const changed of [{graveyard_permission_key: ''}, {graveyard_permission_key: 5},
  {graveyard_permission_key: 'x'.repeat(101)}, {graveyard_permission_name: 3}, {from_graveyard: false}]) {
  assert.throws(() => parseLegalMoves(packet({...graveyardLand, ...changed})), /legal-moves/);
}
console.log('PASS limited graveyard permission source contracts');

const resources = {delve: ['grave'], improvise: ['artifact'], convoke: [{card_id: 'creature', pay_as: ['generic', 'G']}]};
const resourcePacket = value => ({...legal, moves: [{type: 'cast_spell', cost_options: [{...castCosts, resource_payment_candidates: value}]}]});
assert.equal(parseLegalMoves(resourcePacket(resources)).moves.length, 1);
for (const invalid of [{...resources, delve: ['grave', 'grave']}, {...resources, improvise: [2]},
  {...resources, convoke: [{card_id: 'creature', pay_as: ['C']}]},
  {...resources, convoke: [{card_id: 'creature', pay_as: ['S']}]},
  {...resources, convoke: [{card_id: 'creature', pay_as: []}]},
  {...resources, convoke: [{card_id: 'creature', pay_as: ['G', 'G']}]},
  {...resources, convoke: [...resources.convoke, ...resources.convoke]}]) {
  assert.throws(() => parseLegalMoves(resourcePacket(invalid)), /legal-moves response/);
}
console.log('PASS non-mana casting resource candidates and colored/generic-only convoke contracts');
