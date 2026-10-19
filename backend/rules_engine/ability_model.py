from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    unsupported_resolution: tuple[str, ...] = ()


def spell_resolution_gaps(card: CardInstance, action_targets: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Inspect the full selected spell surface before any costs are paid."""
    from rules_engine.card_faces import select_cast_face
    from rules_engine.coverage import unsupported_resolution_clauses
    from rules_engine.oracle_effects import _extract_modes, spell_resolution_text
    targets = action_targets or {}
    selected = targets.get('selected_face_index', getattr(card, 'selected_face_index', None))
    if getattr(card, 'card_faces', None) and (
            getattr(card, 'selected_face_index', None) is None or selected != card.selected_face_index):
        try:
            card = select_cast_face(card, selected)
        except (ValueError, TypeError):
            # Invalid choices belong to the existing face validation, not inference.
            return ()
    from rules_engine.printed_body import printed_body_gaps
    body_gaps = printed_body_gaps(card)
    if body_gaps:
        return body_gaps
    if not set(getattr(card, 'types', []) or []).intersection({'Instant', 'Sorcery'}):
        return ()
    text = spell_resolution_text(card, card.oracle_text or '')
    modes = _extract_modes(text)
    if modes:
        selected = targets.get('mode_texts') or ([targets['mode_text']] if targets.get('mode_text') else [])
        if not selected:
            # A legal supported mode must not be removed by an unselected one.
            return ()
        printed = {mode.casefold(): mode for mode in modes}
        text = ' '.join(printed.get(str(mode).casefold(), '') for mode in selected)
    return tuple(unsupported_resolution_clauses(text))


def unsupported_spell_reason(card: CardInstance, action_targets: dict[str, Any] | None = None) -> str | None:
    gaps = spell_resolution_gaps(card, action_targets)
    return 'Unsupported spell resolution: ' + ', '.join(gaps) if gaps else None


def build_spell_spec(state: MatchState, card: CardInstance, controller: int, action_targets: dict[str, Any] | None = None, *, report_unsupported: bool = True) -> AbilitySpec:
    """Compile a spell, never a permanent's later activated/triggered text."""
    from rules_engine.kicker import spell_kicker_view
    card = spell_kicker_view(card)
    types = set(getattr(card, "types", []) or [])
    if types.intersection({"Instant", "Sorcery"}) or not types.intersection({"Creature", "Artifact", "Enchantment", "Planeswalker", "Battle", "Land"}):
        spec = build_ability_spec(state, card, controller, action_targets, report_unsupported=report_unsupported)
        gaps = spell_resolution_gaps(card, action_targets)
        if spec.used_fallback and not gaps:
            gaps = ('unrecognized spell resolution',)
        for mode in (action_targets or {}).get('mode_texts') or []:
            branch_targets = {**action_targets, **(action_targets.get('mode_targets') or {}).get(mode, {}),
                              'mode_text': mode, 'mode_texts': []}
            branch = build_ability_spec(state, card, controller, branch_targets, report_unsupported=False)
            if branch.used_fallback:
                gaps = tuple(dict.fromkeys((*gaps, 'unrecognized selected-mode resolution')))
        return replace(spec, unsupported_resolution=gaps)
    from rules_engine.cast_choice import build_cast_hints
    choices = {key: value for key, value in (action_targets or {}).items() if key in {
        "selected_face_index", "x_value", "target_card_id", "chosen_creature_type",
    }}
    return AbilitySpec(
        source_card_id=getattr(card, "id", None), source_name=card.name,
        controller=controller, oracle_text=card.oracle_text or "", mana_cost=card.mana_cost or "",
        target_hints=build_cast_hints(state, card, controller, action_targets), modes=[],
        choices=choices, effect=EffectSpec("noop", dict(choices)),
        unsupported_resolution=spell_resolution_gaps(card, action_targets),
    )


def build_ability_spec(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
    *,
    report_unsupported: bool = True,
) -> AbilitySpec:
    action_targets = dict(action_targets or {})
    target_hints = inspect_target_hints(state, card, controller, action_targets)
    effect_key, payload = infer_effect_from_oracle(
        state,
        card,
        controller,
        action_targets=action_targets,
        report_unsupported=report_unsupported,
    )
    oracle = (card.oracle_text or "").strip()
    modes = list(target_hints.get("modes", []))
    choices = {
        key: action_targets[key]
        for key in (
            "selected_face_index", "mode_text", "mode_texts", "mode_targets", "x_value",
            "target_card_id", "target_card_ids", "target_stack_id",
            "target_player", "search_contains", "top_n", "max_creatures", "mv_max",
            "search_card_ids", "topdeck_card_ids", "chosen_creature_type",
            "replacement_source_id",
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
    awaiting_mode = bool(modes) and not (action_targets.get('mode_text') or action_targets.get('mode_texts'))
    used_fallback = effect_key == "noop" and bool(oracle) and not static_only and not awaiting_mode and not event_supported
    restrictions = infer_target_restrictions(state, str(action_targets.get("mode_text") or oracle), controller)
    if restrictions:
        payload.setdefault("target_restrictions", restrictions)
    for key in ("target_card_id", "target_card_ids", "target_player", "search_card_ids"):
        if key in action_targets and key not in payload:
            payload[key] = action_targets[key]
    if "replacement_source_id" in action_targets:
        payload.setdefault("__replacement_source_id", str(action_targets["replacement_source_id"]))
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
