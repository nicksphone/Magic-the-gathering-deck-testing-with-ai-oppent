import type { MatchState } from "../types";

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
  return value as MatchState;
}
