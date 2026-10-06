import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "../src/App";
import { api, type SimulationCoverage, type StartMatchPayload } from "../src/api/client";
import { HttpResponseError } from "../src/api/errors";
import { startSignature } from "../src/lib/interactive-preflight";
import type { DeckRecord, MatchState } from "../src/types";
import "../src/styles/app.css";

const decks: DeckRecord[] = [
  { id: 1, name: "Island list", source: "UI fixture", archetype_guess: "Control", mainboard: [{ quantity: 60, card_name: "Island" }], sideboard: [{ quantity: 1, card_name: "Willbender" }] },
  { id: 2, name: "Forest list", source: "UI fixture", archetype_guess: "Midrange", mainboard: [{ quantity: 60, card_name: "Forest" }], sideboard: [] },
  { id: 3, name: "Mountain list", source: "UI fixture", archetype_guess: "Aggro", mainboard: [{ quantity: 60, card_name: "Mountain" }], sideboard: [] },
];
const gaps: SimulationCoverage = {
  status: "exploratory", known_unsupported_cards: [
    { deck: "A", card_name: "Willbender", mechanics: ["morph"] },
    { deck: "B", card_name: "Xenagos, God of Revels", mechanics: ["unsupported conditional static predicate"],
      static_clause_gaps: [{ clause: "as long as your devotion to red and green is less than seven, xenagos isn't a creature",
        condition: "your devotion to red and green is less than seven", reasons: ["unsupported conditional static predicate"],
        face_name: "Xenagos, God of Revels", face_index: null }] },
  ],
};
type Receipt = { payload: StartMatchPayload; state: MatchState };
const receipts: Record<string, Receipt> = JSON.parse(sessionStorage.getItem("interactiveFixture.receipts") ?? "{}");
const requests: { key: string; payload: StartMatchPayload }[] = JSON.parse(sessionStorage.getItem("interactiveFixture.requests") ?? "[]");
const preflights: { a: unknown; b: unknown }[] = [];
const queuedPreflights: { resolve: (value: SimulationCoverage) => void; reject: (error: Error) => void }[] = [];
const queuedStarts: (() => void)[] = [];
let blockedFetches = 0;
const fixture = {
  decks, preflights, requests, receipts, holdPreflight: false, holdStart: false, emptyGaps: false,
  preflightError: false, rejectStart: false,
  resolvePreflight(fail = false) {
    const next = queuedPreflights.shift();
    if (!next) throw new Error("No queued preflight");
    if (fail) next.reject(new Error("Fixture stale coverage failure"));
    else next.resolve(fixture.emptyGaps ? { status: "exploratory", known_unsupported_cards: [] } : gaps);
  },
  releaseStart() { queuedStarts.splice(0).forEach(resolve => resolve()); },
  get created() { return Object.keys(receipts).length; },
  get blockedFetches() { return blockedFetches; },
};
declare global { interface Window { interactiveFixture: typeof fixture } }
window.interactiveFixture = fixture;
window.fetch = async () => { blockedFetches++; throw new Error("Unexpected real network API request in isolated UI fixture"); };
api.health = async () => ({ ok: true });
api.listDecks = async () => structuredClone(decks);
api.listBuiltins = async () => [];
api.listExpansionTopDecks = async () => [];
api.listDiagnosticRuns = async () => ({ runs: [] });
api.savedMatches = async () => Object.values(receipts).map(({ state }) => ({
  id: state.id, mode: state.mode!, turn: state.turn, revision: 0, game_number: 1, players: ["A", "B"],
}));
api.preflightSimulateBatch = async (a, b) => {
  preflights.push({ a: structuredClone(a), b: structuredClone(b) });
  if (fixture.holdPreflight) return await new Promise((resolve, reject) => queuedPreflights.push({ resolve, reject }));
  if (fixture.preflightError) throw new Error("Fixture coverage offline");
  return fixture.emptyGaps ? { status: "exploratory", known_unsupported_cards: [] } : structuredClone(gaps);
};
api.startMatch = async (payload, key) => {
  if (!key) throw new Error("Missing idempotency key");
  requests.push({ key, payload: structuredClone(payload) });
  sessionStorage.setItem("interactiveFixture.requests", JSON.stringify(requests));
  if (fixture.rejectStart) throw new HttpResponseError("Fixture rejected start", 422);
  if (receipts[key] && startSignature(receipts[key].payload) !== startSignature(payload)) throw new Error("Same key, different intent");
  if (!receipts[key]) {
    const player = { id: 1, name: "UI fixture", life: 20, hand: [], hand_count: 0, battlefield: [], graveyard: [], graveyard_count: 0, exile: [], exile_count: 0, library_count: 60, mana_pool: {} };
    receipts[key] = { payload: structuredClone(payload), state: {
      id: `ui-${key}`, revision: 0, mode: payload.mode, controllers: { "1": payload.controller_a, "2": payload.controller_b },
      turn: 1, active_player: 1, priority_player: 1, step: "precombat_main", winner: 1, match_complete: true,
      score: { "1": 0, "2": 0 }, players: { "1": structuredClone(player), "2": { ...structuredClone(player), id: 2 } },
      stack: [], log: ["UI-only receipt fixture; no game was played"], blocks: {}, best_of: payload.best_of, game_number: 1,
    } };
    sessionStorage.setItem("interactiveFixture.receipts", JSON.stringify(receipts));
  }
  if (fixture.holdStart) await new Promise<void>(resolve => queuedStarts.push(resolve));
  const losses = Number(sessionStorage.getItem("interactiveFixture.losses") ?? "0");
  if (losses > 0) {
    sessionStorage.setItem("interactiveFixture.losses", String(losses - 1));
    throw new TypeError("Fixture dropped accepted start response");
  }
  return structuredClone(receipts[key].state);
};
api.getMatch = async id => {
  const receipt = Object.values(receipts).find(row => row.state.id === id);
  if (!receipt) throw new Error("Unknown UI fixture receipt");
  return structuredClone(receipt.state);
};
api.legalMoves = async () => ({ moves: [], player_id: 1, revision: 0, can_auto_pass: false });
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
