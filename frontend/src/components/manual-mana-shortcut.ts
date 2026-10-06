import type { LegalMove } from '../types';
import { baseManaOptions } from './manual-mana-output.ts';

/** A preset may select a unique plain output, never infer a payment or ability. */
export function manaShortcut(moves: LegalMove[], cardId: string, color: string, land: boolean): Record<string, unknown> | null {
  const matching = moves.filter(move => move.type === 'activate_mana_ability' && move.card_id === cardId && Number(move.outputs?.[color] ?? 0) > 0);
  const plain = matching.filter(move => (!move.cost_text?.trim() || /^\{T\}$/i.test(move.cost_text.trim()))
    && !move.required_choices?.payment_choices && !move.required_choices?.hybrid_choices
    && !move.hybrid_symbols?.length && !(move.activation_costs?.discard_cards || move.activation_costs?.sacrifice_creatures || move.activation_costs?.pay_life));
  if (plain.length !== 1) return null;
  const move = plain[0];
  const options = baseManaOptions(move);
  if (options?.length === 0) return null;
  const explicit = {type: 'activate_mana_ability', card_id: cardId, ability_index: move.ability_index, color};
  if (options?.some(option => Object.keys(option.output_bundle).length > 1)) {
    // Multiple anchors for the same sole vector are equivalent; multiple vectors need a human choice.
    if (new Set(options.map(option => option.label)).size !== 1) return null;
    const option = options.find(option => option.color === color) ?? options[0];
    return {...explicit, color: option.color, output_bundle: {...option.output_bundle}};
  }
  if (options && new Set(options.filter(option => option.color === color).map(option => option.label)).size > 1) return null;
  return matching.length === 1 ? {type: land ? 'tap_land_for_mana' : 'tap_nonland_for_mana', card_id: cardId, color} : explicit;
}
