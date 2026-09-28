from __future__ import annotations

import uuid

from game_state.state import MatchState, StackItem, Step, TURN_STEPS, Zone, assign_static_order_on_battlefield_entry, draw_card
from rules_engine import combat
from rules_engine.cast_choice import build_cast_hints, enrich_divide_total, validate_cast_choice
from rules_engine.card_types import is_land_card as _is_land_card
from rules_engine.costs import apply_activated_costs, apply_additional_costs, check_cost_option_available, collect_cost_options, normalize_cost_choice
from rules_engine.cycling import cycling_cost, cycling_is_variable, cycling_variant
from rules_engine.mana import add_generic_to_cost, auto_pay_cost, mana_value
from rules_engine.mana import land_mana_amount
from rules_engine.move_generator import legal_moves
from rules_engine.library_permissions import choose_type_for_realmwalker, top_library_creature_for_type
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.oracle_effects import crew_value, extract_activated_abilities, extract_loyalty_abilities, extract_saga_chapters
from rules_engine.ability_model import build_ability_spec, build_spell_spec
from rules_engine.priority import pass_priority
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.targeting import validate_hexproof_shroud_targets, validate_protection_targets
from rules_engine.events import emit_event, resume_trigger_order, resume_trigger_target
from rules_engine.restrictions import can_cast_in_current_timing
from rules_engine.ward import ward_tax_for_targets
from rules_engine.attachments import attach_if_legal
from effects.registry import resolve_effect


class RulesEngine:
    def next_step(self, state: MatchState) -> None:
        if state.pregame_pending:
            return
        if state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order:
            return
        if state.winner is not None:
            return
        if state.stack:
            resolve_top_of_stack(state)
            apply_state_based_actions(state)
            if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
                state.priority_player = state.active_player
            return

        if state.step == Step.CLEANUP and state.cleanup_pending:
            self._finish_cleanup(state)
            return
        if state.step == Step.CLEANUP and state.cleanup_repeat_required:
            state.cleanup_repeat_required = False
            state.log.append("Another cleanup step begins.")
            self._apply_step_start_actions(state)
            return

        if state.step == Step.COMBAT_DAMAGE and state.combat_damage_stage == "first":
            self._clear_mana_pools(state)
            combat.finish_combat_damage(state)
            apply_state_based_actions(state)
            if not state.pending_mechanic_choice and not state.pending_replacement_choice and not state.pending_trigger_order:
                state.priority_player = state.active_player
                state.passed_priority = set()
            return

        self._clear_mana_pools(state)
        idx = TURN_STEPS.index(state.step)
        if idx == len(TURN_STEPS) - 1:
            state.spells_cast_last_turn = int(state.spells_cast_this_turn.get(state.active_player, 0) or 0)
            state.turn += 1
            state.active_player = 1 if state.active_player == 2 else 2
            state.spells_cast_this_turn[state.active_player] = 0
            state.step = TURN_STEPS[0]
            state.loyalty_activated_this_turn = set()
            state.trigger_once_seen_this_turn = set()
            player = state.players[state.active_player]
            for cid in list(player.battlefield):
                card = state.cards[cid]
                if "Creature" in card.types and card.entered_turn < state.turn:
                    card.summoning_sick = False
            state.players[state.active_player].lands_played_this_turn = 0
            state.players[state.active_player].max_land_plays_this_turn = compute_max_land_plays_this_turn(
                state, state.active_player
            )
            state.players[state.active_player].land_plays_recorded_on_turn = 0
            for player_state in state.players.values():
                player_state.exile_play_until = {
                    cid: expiry
                    for cid, expiry in player_state.exile_play_until.items()
                    if expiry >= state.turn and cid in player_state.exile
                }
        else:
            state.step = TURN_STEPS[idx + 1]
            if state.step == Step.DECLARE_ATTACKERS:
                state.attackers_declared = False
                state.combat_damage_resolved = False
                state.combat_damage_stage = "none"
                state.first_strike_damage_ids = set()
            elif state.step == Step.DECLARE_BLOCKERS:
                state.blockers_declared = False
            elif state.step == Step.COMBAT_DAMAGE:
                combat.begin_combat_damage(state)
                apply_state_based_actions(state)
            elif state.step == Step.POSTCOMBAT_MAIN:
                state.attackers = []
                state.attack_targets = {}
                state.blocks = {}
                state.attackers_declared = False
                state.blockers_declared = False

        self._apply_step_start_actions(state)
        if not state.pending_mechanic_choice and not state.pending_replacement_choice and not state.pending_trigger_order:
            state.priority_player = state.active_player
            state.passed_priority = set()

    def _apply_step_start_actions(self, state: MatchState) -> None:
        player = state.players[state.active_player]
        if state.step == Step.UNTAP:
            for cid in player.battlefield:
                state.cards[cid].tapped = False
            state.log.append(f"{player.name} untaps.")
        elif state.step == Step.UPKEEP:
            self._update_day_night(state)
            emit_event(state, "begin_step", {"step": "upkeep", "active_player": state.active_player})
        elif state.step == Step.DRAW and state.turn > 1:
            state.draws_in_current_draw_step[state.active_player] = 0
            before = len(player.hand)
            resolve_effect(state, state.active_player, "draw_cards", {"amount": 1})
            after = len(player.hand)
            if after == before + 1 and not state.pending_mechanic_choice:
                state.log.append(f"{player.name} draws a card. Hand {before}->{after}.")
            else:
                state.log.append(f"{player.name} processes the draw step. Hand {before}->{after}.")
        elif state.step == Step.DRAW and state.turn == 1:
            state.draws_in_current_draw_step[state.active_player] = 0
            state.log.append(f"{player.name} skips draw on turn 1 (on the play rule).")
        elif state.step == Step.PRECOMBAT_MAIN:
            self._advance_sagas(state)
        elif state.step == Step.END_STEP:
            emit_event(state, "begin_step", {"step": "end_step", "active_player": state.active_player})
        elif state.step == Step.CLEANUP:
            state.cleanup_pending = True
            self._enforce_cleanup_hand_size(state, state.active_player)
            if not state.pending_mechanic_choice:
                self._finish_cleanup(state)

    def _finish_cleanup(self, state: MatchState) -> None:
        # Damage removal and duration expiry have no intervening SBA check.
        self._clear_marked_damage(state)
        self._clear_prevention_shields(state)
        self._revert_expired_control_changes(state)
        self._revert_crew_vehicles(state)
        state.pending_entry_counters = [
            entry
            for entry in getattr(state, "pending_entry_counters", [])
            if int(entry.get("expires_turn", state.turn)) > int(state.turn)
        ]
        state.turn_cant_gain_life = set()
        state.turn_damage_cant_be_prevented = False
        performed_sba = False
        while True:
            before = {cid: (card.zone, dict(card.counters), card.loyalty) for cid, card in state.cards.items()}
            apply_state_based_actions(state)
            changed = before != {cid: (card.zone, dict(card.counters), card.loyalty) for cid, card in state.cards.items()}
            performed_sba = performed_sba or changed
            if not changed or state.pending_replacement_choice or state.pending_trigger_order or state.winner is not None:
                break
        state.cleanup_repeat_required = state.cleanup_repeat_required or performed_sba or bool(state.cleanup_deferred_triggers or state.pending_replacement_choice or state.pending_trigger_order)
        if state.pending_replacement_choice or state.pending_trigger_order:
            return
        state.cleanup_pending = False
        triggers = state.cleanup_deferred_triggers
        state.cleanup_deferred_triggers = []
        from rules_engine.events import _push_triggers
        _push_triggers(state, "cleanup", triggers)
        if not state.pending_trigger_order:
            state.priority_player = state.active_player
        state.passed_priority = set()

    def _revert_crew_vehicles(self, state: MatchState) -> None:
        for card in state.cards.values():
            if int(card.counters.get("__crew_until_turn", -1)) != int(state.turn):
                continue
            card.counters.pop("__crew_until_turn", None)
            removed_creature = bool(card.counters.pop("__crew_added_creature", 0))
            if removed_creature and "Creature" in card.types:
                card.types.remove("Creature")
            if card.counters.pop("__crew_added_artifact", 0) and "Artifact" in card.types:
                card.types.remove("Artifact")
            state.log.append(f"{card.name} is no longer a creature after cleanup." if removed_creature else f"Crew effect ends for {card.name} after cleanup.")

    def _advance_sagas(self, state: MatchState) -> None:
        for cid in list(state.players[state.active_player].battlefield):
            card = state.cards.get(cid)
            if card is None or "Saga" not in (card.type_line or ""):
                continue
            chapters = extract_saga_chapters(card.oracle_text)
            if not chapters:
                continue
            lore = int(card.counters.get("__lore", 0) or 0) + 1
            card.counters["__lore"] = lore
            chapter = next((item for item in chapters if int(item["number"]) == lore), None)
            state.log.append(f"{card.name} gets a lore counter ({lore}).")
            if chapter is None:
                continue
            proxy = type("SagaChapterProxy", (), {"oracle_text": chapter["text"], "name": card.name, "mana_cost": "", "types": ["Enchantment"]})()
            ability = build_ability_spec(
                state,
                proxy,
                card.controller,
                action_targets={"source_card_id": cid, "target_card_id": cid},
            )
            state.stack.append(
                StackItem(
                    id=str(uuid.uuid4()),
                    source_card_id=cid,
                    controller=card.controller,
                    label=f"{card.name} chapter {chapter['number']}",
                    effect_key=ability.effect.key,
                    payload=ability.effect.payload,
                )
            )
            state.priority_player = state.active_player
            state.passed_priority = set()
            state.log.append(f"{card.name} chapter {chapter['number']} triggers.")

    def _revert_expired_control_changes(self, state: MatchState) -> None:
        for cid, data in list(state.temporary_control_changes.items()):
            if int(data.get("expires_turn", state.turn)) != int(state.turn):
                continue
            card = state.cards.get(cid)
            original = int(data.get("controller", 0) or 0)
            if card and card.zone == Zone.BATTLEFIELD and original in state.players and card.controller != original:
                current = state.players[card.controller].battlefield
                if cid in current:
                    current.remove(cid)
                state.players[original].battlefield.append(cid)
                card.controller = original
                state.log.append(f"Control of {card.name} returns to {state.players[original].name}.")
            state.temporary_control_changes.pop(cid, None)

    def _update_day_night(self, state: MatchState) -> None:
        """Apply the core day/night turn-count rule at the beginning of upkeep."""
        if state.turn <= 1:
            return
        cast_count = int(getattr(state, "spells_cast_last_turn", 0) or 0)
        previous = str(getattr(state, "day_night", "none") or "none")
        next_state = previous
        if previous == "none":
            if cast_count == 0:
                next_state = "night"
            elif cast_count >= 2:
                next_state = "day"
        elif previous == "day" and cast_count == 0:
            next_state = "night"
        elif previous == "night" and cast_count >= 2:
            next_state = "day"
        if next_state == previous:
            return
        state.day_night = next_state
        state.log.append(f"The game becomes {next_state}.")
        emit_event(state, "day_night_changed", {"from": previous, "to": next_state, "spell_count": cast_count})
        self._transform_day_night_permanents(state, next_state)

    def _transform_day_night_permanents(self, state: MatchState, current: str) -> None:
        target_marker = "daybound" if current == "night" else "nightbound"
        target_face = 1 if current == "night" else 0
        for player in state.players.values():
            for cid in list(player.battlefield):
                card = state.cards[cid]
                if not card.card_faces or target_marker not in (card.oracle_text or "").lower():
                    continue
                if target_face >= len(card.card_faces):
                    continue
                resolve_effect(
                    state,
                    card.controller,
                    "transform_card",
                    {"target_card_id": cid, "face_index": target_face},
                )

    def _clear_mana_pools(self, state: MatchState) -> None:
        for p in state.players.values():
            for color in p.mana_pool:
                p.mana_pool[color] = 0

    def _clear_marked_damage(self, state: MatchState) -> None:
        for card in state.cards.values():
            if "__damage_marked" in card.counters:
                card.counters.pop("__damage_marked", None)
            if "__deathtouch_damaged" in card.counters:
                card.counters.pop("__deathtouch_damaged", None)
            if "__eot_power" in card.counters:
                card.counters.pop("__eot_power", None)
            if "__eot_toughness" in card.counters:
                card.counters.pop("__eot_toughness", None)

    def _clear_prevention_shields(self, state: MatchState) -> None:
        for player in state.players.values():
            player.prevent_damage_shield = 0
        for card in state.cards.values():
            card.counters.pop("__prevent_damage_shield", None)

    def _enforce_cleanup_hand_size(self, state: MatchState, player_id: int) -> None:
        player = state.players[player_id]
        if self._has_no_max_hand_size_effect(state, player_id):
            return
        max_hand_size = 7
        if len(player.hand) <= max_hand_size:
            return
        discard_count = len(player.hand) - max_hand_size
        human_players = state.replacement_choice_players
        human = state.replacement_choice_required and (not human_players or player_id in human_players)
        if human or player_id in state.mechanic_choice_players:
            state.pending_mechanic_choice = {"kind": "cleanup_discard", "player_id": player_id, "options": list(player.hand), "count": discard_count, "label": "Discard to maximum hand size"}
            state.priority_player = player_id
        else:
            from rules_engine.zone_actions import discard_selected
            discard_selected(state, player_id, list(player.hand[:discard_count]))

    def choose_cleanup_discards(self, state: MatchState, player_id: int, action: dict) -> bool:
        from rules_engine.zone_actions import discard_selected
        pending = state.pending_mechanic_choice
        ids = action.get("card_ids")
        if not pending or pending["kind"] != "cleanup_discard" or pending["player_id"] != player_id or not isinstance(ids, list) or len(ids) != pending["count"]:
            return False
        if not discard_selected(state, player_id, ids):
            return False
        state.pending_mechanic_choice = None
        self._finish_cleanup(state)
        return True

    def _has_no_max_hand_size_effect(self, state: MatchState, player_id: int) -> bool:
        player = state.players[player_id]
        for cid in player.battlefield:
            card = state.cards[cid]
            oracle = (card.oracle_text or "").lower()
            if "no maximum hand size" in oracle:
                return True
        return False

    def take_action(self, state: MatchState, player_id: int, action: dict, *, reject_invalid: bool = False) -> None:
        def reject(reason: str) -> None:
            if reject_invalid:
                from rules_engine.action_validation import ActionRejected
                raise ActionRejected(reason)

        if state.winner is not None:
            return
        kind = action.get("type")
        if state.pending_mechanic_choice:
            if state.pending_mechanic_choice["kind"] == "cleanup_discard":
                if kind == "choose_mechanic":
                    if not self.choose_cleanup_discards(state, player_id, action):
                        reject("Invalid cleanup discard selection")
                return
            from rules_engine.keyword_actions import finish_mechanic_choice
            if kind == "choose_mechanic":
                if finish_mechanic_choice(state, player_id, action):
                    apply_state_based_actions(state)
                else:
                    reject("Invalid mechanic choice")
            return

        if state.pregame_pending:
            self._handle_pregame_action(state, player_id, action)
            return

        pending = getattr(state, "pending_replacement_choice", None)
        pending_order = getattr(state, "pending_trigger_order", None)
        if pending_order:
            if int(pending_order.get("current_controller", -1)) != player_id:
                return
            if pending_order.get("phase") == "optional":
                if kind != "choose_optional_effect" or not state.stack or state.stack[-1].id != pending_order.get("current_stack_id") or action.get("stack_id") != pending_order.get("current_stack_id") or type(action.get("accept")) is not bool:
                    reject("Invalid optional effect choice")
                    return
                state.stack[-1].payload["__may_choose"] = action["accept"]
                state.stack[-1].payload["__may_decided"] = True
                state.pending_trigger_order = None
                resolve_top_of_stack(state)
            elif pending_order.get("phase") == "targets":
                if kind != "choose_trigger_target" or not resume_trigger_target(state, str(action.get("stack_id", "")), str(action.get("target_card_id", ""))):
                    reject("Invalid trigger target")
                    return
            else:
                requested = action.get("trigger_order") or []
                if kind != "choose_trigger_order" or not isinstance(requested, list) or not resume_trigger_order(state, requested):
                    reject("Invalid trigger order")
                    return
            if not state.pending_trigger_order:
                state.priority_player = state.active_player
                state.passed_priority = set()
            apply_state_based_actions(state)
            return
        if pending:
            if kind != "choose_replacement" or int(pending.get("player_id", -1)) != player_id:
                return
            chosen_id = str(action.get("replacement_source_id") or "")
            allowed = {str(option.get("source_id")) for option in (pending.get("options") or [])}
            if chosen_id not in allowed:
                reject("Invalid replacement choice")
                state.log.append("Invalid replacement choice; resolution remains paused.")
                return
            if pending.get("resume_kind") == "draw_event":
                from rules_engine.stack_engine import resume_paused_resolution

                state.pending_replacement_choice = None
                state.log.append(f"{state.players[player_id].name} chooses replacement source {chosen_id}.")
                resolve_effect(
                    state, int(pending["controller"]), "draw_cards",
                    {**pending["draw_payload"], "__replacement_source_id": chosen_id},
                )
                resume_paused_resolution(state, pending)
                apply_state_based_actions(state)
                return
            if pending.get("resume_kind") == "state_based_die":
                from rules_engine.state_based_actions import resume_state_based_die_replacement

                state.pending_replacement_choice = None
                state.log.append(
                    f"{state.players[player_id].name} chooses replacement source {chosen_id}."
                )
                resume_state_based_die_replacement(state, str(pending.get("target_card_id", "")), chosen_id)
                from rules_engine.stack_engine import resume_paused_resolution
                resume_paused_resolution(state, pending)
                apply_state_based_actions(state)
                if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
                    state.priority_player = state.active_player
                    state.passed_priority = set()
                return
            if pending.get("resume_kind") == "combat_die":
                from rules_engine.combat import resume_combat_die_replacement

                state.pending_replacement_choice = None
                state.log.append(
                    f"{state.players[player_id].name} chooses replacement source {chosen_id}."
                )
                resume_combat_die_replacement(state, str(pending.get("target_card_id", "")), chosen_id)
                from rules_engine.stack_engine import resume_paused_resolution
                resume_paused_resolution(state, pending)
                apply_state_based_actions(state)
                if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
                    state.priority_player = state.active_player
                    state.passed_priority = set()
                return
            if pending.get("resume_kind") == "legend_die":
                from rules_engine.state_based_actions import resume_legend_rule_replacement

                state.pending_replacement_choice = None
                state.log.append(
                    f"{state.players[player_id].name} chooses replacement source {chosen_id}."
                )
                resume_legend_rule_replacement(
                    state,
                    int(pending.get("legend_player_id", player_id)),
                    str(pending.get("target_card_id", "")),
                    chosen_id,
                )
                from rules_engine.stack_engine import resume_paused_resolution
                resume_paused_resolution(state, pending)
                apply_state_based_actions(state)
                if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
                    state.priority_player = state.active_player
                    state.passed_priority = set()
                return
            if pending.get("resume_kind") == "damage_chain":
                state.pending_replacement_choice = None
                state.log.append(
                    f"{state.players[player_id].name} chooses replacement source {chosen_id}."
                )
                resolve_effect(
                    state,
                    int(pending.get("controller", player_id)),
                    "deal_damage",
                    {
                        "target_player": pending.get("target_player"),
                        "target_card_id": pending.get("target_card_id"),
                        "amount": int(pending.get("amount", 0) or 0),
                        "__source_card_id": pending.get("source_card_id"),
                        "__replacement_source_id": chosen_id,
                        "__used_replacement_source_ids": list(pending.get("selected_source_ids") or [])
                        + [chosen_id],
                    },
                )
                from rules_engine.stack_engine import resume_paused_resolution
                resume_paused_resolution(state, pending)
                apply_state_based_actions(state)
                if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
                    state.priority_player = state.active_player
                    state.passed_priority = set()
                return
            if not state.stack or state.stack[-1].id != pending.get("stack_id"):
                reject("Replacement continuation is no longer available")
                state.log.append("Invalid replacement choice; resolution remains paused.")
                return
            state.stack[-1].payload["__replacement_source_id"] = chosen_id
            state.pending_replacement_choice = None
            state.log.append(
                f"{state.players[player_id].name} chooses replacement source {chosen_id}."
            )
            resolve_top_of_stack(state)
            if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
                state.priority_player = state.active_player
                state.passed_priority = set()
            apply_state_based_actions(state)
            return

        if state.cleanup_pending and state.step == Step.CLEANUP:
            self._finish_cleanup(state)
            if state.pending_trigger_order or state.pending_replacement_choice:
                return
        if state.step == Step.CLEANUP and not state.cleanup_repeat_required and kind != "pass_priority":
            return
        if kind == "pass_priority":
            actor = state.players.get(player_id)
            if actor:
                state.log.append(
                    f"{actor.name} passes priority on {state.step.value} (stack={len(state.stack)})."
                )
            both_passed = pass_priority(state, player_id)
            if both_passed:
                if state.stack:
                    resolve_top_of_stack(state)
                    if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
                        state.priority_player = state.active_player
                else:
                    self.next_step(state)
            apply_state_based_actions(state)
            return

        if state.priority_player != player_id:
            return

        player = state.players[player_id]
        if kind == "ninjutsu":
            from rules_engine.keyword_actions import activate_ninjutsu
            if not activate_ninjutsu(state, player_id, action):
                reject("Cannot pay or activate Ninjutsu")
        elif kind == "play_land":
            cid = action["card_id"]
            from rules_engine.card_faces import select_cast_face, apply_cast_face, exile_permission, leave_exile
            card = state.cards[cid]
            face_index = action.get("selected_face_index", 0) or 0
            if face_index and card.layout != "modal_dfc":
                reject("This card has no playable alternate land face")
                return
            face = select_cast_face(card, face_index)
            from_exile = bool(action.get("from_exile"))
            allowed_source = exile_permission(state, player_id, cid, face_index) if from_exile else cid in player.hand
            if not (state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack):
                apply_state_based_actions(state)
                return
            player.max_land_plays_this_turn = compute_max_land_plays_this_turn(state, player_id)
            max_land_plays = max(1, int(getattr(player, "max_land_plays_this_turn", 1)))
            if getattr(player, "last_land_play_turn", 0) != state.turn:
                player.last_land_play_turn = state.turn
                player.lands_played_this_turn = 0
                player.land_plays_recorded_on_turn = 0
            used_land_plays = max(
                int(getattr(player, "lands_played_this_turn", 0)) if getattr(player, "last_land_play_turn", 0) == state.turn else 0,
                int(getattr(player, "land_plays_recorded_on_turn", 0)),
            )
            if allowed_source and used_land_plays < max_land_plays and _is_land_card(face):
                if from_exile:
                    leave_exile(state, cid)
                else:
                    player.hand.remove(cid)
                apply_cast_face(card, face)
                player.battlefield.append(cid)
                player.lands_played_this_turn = used_land_plays + 1
                player.land_plays_recorded_on_turn = used_land_plays + 1
                player.last_land_play_turn = state.turn
                state.cards[cid].zone = Zone.BATTLEFIELD
                state.cards[cid].summoning_sick = False
                from rules_engine.land_rules import apply_land_entry
                apply_land_entry(card)
                assign_static_order_on_battlefield_entry(state, cid)
                state.log.append(f"{player.name} plays {state.cards[cid].name}.")
                emit_event(state, "enters_battlefield", {"card_id": cid, "controller": player_id})

        elif kind == "tap_land_for_mana":
            cid = action["card_id"]
            if cid in player.battlefield and not state.cards[cid].tapped and "Land" in state.cards[cid].types:
                state.cards[cid].tapped = True
                color = _infer_mana_from_land(
                    state.cards[cid].name,
                    oracle_text=getattr(state.cards[cid], "oracle_text", "") or "",
                    requested_color=action.get("color"),
                )
                amount = land_mana_amount(state, player_id, cid)
                player.mana_pool[color] += amount
                state.log.append(f"{player.name} taps {state.cards[cid].name} for {amount} {color}.")

        elif kind == "tap_lands_bulk":
            land_name = str(action.get("land_name", "")).strip().lower()
            count = max(0, int(action.get("count", 0)))
            if land_name and count > 0:
                tapped = 0
                produced = None
                produced_total = 0
                for cid in list(player.battlefield):
                    card = state.cards[cid]
                    if tapped >= count:
                        break
                    if "Land" not in card.types or card.tapped:
                        continue
                    if card.name.strip().lower() != land_name:
                        continue
                    card.tapped = True
                    color = _infer_mana_from_land(
                        card.name,
                        oracle_text=getattr(card, "oracle_text", "") or "",
                        requested_color=action.get("color"),
                    )
                    amount = land_mana_amount(state, player_id, cid)
                    player.mana_pool[color] += amount
                    produced = color
                    produced_total += amount
                    tapped += 1
                if tapped > 0 and produced:
                    state.log.append(
                        f"{player.name} taps {tapped}x {action.get('land_name')} for "
                        f"{produced_total} {produced}."
                    )

        elif kind == "cast_spell":
            cid = action["card_id"]
            from_exile = bool(action.get("from_exile"))
            from_library = bool(action.get("from_library"))
            from_graveyard = bool(action.get("from_graveyard"))
            from rules_engine.card_faces import exile_permission, leave_exile
            chosen_face = action.get("selected_face_index", (action.get("targets") or {}).get("selected_face_index", 0)) or 0
            allowed_source = (
                exile_permission(state, player_id, cid, chosen_face)
                if from_exile
                else (cid in player.graveyard if from_graveyard else cid in player.hand if not from_library else top_library_creature_for_type(state, player_id) is not None and player.library[-1] == cid)
            )
            if allowed_source:
                card = state.cards[cid]
                at_targets = action.get("targets", {})
                selected_face_index = action.get("selected_face_index", at_targets.get("selected_face_index"))
                if selected_face_index and card.layout in {"transform", "meld", "flip", "double_faced_token"}:
                    reject("This back face cannot be cast directly")
                    state.log.append(f"{card.name}'s back face cannot be cast directly.")
                    return
                face_card = _select_face_for_cast(card, selected_face_index)
                timing_ok, timing_reason = can_cast_in_current_timing(state, face_card, player_id)
                if not timing_ok:
                    reject(timing_reason)
                    state.log.append(f"{player.name} cannot cast {card.name}: {timing_reason}")
                    apply_state_based_actions(state)
                    return
                if _is_land_card(face_card):
                    reject("Lands must be played, not cast")
                    state.log.append(f"{player.name} cannot cast land card {card.name} as a spell.")
                    apply_state_based_actions(state)
                    return
                options = collect_cost_options(state, player_id, face_card)
                if not options:
                    reject("No supported casting cost")
                    return
                chosen = normalize_cost_choice(action, options)
                from rules_engine.alternative_casts import validate_escape_exiles
                escape_ids = validate_escape_exiles(state, player_id, cid, chosen.exile_graveyard, action.get("escape_exile_ids")) if chosen.id == "escape" else []
                if escape_ids is None:
                    reject("Invalid escape exile selection")
                    state.log.append("Invalid escape exile selection.")
                    return
                # Extract x_value early — needed for cost checking and payment
                at_targets = action.get("targets", {}) if isinstance(action, dict) else {}
                x_value = int(at_targets.get("x_value", 0) or 0)
                if not check_cost_option_available(state, player_id, face_card, chosen, x_value=x_value):
                    explicit_choice = bool(((action.get("cost_choice") or {}).get("id")))
                    if not explicit_choice:
                        chosen = next(
                            (
                                opt
                                for opt in options
                                if check_cost_option_available(state, player_id, face_card, opt, x_value=x_value)
                            ),
                            chosen,
                        )
                    if not check_cost_option_available(state, player_id, face_card, chosen, x_value=x_value):
                        reject("Cannot satisfy chosen casting costs")
                        state.log.append(f"{player.name} cannot satisfy chosen costs for {card.name}.")
                        apply_state_based_actions(state)
                        return
                action_targets = enrich_divide_total(card, at_targets)
                selected_face_index = action.get("selected_face_index")
                if selected_face_index is None and isinstance(action_targets, dict):
                    selected_face_index = action_targets.get("selected_face_index")
                face_card = _select_face_for_cast(card, selected_face_index)
                if face_card is not card:
                    action_targets = dict(action_targets)
                    action_targets.setdefault("selected_face_index", selected_face_index if selected_face_index is not None else 0)
                hints = build_cast_hints(state, face_card, player_id, action_targets)
                if reject_invalid:
                    from rules_engine.action_validation import require_declared_targets
                    require_declared_targets(face_card, hints, action_targets, player_id, spell=True)
                if hints.get("supports_divide") and "divide_total" not in action_targets:
                    reject("Cannot derive this allocation total from the supported card effect")
                ok, error = validate_cast_choice(hints, action_targets)
                if not ok:
                    reject(error)
                    state.log.append(f"Invalid targets for {card.name}: {error}")
                    apply_state_based_actions(state)
                    return
                ok_prot, err_prot = validate_protection_targets(state, face_card, action_targets)
                if not ok_prot:
                    reject(err_prot)
                    state.log.append(f"Invalid targets for {card.name}: {err_prot}")
                    apply_state_based_actions(state)
                    return
                ok_hs, err_hs = validate_hexproof_shroud_targets(state, player_id, action_targets)
                if not ok_hs:
                    reject(err_hs)
                    state.log.append(f"Invalid targets for {card.name}: {err_hs}")
                    apply_state_based_actions(state)
                    return
                target_ids: list[str] = []
                if action_targets.get("target_card_id"):
                    target_ids.append(action_targets["target_card_id"])
                target_ids.extend([x for x in (action_targets.get("target_card_ids") or []) if x not in target_ids])
                ward_tax = ward_tax_for_targets(state, player_id, target_ids)
                adjusted_cost = add_generic_to_cost(chosen.mana_cost, ward_tax)
                paid = auto_pay_cost(
                    state, player_id, adjusted_cost, is_land=("Land" in face_card.types),
                    card_name=face_card.name, x_value=x_value, spell_types=set(face_card.types),
                )
                if not paid:
                    reject("Cannot pay spell cost and ward tax")
                    if ward_tax > 0:
                        state.log.append(f"{player.name} cannot pay ward tax ({ward_tax}) for {card.name}.")
                    else:
                        state.log.append(f"{player.name} cannot pay mana cost for {card.name}.")
                    apply_state_based_actions(state)
                    return
                if not apply_additional_costs(state, player_id, chosen, cid):
                    reject("Cannot pay additional casting costs")
                    state.log.append(f"{player.name} failed additional costs for {card.name}.")
                    apply_state_based_actions(state)
                    return
                ability = build_spell_spec(state, face_card, player_id, action_targets=action_targets)
                effect_key, payload = ability.effect.key, ability.effect.payload
                payload["__announced_targets"] = dict(action_targets)
                if x_value > 0:
                    payload.setdefault("x_value", x_value)

                for exile_id in escape_ids:
                    player.graveyard.remove(exile_id)
                    player.exile.append(exile_id)
                    state.cards[exile_id].zone = Zone.EXILE
                if chosen.id == "prototype":
                    from rules_engine.alternative_casts import apply_prototype
                    apply_prototype(card)
                from rules_engine.card_faces import apply_cast_face
                apply_cast_face(card, face_card)
                if chosen.id == "escape":
                    payload["__escaped"] = True
                if from_exile:
                    leave_exile(state, cid)
                else:
                    (player.graveyard if from_graveyard else player.hand if not from_library else player.library).remove(cid)
                player.exile_play_until.pop(cid, None)
                card.zone = Zone.STACK
                card.controller = player_id
                state.spells_cast_this_turn[player_id] = int(state.spells_cast_this_turn.get(player_id, 0) or 0) + 1
                add_to_stack(state, source_card_id=cid, controller=player_id, label=card.name, effect_key=effect_key, payload=payload)

        elif kind == "cycle_card":
            cid = action.get("card_id")
            if not cid or cid not in player.hand:
                apply_state_based_actions(state)
                return
            card = state.cards[cid]
            cycle_cost = cycling_cost(card.oracle_text, allow_variable=True)
            x_value = int(action.get("x_value", 0) or 0)
            if x_value < 0 or (cycle_cost and not cycling_is_variable(cycle_cost) and x_value != 0):
                reject("Invalid cycling X value")
                state.log.append(f"Invalid cycling X value for {card.name}.")
                apply_state_based_actions(state)
                return
            if not cycle_cost or not auto_pay_cost(state, player_id, cycle_cost, card_name=card.name, x_value=x_value):
                reject("Cannot pay cycling cost")
                state.log.append(f"{player.name} cannot pay cycling cost for {card.name}.")
                apply_state_based_actions(state)
                return
            player.hand.remove(cid)
            player.graveyard.append(cid)
            card.zone = Zone.GRAVEYARD
            state.log.append(f"{player.name} cycles {card.name}.")
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{card.name} cycling ability",
                is_spell=False,
                effect_key="cycle_search" if cycling_variant(card.oracle_text) else "cycle_draw",
                payload=(
                    {"contains": cycling_variant(card.oracle_text), "count": 1, "shuffle": True}
                    if cycling_variant(card.oracle_text)
                    else {"amount": 1}
                ),
            )
            # Discard is a cost event, but its triggered abilities are put on
            # the stack after the cycling ability and therefore above it.
            emit_event(state, "discard", {"card_id": cid, "controller": player_id})
            # The cycle trigger is put above the cycling ability, matching
            # activation-cost timing: the draw ability resolves first only
            # if no triggered ability was created.
            emit_event(state, "cycle", {"card_id": cid, "controller": player_id, "x_value": x_value})

        elif kind == "attack":
            ids = action.get("attackers", [])
            attack_targets = action.get("attack_targets", {})
            combat.declare_attackers(state, ids, attack_targets if isinstance(attack_targets, dict) else {})
            state.attackers_declared = True

        elif kind == "activate_ability":
            cid = action.get("card_id")
            if not cid or cid not in player.battlefield:
                apply_state_based_actions(state)
                return
            abilities = extract_activated_abilities(state.cards[cid])
            ability_index = int(action.get("ability_index", -1))
            ability = next((item for item in abilities if item["index"] == ability_index), None)
            if ability is None:
                apply_state_based_actions(state)
                return
            cost = ability["mana_cost"]
            if "{X}" in cost.upper():
                reject("Variable activated costs are unsupported")
                state.log.append("Variable activated costs are not yet supported; no costs paid.")
                return
            action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
            proxy = type("ActivatedOracleProxy", (), {"oracle_text": ability["text"], "name": state.cards[cid].name, "mana_cost": ""})()
            action_targets = enrich_divide_total(proxy, action_targets)
            hints = build_cast_hints(state, proxy, player_id, action_targets)
            if reject_invalid:
                from rules_engine.action_validation import require_declared_targets
                require_declared_targets(proxy, hints, action_targets, player_id)
            if hints.get("supports_divide") and "divide_total" not in action_targets:
                reject("Cannot derive this allocation total from the supported ability")
            valid, error = validate_cast_choice(hints, action_targets)
            if not valid:
                reject(error)
                state.log.append(f"Invalid activation targets: {error}")
                return
            valid, error = validate_hexproof_shroud_targets(state, player_id, action_targets)
            if not valid:
                reject(error)
                state.log.append(f"Invalid activation targets: {error}")
                return
            valid, error = validate_protection_targets(state, state.cards[cid], action_targets)
            if not valid:
                reject(error)
                state.log.append(f"Invalid activation targets: {error}")
                return
            if not apply_activated_costs(state, player_id, cid, cost):
                reject("Cannot pay activation costs")
                state.log.append(f"{player.name} cannot pay activation cost for {state.cards[cid].name}.")
                apply_state_based_actions(state)
                return
            resolved = build_ability_spec(state, proxy, player_id, action_targets=action_targets)
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{state.cards[cid].name} ability",
                is_spell=False,
                effect_key=resolved.effect.key,
                payload=resolved.effect.payload,
            )

        elif kind == "activate_loyalty":
            if not (state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack):
                state.log.append("Loyalty abilities can only be activated at sorcery speed on your turn.")
                apply_state_based_actions(state)
                return
            cid = action.get("card_id")
            ability_index = int(action.get("ability_index", -1))
            if not cid or cid not in player.battlefield:
                apply_state_based_actions(state)
                return
            if cid in state.loyalty_activated_this_turn:
                state.log.append(f"{state.cards[cid].name} already activated a loyalty ability this turn.")
                apply_state_based_actions(state)
                return
            pw = state.cards[cid]
            if "Planeswalker" not in pw.types:
                apply_state_based_actions(state)
                return
            abilities = extract_loyalty_abilities(pw)
            if ability_index < 0 or ability_index >= len(abilities):
                state.log.append(f"Invalid loyalty ability index for {pw.name}.")
                apply_state_based_actions(state)
                return
            ability = abilities[ability_index]
            current_loyalty = int(pw.loyalty or 0)
            if ability.get("x_cost"):
                x_value = int((action.get("targets") or {}).get("x_value", 0) or 0)
                if x_value < 0:
                    state.log.append(f"Invalid X value for {pw.name} loyalty ability.")
                    apply_state_based_actions(state)
                    return
                if ability.get("x_sign", -1) < 0:
                    next_loyalty = current_loyalty - x_value
                else:
                    next_loyalty = current_loyalty + x_value
            else:
                next_loyalty = current_loyalty + int(ability["delta"])
            if next_loyalty < 0:
                reject("Not enough loyalty for this ability")
                state.log.append(f"{pw.name} does not have enough loyalty for that ability.")
                apply_state_based_actions(state)
                return
            action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
            proxy = type("LoyaltyOracleProxy", (), {"oracle_text": ability["text"], "name": pw.name, "mana_cost": ""})()
            if ability.get("x_cost") and "x_value" not in action_targets:
                action_targets = dict(action_targets)
                action_targets["x_value"] = max(0, min(current_loyalty, int(action_targets.get("x_value", 0) or 0)))
            action_targets = enrich_divide_total(proxy, action_targets)
            hints = build_cast_hints(state, proxy, player_id, action_targets)
            if reject_invalid:
                from rules_engine.action_validation import require_declared_targets
                require_declared_targets(proxy, hints, action_targets, player_id)
            if hints.get("supports_divide") and "divide_total" not in action_targets:
                reject("Cannot derive this allocation total from the supported ability")
            valid, error = validate_cast_choice(hints, action_targets)
            if not valid:
                reject(error)
                state.log.append(f"Invalid targets for {pw.name}: {error}")
                return
            ok_hs, err_hs = validate_hexproof_shroud_targets(state, player_id, action_targets)
            if not ok_hs:
                reject(err_hs)
                state.log.append(f"Invalid targets for {pw.name}: {err_hs}")
                apply_state_based_actions(state)
                return
            ok_prot, err_prot = validate_protection_targets(state, pw, action_targets)
            if not ok_prot:
                reject(err_prot)
                state.log.append(f"Invalid targets for {pw.name}: {err_prot}")
                apply_state_based_actions(state)
                return
            pw.loyalty = next_loyalty
            state.loyalty_activated_this_turn.add(cid)
            ability = build_ability_spec(state, proxy, player_id, action_targets=action_targets)
            effect_key, payload = ability.effect.key, ability.effect.payload
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{pw.name} loyalty ability",
                is_spell=False,
                effect_key=effect_key,
                payload=payload,
            )

        elif kind == "crew":
            vehicle_id = action.get("card_id")
            vehicle = state.cards.get(vehicle_id) if vehicle_id else None
            selected = list(action.get("crew_card_ids") or [])
            required = crew_value(vehicle) if vehicle is not None else None
            from rules_engine.continuous import effective_power
            valid = (
                vehicle is not None
                and vehicle_id in player.battlefield
                and "Artifact" in vehicle.types
                and required is not None
                and len(selected) == len(set(selected))
                and all(
                    cid in player.battlefield
                    and cid != vehicle_id
                    and "Creature" in state.cards[cid].types
                    and not state.cards[cid].tapped
                    for cid in selected
                )
                and sum(max(0, effective_power(state, cid)) for cid in selected) >= required
            )
            if valid:
                for cid in selected:
                    state.cards[cid].tapped = True
                add_to_stack(
                    state, source_card_id=vehicle_id, controller=player_id,
                    label=f"{vehicle.name} crew", effect_key="crew_vehicle",
                    payload={"card_id": vehicle_id, "effect_timestamp": vehicle.effect_timestamp,
                             "crew_card_ids": selected}, is_spell=False,
                )
                state.log.append(f"{player.name} taps {len(selected)} creature(s) to crew {vehicle.name}.")
            else:
                reject("Crew selection does not satisfy the activation cost")

        elif kind == "equip":
            cid = action.get("card_id")
            target_id = action.get("target_card_id")
            if not cid or not target_id:
                apply_state_based_actions(state)
                return
            if cid not in player.battlefield:
                apply_state_based_actions(state)
                return
            equip_cost = _extract_equip_cost_text(state.cards[cid].oracle_text or "")
            if not equip_cost:
                apply_state_based_actions(state)
                return
            if not auto_pay_cost(state, player_id, equip_cost, card_name=state.cards[cid].name):
                reject("Cannot pay equipment cost")
                state.log.append(f"{player.name} cannot pay equip cost for {state.cards[cid].name}.")
                apply_state_based_actions(state)
                return
            if attach_if_legal(state, cid, target_id):
                state.log.append(f"{player.name} equips {state.cards[cid].name} to {state.cards[target_id].name}.")
            else:
                reject("Cannot legally equip this target")
                state.log.append(f"{player.name} cannot legally equip {state.cards[cid].name} to chosen target.")

        elif kind == "block":
            if getattr(state, "blockers_declared", False):
                apply_state_based_actions(state)
                return
            blocks = action.get("blocks", {})
            combat.declare_blockers(state, blocks)
            state.blockers_declared = True
            # After blockers are declared, the active player receives priority.
            # Without this handoff, the defending player can be re-queried in declare_blockers
            # and re-submit block actions indefinitely.
            state.priority_player = state.active_player
            state.passed_priority = set()

        elif kind == "combat_damage":
            combat.combat_damage(state)

        apply_state_based_actions(state)

    def legal_moves(self, state: MatchState, player_id: int) -> list[dict]:
        return legal_moves(state, player_id)

    def _handle_pregame_action(self, state: MatchState, player_id: int, action: dict) -> None:
        if player_id in state.kept_hands:
            remaining = [pid for pid in [1, 2] if pid not in state.kept_hands]
            if remaining:
                state.priority_player = remaining[0]
            return
        kind = action.get("type")
        player = state.players[player_id]
        if kind == "mulligan":
            if state.mulligan_count.get(player_id, 0) >= 7:
                return
            while player.hand:
                cid = player.hand.pop()
                player.library.append(cid)
                state.cards[cid].zone = Zone.LIBRARY
            rng = getattr(state, "rng", None)
            if rng is not None and hasattr(rng, "shuffle"):
                rng.shuffle(player.library)
            else:
                import random

                random.shuffle(player.library)
            for _ in range(7):
                draw_card(state, player_id)
            state.mulligan_count[player_id] = state.mulligan_count.get(player_id, 0) + 1
            state.log.append(f"{player.name} takes a mulligan to {7 - state.mulligan_count[player_id]}.")
            remaining = [pid for pid in [1, 2] if pid not in state.kept_hands]
            if remaining:
                state.priority_player = remaining[0]
            return
        if kind == "keep_hand":
            bottom = action.get("bottom_card_ids", [])
            need_bottom = state.mulligan_count.get(player_id, 0)
            chosen = [cid for cid in bottom if cid in player.hand][:need_bottom]
            if len(chosen) < need_bottom:
                chosen += _auto_bottom_cards(state, player_id, need_bottom - len(chosen), exclude=set(chosen))
            for cid in reversed(chosen):
                if cid in player.hand:
                    player.hand.remove(cid)
                    player.library.insert(0, cid)
                    state.cards[cid].zone = Zone.LIBRARY
            state.kept_hands.add(player_id)
            state.log.append(f"{player.name} keeps hand.")
            if len(state.kept_hands) == 2:
                state.pregame_pending = False
                state.priority_player = state.active_player
                state.step = Step.UNTAP
                self._apply_step_start_actions(state)
                state.log.append("Pregame complete. Proceeding to turn structure.")
            else:
                remaining = [pid for pid in [1, 2] if pid not in state.kept_hands]
                if remaining:
                    state.priority_player = remaining[0]


def _infer_mana_from_land(name: str, oracle_text: str = "", requested_color: str | None = None) -> str:
    import re

    colors = _land_colors_from_metadata(name, oracle_text)
    req = (requested_color or "").strip().upper()
    if req in colors:
        return req
    if colors:
        # Deterministic default when no requested color is provided.
        for preferred in ["U", "B", "R", "G", "W", "C"]:
            if preferred in colors:
                return preferred
    return "C"


def _land_colors_from_metadata(name: str, oracle_text: str = "") -> set[str]:
    import re

    n = name.lower()
    colors: set[str] = set()
    dual_pref = {
        "hallowed fountain": {"W", "U"},
        "sacred foundry": {"R", "W"},
        "watery grave": {"U", "B"},
        "blood crypt": {"B", "R"},
        "overgrown tomb": {"B", "G"},
        "breeding pool": {"U", "G"},
        "stomping ground": {"R", "G"},
        "steam vents": {"U", "R"},
        "godless shrine": {"W", "B"},
        "temple garden": {"W", "G"},
    }
    if n in dual_pref:
        colors |= dual_pref[n]
    if "plains" in n:
        colors.add("W")
    if "island" in n:
        colors.add("U")
    if "swamp" in n:
        colors.add("B")
    if "mountain" in n:
        colors.add("R")
    if "forest" in n:
        colors.add("G")
    for sym in re.findall(r"\{([WUBRGC])\}", (oracle_text or "").upper()):
        colors.add(sym)
    if not colors:
        colors.add("C")
    return colors


def _auto_bottom_cards(state: MatchState, player_id: int, count: int, exclude: set[str] | None = None) -> list[str]:
    from rules_engine.mana import parse_mana_cost

    exclude = exclude or set()
    hand_cards = [state.cards[cid] for cid in state.players[player_id].hand if cid not in exclude]
    scored = []
    for card in hand_cards:
        land_bias = -3 if "Land" in card.types else 0
        cmc = mana_value(card.mana_cost, is_land=("Land" in card.types))
        score = cmc + land_bias
        scored.append((score, card.id))
    scored.sort(reverse=True)
    return [cid for _, cid in scored[: max(0, count)]]


def _extract_equip_cost_text(oracle_text: str) -> str:
    import re
    m = re.search(r"Equip\s+(\{[^}]+\}(?:\{[^}]+\})*)", oracle_text or "", flags=re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _select_face_for_cast(card, selected_face_index) -> object:
    from rules_engine.card_faces import select_cast_face
    return select_cast_face(card, selected_face_index)
