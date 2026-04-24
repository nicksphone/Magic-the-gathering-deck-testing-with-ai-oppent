from __future__ import annotations

import re
from typing import Any

from game_state.state import CardInstance, MatchState


DAMAGE_RE = re.compile(r"deals?\s+(\d+)\s+damage")
X_DAMAGE_RE = re.compile(r"deals?\s+x\s+damage")
DRAW_RE = re.compile(r"draw\s+(a|\d+)\s+card")
X_DRAW_RE = re.compile(r"draw\s+x\s+card")
GAIN_RE = re.compile(r"gain\s+(\d+)\s+life")
TOKEN_PT_RE = re.compile(r"create[^.]*?(\d+)\/(\d+)")
CHOOSE_ONE_RE = re.compile(r"choose one\s*[—-]\s*(.+)", re.IGNORECASE | re.DOTALL)
CHOOSE_TWO_RE = re.compile(r"choose two", re.IGNORECASE)
DIVIDE_RE = re.compile(r"divide[^.]*damage[^.]*among[^.]*targets", re.IGNORECASE)
UP_TO_RE = re.compile(r"up to\s+(\d+)\s+target", re.IGNORECASE)


def infer_effect_from_oracle(
    state: MatchState,
    card: CardInstance,
    controller: int,
    action_targets: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    oracle = (card.oracle_text or "").lower()
    name = card.name.lower()
    action_targets = action_targets or {}
    mode_text = action_targets.get("mode_text")
    mode_texts = action_targets.get("mode_texts") or []
    x_value = int(action_targets.get("x_value", 0) or 0)
    if mode_text:
        oracle = mode_text.lower()
    elif mode_texts:
        oracle = " ; ".join(str(x).lower() for x in mode_texts)

    if "counter target spell" in oracle and state.stack:
        target_stack_id = action_targets.get("target_stack_id") or state.stack[-1].id
        return "counter_spell", {"target_stack_id": target_stack_id}

    damage_match = DAMAGE_RE.search(oracle)
    if damage_match:
        amount = int(damage_match.group(1))
        if DIVIDE_RE.search(oracle):
            distribution = action_targets.get("target_distribution", {})
            return "deal_damage_multi", {"target_distribution": distribution}
        target_player = action_targets.get("target_player")
        target_card_id = action_targets.get("target_card_id")
        if target_card_id:
            return "deal_damage", {"target_card_id": target_card_id, "amount": amount}
        if target_player is None:
            target_player = 1 if controller == 2 else 2
        return "deal_damage", {"target_player": target_player, "amount": amount}
    if X_DAMAGE_RE.search(oracle):
        amount = max(0, x_value)
        if DIVIDE_RE.search(oracle):
            distribution = action_targets.get("target_distribution", {})
            return "deal_damage_multi", {"target_distribution": distribution}
        target_player = action_targets.get("target_player")
        target_card_id = action_targets.get("target_card_id")
        if target_card_id:
            return "deal_damage", {"target_card_id": target_card_id, "amount": amount}
        if target_player is None:
            target_player = 1 if controller == 2 else 2
        return "deal_damage", {"target_player": target_player, "amount": amount}

    draw_match = DRAW_RE.search(oracle)
    if draw_match:
        raw = draw_match.group(1)
        amount = 1 if raw == "a" else int(raw)
        return "draw_cards", {"amount": amount}
    if X_DRAW_RE.search(oracle):
        return "draw_cards", {"amount": max(0, x_value)}

    gain_match = GAIN_RE.search(oracle)
    if gain_match:
        return "gain_life", {"amount": int(gain_match.group(1))}

    if "destroy target" in oracle:
        target = action_targets.get("target_card_id")
        if target:
            return "destroy_permanent", {"target_card_id": target}
        opp = 1 if controller == 2 else 2
        target = _first_creature(state, opp)
        if target:
            return "destroy_permanent", {"target_card_id": target}

    if "exile target" in oracle:
        target = action_targets.get("target_card_id")
        if target:
            return "exile", {"target_card_id": target}
        opp = 1 if controller == 2 else 2
        target = _first_creature(state, opp)
        if target:
            return "exile", {"target_card_id": target}

    if "return target" in oracle and "graveyard" in oracle and "hand" in oracle:
        return "return_from_graveyard", {}

    token_match = TOKEN_PT_RE.search(oracle)
    if "token" in oracle and token_match:
        return "create_token", {"name": "Token", "power": int(token_match.group(1)), "toughness": int(token_match.group(2))}

    if any(k in name for k in ["bolt", "spike", "shock", "skewer"]):
        opp = action_targets.get("target_player", 1 if controller == 2 else 2)
        return "deal_damage", {"target_player": opp, "amount": 3}
    if any(k in name for k in ["consider", "deluge"]):
        return "draw_cards", {"amount": 1}
    if "counterspell" in name and state.stack:
        return "counter_spell", {"target_stack_id": state.stack[-1].id}

    return "gain_life", {"amount": 0}


def inspect_target_hints(state: MatchState, card: CardInstance, controller: int) -> dict[str, Any]:
    oracle = (card.oracle_text or "").lower()
    hints: dict[str, Any] = {}
    opponent = 1 if controller == 2 else 2
    modes = _extract_modes(oracle)
    if modes:
        hints["modes"] = modes
    if CHOOSE_TWO_RE.search(oracle):
        hints["choose_two_modes"] = True
    if "x" in (card.mana_cost or "").lower() or " x " in oracle:
        hints["requires_x_value"] = True
    up_to_match = UP_TO_RE.search(oracle)
    if up_to_match:
        hints["up_to_target_count"] = int(up_to_match.group(1))

    if "counter target spell" in oracle:
        hints["stack_targets"] = [{"id": x.id, "label": x.label} for x in state.stack]
    if "target creature" in oracle or "destroy target" in oracle or "exile target" in oracle:
        hints["creature_targets"] = [
            {"id": cid, "name": state.cards[cid].name}
            for cid in state.players[opponent].battlefield
            if "Creature" in state.cards[cid].types
        ]
    if "any target" in oracle or "target player" in oracle or "deals" in oracle:
        hints["player_targets"] = [
            {"id": 1, "name": state.players[1].name},
            {"id": 2, "name": state.players[2].name},
        ]
    if DIVIDE_RE.search(oracle):
        hints["supports_divide"] = True
    return hints


def _first_creature(state: MatchState, player_id: int) -> str | None:
    for cid in state.players[player_id].battlefield:
        if "Creature" in state.cards[cid].types:
            return cid
    return None


def _extract_modes(oracle: str) -> list[str]:
    match = CHOOSE_ONE_RE.search(oracle)
    if not match:
        return []
    body = match.group(1).strip()
    body = body.replace("\n", " ")
    candidates = [x.strip(" ;:.") for x in body.split(";")]
    return [c for c in candidates if c]
