import type { DeckItem, DeckRecord, MatchState } from "../types";
import { HttpResponseError, httpErrorMessage } from "./errors";
import { apiBase, cardMediaUrl } from "./routing";
import { parseAiDebugHands, parseLegalMoves, parseMatchState, parseSavedMatches } from "./match-contract";
import { parseBatchJobStatus, parseSimulationCoverage } from "./simulation-contract";
import { recordRequestSignal, requestSignalAborted, requestSignalStart } from "./request-signal-diagnostics";

const configuredApi = import.meta.env.VITE_API_BASE_URL;
const API = apiBase(configuredApi);
const LONG_REQUEST_TIMEOUT_MS = 600000;

export const API_BASE = API;

export type HealthResponse = {
  ok: boolean;
  service?: string;
  version?: string;
};

export function resolveCardMediaUrl(uri?: string): string | undefined {
  return cardMediaUrl(uri, API);
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
  id?: string | number;
  card_data_sources?: string[];
  match_ready?: boolean;
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

function parseDeckImportResponse(value: unknown): DeckImportResponse {
  const record = (item: unknown): item is Record<string, unknown> =>
    typeof item === "object" && item !== null && !Array.isArray(item);
  const number = (item: unknown): item is number => typeof item === "number" && Number.isFinite(item);
  const count = (item: unknown): item is number => number(item) && Number.isInteger(item) && item >= 0;
  const strings = (item: unknown): item is string[] =>
    Array.isArray(item) && item.every(part => typeof part === "string");
  const numberMap = (item: unknown) => record(item) && Object.values(item).every(number);
  const texts = (item: Record<string, unknown>, fields: string[], nullable = false) =>
    fields.every(field => item[field] === undefined || typeof item[field] === "string"
      || (nullable && item[field] === null));
  const characteristics = (item: Record<string, unknown>) => ["power", "toughness"].every(field =>
    item[field] === undefined || item[field] === null || typeof item[field] === "string" || number(item[field]));
  const metadata = (item: unknown) => record(item)
    && typeof item.scryfall_id === "string" && typeof item.name === "string"
    && (item.id == null || typeof item.id === "string" || number(item.id))
    && texts(item, ["oracle_text", "mana_cost", "type_line"])
    && characteristics(item)
    && texts(item, ["image_uri"], true)
    && (item.colors === undefined || strings(item.colors))
    && (item.card_data_sources === undefined || strings(item.card_data_sources))
    && (item.match_ready === undefined || typeof item.match_ready === "boolean")
    && (item.legalities === undefined || (record(item.legalities)
      && Object.values(item.legalities).every(status => typeof status === "string")))
    && (item.card_faces === undefined || (Array.isArray(item.card_faces) && item.card_faces.every(face =>
      record(face) && texts(face, ["name", "mana_cost", "oracle_text", "type_line", "image_uri"], true)
      && characteristics(face)
      && (face.colors == null || strings(face.colors)))));
  const board = (items: unknown): items is DeckItem[] => Array.isArray(items)
    && items.every(item => record(item) && typeof item.card_name === "string" && count(item.quantity));
  // Display projections retain one row per parsed entry, including unresolved cards.
  const resolved = (rows: unknown, items: DeckItem[]) => rows === undefined || (Array.isArray(rows)
    && rows.length === items.length && rows.every((row, index) => record(row)
      && row.card_name === items[index].card_name && row.quantity === items[index].quantity
      && (row.card_metadata == null || metadata(row.card_metadata))));
  const analysis = (item: unknown) => item === undefined || (record(item)
    && texts(item, ["primary_archetype", "secondary_archetype"])
    && ["confidence", "land_count", "creature_count", "noncreature_spell_count"].every(field =>
      item[field] === undefined || number(item[field]))
    && (item.scores === undefined || numberMap(item.scores))
    && (item.signals === undefined || strings(item.signals)));
  if (!record(value) || !(value.deck_id === null || count(value.deck_id))
    || typeof value.name !== "string" || typeof value.archetype_guess !== "string"
    || !strings(value.errors) || !Array.isArray(value.suggestions)
    || !value.suggestions.every(item => record(item) && count(item.line) && item.line > 0
      && typeof item.input === "string" && (item.suggestion === null || typeof item.suggestion === "string")
      && number(item.score))
    || !board(value.mainboard) || !board(value.sideboard)
    || !numberMap(value.mana_curve) || !numberMap(value.color_profile)
    || !resolved(value.resolved_mainboard_cards, value.mainboard)
    || !resolved(value.resolved_sideboard_cards, value.sideboard) || !analysis(value.analysis)) {
    throw new Error("Invalid deck import response");
  }
  return value as DeckImportResponse;
}

export type CardCompletenessReport = {
  requested: number;
  complete: number;
  missing: Record<string, number>;
  unsupported_count?: number;
  cards: {
    name: string;
    cached: boolean;
    match_ready?: boolean;
    needs_card_sync?: boolean;
    card_data_sources?: string[];
    image_status?: "fallback" | "remote" | "local";
    oracle_source: "cache" | "knowledge" | "fallback" | "missing";
    placeholder_image: boolean;
    unsupported_mechanics?: string[];
    rules_coverage?: "known_unsupported" | "not_certified";
  }[];
};

export type ExpansionTopDeckMeta = {
  code: string;
  expansion: string;
  release_year: number;
  deck_name: string;
  archetype: string;
  kind: "tournament" | "archetype_template";
  format: string | null;
  event_name: string | null;
  player_name: string | null;
  finish: string | null;
  decklist_source_url: string | null;
  event_source_url: string | null;
};

export type ExpansionTopDeckPayload = Omit<ExpansionTopDeckMeta, "deck_name"> & {
  name: string;
  archetype: string;
  deck_text: string;
};

export type BatchSimulationJobStart = {
  job_id: string;
  status: string;
};

export type SimulationCoverage = {
  status: "exploratory";
  known_unsupported_cards: {
    deck: "A" | "B";
    card_name: string;
    mechanics: string[];
    static_clause_gaps?: {
      clause: string;
      condition: string;
      reasons: string[];
      face_index: number | null;
      face_name: string;
    }[];
  }[];
};

export type BatchSimulationJobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed" | "canceled";
  completed_matches: number;
  total_matches: number;
  started_at: number;
  finished_at?: number | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
};

export type DiagnosticRunSummary = {
  run_name: string;
  modified_at: number;
  summary: Record<string, unknown>;
};

export type DiagnosticRunDetail = DiagnosticRunSummary & {
  anomaly_clusters: unknown;
  anomaly_samples: Record<string, unknown>[];
  games: Record<string, unknown>[];
  artifacts: {
    summary: string;
    clusters: string | null;
    anomaly_games: string | null;
    games: string | null;
  };
};

export type DiagnosticRunComparison = {
  left: DiagnosticRunSummary;
  right: DiagnosticRunSummary;
  numeric_deltas: Record<string, {
    left: number | null;
    right: number | null;
    delta_right_minus_left: number;
  }>;
};

export type DiagnosticReplayComparison = {
  left: { run_name: string; game_index: number; record: Record<string, unknown> };
  right: { run_name: string; game_index: number; record: Record<string, unknown> };
  first_divergence: Record<string, unknown>;
  identical: boolean;
};

export type DiagnosticGamePage = {
  run_name: string;
  game_index: number;
  record: Record<string, unknown>;
  offset: number;
  limit: number;
  total_lines: number;
  lines: string[];
  has_more: boolean;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const diagnosticEnabled = import.meta.env.VITE_REQUEST_SIGNAL_DIAGNOSTICS === "1";
  const diagnosticStarted = diagnosticEnabled ? requestSignalStart() : null;
  let requestOptions: RequestInit | undefined;
  let initialAborted: boolean | null = null;
  let fetchArgumentsReady = false;
  let res: Response;
  try {
    // Keep URL, option getters and the selected signal in their original order.
    res = await fetch(`${API}${path}`, (requestOptions = {
      headers: { "Content-Type": "application/json" },
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(30000),
    }, initialAborted = diagnosticEnabled ? requestSignalAborted(requestOptions.signal) : null, fetchArgumentsReady = true, requestOptions));
  } catch (error) {
    if (diagnosticEnabled && fetchArgumentsReady) recordRequestSignal(path, requestOptions, error, diagnosticStarted, initialAborted);
    throw error;
  }
  if (!res.ok) {
    const txt = await res.text();
    throw new HttpResponseError(httpErrorMessage(txt, res.status), res.status);
  }
  return res.json() as Promise<T>;
}

async function matchReq(path: string, init?: RequestInit): Promise<MatchState> {
  return parseMatchState(await req<unknown>(path, init));
}

export type MatchWrite = { revision: number; key: string };
export type StartMatchPayload = {
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
};
const writeHeaders = (write?: MatchWrite): Record<string, string> => write ? { "Content-Type": "application/json", "X-Match-Revision": String(write.revision), "Idempotency-Key": write.key } : { "Content-Type": "application/json" };

export type SavedMatch = { id: string; mode: NonNullable<MatchState["mode"]>; turn: number; game_number: number; revision: number; players: string[] };

export const api = {
  health: () => req<HealthResponse>("/health"),
  listBuiltins: () => req<string[]>("/decks/builtin"),
  getBuiltinText: (name: string) => req<{ name: string; deck_text: string }>(`/decks/builtin/${encodeURIComponent(name)}`),
  listExpansionTopDecks: () => req<ExpansionTopDeckMeta[]>("/decks/expansion-top"),
  getExpansionTopDeck: (code: string) =>
    req<ExpansionTopDeckPayload>(`/decks/expansion-top/${encodeURIComponent(code)}`),
  importExpansionTopDeck: (code: string) =>
    req<unknown>(`/decks/expansion-top/${encodeURIComponent(code)}/import`, { method: "POST" }).then(parseDeckImportResponse),
  importAllExpansionTopDecks: () => req<{ requested: number; imported: number; with_errors: number }>("/decks/expansion-top/import-all", { method: "POST" }),
  importDeck: (name: string, deck_text: string, source = "user") =>
    req<unknown>("/decks/import", { method: "POST", body: JSON.stringify({ name, deck_text, source }) }).then(parseDeckImportResponse),
  listDecks: () => req<DeckRecord[]>("/decks"),
  cardCompleteness: (names: string[]) => {
    const query = names.map((name) => `names=${encodeURIComponent(name)}`).join("&");
    return req<CardCompletenessReport>(`/cards/completeness${query ? `?${query}` : ""}`);
  },
  savedDeckCompleteness: () =>
    req<{ deck_id: number; name: string; source: string; report: CardCompletenessReport }[]>("/decks/completeness"),
  deckCompleteness: (deckId: number) =>
    req<{ deck_id: number; name: string; source: string; report: CardCompletenessReport }>(`/decks/${deckId}/card-completeness`),
  startMatch: (payload: StartMatchPayload, key?: string) => matchReq("/matches/start", {
    method: "POST", headers: key ? { "Content-Type": "application/json", "Idempotency-Key": key } : undefined,
    body: JSON.stringify(payload),
  }),
  getMatch: (id: string) => matchReq(`/matches/${id}`),
  aiDebugHands: (id: string) => req<unknown>(`/matches/${id}/debug/ai-hands`).then(parseAiDebugHands),
  savedMatches: () => req<unknown>("/matches").then(parseSavedMatches),
  legalMoves: (matchId: string, playerId?: number) =>
    req<unknown>(
      `/matches/${matchId}/legal-moves${playerId ? `?player_id=${playerId}` : ""}`,
    ).then(parseLegalMoves),
  act: (matchId: string, player_id: number, action: Record<string, unknown>, write?: MatchWrite) =>
    matchReq(`/matches/${matchId}/action`, { method: "POST", headers: writeHeaders(write), body: JSON.stringify({ player_id, action }) }),
  // Master planning can outlast the ordinary read/manual-action deadline.
  autoplay: (matchId: string, ticks = 1, write?: MatchWrite) => matchReq(`/matches/${matchId}/autoplay?ticks=${ticks}`, {
    method: "POST", headers: writeHeaders(write), signal: AbortSignal.timeout(LONG_REQUEST_TIMEOUT_MS),
  }),
  sideboard: (matchId: string, player_id: number, cards_out: DeckItem[], cards_in: DeckItem[], write?: MatchWrite) =>
    matchReq(`/matches/${matchId}/sideboard`, {
      method: "POST",
      headers: writeHeaders(write),
      body: JSON.stringify({ player_id, cards_out, cards_in }),
    }),
  nextGame: (matchId: string, choice: { player_id: number; play_first: boolean } | null, write?: MatchWrite) =>
    matchReq(`/matches/${matchId}/next-game`, { method: "POST", headers: writeHeaders(write), body: choice ? JSON.stringify(choice) : undefined }),
  setPriorityStops: (matchId: string, player_id: number, stops: string[], write?: MatchWrite) =>
    matchReq(`/matches/${matchId}/priority-stops`, {
      method: "POST",
      headers: writeHeaders(write),
      body: JSON.stringify({ player_id, stops }),
    }),
  simulateBatch: (deck_a: DeckItem[], deck_b: DeckItem[], matches: number, difficulty: string, max_ticks = 3000) =>
    req("/simulate/batch", {
      method: "POST",
      signal: AbortSignal.timeout(LONG_REQUEST_TIMEOUT_MS),
      body: JSON.stringify({ deck_a, deck_b, matches, difficulty, max_ticks }),
    }),
  startSimulateBatchJob: (deck_a: DeckItem[], deck_b: DeckItem[], matches: number, difficulty: string, max_ticks = 3000, startKey?: string) =>
    req<BatchSimulationJobStart>("/simulate/batch/start", {
      method: "POST",
      headers: startKey ? { "Content-Type": "application/json", "Idempotency-Key": startKey } : undefined,
      body: JSON.stringify({ deck_a, deck_b, matches, difficulty, max_ticks }),
    }),
  preflightSimulateBatch: async (deck_a: DeckItem[], deck_b: DeckItem[]) =>
    parseSimulationCoverage(await req<unknown>("/simulate/batch/preflight", {
      method: "POST",
      body: JSON.stringify({ deck_a, deck_b }),
    })),
  getSimulateBatchJob: async (jobId: string) =>
    parseBatchJobStatus(await req<unknown>(`/simulate/batch/${encodeURIComponent(jobId)}`)),
  cancelSimulateBatchJob: async (jobId: string) =>
    parseBatchJobStatus(await req<unknown>(`/simulate/batch/${encodeURIComponent(jobId)}/cancel`, { method: "POST" })),
  listDiagnosticRuns: (limit = 20) =>
    req<{ runs: DiagnosticRunSummary[] }>(`/diagnostics/runs?limit=${limit}`),
  getDiagnosticRun: (runName: string) =>
    req<DiagnosticRunDetail>(`/diagnostics/runs/${encodeURIComponent(runName)}`),
  compareDiagnosticRuns: (left: string, right: string) =>
    req<DiagnosticRunComparison>(`/diagnostics/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`),
  compareDiagnosticReplay: (left: string, right: string, leftGame = 0, rightGame = 0) =>
    req<DiagnosticReplayComparison>(
      `/diagnostics/compare/replay?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}&left_game=${leftGame}&right_game=${rightGame}`,
    ),
  getDiagnosticGamePage: (runName: string, gameIndex: number, offset = 0, limit = 120) =>
    req<DiagnosticGamePage>(`/diagnostics/runs/${encodeURIComponent(runName)}/games/${gameIndex}?offset=${offset}&limit=${limit}`),
};
