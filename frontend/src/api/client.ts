import type { DeckItem, DeckRecord, LegalMove, MatchState } from "../types";

const API =
  (import.meta as any).env?.VITE_API_BASE_URL ||
  "/api";

export const API_BASE = API;

export function resolveCardMediaUrl(uri?: string): string | undefined {
  if (!uri) return undefined;
  if (uri.startsWith("http://") || uri.startsWith("https://")) return uri;
  const path = uri.startsWith("/") ? uri : `/${uri}`;
  if (API === "/api" && path.startsWith("/card-images/")) return path;
  return `${API}${path}`;
}

export type DeckImportResponse = {
  deck_id: number | null;
  name: string;
  archetype_guess: string;
  errors: string[];
  suggestions: { line: number; input: string; suggestion: string | null; score: number }[];
  mainboard: DeckItem[];
  sideboard: DeckItem[];
  mana_curve: Record<string, number>;
  color_profile: Record<string, number>;
  resolved_mainboard_cards?: ResolvedDeckCard[];
  resolved_sideboard_cards?: ResolvedDeckCard[];
  analysis?: {
    primary_archetype?: string;
    secondary_archetype?: string;
    confidence?: number;
    scores?: Record<string, number>;
    signals?: string[];
    land_count?: number;
    creature_count?: number;
    noncreature_spell_count?: number;
  };
};

export type ResolvedCardMetadata = {
  id: string;
  scryfall_id: string;
  name: string;
  oracle_text?: string;
  mana_cost?: string;
  type_line?: string;
  colors?: string[];
  power?: number | string | null;
  toughness?: number | string | null;
  image_uri?: string | null;
  legalities?: Record<string, string>;
  card_faces?: {
    name?: string;
    mana_cost?: string;
    oracle_text?: string;
    type_line?: string;
    image_uri?: string | null;
  }[];
};

export type ResolvedDeckCard = {
  quantity: number;
  card_name: string;
  card_metadata?: ResolvedCardMetadata | null;
};

export type ExpansionTopDeckMeta = {
  code: string;
  expansion: string;
  release_year: number;
  deck_name: string;
  archetype: string;
};

export type ExpansionTopDeckPayload = {
  code: string;
  expansion: string;
  release_year: number;
  name: string;
  archetype: string;
  deck_text: string;
};

export type BatchSimulationJobStart = {
  job_id: string;
  status: string;
};

export type BatchSimulationJobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  completed_matches: number;
  total_matches: number;
  started_at: number;
  finished_at?: number | null;
  error?: string | null;
  result?: any;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listBuiltins: () => req<string[]>("/decks/builtin"),
  getBuiltinText: (name: string) => req<{ name: string; deck_text: string }>(`/decks/builtin/${encodeURIComponent(name)}`),
  listExpansionTopDecks: () => req<ExpansionTopDeckMeta[]>("/decks/expansion-top"),
  getExpansionTopDeck: (code: string) =>
    req<ExpansionTopDeckPayload>(`/decks/expansion-top/${encodeURIComponent(code)}`),
  importExpansionTopDeck: (code: string) =>
    req<DeckImportResponse>(`/decks/expansion-top/${encodeURIComponent(code)}/import`, { method: "POST" }),
  importAllExpansionTopDecks: () => req<{ requested: number; imported: number; with_errors: number }>("/decks/expansion-top/import-all", { method: "POST" }),
  importDeck: (name: string, deck_text: string, source = "user") =>
    req<DeckImportResponse>("/decks/import", { method: "POST", body: JSON.stringify({ name, deck_text, source }) }),
  listDecks: () => req<DeckRecord[]>("/decks"),
  startMatch: (payload: {
    deck_a: DeckItem[];
    deck_b: DeckItem[];
    deck_a_sideboard?: DeckItem[];
    deck_b_sideboard?: DeckItem[];
    deck_a_id?: number;
    deck_b_id?: number;
    controller_a: "human" | "ai";
    controller_b: "human" | "ai";
    ai_difficulty: string;
    mode: "player_vs_ai" | "ai_vs_ai" | "human_vs_human";
    best_of: number;
  }) => req<MatchState>("/matches/start", { method: "POST", body: JSON.stringify(payload) }),
  getMatch: (id: string) => req<MatchState>(`/matches/${id}`),
  legalMoves: (matchId: string, playerId?: number) =>
    req<{ player_id: number; moves: LegalMove[] }>(
      `/matches/${matchId}/legal-moves${playerId ? `?player_id=${playerId}` : ""}`,
    ),
  act: (matchId: string, player_id: number, action: Record<string, unknown>) =>
    req<MatchState>(`/matches/${matchId}/action`, { method: "POST", body: JSON.stringify({ player_id, action }) }),
  autoplay: (matchId: string, ticks = 1) => req<MatchState>(`/matches/${matchId}/autoplay?ticks=${ticks}`, { method: "POST" }),
  sideboard: (matchId: string, player_id: number, cards_out: DeckItem[], cards_in: DeckItem[]) =>
    req<MatchState>(`/matches/${matchId}/sideboard`, {
      method: "POST",
      body: JSON.stringify({ player_id, cards_out, cards_in }),
    }),
  nextGame: (matchId: string) => req<MatchState>(`/matches/${matchId}/next-game`, { method: "POST" }),
  setPriorityStops: (matchId: string, player_id: number, stops: string[]) =>
    req<MatchState>(`/matches/${matchId}/priority-stops`, {
      method: "POST",
      body: JSON.stringify({ player_id, stops }),
    }),
  simulateBatch: (deck_a: DeckItem[], deck_b: DeckItem[], matches: number, difficulty: string, max_ticks = 3000) =>
    req("/simulate/batch", {
      method: "POST",
      body: JSON.stringify({ deck_a, deck_b, matches, difficulty, max_ticks }),
    }),
  startSimulateBatchJob: (deck_a: DeckItem[], deck_b: DeckItem[], matches: number, difficulty: string, max_ticks = 3000) =>
    req<BatchSimulationJobStart>("/simulate/batch/start", {
      method: "POST",
      body: JSON.stringify({ deck_a, deck_b, matches, difficulty, max_ticks }),
    }),
  getSimulateBatchJob: (jobId: string) =>
    req<BatchSimulationJobStatus>(`/simulate/batch/${encodeURIComponent(jobId)}`),
};
