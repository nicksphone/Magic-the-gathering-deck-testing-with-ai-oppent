import type { LegalMove, MatchState } from "../types";
import type { SavedMatch } from "./client";

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function card(value: unknown): boolean {
  return record(value)
    && typeof value.id === "string"
    && typeof value.name === "string"
    && typeof value.tapped === "boolean"
    && Array.isArray(value.types)
    && value.types.every((type) => typeof type === "string")
    && (value.power === null || typeof value.power === "number")
    && (value.toughness === null || typeof value.toughness === "number")
    && (value.colors === undefined || (Array.isArray(value.colors) && value.colors.every((color) => typeof color === "string" && /^[WUBRG]$/.test(color))))
    && (value.mana_source_colors === undefined || (Array.isArray(value.mana_source_colors) && value.mana_source_colors.every((color) => typeof color === "string" && /^[WUBRGC]$/.test(color))))
    && (value.mana_source_amounts === undefined || (record(value.mana_source_amounts) && Object.entries(value.mana_source_amounts).every(([color, amount]) => /^[WUBRGC]$/.test(color) && Number.isInteger(amount) && (amount as number) > 0)))
    && (value.card_faces === undefined || (Array.isArray(value.card_faces) && value.card_faces.every(record)));
}

export function parseMatchState(value: unknown): MatchState {
  if (!record(value) || typeof value.id !== "string" || typeof value.step !== "string"
    || typeof value.turn !== "number" || typeof value.active_player !== "number"
    || typeof value.priority_player !== "number" || !record(value.players)
    || !record(value.score) || !Array.isArray(value.stack) || !Array.isArray(value.log)) {
    throw new Error("Invalid match response: missing core state fields");
  }
  for (const seat of ["1", "2"]) {
    const player = value.players[seat];
    if (!record(player) || typeof player.life !== "number" || !Array.isArray(player.hand)
      || !Array.isArray(player.battlefield) || !player.hand.every(card)
      || !player.battlefield.every(card)) {
      throw new Error(`Invalid match response: player ${seat} card view`);
    }
  }
  if (value.blocks !== undefined && (!record(value.blocks)
    || !Object.values(value.blocks).every((ids) => Array.isArray(ids) && ids.every((id) => typeof id === "string")))) {
    throw new Error("Invalid match response: blocks must map attackers to blocker ID arrays");
  }
  if (value.attack_bands !== undefined && (!Array.isArray(value.attack_bands)
    || !value.attack_bands.every((band) => Array.isArray(band) && band.every((id) => typeof id === "string")))) {
    throw new Error("Invalid match response: attack bands must be card ID arrays");
  }
  const pending = value.pending_mechanic_choice;
  if (pending !== undefined && pending !== null && (!record(pending)
    || typeof pending.kind !== "string" || (pending.player_id !== 1 && pending.player_id !== 2)
    || (pending.options !== undefined && (!Array.isArray(pending.options) || !pending.options.every((id) => typeof id === "string")))
    || (record(value.controllers) && value.controllers[String(pending.player_id)] === "ai"
      && ("options" in pending || "library_ids" in pending || "effect_payload" in pending)))) {
    throw new Error("Invalid match response: pending mechanic choice");
  }
  if (value.sideboarding !== undefined && (!record(value.sideboarding)
    || !Object.entries(value.sideboarding).every(([seat, inventory]) => ["1", "2"].includes(seat)
      && record(inventory) && typeof inventory.applied === "boolean"
      && [inventory.mainboard, inventory.sideboard].every((items) => Array.isArray(items)
        && items.every((item) => record(item) && typeof item.card_name === "string"
          && Number.isInteger(item.quantity) && (item.quantity as number) > 0))))) {
    throw new Error("Invalid match response: sideboarding inventory");
  }
  return value as MatchState;
}

export type LegalMovesResponse = { player_id: number; moves: LegalMove[]; revision: number };

export function parseLegalMoves(value: unknown): LegalMovesResponse {
  if (!record(value) || (value.player_id !== 1 && value.player_id !== 2)
    || !Number.isInteger(value.revision) || (value.revision as number) < 0
    || !Array.isArray(value.moves) || !value.moves.every((move) => record(move)
      && typeof move.type === "string" && move.type.length > 0
      && (move.card_view === undefined || card(move.card_view))
      && (move.min_count === undefined || (Number.isInteger(move.min_count) && (move.min_count as number) >= 0
        && Number.isInteger(move.count) && (move.min_count as number) <= (move.count as number)))
      && (move.options === undefined || (Array.isArray(move.options) && move.options.every((id) => typeof id === "string"))))) {
    throw new Error("Invalid legal-moves response: seat, revision or move shape");
  }
  return value as LegalMovesResponse;
}

export function parseSavedMatches(value: unknown): SavedMatch[] {
  if (!Array.isArray(value) || !value.every((match) => record(match)
    && typeof match.id === "string" && match.id.length > 0
    && typeof match.mode === "string" && ["player_vs_ai", "ai_vs_ai", "human_vs_human"].includes(match.mode)
    && Number.isInteger(match.turn) && (match.turn as number) >= 1
    && Number.isInteger(match.game_number) && (match.game_number as number) >= 1
    && Number.isInteger(match.revision) && (match.revision as number) >= 0
    && Array.isArray(match.players) && match.players.length === 2
    && match.players.every((name) => typeof name === "string"))) {
    throw new Error("Invalid saved-matches response: match summary shape");
  }
  return value as SavedMatch[];
}
