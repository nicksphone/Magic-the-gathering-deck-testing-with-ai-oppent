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
const castCosts = { id: 'base_discard', discard_cards: 1, sacrifice_creatures: 0, discard_card_ids: ['fodder'] };
assert.equal(parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [castCosts] }] }).moves.length, 1);
assert.equal(parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts,
  additional_cost_group: 'base', discard_cards: 2, discard_card_ids: ['first', 'second'] }] }] }).moves.length, 1);
assert.throws(() => parseLegalMoves({ ...legal, moves: [{ type: 'cast_spell', cost_options: [{ ...castCosts,
  additional_cost_group: 5 }] }] }), /legal-moves response/);
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
