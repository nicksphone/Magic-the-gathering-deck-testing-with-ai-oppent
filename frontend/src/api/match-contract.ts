import type { CardView, LegalMove, MatchState } from "../types";
import type { SavedMatch } from "./client";
import { baseManaOptions } from '../components/manual-mana-output.ts';

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function resourceCandidates(value: unknown): boolean {
  if (!record(value)) return false;
  const ids = (items: unknown): items is string[] => Array.isArray(items)
    && items.every(id => typeof id === 'string' && id.length > 0) && new Set(items).size === items.length;
  return ids(value.delve) && ids(value.improvise) && Array.isArray(value.convoke)
    && value.convoke.every(row => record(row) && typeof row.card_id === 'string' && row.card_id.length > 0
      && ids(row.pay_as) && row.pay_as.length > 0
      && row.pay_as.every(color => color === 'generic' || /^[WUBRG]$/.test(color)))
    && new Set(value.convoke.map(row => row.card_id)).size === value.convoke.length;
}

function card(value: unknown): boolean {
  return record(value)
    && typeof value.id === "string"
    && typeof value.name === "string"
    && [value.type_line, value.base_type_line].every(line => line === undefined || typeof line === "string")
    && typeof value.tapped === "boolean"
    && (value.was_foretold === undefined || typeof value.was_foretold === 'boolean')
    && (value.suspended === undefined || typeof value.suspended === 'boolean')
    && ['foretell_order', 'foretold_turn'].every(key => value[key] === undefined || value[key] === null
      || (Number.isInteger(value[key]) && (value[key] as number) >= 0))
    && Array.isArray(value.types)
    && value.types.every((type) => typeof type === "string")
    && (value.keyword_counts === undefined || (record(value.keyword_counts)
      && Object.entries(value.keyword_counts).every(([keyword, count]) => keyword.length > 0
        && Number.isInteger(count) && (count as number) > 0)))
    && (value.power === null || typeof value.power === "number")
    && (value.toughness === null || typeof value.toughness === "number")
    && [value.printed_power, value.printed_toughness].every(value => value === undefined || value === null || typeof value === "string")
    && (value.attached_to === undefined || value.attached_to === null || typeof value.attached_to === "string")
    && (value.effect_warnings === undefined || (Array.isArray(value.effect_warnings) && value.effect_warnings.every((warning) => typeof warning === "string")))
    && (value.colors === undefined || (Array.isArray(value.colors) && value.colors.every((color) => typeof color === "string" && /^[WUBRG]$/.test(color))))
    && (value.mana_source_colors === undefined || (Array.isArray(value.mana_source_colors) && value.mana_source_colors.every((color) => typeof color === "string" && /^[WUBRGC]$/.test(color))))
    && (value.mana_source_amounts === undefined || (record(value.mana_source_amounts) && Object.entries(value.mana_source_amounts).every(([color, amount]) => /^[WUBRGC]$/.test(color) && Number.isInteger(amount) && (amount as number) > 0)))
    && (value.card_faces === undefined || (Array.isArray(value.card_faces) && value.card_faces.every(record)));
}

export type AiDebugHands = {
  debug_only: true; match_id: string; revision: number; game_number: number;
  turn: number; hands: Record<string, CardView[]>;
};

export function parseAiDebugHands(value: unknown): AiDebugHands {
  if (!record(value) || value.debug_only !== true || typeof value.match_id !== 'string'
    || !Number.isInteger(value.revision) || (value.revision as number) < 0
    || !Number.isInteger(value.game_number) || (value.game_number as number) < 1
    || !Number.isInteger(value.turn) || (value.turn as number) < 1
    || !record(value.hands) || !Object.entries(value.hands).every(([seat, cards]) =>
      ['1', '2'].includes(seat) && Array.isArray(cards) && cards.every(card))) {
    throw new Error('Invalid AI hand debug response');
  }
  return value as AiDebugHands;
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
    if (player.land_plays_remaining !== undefined && (!Number.isInteger(player.land_plays_remaining)
      || (player.land_plays_remaining as number) < 0)) {
      throw new Error(`Invalid match response: player ${seat} land allowance`);
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

export type LegalMovesResponse = { player_id: number; moves: LegalMove[]; revision: number; can_auto_pass?: boolean };

function targetHints(value: unknown): boolean {
  if (!record(value)) return false;
  if (value.linked_target_pairs !== undefined && (!Array.isArray(value.linked_target_pairs)
    || !value.linked_target_pairs.every(pair => record(pair) && typeof pair.primary_name === 'string'
      && typeof pair.creature_id === 'string' && typeof pair.creature_name === 'string'
      && record(pair.targets) && Object.keys(pair.targets).every(key => ['target_player', 'target_card_id', 'target_card_ids'].includes(key))
      && (pair.primary_kind === 'player'
        ? (pair.primary_id === 1 || pair.primary_id === 2) && pair.targets.target_player === pair.primary_id
          && pair.targets.target_card_id === pair.creature_id && pair.targets.target_card_ids === undefined
        : pair.primary_kind === 'planeswalker' && typeof pair.primary_id === 'string'
          && pair.targets.target_player === undefined && pair.targets.target_card_id === undefined
          && Array.isArray(pair.targets.target_card_ids) && pair.targets.target_card_ids.length === 2
          && pair.targets.target_card_ids[0] === pair.primary_id && pair.targets.target_card_ids[1] === pair.creature_id)))) return false;
  if (value.required_target_instance_count === undefined && value.ordered_creature_modifiers === undefined) return true;
  return value.required_distinct_target_count === undefined
    && Number.isInteger(value.required_target_instance_count)
    && (value.required_target_instance_count as number) >= 2
    && (value.required_target_instance_count as number) <= 250
    && Array.isArray(value.ordered_creature_modifiers)
    && value.ordered_creature_modifiers.length === value.required_target_instance_count
    && value.ordered_creature_modifiers.every(modifier => record(modifier)
      && Number.isInteger(modifier.power) && Number.isInteger(modifier.toughness)
      && Array.isArray(modifier.keywords) && modifier.keywords.length === 0);
}

function paymentOptions(value: unknown): boolean {
  if (!record(value)) return false;
  const valid = ['pay_life', 'discard_cards', 'sacrifice_creatures'].every(key => Number.isInteger(value[key]) && (value[key] as number) >= 0)
    && ['discard_card_ids', 'sacrifice_card_ids', 'fixed_discard_card_ids', 'fixed_sacrifice_card_ids'].every(key => {
      const ids = value[key];
      return Array.isArray(ids) && ids.every((id: unknown) => typeof id === 'string' && id.length > 0)
        && new Set(ids).size === ids.length;
    });
  if (!valid) return false;
  return [['discard_card_ids', 'discard_cards', 'fixed_discard_card_ids'],
    ['sacrifice_card_ids', 'sacrifice_creatures', 'fixed_sacrifice_card_ids']].every(([key, countKey, fixedKey]) => {
    const options = value[key] as string[], fixed = value[fixedKey] as string[];
    return fixed.length <= (value[countKey] as number) && options.length >= (value[countKey] as number)
      && fixed.every(id => options.includes(id));
  });
}

function manaChoiceView(move: Record<string, unknown>): boolean {
  if (move.activation_costs !== undefined && !paymentOptions(move.activation_costs)) return false;
  if (move.hybrid_symbols !== undefined && (!Array.isArray(move.hybrid_symbols) || !move.hybrid_symbols.every(symbol =>
    record(symbol) && typeof symbol.symbol === 'string' && Array.isArray(symbol.choices) && symbol.choices.length > 0
    && new Set(symbol.choices).size === symbol.choices.length
    && symbol.choices.every(branch => typeof branch === 'string' && /^(?:[WUBRGCS]|2|P)$/.test(branch))))) return false;
  const options = baseManaOptions({output_options: move.output_options, base_output_bundles: move.base_output_bundles});
  if (options !== null && !options.length) return false;
  const required = move.required_choices;
  if (required === undefined) return true;
  if (!record(required) || !record(move.activation_costs) || !Array.isArray(move.hybrid_symbols)) return false;
  const costs = move.activation_costs;
  const discard = Number(costs.discard_cards) - (costs.fixed_discard_card_ids as string[]).length;
  const sacrifice = Number(costs.sacrifice_creatures) - (costs.fixed_sacrifice_card_ids as string[]).length;
  return required.discard_card_count === discard && required.sacrifice_card_count === sacrifice
    && required.hybrid_choice_count === move.hybrid_symbols.length
    && required.payment_choices === Boolean(discard || sacrifice)
    && required.hybrid_choices === Boolean(move.hybrid_symbols.length);
}

export function parseLegalMoves(value: unknown): LegalMovesResponse {
  if (!record(value) || (value.player_id !== 1 && value.player_id !== 2)
    || (value.can_auto_pass !== undefined && typeof value.can_auto_pass !== "boolean")
    || !Number.isInteger(value.revision) || (value.revision as number) < 0
    || !Array.isArray(value.moves) || !value.moves.every((move) => record(move)
      && typeof move.type === "string" && move.type.length > 0
      && (move.type !== 'suspend' || (typeof move.card_id === 'string' && move.card_id.length > 0
        && typeof move.mana_cost === 'string' && /^(?:\{(?:\d+|[WUBRGCS])\})+$/.test(move.mana_cost)
        && Number.isInteger(move.time_counters) && (move.time_counters as number) > 0))
      && (move.kind !== 'suspend_cast' || (move.type === 'choose_mechanic' && move.player_id === value.player_id
        && move.count === 1 && Array.isArray(move.options) && move.options.length === 1 && move.options[0] === 'decline'))
      && (move.banding_attackers === undefined || (Array.isArray(move.banding_attackers)
        && move.banding_attackers.every(id => typeof id === "string" && Array.isArray(move.options) && move.options.includes(id))))
      && (move.legal_blocks === undefined || (record(move.legal_blocks) && Object.entries(move.legal_blocks).every(([id, targets]) =>
        Array.isArray(move.blockers) && move.blockers.some(card => record(card) && card.id === id)
        && Array.isArray(targets) && new Set(targets).size === targets.length && targets.every(target => typeof target === "string"
          && Array.isArray(move.attackers) && move.attackers.some(card => record(card) && card.id === target)))))
      && (move.blocker_capacities === undefined || (record(move.blocker_capacities) && Object.entries(move.blocker_capacities).every(([id, capacity]) =>
        Array.isArray(move.blockers) && move.blockers.some(card => record(card) && card.id === id)
        && (capacity === null || (Number.isInteger(capacity) && (capacity as number) >= 1)))))
      && (move.target_hints === undefined || targetHints(move.target_hints))
      && (move.type !== 'activate_mana_ability' || (Number.isInteger(move.ability_index)
        && (move.ability_index as number) >= 0 && typeof move.cost_text === 'string'
        && record(move.outputs) && Object.entries(move.outputs).every(([color, amount]) =>
          /^[WUBRGC]$/.test(color) && Number.isInteger(amount) && (amount as number) >= 0)
        && manaChoiceView(move)))
      && (move.card_view === undefined || card(move.card_view))
      && (move.graveyard_permission_key === undefined || (typeof move.graveyard_permission_key === 'string'
        && move.graveyard_permission_key.length > 0 && move.graveyard_permission_key.length <= 100 && move.from_graveyard === true))
      && (move.graveyard_permission_name === undefined || (typeof move.graveyard_permission_name === 'string'
        && move.graveyard_permission_name.length > 0 && move.from_graveyard === true))
      && (move.payment_options === undefined || paymentOptions(move.payment_options))
      && (move.cost_options === undefined || (Array.isArray(move.cost_options) && move.cost_options.every(option =>
        record(option) && typeof option.id === 'string'
        && (option.graveyard_permission_key == null || (typeof option.graveyard_permission_key === 'string'
          && option.graveyard_permission_key.length > 0 && option.graveyard_permission_key.length <= 100))
        && (option.graveyard_permission_max_mana_value == null || (Number.isInteger(option.graveyard_permission_max_mana_value)
          && (option.graveyard_permission_max_mana_value as number) >= 0))
        && (option.additional_cost_group == null || typeof option.additional_cost_group === 'string')
        && (option.kicked === undefined || typeof option.kicked === 'boolean')
        && ['discard_x', 'discard_all', 'sacrifice_all'].every(key => option[key] === undefined || typeof option[key] === 'boolean')
        && (option.kicker_base_id == null || typeof option.kicker_base_id === 'string')
        && (option.target_hints === undefined || targetHints(option.target_hints))
        && (option.resource_payment_candidates === undefined || resourceCandidates(option.resource_payment_candidates))
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
