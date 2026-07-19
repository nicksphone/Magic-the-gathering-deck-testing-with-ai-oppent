from __future__ import annotations

import random

from game_state.state import CardInstance, MatchState, PlayerState, StackItem, Step, TURN_STEPS, Zone


def _tupleize(value):
    if isinstance(value, list):
        return tuple(_tupleize(item) for item in value)
    return value


def serialize_match_snapshot(state: MatchState) -> dict:
    """Serialize all mutable rules state needed to resume a match."""
    return {
        "id": state.id,
        "turn": state.turn,
        "active_player": state.active_player,
        "priority_player": state.priority_player,
        "step": state.step.value,
        "passed_priority": sorted(state.passed_priority),
        "attackers": list(state.attackers),
        "attack_targets": dict(state.attack_targets),
        "blocks": {key: list(value) for key, value in state.blocks.items()},
        "attackers_declared": state.attackers_declared,
        "blockers_declared": state.blockers_declared,
        "winner": state.winner,
        "best_of": state.best_of,
        "score": {str(key): value for key, value in state.score.items()},
        "pregame_pending": state.pregame_pending,
        "mulligan_count": {str(key): value for key, value in state.mulligan_count.items()},
        "kept_hands": sorted(state.kept_hands),
        "loyalty_activated_this_turn": sorted(state.loyalty_activated_this_turn),
        "trigger_once_seen_this_turn": sorted(state.trigger_once_seen_this_turn),
        "priority_stops": {
            str(key): sorted(step.value for step in value)
            for key, value in state.priority_stops.items()
        },
        "log": list(state.log),
        "next_static_order": state.next_static_order,
        "day_night": state.day_night,
        "spells_cast_this_turn": {str(key): value for key, value in state.spells_cast_this_turn.items()},
        "spells_cast_last_turn": state.spells_cast_last_turn,
        "temporary_control_changes": {
            str(cid): {str(key): int(value) for key, value in data.items()}
            for cid, data in state.temporary_control_changes.items()
        },
        "turn_cant_gain_life": sorted(state.turn_cant_gain_life),
        "turn_damage_cant_be_prevented": state.turn_damage_cant_be_prevented,
        "rng_state": state.rng.getstate(),
        "players": {
            str(pid): {
                "id": player.id,
                "name": player.name,
                "life": player.life,
                "library": list(player.library),
                "hand": list(player.hand),
                "battlefield": list(player.battlefield),
                "graveyard": list(player.graveyard),
                "exile": list(player.exile),
                "exile_play_until": dict(player.exile_play_until),
                "mana_pool": dict(player.mana_pool),
                "prevent_damage_shield": player.prevent_damage_shield,
                "max_land_plays_this_turn": player.max_land_plays_this_turn,
                "lands_played_this_turn": player.lands_played_this_turn,
                "last_land_play_turn": player.last_land_play_turn,
                "land_plays_recorded_on_turn": player.land_plays_recorded_on_turn,
            }
            for pid, player in state.players.items()
        },
        "cards": {
            cid: {
                "id": card.id,
                "name": card.name,
                "owner": card.owner,
                "controller": card.controller,
                "zone": card.zone.value,
                "types": list(card.types),
                "mana_cost": card.mana_cost,
                "power": card.power,
                "toughness": card.toughness,
                "loyalty": card.loyalty,
                "tapped": card.tapped,
                "summoning_sick": card.summoning_sick,
                "entered_turn": card.entered_turn,
                "counters": dict(card.counters),
                "keywords": list(card.keywords),
                "oracle_text": card.oracle_text,
                "type_line": card.type_line,
                "image_uri": card.image_uri,
                "attached_to": card.attached_to,
                "static_order": card.static_order,
                "instance_order": card.instance_order,
                "card_faces": list(card.card_faces),
                "selected_face_index": card.selected_face_index,
            }
            for cid, card in state.cards.items()
        },
        "stack": [
            {
                "id": item.id,
                "source_card_id": item.source_card_id,
                "controller": item.controller,
                "label": item.label,
                "effect_key": item.effect_key,
                "payload": item.payload,
                "targets": list(item.targets),
            }
            for item in state.stack
        ],
    }


def deserialize_match_snapshot(payload: dict) -> MatchState:
    players = {}
    for raw in payload["players"].values():
        player = PlayerState(id=int(raw["id"]), name=str(raw["name"]), life=int(raw["life"]))
        for key in ("library", "hand", "battlefield", "graveyard", "exile"):
            setattr(player, key, list(raw.get(key, [])))
        player.exile_play_until = {str(key): int(value) for key, value in raw.get("exile_play_until", {}).items()}
        player.mana_pool = {str(key): int(value) for key, value in raw.get("mana_pool", {}).items()}
        for key in (
            "prevent_damage_shield", "max_land_plays_this_turn", "lands_played_this_turn",
            "last_land_play_turn", "land_plays_recorded_on_turn",
        ):
            setattr(player, key, int(raw.get(key, getattr(player, key))))
        players[player.id] = player

    cards = {}
    for cid, raw in payload["cards"].items():
        cards[cid] = CardInstance(
            id=str(raw["id"]), name=str(raw["name"]), owner=int(raw["owner"]),
            controller=int(raw["controller"]), zone=Zone(raw["zone"]),
            types=list(raw.get("types", [])), mana_cost=str(raw.get("mana_cost", "")),
            power=raw.get("power"), toughness=raw.get("toughness"), loyalty=raw.get("loyalty"),
            tapped=bool(raw.get("tapped", False)), summoning_sick=bool(raw.get("summoning_sick", True)),
            entered_turn=int(raw.get("entered_turn", 0)), counters=dict(raw.get("counters", {})),
            keywords=list(raw.get("keywords", [])), oracle_text=str(raw.get("oracle_text", "")),
            type_line=str(raw.get("type_line", "")), image_uri=raw.get("image_uri"),
            attached_to=raw.get("attached_to"), static_order=int(raw.get("static_order", 0)),
            instance_order=int(raw.get("instance_order", 0)), card_faces=list(raw.get("card_faces", [])),
            selected_face_index=raw.get("selected_face_index"),
        )

    state = MatchState(
        id=str(payload["id"]), players=players, cards=cards,
        stack=[StackItem(
            id=str(item["id"]), source_card_id=str(item["source_card_id"]),
            controller=int(item["controller"]), label=str(item["label"]),
            effect_key=str(item["effect_key"]), payload=dict(item.get("payload", {})),
            targets=list(item.get("targets", [])),
        ) for item in payload.get("stack", [])],
    )
    for key in ("turn", "active_player", "priority_player", "winner", "best_of", "next_static_order"):
        if payload.get(key) is not None:
            setattr(state, key, int(payload[key]) if key != "winner" else payload[key])
    state.step = Step(payload.get("step", Step.UNTAP.value))
    state.passed_priority = {int(value) for value in payload.get("passed_priority", [])}
    state.attackers = list(payload.get("attackers", []))
    state.attack_targets = dict(payload.get("attack_targets", {}))
    state.blocks = {key: list(value) for key, value in payload.get("blocks", {}).items()}
    state.attackers_declared = bool(payload.get("attackers_declared", False))
    state.blockers_declared = bool(payload.get("blockers_declared", False))
    state.score = {int(key): int(value) for key, value in payload.get("score", {"1": 0, "2": 0}).items()}
    state.pregame_pending = bool(payload.get("pregame_pending", True))
    state.mulligan_count = {int(key): int(value) for key, value in payload.get("mulligan_count", {}).items()}
    state.kept_hands = {int(value) for value in payload.get("kept_hands", [])}
    state.loyalty_activated_this_turn = set(payload.get("loyalty_activated_this_turn", []))
    state.trigger_once_seen_this_turn = set(payload.get("trigger_once_seen_this_turn", []))
    state.priority_stops = {
        int(key): {Step(value) for value in values}
        for key, values in payload.get("priority_stops", {}).items()
    }
    state.log = list(payload.get("log", []))
    state.next_static_order = int(payload.get("next_static_order", 1))
    state.day_night = str(payload.get("day_night", "none") or "none")
    state.spells_cast_this_turn = {
        int(key): int(value) for key, value in payload.get("spells_cast_this_turn", {"1": 0, "2": 0}).items()
    }
    state.spells_cast_last_turn = int(payload.get("spells_cast_last_turn", 0) or 0)
    state.temporary_control_changes = {
        str(cid): {str(key): int(value) for key, value in data.items()}
        for cid, data in payload.get("temporary_control_changes", {}).items()
    }
    state.turn_cant_gain_life = {int(value) for value in payload.get("turn_cant_gain_life", [])}
    state.turn_damage_cant_be_prevented = bool(payload.get("turn_damage_cant_be_prevented", False))
    state.rng.setstate(_tupleize(payload["rng_state"]))
    return state


def serialize_match(state: MatchState) -> dict:
    step_order = [x.value for x in TURN_STEPS]

    def _sort_steps(steps: set) -> list[str]:
        vals = [s.value for s in steps]
        return sorted(vals, key=lambda x: step_order.index(x) if x in step_order else 999)

    return {
        "id": state.id,
        "turn": state.turn,
        "active_player": state.active_player,
        "priority_player": state.priority_player,
        "step": state.step.value,
        "winner": state.winner,
        "score": state.score,
        "pregame_pending": state.pregame_pending,
        "mulligan_count": state.mulligan_count,
        "kept_hands": sorted(list(state.kept_hands)),
        "day_night": state.day_night,
        "spells_cast_this_turn": state.spells_cast_this_turn,
        "turn_cant_gain_life": sorted(state.turn_cant_gain_life),
        "turn_damage_cant_be_prevented": state.turn_damage_cant_be_prevented,
        "priority_stops": {
            str(pid): _sort_steps(steps)
            for pid, steps in state.priority_stops.items()
        },
        "players": {
            pid: {
                "id": p.id,
                "name": p.name,
                "life": p.life,
                "library_count": len(p.library),
                "hand_count": len(p.hand),
                "battlefield": [
                    {
                        "id": cid,
                        "name": state.cards[cid].name,
                        "tapped": state.cards[cid].tapped,
                        "summoning_sick": state.cards[cid].summoning_sick,
                        "power": state.cards[cid].power,
                        "toughness": state.cards[cid].toughness,
                        "loyalty": state.cards[cid].loyalty,
                        "mana_cost": state.cards[cid].mana_cost,
                        "oracle_text": state.cards[cid].oracle_text,
                        "image_uri": state.cards[cid].image_uri,
                        "types": state.cards[cid].types,
                    }
                    for cid in p.battlefield
                ],
                "hand": [
                    {
                        "id": cid,
                        "name": state.cards[cid].name,
                        "mana_cost": state.cards[cid].mana_cost,
                        "oracle_text": state.cards[cid].oracle_text,
                        "image_uri": state.cards[cid].image_uri,
                        "types": state.cards[cid].types,
                    }
                    for cid in p.hand
                ],
                "graveyard_count": len(p.graveyard),
                "exile_count": len(p.exile),
                "mana_pool": p.mana_pool,
            }
            for pid, p in state.players.items()
        },
        "stack": [
            {
                "id": item.id,
                "label": item.label,
                "controller": item.controller,
                "effect_key": item.effect_key,
                "targets": item.targets,
            }
            for item in state.stack
        ],
        "attackers": state.attackers,
        "attack_targets": state.attack_targets,
        "blocks": state.blocks,
        "log": state.log[-120:],
    }
