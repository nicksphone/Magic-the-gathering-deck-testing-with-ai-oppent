from __future__ import annotations

from collections.abc import Callable

from effects import handlers
from game_state.state import MatchState


EffectHandler = Callable[[MatchState, int, dict], None]

EFFECT_HANDLERS: dict[str, EffectHandler] = {
    "deal_damage": handlers.deal_damage,
    "deal_damage_multi": handlers.deal_damage_multi,
    "draw_cards": handlers.draw_cards,
    "cycle_draw": handlers.cycle_draw,
    "cycle_search": handlers.cycle_search,
    "gain_life": handlers.gain_life,
    "lose_life": handlers.lose_life,
    "destroy_permanent": handlers.destroy_permanent,
    "destroy_all_creatures": handlers.destroy_all_creatures,
    "destroy_all_artifacts": handlers.destroy_all_artifacts,
    "destroy_all_enchantments": handlers.destroy_all_enchantments,
    "destroy_all_artifacts_and_enchantments": handlers.destroy_all_artifacts_and_enchantments,
    "counter_spell": handlers.counter_spell,
    "counter_ability": handlers.counter_ability,
    "copy_spell": handlers.copy_spell,
    "copy_ability": handlers.copy_ability,
    "exile": handlers.exile_permanent,
    "return_from_graveyard": handlers.return_from_graveyard,
    "put_land_from_hand": handlers.put_land_from_hand,
    "cast_from_graveyard": handlers.cast_from_graveyard,
    "return_creature_from_graveyard_to_battlefield": handlers.return_creature_from_graveyard_to_battlefield,
    "return_permanent_from_graveyard_to_battlefield": handlers.return_permanent_from_graveyard_to_battlefield,
    "search_library": handlers.search_library,
    "create_token": handlers.create_token,
    "create_shark_token": handlers.create_shark_token,
    "exile_top_cards_playable": handlers.exile_top_cards_playable,
    "reveal_defending_top_land": handlers.reveal_defending_top_land,
    "add_mana": handlers.add_mana,
    "add_counters": handlers.add_counters,
    "put_green_creature_from_hand": handlers.put_green_creature_from_hand,
    "temporary_pt_buff": handlers.temporary_pt_buff,
    "sacrifice": handlers.sacrifice,
    "tap": handlers.tap_card,
    "untap": handlers.untap_card,
    "continuous_buff": handlers.continuous_buff,
    "grant_keyword": handlers.grant_keyword,
    "prevent_damage": handlers.prevent_damage,
    "discard_cards": handlers.discard_cards,
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
        for item in payload.get("effects", []):
            key = item.get("effect_key")
            data = dict(item.get("payload", {}) or {})
            if source_card_id and "__source_card_id" not in data:
                data["__source_card_id"] = source_card_id
            if not key:
                continue
            resolve_effect(state, controller, key, data)
        return
    handler = EFFECT_HANDLERS.get(effect_key)
    if handler is None:
        state.log.append(f"Missing effect handler: {effect_key}")
        return
    handler(state, controller, payload)
