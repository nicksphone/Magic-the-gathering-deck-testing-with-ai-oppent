from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from game_state.state import CardInstance, MatchState
from rules_engine.oracle_effects import infer_effect_from_oracle, infer_target_restrictions, inspect_target_hints


@dataclass(frozen=True)
class EffectSpec:
    key: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AbilitySpec:
    """Stable application-level representation of a card action.

    The parser remains the compatibility source for legacy cards, but callers
    now receive explicit choices, targets, modes, and fallback status instead
    of passing unstructured Oracle text through every rules layer.
    """

    source_card_id: str | None
    source_name: str
    controller: int
    oracle_text: str
    mana_cost: str
    target_hints: dict[str, Any]
    modes: list[str]
    choices: dict[str, Any]
    effect: EffectSpec
    used_fallback: bool = False
    event_supported: bool = False


def build_ability_spec(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> AbilitySpec:
    action_targets = dict(action_targets or {})
    target_hints = inspect_target_hints(state, card, controller, action_targets)
    effect_key, payload = infer_effect_from_oracle(
        state,
        card,
        controller,
        action_targets=action_targets,
    )
    oracle = (card.oracle_text or "").strip()
    modes = list(target_hints.get("modes", []))
    choices = {
        key: action_targets[key]
        for key in (
            "selected_face_index", "mode_text", "mode_texts", "x_value",
            "target_card_id", "target_card_ids", "target_stack_id",
            "target_player", "search_contains", "top_n", "max_creatures", "mv_max",
            "search_card_ids", "topdeck_card_ids", "chosen_creature_type",
        )
        if key in action_targets
    }
    action_text = any(
        marker in oracle.lower()
        for marker in (
            "draw", "destroy", "exile", "counter", "deal", "damage", "create",
            "return", "search", "sacrifice", "tap", "untap", "gain", "lose",
            "discard", "mill", "put ", "copy",
        )
    )
    static_only = bool(oracle) and not action_text and any(
        marker in oracle.lower()
        for marker in (
            "haste", "flying", "trample", "vigilance", "first strike", "double strike",
            "deathtouch", "lifelink", "menace", "reach", "ward", "hexproof", "indestructible",
            "can't be blocked", "can't attack", "can't block", "prowess",
            "lands you control have", "add two mana of any one color",
            "power is equal", "toughness is equal", "gets +1/+1 for each",
            "card types among cards in all graveyards",
        )
    )
    if re.search(r"(?:^|\n)\s*[+-]\d+\s*:", oracle):
        static_only = True
    if re.search(r"\{[^}]+\}(?:\{[^}]+\})*:\s*", oracle) and not any(
        marker in oracle.lower() for marker in ("when ", "whenever ", "at the beginning")
    ):
        static_only = True
    lower_oracle = oracle.lower()
    event_supported = (
        ("at the beginning of your upkeep" in lower_oracle and "top card" in lower_oracle and "transform" in lower_oracle)
        or ("whenever you cast a noncreature spell" in lower_oracle and "+1/+1 counter" in lower_oracle)
        or ("when this creature dies" in lower_oracle and "deals damage equal to its power" in lower_oracle)
        or ("when this creature enters" in lower_oracle and "cast target instant card from your graveyard" in lower_oracle)
        or ("would deal noncombat damage to a creature" in lower_oracle and "-1/-1 counters" in lower_oracle)
        or ("as this creature enters, choose a creature type" in lower_oracle and "cast creature spells of the chosen type from the top" in lower_oracle)
        or ("when you cast this spell" in lower_oracle and "gain half x life" in lower_oracle and "draw half x cards" in lower_oracle)
    )
    # A modal spell with no selected mode is waiting for a choice, not an
    # unsupported Oracle parse. The selected mode is parsed when materialized.
    used_fallback = effect_key == "noop" and bool(oracle) and not static_only and not modes and not event_supported
    restrictions = infer_target_restrictions(state, oracle, controller)
    if restrictions:
        payload.setdefault("target_restrictions", restrictions)
    for key in ("target_card_id", "target_card_ids", "target_player", "search_card_ids"):
        if key in action_targets and key not in payload:
            payload[key] = action_targets[key]
    if "chosen_creature_type" in action_targets:
        payload.setdefault("chosen_creature_type", str(action_targets["chosen_creature_type"]))
    return AbilitySpec(
        source_card_id=getattr(card, "id", None),
        source_name=card.name,
        controller=controller,
        oracle_text=oracle,
        mana_cost=card.mana_cost or "",
        target_hints=target_hints,
        modes=modes,
        choices=choices,
        effect=EffectSpec(effect_key, dict(payload)),
        used_fallback=used_fallback,
        event_supported=event_supported,
    )
