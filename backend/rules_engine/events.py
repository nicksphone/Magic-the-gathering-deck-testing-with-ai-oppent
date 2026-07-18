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
    for order_index, trig in enumerate(ordered):
        state.stack.append(
            StackItem(
                id=str(uuid.uuid4()),
                source_card_id=trig["source_card_id"],
                controller=trig["controller"],
                label=trig["label"],
                effect_key=trig["effect_key"],
                payload={**trig["payload"], "__trigger_order": order_index, "__trigger_event": event},
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
            elif event == "creature_dies" and _matches_creature_dies_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "permanent_dies" and _matches_permanent_dies_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "leaves_battlefield" and _matches_leaves_battlefield_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "day_night_changed" and _matches_day_night_trigger(oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "enters_battlefield" and _matches_enters_battlefield_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} ETB", event=event, payload=payload))
            elif event == "sacrifice" and _matches_sacrifice_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} sacrifice trigger", event=event, payload=payload))
            elif event == "discard" and _matches_discard_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} discard trigger", event=event, payload=payload))
            elif event == "cycle" and _matches_cycle_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} cycling trigger", event=event, payload=payload))
            elif event == "combat_damage_dealt" and _matches_combat_damage_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} combat damage trigger", event=event, payload=payload))
            elif event == "attack_declared" and _matches_attack_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} attack trigger", event=event, payload=payload))
            elif event == "block_declared" and _matches_block_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} block trigger", event=event, payload=payload))
            elif event in {"spell_cast", "spell_copy"}:
                cast_controller = int(payload.get("controller", 0) or 0)
                source_card_id = str(payload.get("source_card_id", "") or "")
                source_card = state.cards.get(source_card_id) if source_card_id else None
                source_types = {t.lower() for t in (getattr(source_card, "types", []) or [])}
                if cast_controller == card.controller and "whenever you cast a spell" in oracle:
                    out.append(
                        _trigger_from_oracle(
                            state,
                            cid,
                            card.controller,
                            oracle,
                            default_label=f"{card.name} cast trigger",
                            event=event,
                            payload=payload,
                        )
                    )
                elif cast_controller == card.controller and (
                    ("whenever you cast an instant spell" in oracle and "instant" in source_types)
                    or ("whenever you cast a sorcery spell" in oracle and "sorcery" in source_types)
                    or ("whenever you cast an instant or sorcery spell" in oracle and ("instant" in source_types or "sorcery" in source_types))
                ):
                    out.append(
                        _trigger_from_oracle(
                            state,
                            cid,
                            card.controller,
                            oracle,
                            default_label=f"{card.name} cast trigger",
                            event=event,
                            payload=payload,
                        )
                    )
                elif cast_controller == card.controller and source_card and "creature" not in source_types and (
                    "prowess" in oracle
                    or "magecraft" in oracle
                    or "whenever you cast a noncreature spell" in oracle
                    or "whenever you cast a non-creature spell" in oracle
                    or "whenever you cast or copy an instant or sorcery spell" in oracle
                    or "whenever you cast or copy a noncreature spell" in oracle
                    or "whenever you cast or copy a non-creature spell" in oracle
                    or "gets +1/+1 until end of turn" in oracle
                ):
                    ability = _trigger_from_oracle(
                        state,
                        cid,
                        card.controller,
                        oracle,
                        default_label=f"{card.name} spell trigger",
                        event=event,
                        payload=payload,
                    )
                    if ability["effect_key"] != "gain_life" or ability["payload"].get("amount") != 0:
                        out.append(ability)
                    elif "prowess" in oracle or "magecraft" in oracle or "gets +1/+1 until end of turn" in oracle:
                        out.append(
                            {
                                "source_card_id": cid,
                                "controller": card.controller,
                                "label": f"{card.name} spell trigger",
                                "effect_key": "temporary_pt_buff",
                                "payload": {"target_card_id": cid, "power": 1, "toughness": 1},
                            }
                        )
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
    out.sort(key=lambda trig: (0 if trig["controller"] == state.active_player else 1, str(trig["source_card_id"]), str(trig["label"])))
    return out


def _matches_creature_dies_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    dead_id = payload.get("card_id")
    dead_card = state.cards.get(dead_id) if dead_id in state.cards else None
    dead_types = set(getattr(dead_card, "types", []) or []) if dead_card else set()
    if "whenever another creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and dead_id != card.id and "Creature" in dead_types
    if "whenever a creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types
    if "whenever another nontoken creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and dead_id != card.id and "Creature" in dead_types and "Token" not in dead_types
    if "whenever a nontoken creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types and "Token" not in dead_types
    if "whenever one or more nontoken creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types and "Token" not in dead_types
    if "whenever one or more creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types
    if "whenever a creature dies" in oracle or "whenever another creature dies" in oracle:
        return True
    if "whenever one or more creatures die" in oracle:
        return True
    if "whenever a creature you control dies" in oracle or "whenever another creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller
    if "whenever one or more creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller
    if "whenever a nontoken creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "token" not in {str(t).lower() for t in (getattr(dead_card, "types", []) or [])}
    if "whenever one or more nontoken creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "token" not in {str(t).lower() for t in (getattr(dead_card, "types", []) or [])}
    return False


def _matches_permanent_dies_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    dead_id = payload.get("card_id")
    dead_card = state.cards.get(dead_id) if dead_id in state.cards else None
    if not dead_card:
        return False
    dead_types = set(getattr(dead_card, "types", []) or [])
    if "whenever another permanent you control dies" in oracle:
        return dead_card.controller == card.controller and dead_id != card.id
    if "whenever a permanent you control dies" in oracle:
        return dead_card.controller == card.controller
    if "whenever another nontoken permanent you control dies" in oracle:
        return dead_card.controller == card.controller and dead_id != card.id and "Token" not in dead_types
    if "whenever a nontoken permanent you control dies" in oracle:
        return dead_card.controller == card.controller and "Token" not in dead_types
    if "whenever one or more nontoken permanents you control die" in oracle:
        return dead_card.controller == card.controller and "Token" not in dead_types
    if "whenever one or more permanents you control die" in oracle:
        return dead_card.controller == card.controller
    if "whenever a permanent dies" in oracle or "whenever another permanent dies" in oracle:
        return True
    if "whenever one or more permanents die" in oracle:
        return True
    if "whenever a nontoken permanent you control dies" in oracle:
        return dead_card.controller == card.controller and "token" not in {str(t).lower() for t in (getattr(dead_card, "types", []) or [])}
    if "whenever one or more nontoken permanents you control die" in oracle:
        return dead_card.controller == card.controller and "token" not in {str(t).lower() for t in (getattr(dead_card, "types", []) or [])}
    if "whenever an artifact dies" in oracle or "whenever another artifact dies" in oracle:
        return "Artifact" in (getattr(dead_card, "types", []) or [])
    if "whenever an artifact you control dies" in oracle or "whenever another artifact you control dies" in oracle:
        return dead_card.controller == card.controller and "Artifact" in (getattr(dead_card, "types", []) or [])
    if "whenever one or more artifacts you control die" in oracle:
        return dead_card.controller == card.controller and "Artifact" in (getattr(dead_card, "types", []) or [])
    if "whenever an enchantment dies" in oracle or "whenever another enchantment dies" in oracle:
        return "Enchantment" in (getattr(dead_card, "types", []) or [])
    if "whenever an enchantment you control dies" in oracle or "whenever another enchantment you control dies" in oracle:
        return dead_card.controller == card.controller and "Enchantment" in (getattr(dead_card, "types", []) or [])
    if "whenever one or more enchantments you control die" in oracle:
        return dead_card.controller == card.controller and "Enchantment" in (getattr(dead_card, "types", []) or [])
    if "whenever an artifact or enchantment dies" in oracle or "whenever another artifact or enchantment dies" in oracle:
        return _has_artifact_or_enchantment_type(dead_card)
    if "whenever an artifact or enchantment you control dies" in oracle or "whenever another artifact or enchantment you control dies" in oracle:
        return dead_card.controller == card.controller and _has_artifact_or_enchantment_type(dead_card)
    if "whenever one or more artifacts or enchantments you control die" in oracle:
        return dead_card.controller == card.controller and _has_artifact_or_enchantment_type(dead_card)
    return False


def _matches_leaves_battlefield_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    leaving_id = payload.get("card_id")
    leaving = state.cards.get(leaving_id) if leaving_id else None
    if leaving is None:
        return False
    leaving_types = {str(value).lower() for value in (getattr(leaving, "types", []) or [])}
    controlled = leaving.controller == card.controller
    other = leaving_id != card.id
    if "whenever another creature you control leaves the battlefield" in oracle:
        return controlled and other and "creature" in leaving_types
    if "whenever a creature you control leaves the battlefield" in oracle:
        return controlled and "creature" in leaving_types
    if "whenever another permanent you control leaves the battlefield" in oracle:
        return controlled and other
    if "whenever a permanent you control leaves the battlefield" in oracle:
        return controlled
    if "whenever another artifact you control leaves the battlefield" in oracle:
        return controlled and other and "artifact" in leaving_types
    if "whenever an artifact you control leaves the battlefield" in oracle:
        return controlled and "artifact" in leaving_types
    if "whenever another enchantment you control leaves the battlefield" in oracle:
        return controlled and other and "enchantment" in leaving_types
    if "whenever an enchantment you control leaves the battlefield" in oracle:
        return controlled and "enchantment" in leaving_types
    if "whenever another permanent leaves the battlefield" in oracle:
        return other
    if "whenever a permanent leaves the battlefield" in oracle:
        return True
    if "whenever another creature leaves the battlefield" in oracle:
        return other and "creature" in leaving_types
    if "whenever a creature leaves the battlefield" in oracle:
        return "creature" in leaving_types
    return False


def _matches_day_night_trigger(oracle: str, payload: dict[str, Any]) -> bool:
    destination = str(payload.get("to", "") or "").lower()
    if destination not in {"day", "night"}:
        return False
    if destination == "day":
        return "becomes day" in oracle or "becomes day" in oracle.replace("the game ", "")
    return "becomes night" in oracle or "becomes night" in oracle.replace("the game ", "")


def _matches_enters_battlefield_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    entering_id = payload.get("card_id")
    if not entering_id or entering_id not in state.cards:
        return False
    entering_card = state.cards[entering_id]
    # Check controller-scoped clauses before their broader prefixes. Without
    # this ordering, "a creature enters" also matches "under your control".
    entering_types = set(getattr(entering_card, "types", []) or [])
    enters_for_controller = entering_card.controller == card.controller
    if "another creature enters the battlefield under your control" in oracle:
        return "Creature" in entering_types and enters_for_controller and entering_id != card.id
    if "a creature enters the battlefield under your control" in oracle:
        return "Creature" in entering_types and enters_for_controller
    if "another permanent enters the battlefield under your control" in oracle:
        return enters_for_controller and entering_id != card.id
    if "a permanent enters the battlefield under your control" in oracle:
        return enters_for_controller
    if "another artifact enters the battlefield under your control" in oracle:
        return "Artifact" in entering_types and enters_for_controller and entering_id != card.id
    if "an artifact enters the battlefield under your control" in oracle:
        return "Artifact" in entering_types and enters_for_controller
    if "another enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in entering_types and enters_for_controller and entering_id != card.id
    if "an enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in entering_types and enters_for_controller
    if "another artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and enters_for_controller and entering_id != card.id
    if "an artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and enters_for_controller
    if f"when {card.name.lower()} enters the battlefield" in oracle:
        return entering_id == card.id
    if "whenever another creature enters the battlefield" in oracle:
        return "Creature" in (getattr(entering_card, "types", []) or []) and entering_id != card.id
    if "whenever a creature enters the battlefield" in oracle:
        return "Creature" in (getattr(entering_card, "types", []) or [])
    if "whenever a creature enters the battlefield under your control" in oracle:
        return "Creature" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another permanent enters the battlefield" in oracle:
        return entering_id != card.id
    if "whenever a permanent enters the battlefield" in oracle:
        return True
    if "whenever a permanent enters the battlefield under your control" in oracle:
        return entering_card.controller == card.controller
    if "whenever another permanent enters the battlefield under your control" in oracle:
        return entering_card.controller == card.controller and entering_id != card.id
    if "whenever an artifact enters the battlefield" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or [])
    if "whenever an artifact enters the battlefield under your control" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another artifact enters the battlefield" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or []) and entering_id != card.id
    if "whenever another artifact enters the battlefield under your control" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever an enchantment enters the battlefield" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or [])
    if "whenever an enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another enchantment enters the battlefield" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or []) and entering_id != card.id
    if "whenever another enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever an artifact or enchantment enters the battlefield" in oracle:
        return _has_artifact_or_enchantment_type(entering_card)
    if "whenever an artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and entering_card.controller == card.controller
    if "whenever another artifact or enchantment enters the battlefield" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and entering_id != card.id
    if "whenever another artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever a token enters the battlefield" in oracle:
        return "Token" in {str(t).title() for t in (getattr(entering_card, "types", []) or [])}
    if "whenever a token enters the battlefield under your control" in oracle:
        return "Token" in {str(t).title() for t in (getattr(entering_card, "types", []) or [])} and entering_card.controller == card.controller
    if "landfall" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever a land enters the battlefield under your control" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another land enters the battlefield under your control" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever a land enters the battlefield" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or [])
    return False


def _has_artifact_or_enchantment_type(card) -> bool:
    types = {str(t).lower() for t in (getattr(card, "types", []) or [])}
    return "artifact" in types or "enchantment" in types


def _matches_sacrifice_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    sac_id = payload.get("card_id")
    if not sac_id or sac_id not in state.cards:
        return False
    sac_card = state.cards[sac_id]
    if "whenever you sacrifice a permanent" in oracle:
        return sac_card.controller == card.controller
    if "whenever a permanent you control is sacrificed" in oracle or "whenever a permanent you control is sacrificed" in oracle:
        return sac_card.controller == card.controller
    if "whenever you sacrifice a creature" in oracle:
        return sac_card.controller == card.controller and "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever a creature you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Artifact" in (getattr(sac_card, "types", []) or [])
    if "whenever an enchantment you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Enchantment" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact or enchantment you control is sacrificed" in oracle or "whenever an enchantment or artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and _has_artifact_or_enchantment_type(sac_card)
    if "whenever a creature is sacrificed" in oracle:
        return "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact is sacrificed" in oracle:
        return "Artifact" in (getattr(sac_card, "types", []) or [])
    if "whenever an enchantment is sacrificed" in oracle:
        return "Enchantment" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact or enchantment is sacrificed" in oracle or "whenever an enchantment or artifact is sacrificed" in oracle:
        return _has_artifact_or_enchantment_type(sac_card)
    if "whenever a permanent is sacrificed" in oracle:
        return True
    if "whenever another permanent you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id
    if "whenever another creature you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever another artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Artifact" in (getattr(sac_card, "types", []) or [])
    if "whenever another enchantment you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Enchantment" in (getattr(sac_card, "types", []) or [])
    if "whenever another artifact or enchantment you control is sacrificed" in oracle or "whenever another enchantment or artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and _has_artifact_or_enchantment_type(sac_card)
    return False


def _matches_discard_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    discarded_id = payload.get("card_id")
    if not discarded_id or discarded_id not in state.cards:
        return False
    discarded_card = state.cards[discarded_id]
    if "whenever you discard a card" in oracle:
        return discarded_card.controller == card.controller
    if "whenever you discard one or more cards" in oracle:
        return discarded_card.controller == card.controller
    if "whenever one or more cards are discarded" in oracle:
        return True
    if "whenever a card is discarded" in oracle:
        return True
    if "whenever a card you discard" in oracle:
        return discarded_card.controller == card.controller
    if "whenever an opponent discards a card" in oracle or "whenever an opponent discards one or more cards" in oracle:
        return discarded_card.controller != card.controller
    if "whenever one or more cards an opponent discards" in oracle:
        return discarded_card.controller != card.controller
    return False


def _matches_cycle_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    cycled_id = payload.get("card_id")
    cycled = state.cards.get(cycled_id) if cycled_id else None
    if cycled is None:
        return False
    cycling_controller = int(payload.get("controller", getattr(cycled, "controller", 0)) or 0)
    if "an opponent cycles" in oracle or "whenever an opponent cycles" in oracle:
        return cycling_controller != card.controller
    if "you cycle" not in oracle and "whenever you cycle" not in oracle:
        return False
    if cycling_controller != card.controller:
        return False
    if "you cycle a card" in oracle or "you cycle one or more cards" in oracle:
        return True
    # Named cycling triggers (for example, "When you cycle Shark Typhoon")
    # are matched against the actual cycled card name, not a card-specific ID.
    cycled_name = re.sub(r"\s+\([^)]*\)", "", str(cycled.name or "")).strip().lower()
    return bool(cycled_name and f"cycle {cycled_name}" in oracle)


def _matches_combat_damage_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    source_id = payload.get("source_card_id")
    if not source_id or source_id not in state.cards:
        return False
    source_card = state.cards[source_id]
    if source_card.controller != card.controller:
        return False
    if source_id != card.id and "whenever a creature you control deals combat damage" not in oracle and "whenever a creature you control deals combat damage to" not in oracle:
        # Only source-specific combat damage triggers are supported here unless the card explicitly references a creature you control.
        pass
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    if target_player is not None:
        if "deals combat damage to a player" in oracle or "deals combat damage to an opponent" in oracle:
            return True
        if "whenever this creature deals combat damage to a player" in oracle:
            return source_id == card.id
        if "whenever a creature you control deals combat damage to a player" in oracle:
            return "Creature" in (getattr(source_card, "types", []) or [])
    if target_card_id is not None:
        target_card = state.cards.get(target_card_id)
        if not target_card:
            return False
        if "deals combat damage to a creature" in oracle:
            return True
        if "whenever this creature deals combat damage to a creature" in oracle:
            return source_id == card.id
        if "whenever a creature you control deals combat damage to a creature" in oracle:
            return "Creature" in (getattr(source_card, "types", []) or [])
    return False


def _matches_attack_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    attacking_id = payload.get("card_id")
    if not attacking_id or attacking_id not in state.cards:
        return False
    attacking_card = state.cards[attacking_id]
    if attacking_card.controller != card.controller:
        return False
    if "whenever this creature attacks" in oracle:
        return attacking_id == card.id
    named_attack = re.search(r"whenever\s+(.+?)\s+attacks", oracle)
    if named_attack:
        named_source = re.sub(r"\s+\([^)]*\)", "", named_attack.group(1)).strip()
        if named_source not in {
            "this creature",
            "a creature",
            "another creature",
            "a creature you control",
            "another creature you control",
            "one or more creatures",
            "you",
        }:
            return attacking_id == card.id and named_source == (getattr(card, "name", "") or "").lower()
    if "whenever this creature or another creature attacks" in oracle:
        return True
    if "whenever a creature attacks" in oracle:
        return True
    if "whenever a creature you control attacks" in oracle:
        return attacking_card.controller == card.controller and "Creature" in (getattr(attacking_card, "types", []) or [])
    if "whenever you attack" in oracle:
        return attacking_card.controller == card.controller
    if "whenever one or more creatures attack" in oracle:
        return True
    return False


def _matches_block_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    blocker_id = payload.get("blocker_id")
    if not blocker_id or blocker_id not in state.cards:
        return False
    blocker_card = state.cards[blocker_id]
    if blocker_card.controller != card.controller:
        return False
    if "whenever this creature blocks" in oracle:
        return blocker_id == card.id
    if "whenever a creature blocks" in oracle:
        return True
    if "whenever a creature you control blocks" in oracle:
        return "Creature" in (getattr(blocker_card, "types", []) or [])
    if "whenever another creature you control blocks" in oracle:
        return blocker_card.controller == card.controller and blocker_id != card.id and "Creature" in (getattr(blocker_card, "types", []) or [])
    if "whenever this creature or another creature blocks" in oracle:
        return True
    return False


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
    source_card = state.cards.get(source_card_id)
    if source_card is not None:
        if event == "begin_step" and "transform" in oracle and "top card" in oracle and "instant or sorcery" in oracle:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "transform_if_top_matches",
                "payload": {"target_card_id": source_card_id, "required_types": ["Instant", "Sorcery"], "face_index": 1},
            }
        source_name = re.escape((source_card.name or "").lower())
        self_counter = re.search(
            rf"put\s+(a|an|one|two|three|four|five|\d+)\s+\+1/\+1\s+counters?\s+on\s+(?:this creature|this card|{source_name})",
            oracle,
        )
        if self_counter:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "add_counters",
                "payload": _maybe_payload(
                    oracle,
                    {
                        "target_card_id": source_card_id,
                        "counter": "+1/+1",
                        "amount": _number_token(self_counter.group(1)),
                    },
                ),
            }
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
    if any(
        token in oracle
        for token in (
            "create ",
            "destroy target",
            "exile target",
            "tap target",
            "untap target",
            "search your library",
            "discard",
            "sacrifice",
            "return target",
            "add ",
            "lose ",
            "loses ",
            "counter target",
            "cast target",
            "reveals the top card",
        )
    ):
        from rules_engine.ability_model import build_ability_spec

        source_card = state.cards.get(source_card_id)
        if source_card is not None:
            parser_payload = dict(payload)
            # Cycle triggers need the permanent that owns the trigger as the
            # token/effect source. Other event payloads already use
            # source_card_id for the spell or permanent that caused the event.
            if event == "cycle":
                parser_payload["source_card_id"] = source_card_id
            ability = build_ability_spec(state, source_card, controller, action_targets=parser_payload)
            effect_key, effect_payload = ability.effect.key, ability.effect.payload
            if effect_key and effect_key != "noop":
                return {
                    "source_card_id": source_card_id,
                    "controller": controller,
                    "label": default_label,
                    "effect_key": effect_key,
                    "payload": _maybe_payload(oracle, effect_payload),
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


def _number_token(token: str) -> int:
    values = {
        "a": 1,
        "an": 1,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }
    raw = str(token or "").lower()
    return values.get(raw, int(raw) if raw.isdigit() else 1)


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
