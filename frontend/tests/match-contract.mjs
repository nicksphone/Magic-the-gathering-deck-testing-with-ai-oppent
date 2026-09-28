import assert from "node:assert/strict";
import { parseMatchState } from "../src/api/match-contract.ts";

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
assert.throws(() => parseMatchState({ ...state, blocks: { attacker: "blocker-a" } }), /blocks must map/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 1: { ...state.players[1], hand: [{ ...mountain, power: undefined }] } } }), /card view/);
assert.throws(() => parseMatchState({ ...state, players: { ...state.players, 2: undefined } }), /player 2/);
console.log("PASS live match response contract cases");
