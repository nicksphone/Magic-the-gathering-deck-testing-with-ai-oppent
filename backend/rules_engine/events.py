from __future__ import annotations

import uuid
import re
from typing import Any

from game_state.state import MatchState, StackItem


def emit_event(state: MatchState, event: str, payload: dict[str, Any]) -> None:
    triggers = _collect_triggers(state, event, payload)
    if not triggers:
        return
    ordered = _order_apnap(state, triggers)
    for trig in ordered:
        state.stack.append(
            StackItem(
                id=str(uuid.uuid4()),
                source_card_id=trig["source_card_id"],
                controller=trig["controller"],
                label=trig["label"],
                effect_key=trig["effect_key"],
                payload=trig["payload"],
            )
        )
    state.log.append(f"{len(ordered)} triggered ability(s) added to stack ({event}).")


def _collect_triggers(state: MatchState, event: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pid, pstate in state.players.items():
        for cid in list(pstate.battlefield):
            card = state.cards[cid]
            oracle = (card.oracle_text or "").lower()
            once_each_turn = "only once each turn" in oracle or "this ability triggers only once each turn" in oracle
            trigger_key = f"{cid}:{event}"
            if once_each_turn and trigger_key in state.trigger_once_seen_this_turn:
                continue

            if event == "draw_card" and payload.get("player_id") == card.controller and "whenever you draw a card" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "draw_card" and payload.get("player_id") != card.controller and "whenever an opponent draws a card" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "life_gain" and payload.get("player_id") == card.controller and "whenever you gain life" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "creature_dies" and ("whenever a creature dies" in oracle or "whenever another creature dies" in oracle):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "enters_battlefield" and payload.get("card_id") == cid and f"when {card.name.lower()} enters the battlefield" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} ETB", event=event, payload=payload))
            elif event == "begin_step":
                step = str(payload.get("step", "")).lower()
                active_player = int(payload.get("active_player", 0) or 0)
                if step == "upkeep":
                    if "at the beginning of each upkeep" in oracle or "at the beginning of upkeep" in oracle:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} upkeep trigger",
                                event=event,
                                payload=payload,
                            )
                        )
                    elif "at the beginning of your upkeep" in oracle and card.controller == active_player:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} upkeep trigger",
                                event=event,
                                payload=payload,
                            )
                        )
                elif step == "end_step":
                    # Delayed sacrifice marker support for token effects.
                    if card.counters.get("__sac_next_end_step", 0) > 0 and card.controller == active_player:
                        out.append(
                            {
                                "source_card_id": cid,
                                "controller": card.controller,
                                "label": f"{card.name} delayed sacrifice",
                                "effect_key": "sacrifice",
                                "payload": {"target_card_id": cid},
                            }
                        )
                    if "at the beginning of each end step" in oracle or "at the beginning of end step" in oracle:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} end-step trigger",
                                event=event,
                                payload=payload,
                            )
                        )
                    elif "at the beginning of your end step" in oracle and card.controller == active_player:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} end-step trigger",
                                event=event,
                                payload=payload,
                            )
                        )
            if once_each_turn:
                state.trigger_once_seen_this_turn.add(trigger_key)
    return out


def _order_apnap(state: MatchState, triggers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active = state.active_player
    non_active = 1 if active == 2 else 2
    first = [t for t in triggers if t["controller"] == active]
    second = [t for t in triggers if t["controller"] == non_active]
    return first + second


def _trigger_from_oracle(
    state: MatchState,
    source_card_id: str,
    controller: int,
    oracle: str,
    default_label: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    opponent = 1 if controller == 2 else 2
    gain_amount = _first_number(oracle, r"gain (\d+) life")
    lose_amount = _first_number(oracle, r"lose (\d+) life")
    if event == "draw_card":
        drawn_by = int(payload.get("player_id", 0) or 0)
        if drawn_by == controller and "whenever you draw a card" in oracle and gain_amount > 0:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "gain_life",
                "payload": _maybe_payload(oracle, {"target_player": controller, "amount": gain_amount}),
            }
        if drawn_by != controller and "whenever an opponent draws a card" in oracle and lose_amount > 0:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "lose_life",
                "payload": _maybe_payload(oracle, {"target_player": drawn_by, "amount": lose_amount}),
            }

    if "draw a card" in oracle:
        return {
            "source_card_id": source_card_id,
            "controller": controller,
            "label": default_label,
            "effect_key": "draw_cards",
            "payload": _maybe_payload(oracle, {"amount": 1}),
        }
    if "gain 1 life" in oracle or "gain life" in oracle:
        return {
            "source_card_id": source_card_id,
            "controller": controller,
            "label": default_label,
            "effect_key": "gain_life",
            "payload": _maybe_payload(oracle, {"amount": gain_amount or 1}),
        }
    if "deals 1 damage" in oracle or "deal 1 damage" in oracle:
        return {
            "source_card_id": source_card_id,
            "controller": controller,
            "label": default_label,
            "effect_key": "deal_damage",
            "payload": _maybe_payload(oracle, {"target_player": opponent, "amount": 1}),
        }
    return {
        "source_card_id": source_card_id,
        "controller": controller,
        "label": default_label,
        "effect_key": "gain_life",
        "payload": _maybe_payload(oracle, {"amount": 0}),
    }


def _first_number(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except Exception:
        return 0


def _maybe_payload(oracle: str, payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    low = (oracle or "").lower()
    if "you may" not in low:
        return out
    out["__may"] = True
    # Conservative default: skip optional effects that only lose life; otherwise choose yes.
    if "lose life" in low and "gain life" not in low and "draw" not in low:
        out["__may_choose"] = False
    else:
        out["__may_choose"] = True
    return out
