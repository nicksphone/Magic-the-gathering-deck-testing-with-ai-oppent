from __future__ import annotations

import re

from game_state.state import MatchState
from card_data.tactical import tactical_tags
from rules_engine.oracle_text import without_reminder_text
from rules_engine.continuous import effective_keywords, effective_power, effective_toughness


def recurring_engine_value(state, card_id: str, *, surface_card=None) -> float:
    """Value printed recurring rewards, not spent ETBs or trigger conditions."""
    card = surface_card if surface_card is not None else state.cards[card_id]
    text = without_reminder_text(_active_card_surface(card)["oracle_text"])
    effects = []
    for line in text.splitlines():
        if not re.match(r"^(?:whenever|at the beginning)\b", line.strip(), re.I) or "," not in line:
            continue
        if isinstance(state, MatchState) and re.search(r"\bdies?\b", line, re.I):
            from rules_engine.events import _matches_creature_dies_trigger
            from rules_engine.replacement import replacement_options
            if not any(
                "Creature" in state.cards[cid].types
                and _matches_creature_dies_trigger(state, card, line.lower(), {"card_id": cid})
                and not replacement_options(state, "die_zone", target_card_id=cid)
                for player in state.players.values() for cid in player.battlefield
            ):
                continue
        effects.append(line.split(",", 1)[1])
    roles = tactical_tags("\n".join(effects))
    return sum(weight for role, weight in {"drain": 6.0, "draw": 3.0, "token": 3.0}.items()
               if role in roles)


def evaluate_board(state: MatchState, player_id: int) -> float:
    me = state.players[player_id]
    opp_id = 1 if player_id == 2 else 2
    opp = state.players[opp_id]
    my_battlefield = _board_value(state, player_id)
    opp_battlefield = _board_value(state, opp_id)
    life_delta = me.life - opp.life
    cards_delta = len(me.hand) - len(opp.hand)
    my_mana_pool = getattr(me, "mana_pool", {}) or {}
    opp_mana_pool = getattr(opp, "mana_pool", {}) or {}
    mana_delta = sum(my_mana_pool.values()) - sum(opp_mana_pool.values())
    return (
        life_delta * 1.6
        + cards_delta * 0.9
        + (my_battlefield - opp_battlefield) * 0.95
        + mana_delta * 0.15
        + evaluate_inevitability(state, player_id) * 0.7
    )


def repeatable_mana_value(state, card_id: str, *, surface_card=None) -> float:
    """Public-board resource retention, distinct from current payment readiness."""
    from rules_engine.mana import repeatable_nonland_mana_outputs
    card = surface_card if surface_card is not None else state.cards[card_id]
    outputs = repeatable_nonland_mana_outputs(card, state=state)
    controller = getattr(card, "controller", None)
    if not outputs or controller not in state.players:
        return 0.0
    lands = sum("Land" in state.cards[cid].types
                for cid in state.players[controller].battlefield)
    return max(outputs.values()) * (2.0 if lands < 4 else 0.75)


def choose_damage_trigger_target(state: MatchState, controller: int, amount: int, options: list[dict]) -> dict:
    opponent = 3 - controller

    def score(option: dict) -> tuple[float, str]:
        player_id = option.get("target_player")
        if player_id is not None:
            if player_id != opponent:
                return (-1000.0, str(player_id))
            return (1000.0 if state.players[opponent].life <= amount else amount * 1.6, str(player_id))

        card_id = option["target_card_id"]
        card = state.cards[card_id]
        if card.controller != opponent:
            return (-1000.0, card_id)
        keywords = {str(keyword).lower() for keyword in effective_keywords(state, card_id)}
        if "Creature" in card.types:
            remaining = effective_toughness(state, card_id) - int(card.counters.get("__damage_marked", 0))
            if remaining <= amount and "indestructible" not in keywords:
                return (_creature_value(state, card_id), card_id)
        if "Planeswalker" in card.types and card.loyalty is not None:
            return (6.0 if card.loyalty <= amount else 0.5 * amount, card_id)
        return (0.0, card_id)

    return max(options, key=score)


def evaluate_inevitability(state: MatchState, player_id: int) -> float:
    me = state.players[player_id]
    opp_id = 1 if player_id == 2 else 2
    opp = state.players[opp_id]
    me_library = getattr(me, "library", []) or []
    me_hand = getattr(me, "hand", []) or []
    me_graveyard = getattr(me, "graveyard", []) or []
    opp_library = getattr(opp, "library", []) or []
    opp_hand = getattr(opp, "hand", []) or []
    opp_graveyard = getattr(opp, "graveyard", []) or []
    me_long = len(me_library) + len(me_hand) + len(me_graveyard)
    opp_long = len(opp_library) + len(opp_hand) + len(opp_graveyard)
    pw_delta = _planeswalker_count(state, player_id) - _planeswalker_count(state, opp_id)
    return (me_long - opp_long) * 0.08 + pw_delta * 1.6


def _planeswalker_count(state: MatchState, player_id: int) -> int:
    return sum(
        1
        for cid in (getattr(state.players[player_id], "battlefield", []) or [])
        if cid in state.cards and "Planeswalker" in (getattr(state.cards[cid], "types", []) or [])
    )


def _board_value(state: MatchState, player_id: int) -> float:
    total = 0.0
    for cid in getattr(state.players[player_id], "battlefield", []) or []:
        card = state.cards.get(cid)
        if not card:
            continue
        surface = _active_card_surface(card)
        types = set(getattr(card, "types", []) or [])
        types.update(_types_from_type_line(surface["type_line"]))
        if "Creature" in types:
            total += _creature_value(state, cid)
            continue
        total += _noncreature_value(card, surface) + repeatable_mana_value(state, cid)
        if "Land" in types and not getattr(card, "tapped", False):
            total += 0.12
    return total


def _creature_value(state: MatchState, card_id: str) -> float:
    card = state.cards[card_id]
    power = max(0, int(effective_power(state, card_id) or 0))
    toughness = max(0, int(effective_toughness(state, card_id) or 0))
    kws = {str(k).lower() for k in (effective_keywords(state, card_id) or [])}
    value = (power * 1.35 + toughness * 0.55 + recurring_engine_value(state, card_id)
             + repeatable_mana_value(state, card_id))
    value += 0.25 if not getattr(card, "tapped", False) else -0.1
    if "flying" in kws:
        value += 1.1
    if "trample" in kws:
        value += 0.7
    if "menace" in kws:
        value += 0.6
    if "lifelink" in kws:
        value += 0.9
    if "deathtouch" in kws:
        value += 0.8
    if "vigilance" in kws:
        value += 0.35
    if "haste" in kws:
        value += 0.45
    if "indestructible" in kws:
        value += 0.75
    if "hexproof" in kws or "shroud" in kws:
        value += 0.45
    if "ward" in kws:
        value += 0.25
    if "defender" in kws:
        value -= 0.55
    return value


def _noncreature_value(card, surface: dict | None = None) -> float:
    surface = surface or _active_card_surface(card)
    types = set(getattr(card, "types", []) or [])
    types.update(_types_from_type_line(surface["type_line"]))
    text = surface['oracle_text'].lower()
    value = 0.0
    if "Planeswalker" in types:
        value += 7.0
        value += max(0, int(getattr(card, "loyalty", 0) or 0)) * 0.35
    if "Artifact" in types:
        value += 2.0
    if "Enchantment" in types:
        value += 2.1
    if any(k in text for k in ["draw", "search your library", "return target"]):
        value += 1.2
    if any(
        k in text
        for k in [
            "whenever this creature attacks",
            "whenever a creature attacks",
            "whenever you attack",
            "whenever this creature blocks",
            "whenever a creature blocks",
            "whenever this creature deals combat damage",
            "whenever a creature you control deals combat damage",
            "whenever a permanent enters the battlefield",
            "whenever another permanent enters the battlefield",
            "whenever a creature enters the battlefield",
            "whenever a token enters the battlefield",
            "whenever a creature dies",
            "whenever a permanent dies",
            "whenever you sacrifice a",
            "whenever you discard a card",
            "whenever an opponent discards",
        ]
    ):
        value += 1.1
    if any(k in text for k in ["creatures you control get", "+1/+1", "anthem"]):
        value += 2.0
    if any(k in text for k in ["counter target", "destroy target", "exile target"]):
        value += 1.1
    if any(k in text for k in ["add {", "treasure", "create token", "token"]):
        value += 1.0
    if any(k in text for k in ["lifelink", "gain life", "can't lose life"]):
        value += 0.7
    return value


def _active_card_surface(card) -> dict[str, str]:
    faces = list(getattr(card, "card_faces", []) or [])
    index = getattr(card, "selected_face_index", None)
    face = {}
    if faces:
        try:
            if index is not None:
                face = faces[int(index)]
            else:
                face = faces[0]
        except Exception:
            face = faces[0]
    return {
        "name": str((face or {}).get("name") or getattr(card, "name", "") or ""),
        "type_line": str((face or {}).get("type_line") or getattr(card, "type_line", "") or ""),
        "oracle_text": str((face or {}).get("oracle_text") or getattr(card, "oracle_text", "") or ""),
    }


def _types_from_type_line(type_line: str) -> list[str]:
    tl = (type_line or "").strip()
    if not tl:
        return []
    parts = tl.split("—", 1)
    primary = parts[0]
    if "-" in primary:
        primary = primary.split("-", 1)[0]
    return [part.strip() for part in primary.split() if part.strip()]
