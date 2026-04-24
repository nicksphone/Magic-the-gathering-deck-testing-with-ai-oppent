import type { DeckItem, DeckRecord, LegalMove, MatchState } from "../types";

const API =
  (import.meta as any).env?.VITE_API_BASE_URL ||
  `http://${typeof window !== "undefined" ? window.location.hostname : "127.0.0.1"}:8000`;

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
  simulateBatch: (deck_a: DeckItem[], deck_b: DeckItem[], matches: number, difficulty: string) =>
    req("/simulate/batch", {
      method: "POST",
      body: JSON.stringify({ deck_a, deck_b, matches, difficulty }),
    }),
};
