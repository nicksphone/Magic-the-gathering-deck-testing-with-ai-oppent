from __future__ import annotations

from collections.abc import Callable

from effects import handlers
from game_state.state import MatchState


EffectHandler = Callable[[MatchState, int, dict], None]

EFFECT_HANDLERS: dict[str, EffectHandler] = {
    "deal_damage": handlers.deal_damage,
    "deal_damage_multi": handlers.deal_damage_multi,
    "draw_cards": handlers.draw_cards,
    "gain_life": handlers.gain_life,
    "lose_life": handlers.lose_life,
    "destroy_permanent": handlers.destroy_permanent,
    "counter_spell": handlers.counter_spell,
    "exile": handlers.exile_permanent,
    "return_from_graveyard": handlers.return_from_graveyard,
    "search_library": handlers.search_library,
    "create_token": handlers.create_token,
    "add_mana": handlers.add_mana,
    "add_counters": handlers.add_counters,
    "sacrifice": handlers.sacrifice,
    "tap": handlers.tap_card,
    "untap": handlers.untap_card,
    "continuous_buff": handlers.continuous_buff,
    "grant_keyword": handlers.grant_keyword,
    "prevent_damage": handlers.prevent_damage,
    "discard_cards": handlers.discard_cards,
    "topdeck_put_creatures_battlefield": handlers.topdeck_put_creatures_battlefield,
}


def resolve_effect(state: MatchState, controller: int, effect_key: str, payload: dict) -> None:
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
