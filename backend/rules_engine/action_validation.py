"""Checked, copy-on-write actions for external callers, using engine legality."""
from copy import deepcopy
import re

from game_state.state import Step


class ActionRejected(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ActionRejected(reason)


def unique_ids(ids: list[str], allowed, count: int | None = None) -> None:
    require(len(ids) == len(set(ids)), "Card selections cannot contain duplicates")
    require(all(cid in allowed for cid in ids), "Selection contains an unavailable card")
    require(count is None or len(ids) == count, "Incorrect number of selected cards")


def require_declared_targets(card, hints: dict, targets: dict, controller: int, *, spell: bool = False) -> None:
    """External actions must declare choices, not rely on legacy auto-targets."""
    if spell and not set(getattr(card, "types", [])).intersection({"Instant", "Sorcery"}):
        from rules_engine.attachments import is_aura
        if is_aura(card):
            require(bool(targets.get("target_card_id")), "Announce an Aura attachment target")
        # Permanent spells do not target using their later activated/triggered
        # ability text. Aura attachment targets are the supported exception.
        return
    modes = targets.get("mode_texts") or ([targets["mode_text"]] if targets.get("mode_text") else [])
    require(not hints.get("modes") or bool(modes), "Announce the selected mode")
    text = " ".join(modes).lower() if modes else card.oracle_text.lower()
    permanent = bool(targets.get("target_card_id") or targets.get("target_card_ids") or targets.get("target_distribution"))
    from rules_engine.targeting import single_player_permanent_alternative

    alternative = single_player_permanent_alternative(text)
    if alternative:
        player = targets.get("target_player") is not None
        require(player != permanent, "Announce exactly one player or permanent target")
        if player and "opponent" in alternative:
            require(targets["target_player"] != controller, "Target must be an opponent")
        return
    if "any target" in text:
        if text.count("target") == 1:
            selected = (
                int(targets.get("target_player") is not None)
                + int(bool(targets.get("target_card_id")))
                + len(targets.get("target_card_ids") or [])
                + len(targets.get("target_distribution") or {})
            )
            require(selected == 1, "Announce exactly one player or permanent target")
        else:
            require(permanent or targets.get("target_player") is not None, "Announce a target")
    if "target player" in text or "target opponent" in text:
        require(targets.get("target_player") is not None, "Announce a target player")
        require("target opponent" not in text or targets["target_player"] != controller, "Target must be an opponent")
    if re.search(r"\btarget (?:[\w-]+ ){0,4}(?:creature|permanent|land|artifact|enchantment|planeswalker)\b(?!\s+spell)", text) and not re.search(r"up to (?:\d+|one|two|three) target", text):
        require(permanent, "Announce a permanent target")
    if re.search(r"\btarget (?:(?:noncreature|creature|artifact|enchantment|planeswalker|instant|sorcery) )?spell\b", text) or "target activated ability" in text or "target triggered ability" in text:
        require(bool(targets.get("target_stack_id")), "Announce a stack target")


def checked_action(state, rules, player_id: int, action: dict):
    # Even legality helpers run on the copy: no rejected request changes the
    # authoritative state, RNG, logs, cost payments or pending continuations.
    candidate = deepcopy(state)
    validate_action(candidate, rules, player_id, action)
    rules.take_action(candidate, player_id, action, reject_invalid=True)
    if action["type"] == "attack":
        require(set(action["attackers"]).issubset(candidate.attackers), "An attacker cannot attack in this declaration")
    if action["type"] == "block":
        for attacker, blockers in action["blocks"].items():
            require(set(blockers).issubset(candidate.blocks.get(attacker, [])), "Illegal block assignment")
    return candidate


def validate_action(state, rules, player_id: int, action: dict) -> None:
    require(player_id in state.players, "Invalid player")
    require(state.winner is None, "Game is already over")
    kind = action["type"]
    pending = state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order
    if not state.pregame_pending and not pending:
        require(state.priority_player == player_id, "This player does not have priority")
    moves = rules.legal_moves(state, player_id)
    available = [move for move in moves if move["type"] == kind]
    if kind in {"tap_land_for_mana", "tap_lands_bulk", "tap_nonland_for_mana"}:
        require(not state.pregame_pending and not pending, "Mana actions cannot interrupt a pending choice")
        require(state.step != Step.CLEANUP or state.cleanup_repeat_required, "No mana actions during ordinary cleanup")
        validate_tap(state, player_id, action)
        return
    # Declaring no attackers is legal even when the move generator has none.
    if kind == "attack" and not action["attackers"]:
        require(state.step == Step.DECLARE_ATTACKERS and state.active_player == player_id and not state.attackers_declared, "Not an attacker declaration window")
        require(not action.get("attack_targets"), "Attack targets require selected attackers")
        require(not action.get("bands"), "Bands require selected attackers")
        return
    require(bool(available), "Action is not currently legal")
    for key in ("card_id", "ability_index", "return_card_id", "replacement_source_id", "stack_id", "target_card_id"):
        if key in action:
            available = [move for move in available if move.get(key) == action[key]]
    require(bool(available), "Action references an unavailable card, ability or choice")
    move = available[0]
    player = state.players[player_id]
    targets = action.get("targets", {})
    if targets.get("target_stack_id"):
        require(any(item.id == targets["target_stack_id"] for item in state.stack), "Target stack item is unavailable")
    for key in ("target_card_ids", "target_card_id"):
        ids = targets.get(key) or []
        ids = [ids] if isinstance(ids, str) else ids
        require(all(cid in state.cards for cid in ids), "Target card is unavailable")
    require(all(cid in state.cards or cid in {"1", "2"} for cid in targets.get("target_distribution", {})), "Distribution target is unavailable")
    if kind in {"play_land", "cast_spell"}:
        for flag in ("from_exile", "from_library", "from_graveyard"):
            require(bool(action.get(flag)) == bool(move.get(flag)), "Card source zone does not match the legal action")
    if kind == "keep_hand":
        ids = action.get("bottom_card_ids", [])
        unique_ids(ids, player.hand, state.mulligan_count.get(player_id, 0))
    elif kind == "play_land":
        face = action.get("selected_face_index", 0) or 0
        require(any(item.get("selected_face_index", 0) == face and item.get("entry_choice") == action.get("entry_choice") for item in available), "Selected land face or entry choice is unavailable")
    elif kind == "mulligan":
        require(state.mulligan_count.get(player_id, 0) < 7, "Cannot mulligan below zero opening cards")
    elif kind == "choose_mechanic":
        pending = state.pending_mechanic_choice
        if pending["kind"] == "combat_damage":
            from rules_engine.combat import valid_damage_assignment
            require(valid_damage_assignment(state, player_id, action), "Invalid combat damage assignment")
        elif pending["kind"] in {"draw", "land_entry"}:
            require(action.get("choice_id") in pending["options"], "Unavailable draw choice")
        elif pending["kind"] in {"topdeck_put", "search_library"}:
            unique_ids(action.get("card_ids", []), pending["options"])
            require(len(action.get("card_ids", [])) <= pending["count"], "Too many topdeck cards selected")
        else:
            unique_ids(action.get("card_ids", []), pending["options"], pending["count"])
    elif kind == "choose_trigger_order":
        group = state.pending_trigger_order["groups"].get(str(player_id), [])
        expected = [str(trigger["_choice_id"]) for trigger in group]
        unique_ids(action["trigger_order"], expected, len(expected))
    elif kind == "choose_trigger_target":
        require(any(move.get("stack_id") == action["stack_id"] and move.get("target_card_id") == action["target_card_id"] for move in available), "Unavailable trigger target")
    elif kind == "choose_optional_effect":
        require(any(move.get("stack_id") == action["stack_id"] and move.get("accept") is action["accept"] for move in available), "Unavailable optional effect choice")
    elif kind == "attack":
        unique_ids(action["attackers"], move.get("options", []))
        defenders = {item["id"] for item in move.get("defenders", [])}
        require(all(cid in action["attackers"] and target in defenders for cid, target in action.get("attack_targets", {}).items()), "Invalid attack target")
        from rules_engine.combat import valid_attack_bands
        require(valid_attack_bands(state, action["attackers"], action.get("attack_targets", {}), action.get("bands", [])), "Invalid attacking band")
    elif kind == "block":
        attackers = {item["id"] for item in move["attackers"]}
        blockers = {item["id"] for item in move["blockers"]}
        for attacker, ids in action["blocks"].items():
            require(attacker in attackers, "Unavailable attacking creature")
            unique_ids(ids, blockers)
    elif kind == "crew":
        unique_ids(action["crew_card_ids"], {item["id"] for item in move["crew_candidates"]})
    elif kind == "equip":
        require(action["target_card_id"] in {item["id"] for item in move["targets"]}, "Unavailable equipment target")
    elif kind == "cycle_card":
        require(any(item.get("x_value", 0) == action.get("x_value", 0) for item in available), "Unavailable cycling cost")
    elif kind in {"activate_ability", "activate_loyalty"} and targets.get("x_value") is not None:
        from rules_engine.oracle_effects import extract_loyalty_abilities
        require(kind == "activate_loyalty" and extract_loyalty_abilities(state.cards[action["card_id"]])[action["ability_index"]].get("x_cost"), "This ability does not have a chosen X")
    elif kind == "cast_spell":
        from rules_engine.costs import collect_cost_options
        from rules_engine.engine import _select_face_for_cast
        face = action.get("selected_face_index", action.get("targets", {}).get("selected_face_index"))
        if face is not None:
            require(0 <= face < len(state.cards[action["card_id"]].card_faces), "Selected card face is unavailable")
            require(not face or state.cards[action["card_id"]].layout not in {"transform", "meld", "flip", "double_faced_token"}, "This back face cannot be cast directly")
        face_card = _select_face_for_cast(state.cards[action["card_id"]], face)
        if state.cards[action["card_id"]].layout in {"modal_dfc", "adventure"}:
            require(any(item.get("selected_face_index", 0) == (face or 0) for item in available), "Selected face is not currently castable")
        options = collect_cost_options(state, player_id, face_card)
        choice = (action.get("cost_choice") or {}).get("id")
        require(not choice or any(option.id == choice for option in options), "Unknown casting cost option")
        if targets.get("x_value") is not None:
            require("{X}" in face_card.mana_cost.upper(), "This casting cost does not have a chosen X")


def validate_tap(state, player_id: int, action: dict) -> None:
    from rules_engine.engine import _land_colors_from_metadata
    from rules_engine.mana import _nonland_mana_source_colors
    player = state.players[player_id]
    if action["type"] == "tap_nonland_for_mana":
        cid = action["card_id"]
        require(cid in player.battlefield, "Mana source must be a permanent you control")
        colors = _nonland_mana_source_colors(state, cid, state.cards[cid])
        require(action["color"] in colors, "Mana source cannot produce the selected color now")
        return
    if action["type"] == "tap_land_for_mana":
        ids = [action["card_id"]]
    else:
        ids = [cid for cid in player.battlefield if state.cards[cid].name.strip().lower() == action["land_name"].strip().lower() and "Land" in state.cards[cid].types and not state.cards[cid].tapped]
        require(len(ids) >= action["count"], "Not enough untapped matching lands")
        ids = ids[:action["count"]]
    for cid in ids:
        card = state.cards.get(cid)
        require(cid in player.battlefield and card is not None and "Land" in card.types and not card.tapped, "Mana source must be an untapped land you control")
        colors = _land_colors_from_metadata(card.name, card.oracle_text) or {"C"}
        require(not action.get("color") or action["color"] in colors, "Land cannot produce the selected color")
