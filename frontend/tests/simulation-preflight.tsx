import { createRoot } from "react-dom/client";
import "../src/styles/app.css";
import { AnalyticsPanel } from "../src/components/AnalyticsPanel";
import { api } from "../src/api/client";
import type { DeckRecord } from "../src/types";

declare global {
  interface Window { fixtureCompleted?: boolean; fixtureFailed?: boolean; fixturePreflights?: number; fixtureStarts?: number; fixtureAttempts?: number; fixtureResponseLosses?: number; fixtureWrongJobId?: boolean; fixtureCancels?: number; fixturePolls?: number; fixtureClientStartHeader?: string }
}

const realFetch = window.fetch;
try {
  window.fetch = async (_url, init) => {
    window.fixtureClientStartHeader = new Headers(init?.headers).get("Idempotency-Key") ?? "";
    return new Response(JSON.stringify({ job_id: "a".repeat(32), status: "queued" }), { status: 200 });
  };
  await api.startSimulateBatchJob([], [], 1, "master", 500, "a".repeat(32));
} finally {
  window.fetch = realFetch;
}

window.fixturePreflights = 0;
window.fixtureStarts = 0;
window.fixtureAttempts = 0;
window.fixtureResponseLosses = 0;
window.fixtureCancels = 0;
window.fixturePolls = 0;
let canceled = false;
const acceptedKeys = new Set<string>(JSON.parse(sessionStorage.getItem("fixtureAcceptedSimulationKeys") ?? "[]"));
api.listDiagnosticRuns = async () => ({ runs: [] });
api.preflightSimulateBatch = async (deckA) => {
  window.fixturePreflights = (window.fixturePreflights ?? 0) + 1;
  return {
    status: "exploratory",
    known_unsupported_cards: deckA[0].card_name === "Willbender"
      ? [{ deck: "A", card_name: "Willbender", mechanics: ["morph"] },
        { deck: "A", card_name: "Xenagos, God of Revels", mechanics: ["unsupported conditional static predicate", "unsupported conditional static instruction"],
          static_clause_gaps: [{ clause: "as long as your devotion to red and green is less than seven, xenagos isn't a creature",
            condition: "your devotion to red and green is less than seven",
            reasons: ["unsupported conditional static predicate", "unsupported conditional static instruction"],
            face_index: null, face_name: "Xenagos, God of Revels" }] }]
      : [],
  };
};
api.startSimulateBatchJob = async (_deckA, _deckB, _matches, _difficulty, _maxTicks, key) => {
  if (!key) throw new Error("Simulation start key missing");
  window.fixtureAttempts = (window.fixtureAttempts ?? 0) + 1;
  if (!acceptedKeys.has(key)) {
    acceptedKeys.add(key);
    sessionStorage.setItem("fixtureAcceptedSimulationKeys", JSON.stringify([...acceptedKeys]));
    window.fixtureStarts = (window.fixtureStarts ?? 0) + 1;
  }
  canceled = false;
  if ((window.fixtureResponseLosses ?? 0) > 0) {
    window.fixtureResponseLosses = (window.fixtureResponseLosses ?? 0) - 1;
    throw new TypeError("Fixture dropped accepted start response");
  }
  return { job_id: window.fixtureWrongJobId ? "0".repeat(32) : key, status: "queued" };
};
api.getSimulateBatchJob = async (jobId) => {
  window.fixturePolls = (window.fixturePolls ?? 0) + 1;
  return {
    job_id: jobId, status: canceled ? "canceled" : window.fixtureCompleted ? "completed" : window.fixtureFailed ? "failed" : "running", completed_matches: window.fixtureCompleted ? 20 : 0,
    total_matches: 20, started_at: Date.now() / 1000, error: window.fixtureFailed ? "Deliberate UI test failure" : null,
    result: window.fixtureCompleted ? {win_rate_deck_a:50,win_rate_deck_b:50,average_turns:5,deterministic_replay_fingerprint:"UI fixture, not a simulation result"} : null,
  };
};
api.cancelSimulateBatchJob = async (jobId) => {
  window.fixtureCancels = (window.fixtureCancels ?? 0) + 1;
  canceled = true;
  return {
    job_id: jobId, status: "running", completed_matches: 0,
    total_matches: 20, started_at: Date.now() / 1000, result: null,
  };
};

const decks: DeckRecord[] = [
  { id: 1, name: "Morph", source: "fixture", archetype_guess: "Tempo", mainboard: [{ quantity: 60, card_name: "Willbender" }], sideboard: [] },
  { id: 2, name: "Islands", source: "fixture", archetype_guess: "Control", mainboard: [{ quantity: 60, card_name: "Island" }], sideboard: [] },
  { id: 3, name: "Mountains", source: "fixture", archetype_guess: "Aggro", mainboard: [{ quantity: 60, card_name: "Mountain" }], sideboard: [] },
];
createRoot(document.getElementById("root")!).render(<AnalyticsPanel decks={decks} />);
