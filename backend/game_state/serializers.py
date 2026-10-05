from __future__ import annotations
from rules_engine.type_effects import effective_types

import random
from copy import deepcopy

from game_state.state import CardInstance, MatchState, PlayerState, StackItem, Step, TURN_STEPS, Zone
from rules_engine.player_counters import public_counters
from rules_engine.card_types import is_token_card


def _tupleize(value):
    if isinstance(value, list):
        return tuple(_tupleize(item) for item in value)
    return value


def serialize_card_view(state: MatchState, cid: str) -> dict:
    from rules_engine.suspend import suspended
    from rules_engine.land_types import effective_type_line
    from rules_engine.continuous import effective_combat_stats, effective_keyword_counts, attachment_effect_warnings
    from rules_engine.colors import card_color_symbols
    from rules_engine.mana import nonland_mana_outputs, land_mana_colors, land_mana_amount
    card = state.cards[cid]
    creature = "Creature" in effective_types(state, card)
    def numeric(value):
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    base_power, base_toughness = numeric(card.power), numeric(card.toughness)
    power, toughness = effective_combat_stats(state, cid) if creature else (base_power, base_toughness)
    if not creature and card.zone == Zone.BATTLEFIELD:
        power, toughness = None, None
    keyword_counts = effective_keyword_counts(state, cid)
    counters = dict(card.counters)
    if 'Saga' in card.type_line and '__lore' in counters:
        counters['lore'] = counters.pop('__lore')
    from rules_engine.mana_abilities import tap_only_outputs
    outputs = (tap_only_outputs(state, card, ignore_readiness=True)
               if "Land" in effective_types(state, card) else nonland_mana_outputs(state, cid, card, free_only=False)) if card.zone == Zone.BATTLEFIELD else {}
    return {
        "id": cid, "name": card.name, "tapped": card.tapped,
        "summoning_sick": card.summoning_sick,
        "power": power, "toughness": toughness,
        "base_power": base_power, "base_toughness": base_toughness,
        "printed_power": card.printed_power, "printed_toughness": card.printed_toughness,
        "keywords": list(keyword_counts), "keyword_counts": keyword_counts, "base_keywords": list(card.keywords),
        "counters": counters, "damage_marked": int(card.counters.get("__damage_marked", 0)),
        "loyalty": card.loyalty, "mana_cost": card.mana_cost,
        "oracle_text": card.oracle_text, "image_uri": card.image_uri,
        "types": list(effective_types(state, card)), "is_token": is_token_card(card), "type_line": effective_type_line(state, card),
        "base_type_line": card.type_line,
        "attached_to": card.attached_to,
        "bestowed": bool(card.bestow_characteristics),
        "effect_warnings": attachment_effect_warnings(state, cid),
        "colors": sorted(card_color_symbols(card)),
        "mana_source_colors": sorted(outputs),
        "mana_source_amounts": outputs,
        "chosen_creature_type": card.chosen_creature_type,
        "card_faces": list(card.card_faces), "selected_face_index": card.selected_face_index,
        "layout": card.layout,
        "was_foretold": card.was_foretold,
        "foretell_order": card.foretell_record.get('order'),
        "foretold_turn": card.foretell_record.get('turn'),
        "suspended": suspended(card),
    }


def serialize_match_snapshot(state: MatchState) -> dict:
    """Serialize all mutable rules state needed to resume a match."""
    return {
        "id": state.id,
        "starting_decks": {str(pid): deepcopy(rows) for pid, rows in state.starting_decks.items()},
        "card_observations": {str(pid): deepcopy(rows) for pid, rows in state.card_observations.items()},
        "turn": state.turn,
        "active_player": state.active_player,
        "priority_player": state.priority_player,
        "step": state.step.value,
        "passed_priority": sorted(state.passed_priority),
        "attackers": list(state.attackers),
        "attack_targets": dict(state.attack_targets),
        "attack_bands": [list(band) for band in state.attack_bands],
        "blocks": {key: list(value) for key, value in state.blocks.items()},
        "attackers_declared": state.attackers_declared,
        "blockers_declared": state.blockers_declared,
        "combat_damage_resolved": state.combat_damage_resolved,
        "combat_damage_stage": state.combat_damage_stage,
        "first_strike_damage_ids": sorted(state.first_strike_damage_ids),
        "combat_damage_assignments": {source: dict(amounts) for source, amounts in state.combat_damage_assignments.items()},
        "combat_assignment_queue": list(state.combat_assignment_queue),
        "delayed_triggers": deepcopy(state.delayed_triggers),
        "foretells_this_turn": dict(state.foretells_this_turn),
        "cleanup_pending": state.cleanup_pending,
        "cleanup_repeat_required": state.cleanup_repeat_required,
        "cleanup_deferred_triggers": state.cleanup_deferred_triggers,
        "winner": state.winner,
        "failed_draw_players": sorted(state.failed_draw_players),
        "best_of": state.best_of,
        "score": {str(key): value for key, value in state.score.items()},
        "pregame_pending": state.pregame_pending,
        "mulligan_count": {str(key): value for key, value in state.mulligan_count.items()},
        "kept_hands": sorted(state.kept_hands),
        "mulligan_declarations": {str(key): value for key, value in state.mulligan_declarations.items()},
        "mulligan_bottomed": {str(key): value for key, value in state.mulligan_bottomed.items()},
        "loyalty_activated_this_turn": sorted(state.loyalty_activated_this_turn),
        "trigger_once_seen_this_turn": sorted(state.trigger_once_seen_this_turn),
        "trigger_staging": state.trigger_staging,
        "trigger_staging_event": state.trigger_staging_event,
        "staged_triggers": state.staged_triggers,
        "priority_stops": {
            str(key): sorted(step.value for step in value)
            for key, value in state.priority_stops.items()
        },
        "log": list(state.log),
        "next_static_order": state.next_static_order,
        "next_effect_timestamp": state.next_effect_timestamp,
        "next_object_id": state.next_object_id,
        "day_night": state.day_night,
        "spells_cast_this_turn": {str(key): value for key, value in state.spells_cast_this_turn.items()},
        "kicked_spells_cast_this_turn": {str(key): value for key, value in state.kicked_spells_cast_this_turn.items()},
        "declared_attackers_this_turn": {str(key): value for key, value in state.declared_attackers_this_turn.items()},
        "spells_cast_last_turn": state.spells_cast_last_turn,
        "draws_in_current_draw_step": {str(key): value for key, value in state.draws_in_current_draw_step.items()},
        "draws_this_turn": {str(key): value for key, value in state.draws_this_turn.items()},
        "surveils_this_turn": {str(key): value for key, value in state.surveils_this_turn.items()},
        "discards_this_turn": {str(key): value for key, value in state.discards_this_turn.items()},
        "land_entries_this_turn": {str(key): value for key, value in state.land_entries_this_turn.items()},
        "land_entry_history_known": state.land_entry_history_known,
        "players_with_permanent_departure": sorted(state.players_with_permanent_departure),
        "temporary_control_changes": {
            str(cid): {str(key): int(value) for key, value in data.items()}
            for cid, data in state.temporary_control_changes.items()
        },
        "linked_exiles": [dict(item) for item in state.linked_exiles],
        "pending_entry_counters": [dict(item) for item in state.pending_entry_counters],
        "adventure_permissions": dict(state.adventure_permissions),
        "graveyard_permission_uses": dict(state.graveyard_permission_uses),
        "turn_cant_gain_life": sorted(state.turn_cant_gain_life),
        'combat_cost_effects': deepcopy(state.combat_cost_effects),
        "turn_damage_cant_be_prevented": state.turn_damage_cant_be_prevented,
        "replacement_choice_required": state.replacement_choice_required,
        "replacement_choice_players": sorted(state.replacement_choice_players),
        "mechanic_choice_players": sorted(state.mechanic_choice_players),
        "pending_replacement_choice": state.pending_replacement_choice,
        "trigger_order_choice_required": state.trigger_order_choice_required,
        "trigger_order_choice_players": sorted(state.trigger_order_choice_players),
        "pending_trigger_order": state.pending_trigger_order,
        "pending_mechanic_choice": state.pending_mechanic_choice,
        "rng_state": state.rng.getstate(),
        "players": {
            str(pid): {
                "id": player.id,
                "name": player.name,
                "life": player.life,
                "poison": player.poison,
                "counters": dict(player.counters),
                "library": list(player.library),
                "hand": list(player.hand),
                "battlefield": list(player.battlefield),
                "graveyard": list(player.graveyard),
                "exile": list(player.exile),
                "exile_play_until": dict(player.exile_play_until),
                "mana_pool": dict(player.mana_pool),
                "snow_mana_pool": dict(player.snow_mana_pool),
                "restricted_mana_pool": deepcopy(player.restricted_mana_pool),
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
                "is_token": is_token_card(card),
                "mana_cost": card.mana_cost,
                "power": card.power,
                "toughness": card.toughness,
                "printed_power": card.printed_power,
                "printed_toughness": card.printed_toughness,
                "loyalty": card.loyalty,
                "tapped": card.tapped,
                "summoning_sick": card.summoning_sick,
                "entered_turn": card.entered_turn,
                "counters": dict(card.counters),
                "counter_timestamps": dict(card.counter_timestamps),
                "keywords": list(card.keywords),
                "oracle_text": card.oracle_text,
                "type_line": card.type_line,
                "image_uri": card.image_uri,
                "keyword_effects": deepcopy(card.keyword_effects),
                "base_stat_effects": deepcopy(card.base_stat_effects),
                "type_effects": deepcopy(card.type_effects),
                "type_effect_base": deepcopy(card.type_effect_base),
                "attached_to": card.attached_to,
                "static_order": card.static_order,
                "effect_timestamp": card.effect_timestamp,
                "battlefield_incarnation": card.battlefield_incarnation,
                "instance_order": card.instance_order,
                "zone_change_sequence": card.zone_change_sequence,
                "card_faces": list(card.card_faces),
                "layout": card.layout,
                "exile_face_down": card.exile_face_down,
                "foretell_record": deepcopy(card.foretell_record),
                "suspend_haste": deepcopy(card.suspend_haste),
                "granted_flashback": deepcopy(card.granted_flashback),
                "was_foretold": card.was_foretold,
                "was_kicked": card.was_kicked,
                "selected_face_index": card.selected_face_index,
                "chosen_creature_type": card.chosen_creature_type,
                "printed_characteristics": dict(card.printed_characteristics),
                "bestow_characteristics": deepcopy(card.bestow_characteristics),
                "colors": card.colors,
                "last_known_battlefield": dict(card.last_known_battlefield),
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
        player.poison = int(raw.get("poison", 0))
        player.counters = {str(key): int(value) for key, value in raw.get("counters", {}).items() if key != "poison"}
        for key in ("library", "hand", "battlefield", "graveyard", "exile"):
            setattr(player, key, list(raw.get(key, [])))
        player.exile_play_until = {str(key): int(value) for key, value in raw.get("exile_play_until", {}).items()}
        player.mana_pool = {str(key): int(value) for key, value in raw.get("mana_pool", {}).items()}
        player.snow_mana_pool = {str(key): int(value) for key, value in raw.get("snow_mana_pool", {}).items()}
        player.restricted_mana_pool = deepcopy(raw.get("restricted_mana_pool", []))
        for key in (
            "prevent_damage_shield", "max_land_plays_this_turn", "lands_played_this_turn",
            "last_land_play_turn", "land_plays_recorded_on_turn",
        ):
            setattr(player, key, int(raw.get(key, getattr(player, key))))
        players[player.id] = player

    cards = {}
    from rules_engine.keyword_effects import restore_keyword_effects
    for cid, raw in payload["cards"].items():
        cards[cid] = CardInstance(
            id=str(raw["id"]), name=str(raw["name"]), owner=int(raw["owner"]),
            controller=int(raw["controller"]), zone=Zone(raw["zone"]),
            types=list(raw.get("types", [])), is_token=bool(raw.get("is_token", is_token_card(raw))),
            mana_cost=str(raw.get("mana_cost", "")),
            power=raw.get("power"), toughness=raw.get("toughness"), loyalty=raw.get("loyalty"),
            printed_power=raw.get('printed_power'), printed_toughness=raw.get('printed_toughness'),
            tapped=bool(raw.get("tapped", False)), summoning_sick=bool(raw.get("summoning_sick", True)),
            entered_turn=int(raw.get("entered_turn", 0)), counters=dict(raw.get("counters", {})),
            counter_timestamps={str(key): int(value) for key, value in raw.get('counter_timestamps', {}).items()},
            keywords=list(raw.get("keywords", [])), keyword_effects=restore_keyword_effects(raw), oracle_text=str(raw.get("oracle_text", "")),
            base_stat_effects=deepcopy(raw.get('base_stat_effects', [])),
            type_effects=deepcopy(raw.get('type_effects', [])),
            type_effect_base=deepcopy(raw.get('type_effect_base')),
            type_line=str(raw.get("type_line", "")), image_uri=raw.get("image_uri"),
            attached_to=raw.get("attached_to"), static_order=int(raw.get("static_order", 0)),
            effect_timestamp=int(raw.get("effect_timestamp", raw.get("static_order", 0))),
            battlefield_incarnation=raw.get("battlefield_incarnation"),
            zone_change_sequence=int(raw.get("zone_change_sequence", 0)),
            instance_order=int(raw.get("instance_order", 0)), card_faces=list(raw.get("card_faces", [])),
            selected_face_index=raw.get("selected_face_index"),
            layout=str(raw.get("layout") or ""),
            chosen_creature_type=raw.get("chosen_creature_type"),
            printed_characteristics=dict(raw.get("printed_characteristics", {})),
            bestow_characteristics=deepcopy(raw.get('bestow_characteristics', {})),
            colors=list(raw["colors"]) if raw.get("colors") is not None else None,
            last_known_battlefield=dict(raw.get("last_known_battlefield", {})),
            exile_face_down=bool(raw.get("exile_face_down", False)),
            foretell_record=deepcopy(raw.get('foretell_record', {})),
            suspend_haste=deepcopy(raw.get('suspend_haste', {})),
            granted_flashback=deepcopy(raw.get('granted_flashback', {})),
            was_foretold=bool(raw.get('was_foretold', False)),
            was_kicked=bool(raw.get('was_kicked', False)),
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
    state.starting_decks = {int(pid): deepcopy(rows) for pid, rows in payload.get('starting_decks', {}).items()}
    state.card_observations = {int(pid): deepcopy(rows) for pid, rows in payload.get('card_observations', {}).items()}
    state.failed_draw_players = {int(value) for value in payload.get("failed_draw_players", [])}
    state.passed_priority = {int(value) for value in payload.get("passed_priority", [])}
    state.attackers = list(payload.get("attackers", []))
    state.attack_targets = dict(payload.get("attack_targets", {}))
    state.attack_bands = [list(band) for band in payload.get("attack_bands", [])]
    state.blocks = {key: list(value) for key, value in payload.get("blocks", {}).items()}
    state.attackers_declared = bool(payload.get("attackers_declared", False))
    state.blockers_declared = bool(payload.get("blockers_declared", False))
    state.combat_damage_resolved = bool(payload.get("combat_damage_resolved", False))
    state.combat_damage_stage = str(payload.get("combat_damage_stage", "regular" if state.combat_damage_resolved else "none"))
    state.first_strike_damage_ids = {str(cid) for cid in payload.get("first_strike_damage_ids", [])}
    state.combat_damage_assignments = {
        str(source): {str(target): int(amount) for target, amount in amounts.items()}
        for source, amounts in payload.get("combat_damage_assignments", {}).items()
    }
    state.combat_assignment_queue = [str(cid) for cid in payload.get("combat_assignment_queue", [])]
    state.delayed_triggers = deepcopy(payload.get('delayed_triggers', []))
    state.foretells_this_turn = {int(key): int(value) for key, value in
                               payload.get('foretells_this_turn', {'1': 0, '2': 0}).items()}
    state.cleanup_pending = bool(payload.get("cleanup_pending", False))
    state.cleanup_repeat_required = bool(payload.get("cleanup_repeat_required", False))
    state.cleanup_deferred_triggers = list(payload.get("cleanup_deferred_triggers", []))
    state.score = {int(key): int(value) for key, value in payload.get("score", {"1": 0, "2": 0}).items()}
    state.pregame_pending = bool(payload.get("pregame_pending", True))
    state.mulligan_count = {int(key): int(value) for key, value in payload.get("mulligan_count", {}).items()}
    state.kept_hands = {int(value) for value in payload.get("kept_hands", [])}
    state.mulligan_declarations = {int(key): str(value) for key, value in payload.get("mulligan_declarations", {}).items()}
    state.mulligan_bottomed = {int(key): int(value) for key, value in payload.get("mulligan_bottomed", {}).items()}
    state.loyalty_activated_this_turn = set(payload.get("loyalty_activated_this_turn", []))
    state.trigger_once_seen_this_turn = set(payload.get("trigger_once_seen_this_turn", []))
    state.priority_stops = {
        int(key): {Step(value) for value in values}
        for key, values in payload.get("priority_stops", {}).items()
    }
    state.log = list(payload.get("log", []))
    state.next_static_order = int(payload.get("next_static_order", 1))
    state.next_effect_timestamp = int(payload.get("next_effect_timestamp", state.next_static_order))
    state.next_object_id = max(1, int(payload.get("next_object_id", 1)))
    state.day_night = str(payload.get("day_night", "none") or "none")
    state.spells_cast_this_turn = {
        int(key): int(value) for key, value in payload.get("spells_cast_this_turn", {"1": 0, "2": 0}).items()
    }
    state.kicked_spells_cast_this_turn = {
        int(key): int(value) for key, value in payload.get('kicked_spells_cast_this_turn', {'1': 0, '2': 0}).items()
    }
    state.declared_attackers_this_turn = {
        int(key): int(value) for key, value in payload.get("declared_attackers_this_turn", {"1": 0, "2": 0}).items()
    }
    state.spells_cast_last_turn = int(payload.get("spells_cast_last_turn", 0) or 0)
    state.draws_in_current_draw_step = {
        int(key): int(value) for key, value in payload.get("draws_in_current_draw_step", {"1": 0, "2": 0}).items()
    }
    state.draws_this_turn = {
        int(key): int(value) for key, value in payload.get("draws_this_turn", {"1": 0, "2": 0}).items()
    }
    state.surveils_this_turn = {
        int(key): int(value) for key, value in payload.get("surveils_this_turn", {"1": 0, "2": 0}).items()
    }
    state.discards_this_turn = {
        int(key): int(value) for key, value in payload.get("discards_this_turn", {"1": 0, "2": 0}).items()
    }
    state.land_entries_this_turn = {
        int(key): int(value) for key, value in payload.get('land_entries_this_turn', {'1': 0, '2': 0}).items()
    }
    state.land_entry_history_known = ('land_entries_this_turn' in payload
                                     and payload.get('land_entry_history_known', True) is True)
    state.temporary_control_changes = {
        str(cid): {str(key): int(value) for key, value in data.items()}
        for cid, data in payload.get("temporary_control_changes", {}).items()
    }
    state.linked_exiles = [dict(item) for item in payload.get("linked_exiles", [])]
    state.pending_entry_counters = [dict(item) for item in payload.get("pending_entry_counters", [])]
    state.players_with_permanent_departure = {int(pid) for pid in payload.get("players_with_permanent_departure", [])}
    state.adventure_permissions = {str(cid): int(pid) for cid, pid in payload.get("adventure_permissions", {}).items()}
    state.graveyard_permission_uses = {str(key): int(turn) for key, turn in payload.get('graveyard_permission_uses', {}).items()}
    state.turn_cant_gain_life = {int(value) for value in payload.get("turn_cant_gain_life", [])}
    state.combat_cost_effects = deepcopy(payload.get('combat_cost_effects', []))
    state.turn_damage_cant_be_prevented = bool(payload.get("turn_damage_cant_be_prevented", False))
    state.replacement_choice_required = bool(payload.get("replacement_choice_required", False))
    state.replacement_choice_players = {int(value) for value in payload.get("replacement_choice_players", [])}
    state.mechanic_choice_players = {
        int(value) for value in payload.get(
            "mechanic_choice_players", payload.get("library_choice_players", payload.get("search_choice_players", []))
        )
    }
    state.pending_replacement_choice = payload.get("pending_replacement_choice")
    state.trigger_order_choice_required = bool(payload.get("trigger_order_choice_required", False))
    state.trigger_order_choice_players = {int(value) for value in payload.get("trigger_order_choice_players", [])}
    state.trigger_staging = bool(payload.get("trigger_staging", False))
    state.trigger_staging_event = str(payload.get("trigger_staging_event") or "combat_damage_step")
    state.staged_triggers = list(payload.get("staged_triggers", []))
    state.pending_trigger_order = payload.get("pending_trigger_order")
    state.pending_mechanic_choice = payload.get("pending_mechanic_choice")
    state.rng.setstate(_tupleize(payload["rng_state"]))
    return state


def serialize_match(state: MatchState, *, look_players=()) -> dict:
    from rules_engine.foretell import can_look
    from rules_engine.land_rules import remaining_land_plays_this_turn
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
        "mulligan_bottomed": state.mulligan_bottomed,
        "kept_hands": sorted(list(state.kept_hands)),
        "day_night": state.day_night,
        "spells_cast_this_turn": state.spells_cast_this_turn,
        "discards_this_turn": dict(state.discards_this_turn),
        "turn_cant_gain_life": sorted(state.turn_cant_gain_life),
        "turn_damage_cant_be_prevented": state.turn_damage_cant_be_prevented,
        "combat_damage_stage": state.combat_damage_stage,
        "pending_replacement_choice": state.pending_replacement_choice,
        "pending_trigger_order": state.pending_trigger_order,
        "priority_stops": {
            str(pid): _sort_steps(steps)
            for pid, steps in state.priority_stops.items()
        },
        "players": {
            pid: {
                "id": p.id,
                "name": p.name,
                "life": p.life,
                "poison": p.poison,
                "counters": public_counters(p),
                "library_count": len(p.library),
                "hand_count": len(p.hand),
                "land_plays_remaining": remaining_land_plays_this_turn(state, pid),
                "battlefield": [
                    serialize_card_view(state, cid)
                    for cid in p.battlefield
                ],
                "hand": [
                    serialize_card_view(state, cid)
                    for cid in p.hand
                ],
                "graveyard": [
                    serialize_card_view(state, cid)
                    for cid in p.graveyard
                ],
                "graveyard_count": len(p.graveyard),
                "exile": [serialize_card_view(state, cid) for cid in p.exile
                          if not state.cards[cid].exile_face_down or any(
                              can_look(state.cards[cid], pid)
                              for pid in look_players) or state.winner is not None and state.cards[cid].foretell_record],
                "exile_count": len(p.exile),
                "mana_pool": p.mana_pool,
                "snow_mana_pool": p.snow_mana_pool,
                "restricted_mana_pool": deepcopy(p.restricted_mana_pool),
            }
            for pid, p in state.players.items()
        },
        "stack": [
            {
                "id": item.id,
                "label": item.label,
                "controller": item.controller,
                "effect_key": item.effect_key,
                "targets": ((item.payload.get('__announced_targets') or {}).get('target_card_ids', [])
                            if item.payload.get('__ordered_target_instances')
                            or item.payload.get('__ordered_distinct_targets') else item.targets),
            }
            for item in state.stack
        ],
        "attackers": state.attackers,
        "pending_mechanic_choice": state.pending_mechanic_choice,
        "attack_targets": state.attack_targets,
        "attack_bands": state.attack_bands,
        "blocks": state.blocks,
        "log": state.log[-120:],
    }
