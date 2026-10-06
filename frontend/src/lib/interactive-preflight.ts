import type { SimulationCoverage, StartMatchPayload } from "../api/client";
import { parseSimulationCoverage } from "../api/simulation-contract.ts";

export type InteractiveReview = {
  version: 1;
  signature: string;
  coverage: SimulationCoverage;
  exploratoryAcknowledged: boolean;
};
export type PendingInteractiveStart = { key: string; payload: StartMatchPayload; review?: InteractiveReview };

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function ordered(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(ordered);
  if (record(value)) return Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])]));
  return value;
}

// Identity of the complete wire intent, not just deck IDs or visible settings.
export function startSignature(payload: StartMatchPayload): string {
  return JSON.stringify(ordered(payload));
}

export function reviewMatchesPayload(review: unknown, payload: StartMatchPayload): review is InteractiveReview {
  if (!record(review) || review.version !== 1 || review.signature !== startSignature(payload)
    || typeof review.exploratoryAcknowledged !== "boolean") return false;
  try { parseSimulationCoverage(review.coverage); return true; }
  catch { return false; }
}

export function canStartReviewed(review: unknown, payload: StartMatchPayload): review is InteractiveReview {
  return reviewMatchesPayload(review, payload) && review.exploratoryAcknowledged;
}

export function parsePendingInteractiveStart(raw: string | null): PendingInteractiveStart | null {
  if (!raw || raw.length > 500000) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (!record(value) || typeof value.key !== "string" || !/^[0-9a-f]{32}$/.test(value.key)
      || !record(value.payload)) return null;
    const payload = value.payload;
    const items = (rows: unknown) => Array.isArray(rows) && rows.every(row => record(row)
      && typeof row.card_name === "string" && row.card_name.trim().length > 0
      && Number.isInteger(row.quantity) && (row.quantity as number) > 0);
    if (!items(payload.deck_a) || !items(payload.deck_b)
      || (payload.deck_a_sideboard !== undefined && !items(payload.deck_a_sideboard))
      || (payload.deck_b_sideboard !== undefined && !items(payload.deck_b_sideboard))
      || !["human", "ai"].includes(payload.controller_a as string)
      || !["human", "ai"].includes(payload.controller_b as string)
      || !["player_vs_ai", "ai_vs_ai", "human_vs_human"].includes(payload.mode as string)
      || !["casual", "strong", "master", "master_plus"].includes(payload.ai_difficulty as string)
      || ![3, 5, 7, 9].includes(payload.best_of as number)
      || [payload.deck_a_id, payload.deck_b_id].some(id => id !== undefined
        && (!Number.isInteger(id) || (id as number) < 1))) return null;
    const result: PendingInteractiveStart = { key: value.key, payload: payload as StartMatchPayload };
    // Legacy/unreviewed intents retain their key, but cannot auto-create a game.
    if (reviewMatchesPayload(value.review, result.payload)) result.review = value.review;
    return result;
  } catch { return null; }
}
