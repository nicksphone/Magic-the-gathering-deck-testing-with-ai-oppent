from __future__ import annotations

import re
from copy import copy, deepcopy
from typing import Any

from game_state.state import Zone
from rules_engine.continuous import has_keyword
from rules_engine.oracle_text import without_reminder_text
from rules_engine.protection import protection_match_reason


_PLAYER_PERMANENT_ALTERNATIVE_RE = re.compile(
    r"\btarget (?:(?:player|opponent) or (?:creature|planeswalker|permanent|artifact|enchantment|land)"
    r"|(?:creature|planeswalker|permanent|artifact|enchantment|land) or (?:player|opponent))\b",
    re.IGNORECASE,
)


def stack_object_kind(state: Any, item: Any) -> str:
    copied_kind = (item.payload or {}).get("__stack_copy_kind")
    if copied_kind:
        return str(copied_kind)
    if (item.payload or {}).get("__trigger_event"):
        return "triggered"
    source = state.cards.get(item.source_card_id)
    return "spell" if source is not None and source.zone == Zone.STACK else "activated"


def stack_source_card(state: Any, item: Any):
    """Read a spell copy's saved characteristics independently of its card."""
    source = state.cards.get(getattr(item, "source_card_id", None))
    payload = getattr(item, "payload", None) or {}
    if source is None or payload.get("__stack_copy_kind") != "spell":
        return source
    source = copy(source)
    for key, value in (payload.get("__copied_card") or {}).items():
        setattr(source, key, deepcopy(value))
    source.controller = item.controller
    source.zone = Zone.STACK
    return source


_COUNTER_PROTECTION_TERM = r"(?:white|blue|black|red|green|creature|enchantment|artifact|instant|sorcery|planeswalker)"
_SPELL_COUNTER_PROTECTION_RE = re.compile(
    rf"(?:(?P<scope>{_COUNTER_PROTECTION_TERM}(?: and {_COUNTER_PROTECTION_TERM})?) )?"
    r"spells you control (?:can't|cannot) be countered", re.IGNORECASE,
)


def spell_cant_be_countered(state: Any, item: Any) -> bool:
    """Evaluate supported self and battlefield spell protection at resolution."""
    source = stack_source_card(state, item)
    if source is None:
        return False
    self_pattern = rf"(?:this spell|{re.escape(source.name)}) (?:can't|cannot) be countered"
    if any(re.fullmatch(self_pattern, clause.strip(), re.IGNORECASE)
           for clause in re.split(r"[.\n]", without_reminder_text(source.oracle_text))):
        return True
    from rules_engine.colors import card_color_names

    subjects = {str(kind).lower() for kind in source.types} | card_color_names(source)
    for player in state.players.values():
        for cid in player.battlefield:
            permanent = state.cards.get(cid)
            if permanent is None or permanent.zone != Zone.BATTLEFIELD or permanent.controller != item.controller:
                continue
            for clause in re.split(r"[.\n]", without_reminder_text(permanent.oracle_text)):
                match = _SPELL_COUNTER_PROTECTION_RE.fullmatch(clause.strip())
                if match and (not match.group("scope") or subjects.intersection(match.group("scope").lower().split(" and "))):
                    return True
    return False


def single_player_permanent_alternative(text: str) -> str | None:
    """Return the one-target alternative clause, excluding multi-target text."""
    if len(re.findall(r"\btarget\b", text, re.IGNORECASE)) != 1:
        return None
    match = _PLAYER_PERMANENT_ALTERNATIVE_RE.search(text)
    if not match or re.match(r"\s+[a-z]", text[match.end():], re.IGNORECASE):
        return None
    return match.group(0).lower()


def validate_cast_targets(target_hints: dict[str, Any], action_targets: dict[str, Any]) -> tuple[bool, str]:
    action_targets = action_targets or {}
    modes = target_hints.get("modes") or []
    choose_two = bool(target_hints.get("choose_two_modes"))

    if choose_two:
        selected = action_targets.get("mode_texts") or []
        if len(selected) != 2:
            return False, "Exactly two modes must be selected."
        if len(set(selected)) != 2:
            return False, "Mode selections must be different."
        for mode in selected:
            if mode not in modes:
                return False, "Invalid mode selected."
    elif modes and action_targets.get("mode_text") and action_targets.get("mode_text") not in modes:
        return False, "Invalid mode selected."

    if target_hints.get("requires_x_value"):
        raw_x = action_targets.get("x_value", None)
        if raw_x is None:
            return False, "X value is required and must be non-negative."
        try:
            x_val = int(raw_x)
        except Exception:
            return False, "X value is required and must be non-negative."
        if x_val < 0:
            return False, "X value is required and must be non-negative."

    up_to = int(target_hints.get("up_to_target_count", 0) or 0)
    if up_to > 0:
        target_ids = action_targets.get("target_card_ids") or []
        if len(target_ids) > up_to:
            return False, f"Too many targets selected (max {up_to})."

    divide_total = action_targets.get("divide_total")
    distribution = action_targets.get("target_distribution") or {}
    if target_hints.get("supports_divide") and not distribution and divide_total != 0:
        return False, "A target distribution is required."
    if distribution:
        max_targets = target_hints.get("divide_max_targets")
        if max_targets is not None and len(distribution) > int(max_targets):
            return False, f"Too many division targets selected (max {max_targets})."
        for value in distribution.values():
            if int(value) < 0:
                return False, "Distribution values must be non-negative."
            if target_hints.get("supports_divide") and int(value) == 0:
                return False, "Each division target must receive at least one."
    if divide_total is not None:
        try:
            expected = int(divide_total)
        except Exception:
            return False, "Invalid divide_total value."
        actual = sum(int(v) for v in distribution.values())
        if actual != expected:
            return False, "Damage/counter distribution must match divide_total."

    if action_targets.get("mode_targets") is not None:
        if not modes or set(action_targets["mode_targets"]) != set(selected):
            return False, "Mode targets must match the selected modes."
        if any(action_targets.get(key) is not None for key in ("target_card_id", "target_stack_id", "target_player", "target_card_ids")):
            return False, "Use either per-mode or shared targets, not both."
        return True, ""

    mode_oracle = " ".join(
        [str(action_targets.get("mode_text") or "")]
        + [str(x) for x in (action_targets.get("mode_texts") or [])]
    ).lower()
    if target_hints.get("stack_targets") and ("target spell" in mode_oracle or "target activated ability" in mode_oracle or "target triggered ability" in mode_oracle or "copy target" in mode_oracle or not mode_oracle):
        if not action_targets.get("target_stack_id"):
            return False, "A stack target is required."
    if target_hints.get("creature_targets") and ("target creature" in mode_oracle or "return target" in mode_oracle):
        if not action_targets.get("target_card_id") and not (action_targets.get("target_card_ids") or []):
            return False, "A creature target is required."
    if target_hints.get("permanent_targets") and ("target permanent" in mode_oracle or "nonland permanent" in mode_oracle or "return target" in mode_oracle):
        if not action_targets.get("target_card_id") and not (action_targets.get("target_card_ids") or []):
            return False, "A permanent target is required."
    if target_hints.get("graveyard_creature_targets") and ("graveyard" in mode_oracle or "reanimate" in mode_oracle):
        if not action_targets.get("target_card_id"):
            return False, "A graveyard creature target is required."
    if target_hints.get("graveyard_permanent_targets") and ("graveyard" in mode_oracle or "reanimate" in mode_oracle):
        if not action_targets.get("target_card_id"):
            return False, "A graveyard permanent target is required."
    if target_hints.get("aura_targets"):
        target_id = action_targets.get("target_card_id")
        allowed = {str(item.get("id")) for item in target_hints["aura_targets"]}
        if not target_id:
            return False, "An Aura target is required."
        if str(target_id) not in allowed:
            return False, "The selected Aura target is not legal."
    if target_hints.get("player_targets") and ("target player" in mode_oracle or "target opponent" in mode_oracle or "any target" in mode_oracle):
        if action_targets.get("target_player") is None and not action_targets.get("target_card_id"):
            return False, "A player or permanent target is required."
    if target_hints.get("requires_opponent_target") and action_targets.get("target_player") is None:
        return False, "An opponent target is required."
    if target_hints.get("requires_reveal_target") and action_targets.get("target_player") is None:
        return False, "A player target is required."

    selected_player = action_targets.get("target_player")
    if selected_player is not None:
        allowed_players = {str(item["id"]) for item in target_hints.get("player_targets", [])} if "player_targets" in target_hints else {"1", "2"}
        if str(selected_player) not in allowed_players:
            return False, "The selected player is not a legal target for this effect."
    selected_stack = action_targets.get("target_stack_id")
    if selected_stack and "stack_targets" in target_hints and str(selected_stack) not in {str(item["id"]) for item in target_hints["stack_targets"]}:
        return False, "The selected stack item is not a legal target for this effect."
    selected_card_ids = list(action_targets.get("target_card_ids") or [])
    if action_targets.get("target_card_id"):
        selected_card_ids.append(action_targets["target_card_id"])
    selected_card_ids.extend(cid for cid in distribution if str(cid) not in {"1", "2"})
    if selected_card_ids:
        candidate_ids: set[str] = set()
        for key in (
            "creature_targets", "planeswalker_targets", "permanent_targets", "land_targets",
            "artifact_targets", "enchantment_targets", "noncreature_permanent_targets", "aura_targets",
            "graveyard_creature_targets", "graveyard_permanent_targets",
        ):
            candidate_ids.update(str(item.get("id")) for item in (target_hints.get(key) or []) if item.get("id") is not None)
        candidate_surface_present = bool(candidate_ids) or any(key in target_hints for key in (
            "creature_targets", "permanent_targets", "land_targets", "artifact_targets",
            "enchantment_targets", "noncreature_permanent_targets", "aura_targets",
            "graveyard_creature_targets", "graveyard_permanent_targets",
        )) or "planeswalker_targets" in target_hints
        if candidate_surface_present and any(str(cid) not in candidate_ids for cid in selected_card_ids):
            return False, "The selected card is not a legal target for this effect."

    return True, ""


def validate_protection_targets(state, source_card, action_targets: dict[str, Any]) -> tuple[bool, str]:
    target_ids: list[str] = []
    target_card_id = action_targets.get("target_card_id")
    if target_card_id:
        target_ids.append(target_card_id)
    target_card_ids = action_targets.get("target_card_ids") or []
    target_ids.extend([cid for cid in target_card_ids if cid not in target_ids])
    distribution = action_targets.get("target_distribution") or {}
    target_ids.extend([cid for cid in distribution if cid in state.cards and cid not in target_ids])
    for cid in target_ids:
        target = state.cards.get(cid)
        if not target:
            continue
        reason = protection_match_reason(state, cid, source_card)
        if reason is not None:
            return False, f"Target {target.name} has protection from {reason}."
    return True, ""


def validate_hexproof_shroud_targets(
    state,
    source_controller: int,
    action_targets: dict[str, Any],
) -> tuple[bool, str]:
    player_ids = []
    if action_targets.get("target_player") is not None:
        player_ids.append(int(action_targets["target_player"]))
    player_ids.extend(int(pid) for pid in (action_targets.get("target_distribution") or {}) if str(pid) in {"1", "2"})
    for player_id in set(player_ids):
        immunity = player_target_immunity(state, player_id, source_controller)
        if immunity:
            return False, f"Target {state.players[player_id].name} has {immunity}."

    target_ids: list[str] = []
    target_card_id = action_targets.get("target_card_id")
    if target_card_id:
        target_ids.append(target_card_id)
    target_card_ids = action_targets.get("target_card_ids") or []
    target_ids.extend([cid for cid in target_card_ids if cid not in target_ids])
    target_distribution = action_targets.get("target_distribution") or {}
    target_ids.extend([cid for cid in target_distribution.keys() if cid not in target_ids and cid in state.cards])

    for cid in target_ids:
        target = state.cards.get(cid)
        if not target:
            continue
        if has_keyword(state, cid, "shroud"):
            return False, f"Target {target.name} has shroud."
        if target.controller != source_controller and has_keyword(state, cid, "hexproof"):
            return False, f"Target {target.name} has hexproof."
    return True, ""


def player_target_immunity(state, player_id: int, source_controller: int) -> str | None:
    """Recognize unconditional static Oracle clauses on controlled permanents."""
    if player_id not in state.players:
        return None
    for cid in state.players[player_id].battlefield:
        card = state.cards.get(cid)
        if card is None:
            continue
        clauses = without_reminder_text(card.oracle_text or "").splitlines()
        for clause in clauses:
            normalized = clause.strip().lower()
            if normalized == "you have shroud.":
                return "shroud"
            if normalized == "you have hexproof." and player_id != source_controller:
                return "hexproof"
    return None
