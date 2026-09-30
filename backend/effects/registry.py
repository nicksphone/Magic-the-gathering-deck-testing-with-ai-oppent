from __future__ import annotations

from collections.abc import Callable

from effects import handlers
from game_state.state import MatchState


EffectHandler = Callable[[MatchState, int, dict], None]

EFFECT_HANDLERS: dict[str, EffectHandler] = {
    "equip_attachment": handlers.equip_attachment,
    "set_turn_restriction": handlers.set_turn_restriction,
    "deal_damage": handlers.deal_damage,
    "deal_damage_multi": handlers.deal_damage_multi,
    "deal_damage_batch": handlers.deal_damage_batch,
    "damage_each_creature_and_player": handlers.damage_each_creature_and_player,
    "draw_cards": handlers.draw_cards,
    "cycle_draw": handlers.cycle_draw,
    "cycle_search": handlers.cycle_search,
    "gain_life": handlers.gain_life,
    "lose_life": handlers.lose_life,
    "destroy_permanent": handlers.destroy_permanent,
    "change_control": handlers.change_control,
    "destroy_all_creatures": handlers.destroy_all_creatures,
    "exile_all_creatures": handlers.exile_all_creatures,
    "exile_nonland_until_source_leaves": handlers.exile_nonland_until_source_leaves,
    "copy_linked_exiled_card": handlers.copy_linked_exiled_card,
    "exile_all_creatures_incubate": handlers.exile_all_creatures_incubate,
    "exile_colored_permanents_mana_value_at_most": handlers.exile_colored_permanents_mana_value_at_most,
    "exile_all_graveyards": handlers.exile_all_graveyards,
    "destroy_all_artifacts": handlers.destroy_all_artifacts,
    "destroy_all_enchantments": handlers.destroy_all_enchantments,
    "destroy_all_artifacts_and_enchantments": handlers.destroy_all_artifacts_and_enchantments,
    "counter_spell": handlers.counter_spell,
    "counter_spell_unless_pay": handlers.counter_spell_unless_pay,
    "counter_ability": handlers.counter_ability,
    "copy_spell": handlers.copy_spell,
    "copy_ability": handlers.copy_ability,
    "exile": handlers.exile_permanent,
    "return_permanent_to_hand": handlers.return_permanent_to_hand,
    "return_from_graveyard": handlers.return_from_graveyard,
    "put_land_from_hand": handlers.put_land_from_hand,
    "cast_from_graveyard": handlers.cast_from_graveyard,
    "return_creature_from_graveyard_to_battlefield": handlers.return_creature_from_graveyard_to_battlefield,
    "return_permanent_from_graveyard_to_battlefield": handlers.return_permanent_from_graveyard_to_battlefield,
    "search_library": handlers.search_library,
    "create_token": handlers.create_token,
    "attack_count_reward": handlers.attack_count_reward,
    "transform_if_counters": handlers.transform_if_counters,
    "incubate": handlers.incubate,
    "create_token_copy": handlers.create_token_copy,
    "create_shark_token": handlers.create_shark_token,
    "exile_top_cards_playable": handlers.exile_top_cards_playable,
    "look_top_choose": handlers.look_top_choose,
    "look_top_select_hand": handlers.look_top_select_hand,
    "look_top_distinct_types_to_hand": handlers.look_top_distinct_types_to_hand,
    "transform_if_top_matches": handlers.transform_if_top_matches,
    "transform_card": handlers.transform_card,
    "exile_return_transformed": handlers.exile_return_transformed,
    "reveal_defending_top_land": handlers.reveal_defending_top_land,
    "add_mana": handlers.add_mana,
    "add_counters": handlers.add_counters,
    "add_counters_each_creature": handlers.add_counters_each_creature,
    "set_next_creature_entry_counter": handlers.set_next_creature_entry_counter,
    "put_green_creature_from_hand": handlers.put_green_creature_from_hand,
    "temporary_pt_buff": handlers.temporary_pt_buff,
    "temporary_pt_buff_all": handlers.temporary_pt_buff_all,
    "sacrifice": handlers.sacrifice,
    "tap": handlers.tap_card,
    "tap_all_opponent_creatures": handlers.tap_all_opponent_creatures,
    "untap": handlers.untap_card,
    "crew_vehicle": handlers.crew_vehicle,
    "continuous_buff": handlers.continuous_buff,
    "grant_keyword": handlers.grant_keyword,
    "prevent_damage": handlers.prevent_damage,
    "discard_cards": handlers.discard_cards,
    "each_player_discard": handlers.each_player_discard,
    "choose_revealed_discard": handlers.choose_revealed_hand_card,
    "choose_revealed_exile": handlers.choose_revealed_hand_card,
    "topdeck_put_creatures_battlefield": handlers.topdeck_put_creatures_battlefield,
    "topdeck_put_permanents_battlefield": handlers.topdeck_put_permanents_battlefield,
    "topdeck_reveal_creature_to_hand": handlers.topdeck_reveal_creature_to_hand,
    "noop": handlers.noop,
}


def resolve_effect(state: MatchState, controller: int, effect_key: str, payload: dict) -> None:
    if not isinstance(payload, dict):
        state.log.append(f"Invalid payload type for effect {effect_key}: {type(payload).__name__}, expected dict")
        return
    if effect_key == "effect_sequence":
        source_card_id = payload.get("__source_card_id")
        source_lki = payload.get("__source_lki")
        snow_mana_spent = payload.get("snow_mana_spent")
        effects = payload.get("effects", [])
        for index, item in enumerate(effects):
            key = item.get("effect_key")
            data = dict(item.get("payload", {}) or {})
            if key == "lose_life" and payload.get("__targeted_life_loss"):
                data["target_player"] = payload.get("target_player")
            if source_card_id and "__source_card_id" not in data:
                data["__source_card_id"] = source_card_id
            if source_lki is not None:
                data.setdefault("__source_lki", source_lki)
            if snow_mana_spent:
                data.setdefault("snow_mana_spent", snow_mana_spent)
            if not key:
                continue
            resolve_effect(state, controller, key, data)
            pending = state.pending_mechanic_choice or state.pending_replacement_choice
            if pending:
                remaining = []
                for next_effect in effects[index + 1:]:
                    next_data = dict(next_effect.get("payload", {}))
                    if source_card_id:
                        next_data.setdefault("__source_card_id", source_card_id)
                    if source_lki is not None:
                        next_data.setdefault("__source_lki", source_lki)
                    if snow_mana_spent:
                        next_data.setdefault("snow_mana_spent", snow_mana_spent)
                    remaining.append({**next_effect, "payload": next_data})
                pending.setdefault("continuation_effects", []).extend(remaining)
                return
        return
    handler = EFFECT_HANDLERS.get(effect_key)
    if effect_key in {"ninjutsu", "annihilator"}:
        from rules_engine.keyword_actions import resolve_ninjutsu, resolve_annihilator
        handler = {"ninjutsu": resolve_ninjutsu, "annihilator": resolve_annihilator}[effect_key]
    if effect_key == "dredge":
        from rules_engine.dredge import resolve_dredge
        handler = resolve_dredge
    if handler is None:
        state.log.append(f"Missing effect handler: {effect_key}")
        return
    handler(state, controller, payload)
    from rules_engine.linked_exile import flush_linked_exile_returns
    flush_linked_exile_returns(state)
