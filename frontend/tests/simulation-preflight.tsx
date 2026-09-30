import { createRoot } from "react-dom/client";
import { AnalyticsPanel } from "../src/components/AnalyticsPanel";
import { api } from "../src/api/client";
import type { DeckRecord } from "../src/types";

declare global {
  interface Window { fixturePreflights?: number; fixtureStarts?: number; fixtureCancels?: number }
}

window.fixturePreflights = 0;
window.fixtureStarts = 0;
window.fixtureCancels = 0;
let canceled = false;
api.listDiagnosticRuns = async () => ({ runs: [] });
api.preflightSimulateBatch = async (deckA) => {
  window.fixturePreflights = (window.fixturePreflights ?? 0) + 1;
  return {
    status: "exploratory",
    known_unsupported_cards: deckA[0].card_name === "Willbender"
      ? [{ deck: "A", card_name: "Willbender", mechanics: ["morph"] }]
      : [],
  };
};
api.startSimulateBatchJob = async () => {
  window.fixtureStarts = (window.fixtureStarts ?? 0) + 1;
  return { job_id: "fixture-job", status: "queued" };
};
api.getSimulateBatchJob = async () => ({
  job_id: "fixture-job", status: canceled ? "canceled" : "running", completed_matches: 0,
  total_matches: 20, started_at: Date.now() / 1000, result: null,
});
api.cancelSimulateBatchJob = async () => {
  window.fixtureCancels = (window.fixtureCancels ?? 0) + 1;
  canceled = true;
  return {
    job_id: "fixture-job", status: "running", completed_matches: 0,
    total_matches: 20, started_at: Date.now() / 1000, result: null,
  };
};

const decks: DeckRecord[] = [
  { id: 1, name: "Morph", source: "fixture", archetype_guess: "Tempo", mainboard: [{ quantity: 60, card_name: "Willbender" }], sideboard: [] },
  { id: 2, name: "Islands", source: "fixture", archetype_guess: "Control", mainboard: [{ quantity: 60, card_name: "Island" }], sideboard: [] },
  { id: 3, name: "Mountains", source: "fixture", archetype_guess: "Aggro", mainboard: [{ quantity: 60, card_name: "Mountain" }], sideboard: [] },
];
createRoot(document.getElementById("root")!).render(<AnalyticsPanel decks={decks} />);
