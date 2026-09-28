import assert from "node:assert/strict";
import { parseLegalMoves, parseMatchState, parseSavedMatches } from "../src/api/match-contract.ts";

const mountain = { id: "mountain-1", name: "Mountain", tapped: false, types: ["Land"], power: null, toughness: null, card_faces: [] };
const state = {
  id: "match-1", step: "precombat_main", turn: 1, active_player: 1, priority_player: 1,
  score: { 1: 0, 2: 0 }, stack: [], log: [], blocks: { attacker: ["blocker-a", "blocker-b"] },
  players: {
    1: { life: 20, hand: [mountain], battlefield: [] },
    2: { life: 20, hand: [], battlefield: [] },
  },
};
assert.equal(parseMatchState(state), state);
assert.equal(parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, colors: ["W"] }] } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, colors: ["white"] }] } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, blocks: { attacker: "blocker-a" } }), /blocks must map/);
assert.throws(() => parseMatchState({ ...state, attack_bands: [["attacker"], "blocker-a"] }), /attack bands must/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, power: undefined }] } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 2: undefined } }), /player 2/);
assert.equal(parseMatchState({ ...state, sideboarding: { 1: { mainboard: [{ card_name: "Island", quantity: 60 }], sideboard: [], applied: false } } }).id, state.id);
assert.throws(() => parseMatchState({ ...state, sideboarding: { 1: { mainboard: [], sideboard: "Island", applied: false } } }), /sideboarding inventory/);
const aiChoice = { ...state, controllers: { 1: "human", 2: "ai" }, pending_mechanic_choice: { kind: "search_library", player_id: 2, label: "AI is making a choice" } };
assert.equal(parseMatchState(aiChoice), aiChoice);
assert.throws(() => parseMatchState({ ...aiChoice, pending_mechanic_choice: { ...aiChoice.pending_mechanic_choice, options: ["hidden-card"] } }), /pending mechanic choice/);
const legal = { player_id: 1, revision: 0, moves: [{ type: "play_land", card_id: mountain.id, card_view: mountain }] };
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
