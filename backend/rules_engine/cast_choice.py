from __future__ import annotations

import re
from copy import copy
from typing import Any

from game_state.state import CardInstance, MatchState
from rules_engine.oracle_effects import DIVIDE_RE, inspect_target_hints, spell_resolution_text
from rules_engine.oracle_text import without_reminder_text
from rules_engine.targeting import validate_cast_targets, validate_hexproof_shroud_targets, validate_protection_targets

CHOOSE_TWO_RE = re.compile(r"choose two(?:\s*[—-])?", re.IGNORECASE)
FIXED_DAMAGE_RE = re.compile(r"deals?\s+(\d+)\s+damage", re.IGNORECASE)
TARGET_KEYS = (
    "player_targets", "creature_targets", "planeswalker_targets", "stack_targets",
    "graveyard_spell_targets", "graveyard_card_targets", "graveyard_creature_targets", "graveyard_permanent_targets",
    "aura_targets", "permanent_targets", "artifact_targets", "enchantment_targets",
    "land_targets", "noncreature_permanent_targets",
)


def _needs_target(text: str) -> bool:
    text = without_reminder_text(text.lower())
    text = re.sub(r"\bup to (?:one|two|three|\d+) targets?\b", "", text)
    return bool(re.search(r"\btargets?\b", text))


def _has_target_options(hints: dict[str, Any]) -> bool:
    return any(hints.get(key) for key in TARGET_KEYS)


def has_available_targets_for_action(hints: dict[str, Any]) -> bool:
    if 'linked_target_pairs' in hints:
        return bool(hints['linked_target_pairs'])
    if hints.get('required_target_instance_count') and not hints.get('creature_targets'):
        return False
    required = hints.get('required_distinct_target_count')
    if required and len({target['id'] for target in hints.get('creature_targets', [])}) < required:
        return False
    if hints.get("modes"):
        required = 2 if hints.get("choose_two_modes") else 1
        return len(hints.get("available_modes", [])) >= required
    return not hints.get("action_has_target_text") or _has_target_options(hints)


def available_cast_options_and_hints(state: MatchState, card: CardInstance, controller: int, *, without_mana=False):
    """Keep target-dependent payment and legal Aura choices in one contract."""
    from rules_engine.costs import collect_cost_options, check_cost_option_available, casting_method
    from rules_engine.attachments import is_aura
    options = collect_cost_options(state, controller, card, without_mana=without_mana)
    from rules_engine.bestow import is_bestowed
    options = [option for option in options if (casting_method(option.id) == 'bestow') == is_bestowed(card)]
    if not is_aura(card):
        variants = [(option, build_cost_cast_hints(state, card, controller, option))
                    for option in options if check_cost_option_available(state, controller, card, option)]
        variants = [(option, hints) for option, hints in variants if has_available_targets_for_action(hints)]
        return [option for option, _ in variants], variants[0][1] if variants else {}
    hints = build_cast_hints(state, card, controller)
    targets = hints.get("aura_targets", [])
    compatible = {t["id"]: [o.id for o in options if check_cost_option_available(
        state, controller, card, o, target_card_id=t["id"])] for t in targets}
    targets = [t for t in targets if compatible[t["id"]]]
    hints["aura_targets"] = hints["creature_targets"] = targets
    hints["aura_cost_options"] = {t["id"]: compatible[t["id"]] for t in targets}
    hints["choice_schema"]["target_card_id"] = {"type": "string", "required": True, "enum": [t["id"] for t in targets]}
    return [o for o in options if any(o.id in compatible[t["id"]] for t in targets)], hints


def build_cost_cast_hints(state, card, controller, option, action_targets=None):
    from rules_engine.kicker import spell_kicker_view
    hints = build_cast_hints(state, spell_kicker_view(card, option.kicked), controller, action_targets)
    if '{X}' in option.mana_cost.upper():
        hints['requires_x_value'] = True
        hints['choice_schema']['x_value'] = {'type': 'integer', 'required': True, 'minimum': 0}
    return hints


def build_cast_hints(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from rules_engine.kicker import spell_kicker_view
    card = spell_kicker_view(card)
    types = set(getattr(card, "types", []) or [])
    if types.intersection({"Creature", "Artifact", "Enchantment", "Planeswalker", "Battle", "Land"}) and not types.intersection({"Instant", "Sorcery"}):
        from rules_engine.attachments import is_aura
        aura = is_aura(card)
        card = copy(card)
        if aura:
            enchant = re.search(r"^enchant [^.\n]+", without_reminder_text(card.oracle_text or ""), re.I | re.M)
            from rules_engine.bestow import is_bestowed
            card.oracle_text = 'Enchant creature' if is_bestowed(card) else enchant.group(0) if enchant else ""
        else:
            # This is a permanent spell, not one of its later abilities.
            # Preserve mana/face choices without borrowing ability targets.
            card.oracle_text = ""
    hints = inspect_target_hints(state, card, controller, action_targets)
    selected_modes = (action_targets or {}).get("mode_texts") or []
    selected_text = spell_resolution_text(card, " ".join(selected_modes) or (action_targets or {}).get("mode_text") or card.oracle_text or "")
    hints["action_has_target_text"] = _needs_target(selected_text)
    if hints.get("modes"):
        selected = set(selected_modes or ([action_targets["mode_text"]] if action_targets and action_targets.get("mode_text") else []))
        hints["available_modes"] = [
            mode for mode in hints["modes"]
            if (not selected or mode in selected)
            and (not _needs_target(mode)
                 or _has_target_options(inspect_target_hints(state, card, controller, {"mode_text": mode})))
        ]
    hints.setdefault("choice_schema", {})
    face_names = hints.get("face_names") or []
    if face_names:
        hints["choice_schema"]["selected_face_index"] = {
            "type": "integer",
            "required": False,
            "minimum": 0,
            "maximum": max(0, len(face_names) - 1),
        }
    if CHOOSE_TWO_RE.search(card.oracle_text or ""):
        hints["choose_two_modes"] = True
    if hints.get("modes"):
        if hints.get("choose_two_modes"):
            hints["choice_schema"]["mode_texts"] = {"type": "array", "required": True, "min_items": 2, "max_items": 2, "enum": hints["available_modes"]}
            hints["mode_target_hints"] = {
                mode: inspect_target_hints(state, card, controller, {"mode_text": mode})
                for mode in hints["available_modes"]
            }
        else:
            hints["choice_schema"]["mode_text"] = {"type": "string", "required": False, "enum": hints["available_modes"]}
    if hints.get("requires_x_value"):
        hints["choice_schema"]["x_value"] = {"type": "integer", "required": True, "minimum": 0}
    if hints.get("player_targets"):
        hints["choice_schema"]["target_player"] = {"type": "integer", "required": False}
    if hints.get("creature_targets"):
        hints["choice_schema"]["target_card_id"] = {"type": "string", "required": False}
    if hints.get("permanent_targets"):
        hints["choice_schema"]["target_card_id"] = {"type": "string", "required": False}
    if hints.get("graveyard_creature_targets") or hints.get("graveyard_card_targets"):
        hints["choice_schema"]["target_card_id"] = {"type": "string", "required": False}
    if hints.get("aura_targets"):
        hints["choice_schema"]["target_card_id"] = {
            "type": "string",
            "required": True,
            "enum": [item["id"] for item in hints["aura_targets"]],
        }
    if hints.get("stack_targets"):
        hints["choice_schema"]["target_stack_id"] = {"type": "string", "required": False}
    if hints.get("unless_payment"):
        hints["choice_schema"]["pay_unless_counter"] = {"type": "boolean", "required": False}
    hints["choice_schema"]["replacement_source_id"] = {
        "type": "string",
        "required": False,
        "description": "Optional replacement-effect source ID returned by the replacement-options API.",
    }
    if hints.get("up_to_target_count"):
        hints["choice_schema"]["target_card_ids"] = {"type": "array", "required": False, "max_items": hints["up_to_target_count"]}
    required = hints.get('required_distinct_target_count') or hints.get('required_target_instance_count')
    if required:
        hints['choice_schema']['target_card_ids'] = {
            'type': 'array', 'required': True, 'min_items': required,
            'max_items': required, 'unique_items': bool(hints.get('required_distinct_target_count')),
        }
    return hints


def validate_cast_choice(hints: dict[str, Any], action_targets: dict[str, Any]) -> tuple[bool, str]:
    mode_targets = action_targets.get("mode_targets") or {}
    if not isinstance(mode_targets, dict):
        return False, "Mode targets must be an object."
    search_overrides = {"search_contains", "search_count", "search_mv_max"}
    if search_overrides.intersection(action_targets) or any(
        isinstance(targets, dict) and search_overrides.intersection(targets)
        for targets in mode_targets.values()
    ):
        return False, "Library-search restrictions come from the card, not the cast action."
    ok, err = validate_cast_targets(hints, action_targets)
    if not ok:
        return ok, err
    selected_modes = (action_targets.get("mode_texts") or []) + ([action_targets["mode_text"]] if action_targets.get("mode_text") else [])
    if (selected_modes or mode_targets) and not hints.get('modes'):
        return False, 'This spell or ability has no modes.'
    if "available_modes" in hints and any(mode not in hints["available_modes"] for mode in selected_modes):
        return False, "Selected mode has no legal target."
    face_names = hints.get("face_names") or []
    if face_names and action_targets.get("selected_face_index") is not None:
        try:
            selected = int(action_targets.get("selected_face_index"))
        except Exception:
            return False, "Selected face index must be a valid integer."
        if selected < 0 or selected >= len(face_names):
            return False, "Selected face index is out of range."
    if hints.get("library_search") and action_targets.get("search_card_ids") is not None:
        return False, "Library cards are chosen when the search resolves, not when it is cast."
    if hints.get("topdeck_choice") and action_targets.get("topdeck_card_ids") is not None:
        return False, "Topdeck cards are chosen when the effect resolves, not when it is cast."
    if hints.get("top_choice") and any(action_targets.get(key) is not None for key in ("top_choice_hand_id", "top_choice_exile_id", "top_choice_bottom_ids")):
        return False, "Top-card choices are made when the effect resolves, not when it is cast."
    return True, ""


def validate_mode_targets(state: MatchState, card: CardInstance, controller: int, action_targets: dict[str, Any]) -> tuple[bool, str]:
    selected = action_targets.get("mode_texts") or ([action_targets["mode_text"]] if action_targets.get("mode_text") else [])
    choices = action_targets.get("mode_targets") or {}
    if set(choices) != set(selected) or len(choices) != len(selected):
        return False, "Mode targets must match the selected modes."
    for mode in selected:
        targets = {"mode_text": mode, **choices[mode]}
        hints = inspect_target_hints(state, card, controller, targets)
        for check in (
            validate_cast_targets(hints, targets),
            validate_protection_targets(state, card, targets),
            validate_hexproof_shroud_targets(state, controller, targets, card),
        ):
            if not check[0]:
                return check
    return True, ""


def enrich_divide_total(card: CardInstance, action_targets: dict[str, Any]) -> dict[str, Any]:
    targets = dict(action_targets or {})
    oracle_or_mode = f"{card.oracle_text or ''} {targets.get('mode_text') or ''} {' '.join(str(x) for x in (targets.get('mode_texts') or []))}".lower()
    if not DIVIDE_RE.search(oracle_or_mode):
        return targets
    x_value = targets.get("x_value")
    if x_value is not None and re.search(r"\bdeals?\s+x\s+damage", oracle_or_mode):
        targets["divide_total"] = int(x_value)
        return targets
    mode_text = str(targets.get("mode_text") or "")
    match = FIXED_DAMAGE_RE.search(mode_text) or FIXED_DAMAGE_RE.search(card.oracle_text or "")
    if match:
        targets["divide_total"] = int(match.group(1))
    return targets
