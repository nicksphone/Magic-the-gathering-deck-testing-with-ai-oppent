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
    && (value.keyword_counts === undefined || (record(value.keyword_counts)
      && Object.entries(value.keyword_counts).every(([keyword, count]) => keyword.length > 0
        && Number.isInteger(count) && (count as number) > 0)))
    && (value.power === null || typeof value.power === "number")
    && (value.toughness === null || typeof value.toughness === "number")
    && (value.attached_to === undefined || value.attached_to === null || typeof value.attached_to === "string")
    && (value.effect_warnings === undefined || (Array.isArray(value.effect_warnings) && value.effect_warnings.every((warning) => typeof warning === "string")))
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
  if (value.discards_this_turn !== undefined && (!record(value.discards_this_turn)
    || Object.keys(value.discards_this_turn).length !== 2
    || !["1", "2"].every(seat => Number.isInteger((value.discards_this_turn as Record<string, unknown>)[seat])
      && ((value.discards_this_turn as Record<string, number>)[seat] >= 0)))) {
    throw new Error("Invalid match response: discard history");
  }
  for (const seat of ["1", "2"]) {
    const player = value.players[seat];
    if (!record(player) || typeof player.life !== "number" || !Array.isArray(player.hand)
      || !Array.isArray(player.battlefield) || !Array.isArray(player.graveyard) || !Array.isArray(player.exile)
      || !player.hand.every(card) || !player.battlefield.every(card)
      || !player.graveyard.every(card) || !player.exile.every(card)
      || !Number.isInteger(player.graveyard_count) || player.graveyard_count !== player.graveyard.length
      || !Number.isInteger(player.exile_count) || (player.exile_count as number) < player.exile.length) {
      throw new Error(`Invalid match response: player ${seat} card view`);
    }
    if (player.counters !== undefined && (!record(player.counters)
      || !Object.entries(player.counters).every(([kind, amount]) => /^[a-z]+(?:-[a-z]+)*$/.test(kind)
        && Number.isInteger(amount) && (amount as number) >= 0))) {
      throw new Error(`Invalid match response: player ${seat} counters`);
    }
    if (player.snow_mana_pool !== undefined) {
      const snowPool = player.snow_mana_pool;
      const pool = player.mana_pool;
      if (!record(snowPool) || !record(pool)
        || !Object.entries(snowPool).every(([color, amount]) => {
          const total = pool[color];
          return /^[WUBRGC]$/.test(color) && typeof amount === "number"
            && Number.isInteger(amount) && amount >= 0
            && typeof total === "number" && amount <= total;
        })) {
        throw new Error(`Invalid match response: player ${seat} snow mana pool`);
      }
    }
    if (player.restricted_mana_pool !== undefined) {
      const lots = player.restricted_mana_pool;
      const totals: Record<string, number> = {};
      const snowTotals: Record<string, number> = {};
      const pool = player.mana_pool;
      const snow = player.snow_mana_pool;
      const types = ["Artifact", "Creature", "Enchantment", "Instant", "Sorcery", "Planeswalker", "Battle"];
      if (!Array.isArray(lots) || !record(pool) || !record(snow) || !lots.every((lot) => {
        if (!record(lot) || typeof lot.color !== "string" || !/^[WUBRGC]$/.test(lot.color)
          || !Number.isInteger(lot.amount) || (lot.amount as number) <= 0 || typeof lot.snow !== "boolean"
          || !record(lot.rule)) return false;
        const rule = lot.rule;
        if (rule.unsupported !== true && (!Array.isArray(rule.cast_types) || !rule.cast_types.length
          || !rule.cast_types.every((type) => types.includes(type)) || !Array.isArray(rule.activate_types)
          || !rule.activate_types.every((type) => types.includes(type)))) return false;
        totals[lot.color] = (totals[lot.color] ?? 0) + (lot.amount as number);
        if (lot.snow) snowTotals[lot.color] = (snowTotals[lot.color] ?? 0) + (lot.amount as number);
        return true;
      }) || !Object.entries(totals).every(([color, amount]) => typeof pool[color] === "number" && amount <= (pool[color] as number))
        || !Object.entries(snowTotals).every(([color, amount]) => typeof snow[color] === "number" && amount <= (snow[color] as number))
        || !Object.entries(totals).every(([color, amount]) => amount - (snowTotals[color] ?? 0) <= (pool[color] as number) - ((snow[color] as number) ?? 0))) {
        throw new Error(`Invalid match response: player ${seat} restricted mana pool`);
      }
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
  for (const field of ["mulligan_count", "mulligan_bottomed"]) {
    const counts = value[field];
    if (counts !== undefined && (!record(counts) || !Object.entries(counts).every(([seat, count]) =>
      ["1", "2"].includes(seat) && Number.isInteger(count) && (count as number) >= 0 && (count as number) <= 7))) {
      throw new Error(`Invalid match response: ${field}`);
    }
  }
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
      && (move.cost_options === undefined || (Array.isArray(move.cost_options) && move.cost_options.every(option =>
        record(option) && typeof option.id === 'string'
        && (option.additional_cost_group == null || typeof option.additional_cost_group === 'string')
        && (option.kicked === undefined || typeof option.kicked === 'boolean')
        && ['discard_x', 'discard_all', 'sacrifice_all'].every(key => option[key] === undefined || typeof option[key] === 'boolean')
        && (option.kicker_base_id == null || typeof option.kicker_base_id === 'string')
        && (option.target_hints === undefined || record(option.target_hints))
        && ['discard_cards', 'sacrifice_creatures'].every(key => Number.isInteger(option[key]) && (option[key] as number) >= 0)
        && ['discard_card_ids', 'sacrifice_card_ids'].every(key => option[key] === undefined ||
          (Array.isArray(option[key]) && option[key].every(id => typeof id === 'string')
            && new Set(option[key]).size === option[key].length)))))
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
