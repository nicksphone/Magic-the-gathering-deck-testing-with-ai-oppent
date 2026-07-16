from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from game_state.state import CardInstance, MatchState
from rules_engine.oracle_effects import infer_effect_from_oracle, inspect_target_hints


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


def build_ability_spec(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> AbilitySpec:
    action_targets = dict(action_targets or {})
    target_hints = inspect_target_hints(state, card, controller)
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
        )
    )
    used_fallback = effect_key == "noop" and bool(oracle) and not static_only
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
    )
