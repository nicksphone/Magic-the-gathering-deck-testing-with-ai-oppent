from __future__ import annotations
from rules_engine.type_effects import effective_types


from game_state.state import MatchState, StackItem, Step, TURN_STEPS, Zone, assign_static_order_on_battlefield_entry, draw_card, pregame_actor, object_incarnation
from rules_engine import combat
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.cast_choice import build_cast_hints, enrich_divide_total, validate_cast_choice
from rules_engine.card_types import is_land_card as _is_land_card
from rules_engine.costs import activated_cost_available, apply_activated_costs, apply_additional_costs, check_cost_option_available, collect_cost_options, normalize_cost_choice, casting_method
from rules_engine.cycling import cycling_cost, cycling_is_variable, cycling_variant
from rules_engine.mana import auto_pay_cost, mana_value
from rules_engine.mana import land_can_produce_mana, land_mana_amount, land_mana_colors
from rules_engine.move_generator import legal_moves
from rules_engine.library_permissions import choose_type_for_realmwalker, top_library_creature_for_type
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.oracle_effects import crew_value, extract_activated_abilities, extract_loyalty_abilities, extract_saga_chapters
from rules_engine.ability_model import build_ability_spec, build_spell_spec
from rules_engine.priority import pass_priority
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.targeting import validate_hexproof_shroud_targets, validate_protection_targets
from rules_engine.events import emit_event, emit_event_batch, flush_staged_triggers, resume_trigger_order, resume_trigger_target
from rules_engine.restrictions import can_activate_in_current_timing, can_cast_in_current_timing
from rules_engine.ward import capture_ward_triggers
from rules_engine.zone_actions import put_into_graveyard
from rules_engine.attachments import attachment_target_is_legal, is_aura
from effects.registry import resolve_effect


class RulesEngine:
    def advance_no_priority_step(self, state: MatchState) -> bool:
        """End an already-entered untap step, never submit a player action."""
        if (state.step != Step.UNTAP or state.pregame_pending or state.winner is not None
                or state.stack or state.pending_mechanic_choice
                or state.pending_replacement_choice or state.pending_trigger_order):
            return False
        # Entry already performed untapping (including stun); do not repeat it.
        self.next_step(state)
        return True

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
            state.spells_cast_this_turn = {1: 0, 2: 0}
            state.kicked_spells_cast_this_turn = {1: 0, 2: 0}
            state.foretells_this_turn = {1: 0, 2: 0}
            state.declared_attackers_this_turn = {1: 0, 2: 0}
            state.draws_this_turn = {1: 0, 2: 0}
            state.surveils_this_turn = {1: 0, 2: 0}
            state.discards_this_turn = {1: 0, 2: 0}
            state.land_entries_this_turn = {1: 0, 2: 0}
            state.land_entry_history_known = True
            state.players_with_permanent_departure = set()
            state.step = TURN_STEPS[0]
            state.loyalty_activated_this_turn = set()
            state.trigger_once_seen_this_turn = set()
            player = state.players[state.active_player]
            for cid in list(player.battlefield):
                card = state.cards[cid]
                if card.entered_turn < state.turn:
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
                state.attack_bands = []
                state.attackers_declared = False
                state.combat_damage_resolved = False
                state.combat_damage_stage = "none"
                state.first_strike_damage_ids = set()
                state.combat_damage_assignments = {}
                state.combat_assignment_queue = []
            elif state.step == Step.DECLARE_BLOCKERS:
                state.blockers_declared = False
            elif state.step == Step.COMBAT_DAMAGE:
                combat.begin_combat_damage(state)
                apply_state_based_actions(state)
            elif state.step == Step.POSTCOMBAT_MAIN:
                state.attackers = []
                state.attack_bands = []
                state.attack_targets = {}
                state.blocks = {}
                state.attackers_declared = False
                state.blockers_declared = False
                state.combat_damage_assignments = {}
                state.combat_assignment_queue = []

        self._apply_step_start_actions(state)
        if state.step == Step.UNTAP:
            # Untap has no priority window; upkeep is the first response window.
            self.next_step(state)
            return
        if not state.pending_mechanic_choice and not state.pending_replacement_choice and not state.pending_trigger_order:
            state.priority_player = 3 - state.active_player if state.step == Step.DECLARE_BLOCKERS and not state.blockers_declared else state.active_player
            state.passed_priority = set()

    def _apply_step_start_actions(self, state: MatchState) -> None:
        player = state.players[state.active_player]
        if state.step == Step.UNTAP:
            # Untap triggers wait with upkeep triggers for the first priority window.
            if not state.trigger_staging:
                state.trigger_staging = True
                state.trigger_staging_event = "untap"
            self._update_day_night(state)
            from rules_engine.named_counters import untap_permanent
            for cid in player.battlefield:
                untap_permanent(state, cid, turn_based=True)
            state.log.append(f"{player.name} untaps.")
        elif state.step == Step.UPKEEP:
            staged_here = not state.trigger_staging or state.trigger_staging_event == "untap"
            if staged_here:
                state.trigger_staging = True
                state.trigger_staging_event = "begin_step"
            emit_event(state, "begin_step", {"step": "upkeep", "active_player": state.active_player})
            if staged_here:
                flush_staged_triggers(state)
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
        elif state.step == Step.END_COMBAT:
            emit_event(state, "begin_step", {"step": "end_combat", "active_player": state.active_player})
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
        state.combat_cost_effects = [row for row in state.combat_cost_effects if row['expires_turn'] > state.turn]
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
        from rules_engine.type_effects import refresh_type_effects
        for card in state.cards.values():
            expired = [effect for effect in card.type_effects if effect['until_end_of_turn']]
            if expired:
                was_creature = 'Creature' in card.types
                card.type_effects = [effect for effect in card.type_effects if not effect['until_end_of_turn']]
                refresh_type_effects(card)
                state.log.append(f"{card.name} is no longer a creature after cleanup." if was_creature and 'Creature' not in card.types
                                 else f"Temporary type effects end for {card.name} after cleanup.")
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
        effects = []
        for cid in list(state.players[state.active_player].battlefield):
            card = state.cards.get(cid)
            if card is None or card.zone != Zone.BATTLEFIELD or "Saga" not in (card.type_line or ""):
                continue
            if not extract_saga_chapters(card.oracle_text):
                continue
            effects.append({'effect_key': 'add_counters', 'payload': {
                'target_card_id': cid, 'counter': 'lore', 'amount': 1,
                '__counter_is_effect': False, 'effect_timestamp': object_incarnation(card),
            }})
        if not effects:
            return
        started_staging = not state.trigger_staging
        if started_staging:
            state.trigger_staging = True
            state.trigger_staging_event = 'saga_lore_added'
        # No priority, SBA or chapter publication between this turn-based batch's
        # placements. The ordinary durable effect queue resumes a paused batch.
        resolve_effect(state, state.active_player, 'effect_sequence', {'effects': effects})
        if started_staging and not state.pending_replacement_choice:
            flush_staged_triggers(state)

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
                card.summoning_sick = True
                card.entered_turn = state.turn
                state.log.append(f"Control of {card.name} returns to {state.players[original].name}.")
            state.temporary_control_changes.pop(cid, None)

    def _update_day_night(self, state: MatchState) -> None:
        """Check an established designation before the active player's untapping."""
        if state.turn <= 1:
            return
        cast_count = int(getattr(state, "spells_cast_last_turn", 0) or 0)
        previous = str(getattr(state, "day_night", "none") or "none")
        next_state = previous
        if previous == "day" and cast_count == 0:
            next_state = "night"
        elif previous == "night" and cast_count >= 2:
            next_state = "day"
        if next_state == previous:
            return
        state.day_night = next_state
        state.log.append(f"The game becomes {next_state}.")
        staged_here = not state.trigger_staging
        if staged_here:
            state.trigger_staging = True
            state.trigger_staging_event = "day_night_changed"
        emit_event(state, "day_night_changed", {"from": previous, "to": next_state, "spell_count": cast_count})
        self._transform_day_night_permanents(state, next_state)
        if staged_here:
            flush_staged_triggers(state)

    def _transform_day_night_permanents(self, state: MatchState, current: str) -> None:
        target_marker = "daybound" if current == "night" else "nightbound"
        target_face = 1 if current == "night" else 0
        transformed_events = []
        for player in state.players.values():
            for cid in list(player.battlefield):
                card = state.cards[cid]
                if not card.card_faces or target_marker not in (card.oracle_text or "").lower():
                    continue
                if target_face >= len(card.card_faces):
                    continue
                previous_face = card.selected_face_index
                resolve_effect(
                    state,
                    card.controller,
                    "transform_card",
                    {"target_card_id": cid, "face_index": target_face, "__defer_transform_event": True},
                )
                if card.selected_face_index != previous_face:
                    transformed_events.append({
                        "card_id": cid, "controller": card.controller,
                        "from_face_index": previous_face, "to_face_index": target_face,
                    })
        emit_event_batch(state, "transformed", transformed_events)

    def _clear_mana_pools(self, state: MatchState) -> None:
        for p in state.players.values():
            for color in p.mana_pool:
                p.mana_pool[color] = 0
            for color in p.snow_mana_pool:
                p.snow_mana_pool[color] = 0
            p.restricted_mana_pool.clear()

    def _clear_marked_damage(self, state: MatchState) -> None:
        for card in state.cards.values():
            card.granted_flashback.clear()
            card.keyword_effects = [effect for effect in getattr(card,'keyword_effects',[]) if not effect['until_end_of_turn']]
            card.base_stat_effects = [effect for effect in getattr(card,'base_stat_effects',[]) if not effect['until_end_of_turn']]
            if "__damage_marked" in card.counters:
                card.counters.pop("__damage_marked", None)
            if "__deathtouch_damaged" in card.counters:
                card.counters.pop("__deathtouch_damaged", None)
            if "__eot_power" in card.counters:
                card.counters.pop("__eot_power", None)
            if "__eot_toughness" in card.counters:
                card.counters.pop("__eot_toughness", None)
            for counter in list(card.counters):
                if counter.startswith("__eot_keyword_"):
                    card.counters.pop(counter, None)

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

    def take_action(self, state: MatchState, player_id: int, action: dict, *, reject_invalid: bool = False, effect_cast: bool = False, suspend_cast: bool = False) -> None:
        def reject(reason: str) -> None:
            if reject_invalid:
                from rules_engine.action_validation import ActionRejected
                raise ActionRejected(reason)

        if state.winner is not None:
            return
        kind = action.get("type")
        if kind in {'cast_spell', 'activate_ability', 'activate_loyalty', 'equip', 'crew', 'cycle_card', 'ninjutsu'}:
            from rules_engine.restrictions import split_second_active
            if split_second_active(state):
                reject("Split second prevents spells and nonmana activated abilities")
                return
        if kind in {'activate_ability', 'activate_loyalty', 'equip', 'crew'}:
            from rules_engine.continuous import printed_abilities_suppressed
            if printed_abilities_suppressed(state, action.get('card_id')):
                reject("This permanent has lost its printed abilities")
                return
        if state.pending_mechanic_choice:
            if state.pending_mechanic_choice['kind'] == 'suspend_cast':
                from rules_engine.suspend import finish_cast_choice
                if not finish_cast_choice(state, player_id, action):
                    reject('Invalid suspend casting choice')
                return
            if state.pending_mechanic_choice['kind'] == 'effect_cast':
                from rules_engine.effect_casts import finish_cast_choice
                if not finish_cast_choice(state, player_id, action):
                    reject('Invalid effect-authorized casting choice')
                return
            if state.pending_mechanic_choice["kind"] in {"opening_hand", "opening_hand_exile"}:
                from rules_engine.opening_hand import finish_opening_hand_choice
                if kind != "choose_mechanic" or not finish_opening_hand_choice(state, player_id, action):
                    reject("Invalid opening-hand action")
                elif state.pending_mechanic_choice is None and not state.pending_replacement_choice:
                    self._finish_pregame(state)
                return
            if state.pending_mechanic_choice["kind"] == "mulligan_bottom":
                if kind != "choose_mechanic" or not self._finish_mulligan_bottom(state, player_id, action):
                    reject("Invalid mulligan bottom selection")
                return
            if state.pending_mechanic_choice["kind"] == "cleanup_discard":
                if kind == "choose_mechanic":
                    if not self.choose_cleanup_discards(state, player_id, action):
                        reject("Invalid cleanup discard selection")
                return
            if state.pending_mechanic_choice["kind"] == "combat_damage":
                if kind == "choose_mechanic" and combat.finish_damage_assignment(state, player_id, action):
                    apply_state_based_actions(state)
                else:
                    reject("Invalid combat damage assignment")
                return
            from rules_engine.keyword_actions import finish_mechanic_choice
            if kind == "choose_mechanic":
                choice_kind = state.pending_mechanic_choice["kind"]
                if finish_mechanic_choice(state, player_id, action):
                    if choice_kind != "land_entry" or not (state.pending_mechanic_choice or state.pending_replacement_choice):
                        apply_state_based_actions(state)
                else:
                    reject("Invalid mechanic choice")
            return

        if state.pregame_pending and not state.pending_replacement_choice:
            if player_id != pregame_actor(state) or kind not in {"keep_hand", "mulligan"}:
                reject("Not this player's mulligan declaration window")
                return
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
                if kind != "choose_trigger_target" or not resume_trigger_target(state, str(action.get("stack_id", "")), action.get("target_card_id"), action.get("target_player")):
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
            if pending.get('resume_kind') == 'counter_event':
                from rules_engine.stack_engine import resume_paused_resolution
                state.pending_replacement_choice = None
                resolve_effect(state, int(pending['controller']), pending['counter_effect'],
                               {**pending['counter_payload'], '__counter_choice': chosen_id})
                resume_paused_resolution(state, pending)
                if state.pregame_pending:
                    if not state.pending_replacement_choice and not state.pending_mechanic_choice:
                        self._finish_pregame(state)
                elif not state.pending_replacement_choice and not state.pending_mechanic_choice:
                    apply_state_based_actions(state)
                return
            if pending.get("resume_kind") == "gain_event":
                from rules_engine.stack_engine import resume_paused_resolution

                state.pending_replacement_choice = None
                state.log.append(f"{state.players[player_id].name} chooses replacement source {chosen_id}.")
                resolve_effect(
                    state, int(pending["controller"]), "gain_life",
                    {**pending["gain_payload"], "__replacement_source_id": chosen_id},
                )
                resume_paused_resolution(state, pending)
                if not state.pending_replacement_choice and not state.pending_mechanic_choice and not pending.get("combat_damage_needs_sba"):
                    apply_state_based_actions(state)
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
            if pending.get("resume_kind") in {"damage_chain", "damage_batch"}:
                state.pending_replacement_choice = None
                state.log.append(
                    f"{state.players[player_id].name} chooses replacement source {chosen_id}."
                )
                from effects.handlers import deal_damage
                dealt = deal_damage(
                    state,
                    int(pending.get("controller", player_id)),
                    {
                        "target_player": pending.get("target_player"),
                        "target_card_id": pending.get("target_card_id"),
                        "amount": int(pending.get("amount", 0) or 0),
                        "__source_card_id": pending.get("source_card_id"),
                        "__source_lki": pending.get("source_lki"),
                        "__replacement_source_id": chosen_id,
                        "__used_replacement_source_ids": list(pending.get("selected_source_ids") or [])
                        + [chosen_id],
                        "__defer_lethal": bool(pending.get("batch_damage") or pending.get("resume_kind") == "damage_batch"),
                        "__batch_damage": bool(pending.get("batch_damage") or pending.get("resume_kind") == "damage_batch"),
                    },
                )
                if pending.get("batch_damage") or pending.get("resume_kind") == "damage_batch":
                    from rules_engine.damage_results import source_has_keyword
                    source_id = pending.get("source_card_id")
                    if dealt and source_has_keyword(state, source_id, "lifelink", pending.get("source_lki")):
                        for item in pending.get("continuation_effects", []):
                            if item.get("effect_key") == "deal_damage_batch":
                                item["payload"]["lifelink_total"] = int(item["payload"].get("lifelink_total", 0)) + dealt
                                break
                from rules_engine.stack_engine import resume_paused_resolution
                resume_paused_resolution(state, pending)
                if not (pending.get("batch_damage") or pending.get("resume_kind") == "damage_batch"):
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

        if state.step == Step.UNTAP:
            if kind == "pass_priority":
                self.next_step(state)
            else:
                reject("Players do not receive priority during the untap step")
            return

        if state.cleanup_pending and state.step == Step.CLEANUP:
            self._finish_cleanup(state)
            if state.pending_trigger_order or state.pending_replacement_choice:
                return
        if state.step == Step.CLEANUP and not state.cleanup_repeat_required and kind != "pass_priority":
            return
        if kind == "pass_priority":
            if not state.stack and state.step == Step.DECLARE_ATTACKERS and not state.attackers_declared and player_id == state.active_player:
                combat.declare_attackers(state, [])
                state.attackers_declared = True
            if not state.stack and state.step == Step.DECLARE_BLOCKERS and not state.blockers_declared and player_id != state.active_player:
                combat.declare_blockers(state, {})
                state.blockers_declared = True
                state.priority_player = state.active_player
                state.passed_priority = set()
                apply_state_based_actions(state)
                return
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

        if state.priority_player != player_id and not (effect_cast and kind == 'cast_spell'):
            return

        player = state.players[player_id]
        if kind == 'suspend':
            from rules_engine.suspend import take_special_action
            if not take_special_action(state, player_id, action.get('card_id')):
                reject('Cannot suspend this card or pay its special-action cost')
                return
        elif kind == 'foretell':
            from rules_engine.foretell import take_special_action
            if not take_special_action(state, player_id, action.get('card_id')):
                reject('Cannot foretell this card or pay its special-action cost')
        elif kind == "ninjutsu":
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
            from_graveyard = bool(action.get('from_graveyard'))
            if (from_graveyard and from_exile) or (action.get('graveyard_permission_key') and not from_graveyard):
                reject('A graveyard permission requires an unambiguous graveyard source')
                return
            from rules_engine.graveyard_permissions import graveyard_land_permission, battlefield_entry_prohibited
            permission_key = None
            if from_graveyard:
                from rules_engine.graveyard_permissions import graveyard_land_choices
                permissions = graveyard_land_choices(state, player_id, cid)
                requested = action.get('graveyard_permission_key')
                permission = next((grant for grant in permissions if grant['key'] == requested), None) if requested else next(iter(permissions), None)
                if permission is None:
                    reject('The selected graveyard land permission is unavailable')
                    return
                permission_key = permission['key']
            allowed_source = (exile_permission(state, player_id, cid, face_index) if from_exile
                              else graveyard_land_permission(state, player_id, cid) if from_graveyard
                              else cid in player.hand)
            if battlefield_entry_prohibited(state, cid, face_index):
                reject('A battlefield ability prohibits this land entering from its source zone')
                return
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
                from rules_engine.entry import apply_entry_choice, land_entry_options
                entry_options = land_entry_options(state, player_id, face)
                entry_choice = action.get("entry_choice")
                if (entry_options and entry_choice not in entry_options) or (not entry_options and entry_choice is not None):
                    reject("Unavailable land-entry choice")
                    return
                if from_exile:
                    leave_exile(state, cid)
                    departures = []
                elif from_graveyard:
                    from rules_engine.resource_events import capture_graveyard_departures
                    departures = capture_graveyard_departures(state, [cid])
                    player.graveyard.remove(cid)
                else:
                    player.hand.remove(cid)
                    departures = []
                if not state.trigger_staging:
                    state.trigger_staging = True
                    state.trigger_staging_event = "land_play"
                apply_cast_face(card, face)
                apply_entry_choice(state, player_id, card, choice=entry_choice or "tapped")
                player.battlefield.append(cid)
                player.lands_played_this_turn = used_land_plays + 1
                player.land_plays_recorded_on_turn = used_land_plays + 1
                player.last_land_play_turn = state.turn
                card.move_to_zone(Zone.BATTLEFIELD)
                state.cards[cid].summoning_sick = True
                assign_static_order_on_battlefield_entry(state, cid)
                state.log.append(f"{player.name} plays {state.cards[cid].name}.")
                if permission_key:
                    from rules_engine.graveyard_permissions import record_graveyard_permission
                    record_graveyard_permission(state, permission_key)
                if departures:
                    from rules_engine.resource_events import emit_graveyard_departures
                    emit_graveyard_departures(state, departures)
                emit_event(state, "enters_battlefield", {"card_id": cid, "controller": player_id})

        elif kind == 'activate_mana_ability':
            from rules_engine.mana_abilities import activate_mana_ability
            if not activate_mana_ability(state, player_id, action['card_id'], action['ability_index'], action['color'],
                                         payment_choices=action.get('payment_choices'),
                                         hybrid_choices=action.get('hybrid_choices'),
                                         output_bundle=action.get('output_bundle')):
                reject('Cannot activate selected mana ability')
                return

        elif kind == "tap_land_for_mana":
            cid = action["card_id"]
            if cid in player.battlefield and land_can_produce_mana(state, cid, free_only=False):
                from rules_engine.mana_abilities import tap_only_outputs
                colors = set(tap_only_outputs(state, state.cards[cid]))
                if action.get("color") and action["color"] not in colors:
                    reject("Land cannot produce the selected color now")
                    return
                color = action.get("color") or next(color for color in "UBRGWC" if color in colors)
                amount = land_mana_amount(state, player_id, cid, color)
                from rules_engine.mana_abilities import preferred_free_spec
                spec = preferred_free_spec(state, state.cards[cid], color, amount, tap_only=True)
                if spec is None:
                    reject('Cannot select mana ability')
                    return
                from rules_engine.mana_abilities import activate_mana_ability
                if not activate_mana_ability(state, player_id, cid, spec[0], color):
                    reject('Cannot pay mana ability costs')
                    return
                state.log.append(f"{player.name} taps {state.cards[cid].name} for {amount} {color}.")

        elif kind == "tap_nonland_for_mana":
            cid = action["card_id"]
            color = action["color"]
            from rules_engine.mana_abilities import mana_ability_views, activate_mana_ability
            views = mana_ability_views(state, state.cards[cid]) if cid in player.battlefield else []
            choices = [view for view in views if color in view['outputs'] and (
                view['outputs'][color] > 0 or sum(view.get('output_bundles', {}).get(color, {}).values()) > 0)]
            if choices:
                spec = max(choices, key=lambda view: view['outputs'][color])
                if not activate_mana_ability(state, player_id, cid, spec['ability_index'], color):
                    reject('Cannot activate mana source')
                    return

        elif kind == "tap_lands_bulk":
            from rules_engine.action_validation import ActionRejected, validate_tap
            try:
                validate_tap(state, player_id, action)
            except ActionRejected as error:
                reject(str(error))
                return
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
                    if not land_can_produce_mana(state, cid, free_only=False):
                        continue
                    if card.name.strip().lower() != land_name:
                        continue
                    colors = land_mana_colors(card, state)
                    if action.get("color") and action["color"] not in colors:
                        continue
                    color = action.get("color") or next(color for color in "UBRGWC" if color in colors)
                    amount = land_mana_amount(state, player_id, cid, color)
                    from rules_engine.mana_abilities import preferred_free_spec
                    spec = preferred_free_spec(state, card, color, amount, tap_only=True)
                    if spec is None:
                        reject('Cannot select mana ability')
                        return
                    from rules_engine.mana_abilities import activate_mana_ability
                    if not activate_mana_ability(state, player_id, cid, spec[0], color):
                        reject('Cannot pay mana ability costs')
                        return
                    produced = color
                    produced_total += amount
                    tapped += 1
                if tapped != count:
                    reject('Cannot pay all requested mana ability costs')
                    return
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
                (effect_cast and suspend_cast and cid in player.exile) or exile_permission(state, player_id, cid, chosen_face)
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
                from rules_engine.bestow import bestow_cost, bestow_cast_view
                bestowed = casting_method((action.get('cost_choice') or {}).get('id', '')) == 'bestow'
                if bestowed:
                    if not bestow_cost(face_card):
                        reject('This card has no bestow cost')
                        return
                    face_card = bestow_cast_view(face_card)
                timing_ok, timing_reason = can_cast_in_current_timing(state, face_card, player_id, during_resolution=effect_cast)
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
                options = collect_cost_options(state, player_id, face_card, without_mana=effect_cast)
                options = [option for option in options if (casting_method(option.id) == 'bestow') == bestowed]
                if not options:
                    reject("No supported casting cost")
                    return
                choice_id = (action.get('cost_choice') or {}).get('id')
                if choice_id and not any(option.id == choice_id for option in options):
                    reject('The selected casting cost or permission is unavailable')
                    return
                chosen = normalize_cost_choice(action, options)
                from rules_engine.alternative_casts import validate_escape_exiles
                escape_ids = validate_escape_exiles(state, player_id, cid, chosen.exile_graveyard, action.get("escape_exile_ids")) if casting_method(chosen.id) == "escape" else []
                if escape_ids is None:
                    reject("Invalid escape exile selection")
                    state.log.append("Invalid escape exile selection.")
                    return
                # Extract x_value early — needed for cost checking and payment
                at_targets = action.get("targets", {}) if isinstance(action, dict) else {}
                x_value = int(at_targets.get("x_value", 0) or 0)
                if choice_id and chosen.graveyard_permission_max_mana_value is not None:
                    from rules_engine.mana import mana_value
                    from rules_engine.alternative_casts import spell_cast_view
                    permission_view = spell_cast_view(face_card, casting_method(chosen.id))
                    if mana_value(permission_view.mana_cost or '', x_value=x_value) > chosen.graveyard_permission_max_mana_value:
                        reject('This spell exceeds the graveyard permission mana-value limit')
                        return
                if effect_cast and '{x}' in (face_card.mana_cost or '').lower() and x_value != 0:
                    reject('X must be zero when casting without paying its mana cost')
                    return
                if not check_cost_option_available(state, player_id, face_card, chosen, x_value=x_value, target_card_id=at_targets.get("target_card_id")):
                    explicit_choice = bool(((action.get("cost_choice") or {}).get("id")))
                    if not explicit_choice:
                        chosen = next(
                            (
                                opt
                                for opt in options
                                if check_cost_option_available(state, player_id, face_card, opt, x_value=x_value, target_card_id=at_targets.get("target_card_id"))
                            ),
                            chosen,
                        )
                    if not check_cost_option_available(state, player_id, face_card, chosen, x_value=x_value, target_card_id=at_targets.get("target_card_id")):
                        reject("Cannot satisfy chosen casting costs")
                        state.log.append(f"{player.name} cannot satisfy chosen costs for {card.name}.")
                        apply_state_based_actions(state)
                        return
                selected_face_index = action.get("selected_face_index")
                if selected_face_index is None and isinstance(at_targets, dict):
                    selected_face_index = at_targets.get("selected_face_index")
                face_card = _select_face_for_cast(card, selected_face_index)
                if bestowed:
                    face_card = bestow_cast_view(face_card)
                from rules_engine.kicker import spell_kicker_view
                printed_face_card = face_card
                from rules_engine.alternative_casts import spell_cast_view
                face_card = spell_cast_view(face_card, casting_method(chosen.id))
                face_card = spell_kicker_view(face_card, chosen.kicked)
                action_targets = enrich_divide_total(face_card, at_targets)
                if face_card is not card:
                    action_targets = dict(action_targets)
                    action_targets.setdefault("selected_face_index", selected_face_index if selected_face_index is not None else 0)
                from rules_engine.cast_choice import build_cost_cast_hints
                hints = build_cost_cast_hints(state, face_card, player_id, chosen, action_targets)
                if reject_invalid:
                    from rules_engine.action_validation import require_declared_targets
                    require_declared_targets(face_card, hints, action_targets, player_id, spell=True)
                if hints.get("supports_divide") and "divide_total" not in action_targets:
                    reject("Cannot derive this allocation total from the supported card effect")
                ok_prot, err_prot = validate_protection_targets(state, face_card, action_targets)
                if not ok_prot:
                    reject(err_prot)
                    state.log.append(f"Invalid targets for {card.name}: {err_prot}")
                    apply_state_based_actions(state)
                    return
                ok_hs, err_hs = validate_hexproof_shroud_targets(state, player_id, action_targets, face_card)
                if not ok_hs:
                    reject(err_hs)
                    state.log.append(f"Invalid targets for {card.name}: {err_hs}")
                    apply_state_based_actions(state)
                    return
                ok, error = validate_cast_choice(hints, action_targets)
                if not ok:
                    reject(error)
                    state.log.append(f"Invalid targets for {card.name}: {error}")
                    apply_state_based_actions(state)
                    return
                if action_targets.get("mode_targets") is not None:
                    from rules_engine.cast_choice import validate_mode_targets
                    ok, error = validate_mode_targets(state, face_card, player_id, action_targets)
                    if not ok:
                        reject(error)
                        state.log.append(f"Invalid mode targets for {card.name}: {error}")
                        apply_state_based_actions(state)
                        return
                # Actual announced choices are available; no mana/additional costs yet.
                admission = build_spell_spec(state, face_card, player_id, action_targets=action_targets,
                                            report_unsupported=False)
                if admission.unsupported_resolution:
                    reason = 'Unsupported spell resolution: ' + ', '.join(admission.unsupported_resolution)
                    reject(reason)
                    state.log.append(reason)
                    return
                ward_specs = capture_ward_triggers(state, player_id, {"__announced_targets": action_targets})
                from rules_engine.costs import additional_cost_selection
                selected_cost_cards = additional_cost_selection(
                    state, player_id, chosen, cid, action.get('cost_choice'), x_value=x_value)
                if selected_cost_cards is None:
                    reject('Invalid additional-cost card selection')
                    return
                # Preserve fixed-count announcements through mana activation.
                # Exhaustive costs still select all remaining cards after mana.
                frozen_cost_choice = dict(action.get('cost_choice') or {})
                reserved_cost_cards = {cid, *escape_ids}
                for key, exhaustive in (('discard_card_ids', chosen.discard_all),
                                        ('sacrifice_card_ids', chosen.sacrifice_all)):
                    if not exhaustive:
                        frozen_cost_choice[key] = selected_cost_cards[key]
                        reserved_cost_cards.update(selected_cost_cards[key])
                adjusted_cost = chosen.mana_cost
                cost_staging = not state.trigger_staging
                if cost_staging:
                    state.trigger_staging = True
                    state.trigger_staging_event = "spell_cast"
                payment_details: dict = {}
                paid = auto_pay_cost(
                    state, player_id, adjusted_cost, is_land=("Land" in effective_types(state, face_card)),
                    card_name=face_card.name, x_value=x_value, spell_types=set(effective_types(state, face_card)),
                    oracle_text=face_card.oracle_text or "",
                    spell_is_aura=bestowed or is_aura(face_card),
                    spell_kicked=chosen.kicked,
                    hybrid_choices=action.get("hybrid_choices"),
                    reserved_life=chosen.pay_life + (x_value if chosen.pay_life_x else 0),
                    payment_details=payment_details,
                    source_card_id=cid, target_card_id=action_targets.get("target_card_id"),
                    cast_resource_card=face_card, resource_choices=action.get('resource_payment'),
                    reserved_card_ids=reserved_cost_cards,
                )
                if not paid:
                    if cost_staging:
                        state.staged_triggers.clear()
                        state.trigger_staging = False
                    reject("Cannot pay spell cost")
                    state.log.append(f"{player.name} cannot pay mana cost for {card.name}.")
                    apply_state_based_actions(state)
                    return
                spell_cost_context: dict = {}
                if not apply_additional_costs(state, player_id, chosen, cid, x_value=x_value,
                                              choice=frozen_cost_choice, context=spell_cost_context):
                    if cost_staging:
                        state.staged_triggers.clear()
                        state.trigger_staging = False
                    reject("Cannot pay additional casting costs")
                    state.log.append(f"{player.name} failed additional costs for {card.name}.")
                    apply_state_based_actions(state)
                    return
                from copy import copy
                effect_surface = copy(face_card)
                effect_surface.paid_cost_context = spell_cost_context
                ability = build_spell_spec(state, effect_surface, player_id, action_targets=action_targets)
                effect_key, payload = ability.effect.key, ability.effect.payload
                payload["__announced_targets"] = dict(action_targets)
                payload['mana_spent'] = payment_details.get('mana_spent', 0)
                if payment_details.get('resource_payment') is not None:
                    payload['__casting_resource_payment'] = payment_details['resource_payment']
                payload['__kicked'] = chosen.kicked
                payload["__ward_trigger_specs"] = ward_specs
                payload["snow_mana_spent"] = payment_details.get("snow_mana_spent", 0)
                payload["snow_mana_colors"] = payment_details.get("snow_mana_colors", {})
                if "Planeswalker" in effective_types(state, face_card) and "compleated" in face_card.oracle_text.lower():
                    payload["__phyrexian_life_symbols"] = payment_details.get("phyrexian_life_symbols", 0)
                if effect_key == "look_top_select_hand":
                    payload["mana_spent_to_cast"] = payment_details.get('mana_spent', 0)
                if x_value > 0:
                    payload.setdefault("x_value", x_value)

                from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
                departures = capture_graveyard_departures(state, escape_ids)
                for exile_id in escape_ids:
                    player.graveyard.remove(exile_id)
                    player.exile.append(exile_id)
                    state.cards[exile_id].move_to_zone(Zone.EXILE)
                emit_graveyard_departures(state, departures)
                if casting_method(chosen.id) == "prototype":
                    from rules_engine.alternative_casts import apply_prototype
                    apply_prototype(card)
                from rules_engine.card_faces import apply_cast_face
                if bestowed:
                    # Apply the selected printed face before bestow's type effect.
                    apply_cast_face(card, _select_face_for_cast(card, selected_face_index))
                    from rules_engine.bestow import begin_bestow
                    begin_bestow(card)
                else:
                    apply_cast_face(card, printed_face_card)
                if casting_method(chosen.id) == "escape":
                    payload["__escaped"] = True
                if casting_method(chosen.id) == "flashback":
                    payload["__flashback"] = True
                from rules_engine.alternative_casts import has_aftermath
                if from_graveyard and has_aftermath(face_card):
                    payload["__aftermath"] = True
                from rules_engine.foretell import record
                was_foretold = bool(record(card))
                if from_exile:
                    leave_exile(state, cid)
                else:
                    departures = capture_graveyard_departures(state, [cid]) if from_graveyard else []
                    (player.graveyard if from_graveyard else player.hand if not from_library else player.library).remove(cid)
                player.exile_play_until.pop(cid, None)
                card.move_to_zone(Zone.STACK)
                if chosen.graveyard_permission_key:
                    from rules_engine.graveyard_permissions import record_graveyard_permission
                    record_graveyard_permission(state, chosen.graveyard_permission_key)
                if not from_exile:
                    emit_graveyard_departures(state, departures)
                if from_exile and was_foretold:
                    card.was_foretold = True
                    payload['__was_foretold'] = True
                card.was_kicked = chosen.kicked
                card.controller = player_id
                state.spells_cast_this_turn[player_id] = int(state.spells_cast_this_turn.get(player_id, 0) or 0) + 1
                if chosen.kicked:
                    state.kicked_spells_cast_this_turn[player_id] = state.kicked_spells_cast_this_turn.get(player_id, 0) + 1
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
            cost_staging = not state.trigger_staging
            if cost_staging:
                state.trigger_staging = True
                state.trigger_staging_event = "discard"
            if not cycle_cost or not auto_pay_cost(state, player_id, cycle_cost, card_name=card.name, x_value=x_value,
                                                 payment_kind="activation", payment_types=set(effective_types(state, card)), source_card_id=cid, ability_kind='cycling'):
                if cost_staging:
                    state.staged_triggers.clear()
                    state.trigger_staging = False
                reject("Cannot pay cycling cost")
                state.log.append(f"{player.name} cannot pay cycling cost for {card.name}.")
                apply_state_based_actions(state)
                return
            player.hand.remove(cid)
            put_into_graveyard(state, cid)
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
            combat.declare_attackers(state, ids, attack_targets if isinstance(attack_targets, dict) else {}, action.get("bands", []), action.get('hybrid_choices'))
            state.attackers_declared = True

        elif kind == "activate_ability":
            cid = action.get("card_id")
            if not cid or cid not in state.cards:
                apply_state_based_actions(state)
                return
            abilities = extract_activated_abilities(state.cards[cid])
            ability_index = int(action.get("ability_index", -1))
            ability = next((item for item in abilities if item["index"] == ability_index), None)
            from rules_engine.oracle_effects import activation_source_eligible
            if ability is None or not activation_source_eligible(state, player_id, cid, ability):
                apply_state_based_actions(state)
                return
            activation_source_zone = state.cards[cid].zone
            if not can_activate_in_current_timing(state, ability["text"], player_id):
                reject("Ability can only be activated at sorcery speed")
                return
            cost = ability["mana_cost"]
            from rules_engine.costs import restricted_x_color
            x_color = restricted_x_color(ability["text"])
            action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
            x_value = int(action_targets.get("x_value", 0) or 0)
            if x_value < 0 or ("{X}" in cost.upper() and "x_value" not in action_targets):
                reject("A non-negative X value is required for this activated cost")
                return
            proxy = type("ActivatedOracleProxy", (), {"id": cid, "oracle_text": ability["text"], "name": state.cards[cid].name, "mana_cost": ""})()
            action_targets = enrich_divide_total(proxy, action_targets)
            proxy.source_oracle_text = state.cards[cid].oracle_text
            if build_ability_spec(state, proxy, player_id, action_targets=action_targets, report_unsupported=False).effect.key == "noop":
                reject("Unsupported activated ability effect")
                state.log.append(f"Unsupported activated ability effect for {state.cards[cid].name}.")
                return
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
            valid, error = validate_hexproof_shroud_targets(state, player_id, action_targets, state.cards[cid])
            if not valid:
                reject(error)
                state.log.append(f"Invalid activation targets: {error}")
                return
            valid, error = validate_protection_targets(state, state.cards[cid], action_targets)
            if not valid:
                reject(error)
                state.log.append(f"Invalid activation targets: {error}")
                return
            if not activated_cost_available(
                state, player_id, cid, cost, action.get("hybrid_choices"), x_value, x_color,
                ability_index=ability_index,
                payment_choices=action.get('payment_choices'),
            ):
                reject("Cannot pay activation costs")
                state.log.append(f"{player.name} cannot pay activation cost for {state.cards[cid].name}.")
                return
            ward_specs = capture_ward_triggers(state, player_id, {"__announced_targets": action_targets})
            cost_context: dict = {}
            cost_staging = not state.trigger_staging
            if cost_staging:
                state.trigger_staging = True
                state.trigger_staging_event = "ability_activation"
            if not apply_activated_costs(state, player_id, cid, cost, context=cost_context, hybrid_choices=action.get("hybrid_choices"), x_value=x_value, restricted_x_color=x_color, ability_index=ability_index, payment_choices=action.get('payment_choices')):
                if cost_staging:
                    state.staged_triggers.clear()
                    state.trigger_staging = False
                reject("Cannot pay activation costs")
                state.log.append(f"{player.name} cannot pay activation cost for {state.cards[cid].name}.")
                apply_state_based_actions(state)
                return
            proxy.source_oracle_text = state.cards[cid].oracle_text
            proxy.sacrificed_toughness = cost_context.get("__sacrificed_toughness")
            resolved = build_ability_spec(state, proxy, player_id, action_targets=action_targets)
            resolved_payload = {**resolved.effect.payload,
                                "__announced_targets": dict(action_targets),
                                "__ward_trigger_specs": ward_specs,
                                "__ability_target_text": ability["text"]}
            if (activation_source_zone == Zone.BATTLEFIELD and state.cards[cid].zone != Zone.BATTLEFIELD
                    and state.cards[cid].last_known_battlefield):
                resolved_payload["__source_lki"] = dict(state.cards[cid].last_known_battlefield)
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{state.cards[cid].name} ability",
                is_spell=False,
                effect_key=resolved.effect.key,
                payload=resolved_payload,
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
            if "Planeswalker" not in effective_types(state, pw):
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
            if next_loyalty > current_loyalty and counter_placement_forbidden(state, 'loyalty', target_card_id=pw.id):
                reject('Cannot pay loyalty cost: counters cannot be placed')
                return
            if next_loyalty < 0:
                reject("Not enough loyalty for this ability")
                state.log.append(f"{pw.name} does not have enough loyalty for that ability.")
                apply_state_based_actions(state)
                return
            action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
            proxy = type("LoyaltyOracleProxy", (), {"id": cid, "oracle_text": ability["text"], "name": pw.name, "mana_cost": ""})()
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
            ok_hs, err_hs = validate_hexproof_shroud_targets(state, player_id, action_targets, pw)
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
            ward_specs = capture_ward_triggers(state, player_id, {"__announced_targets": action_targets})
            loyalty_added = next_loyalty - current_loyalty
            if not apply_activated_costs(state, player_id, cid, '', ability_kind='loyalty'):
                reject('Cannot pay loyalty activation mana costs')
                return
            if loyalty_added <= 0:
                pw.loyalty = next_loyalty
            state.loyalty_activated_this_turn.add(cid)
            ability = build_ability_spec(state, proxy, player_id, action_targets=action_targets)
            effect_key, payload = ability.effect.key, ability.effect.payload
            payload["__announced_targets"] = dict(action_targets)
            payload["__ward_trigger_specs"] = ward_specs
            # Announce the ability before paying its cost, but do not put
            # target/ward triggers on the stack until activation is complete.
            if not state.trigger_staging:
                state.trigger_staging = True
                state.trigger_staging_event = "cast_or_activate"
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{pw.name} loyalty ability",
                is_spell=False,
                effect_key=effect_key,
                payload=payload,
            )
            if loyalty_added > 0:
                resolve_effect(state, player_id, 'add_counters', {
                    'target_card_id': cid, 'counter': 'loyalty', 'amount': loyalty_added,
                    '__counter_is_effect': False,
                    'effect_timestamp': object_incarnation(pw),
                })
                if state.pending_replacement_choice:
                    state.pending_replacement_choice['activation_controller'] = player_id

        elif kind == "crew":
            vehicle_id = action.get("card_id")
            vehicle = state.cards.get(vehicle_id) if vehicle_id else None
            selected = list(action.get("crew_card_ids") or [])
            required = crew_value(vehicle) if vehicle is not None else None
            from rules_engine.continuous import effective_power
            valid = (
                vehicle is not None
                and vehicle_id in player.battlefield
                and "Artifact" in effective_types(state, vehicle)
                and required is not None
                and len(selected) == len(set(selected))
                and all(
                    cid in player.battlefield
                    and cid != vehicle_id
                    and "Creature" in effective_types(state, state.cards[cid])
                    and not state.cards[cid].tapped
                    for cid in selected
                )
                and sum(max(0, effective_power(state, cid)) for cid in selected) >= required
            )
            if valid:
                crew_staging = not state.trigger_staging
                if crew_staging:
                    state.trigger_staging = True
                    state.trigger_staging_event = 'crew_activation'
                if not auto_pay_cost(state, player_id, '', payment_kind='activation', payment_types=set(effective_types(state, vehicle)),
                        source_card_id=vehicle_id, ability_kind='crew', excluded_sources=set(selected)):
                    if crew_staging:
                        state.staged_triggers.clear()
                        state.trigger_staging = False
                    reject('Cannot pay crew activation mana costs')
                    return
                from rules_engine.resource_events import tap_permanents
                tap_permanents(state, selected)
                add_to_stack(
                    state, source_card_id=vehicle_id, controller=player_id,
                    label=f"{vehicle.name} crew", effect_key="crew_vehicle",
                    payload={"card_id": vehicle_id, "effect_timestamp": object_incarnation(vehicle),
                             "crew_card_ids": selected}, is_spell=False,
                )
                state.log.append(f"{player.name} taps {len(selected)} creature(s) to crew {vehicle.name}.")
                if crew_staging:
                    from rules_engine.events import flush_staged_triggers
                    flush_staged_triggers(state)
            else:
                reject("Crew selection does not satisfy the activation cost")

        elif kind == "equip":
            if state.step not in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} or state.active_player != player_id or state.stack:
                reject("Equip can only be activated at sorcery speed")
                return
            cid = action.get("card_id")
            target_id = action.get("target_card_id")
            if not cid or not target_id:
                apply_state_based_actions(state)
                return
            if cid not in player.battlefield:
                apply_state_based_actions(state)
                return
            target = state.cards.get(target_id)
            if (target is None or target.controller != player_id or "Creature" not in effective_types(state, target)
                    or not attachment_target_is_legal(state, state.cards[cid], target_id)):
                reject("Cannot legally equip this target")
                return
            equip_cost = _extract_equip_cost_text(state.cards[cid].oracle_text or "")
            if not equip_cost:
                apply_state_based_actions(state)
                return
            if not auto_pay_cost(state, player_id, equip_cost, card_name=state.cards[cid].name,
                                 payment_kind="activation", payment_types=set(effective_types(state, state.cards[cid])),
                                 ability_kind="equip", source_card_id=cid, target_card_id=target_id):
                reject("Cannot pay equipment cost")
                state.log.append(f"{player.name} cannot pay equip cost for {state.cards[cid].name}.")
                apply_state_based_actions(state)
                return
            add_to_stack(state, cid, player_id, f"{state.cards[cid].name} equip", "equip_attachment", {
                "equipment_id": cid, "target_card_id": target_id,
                "source_timestamp": object_incarnation(state.cards[cid]),
                "target_timestamp": object_incarnation(target),
                "__announced_targets": {"target_card_id": target_id},
                "__ability_target_text": "Attach this Equipment to target creature you control.",
            }, is_spell=False)

        elif kind == "block":
            if getattr(state, "blockers_declared", False):
                apply_state_based_actions(state)
                return
            blocks = action.get("blocks", {})
            combat.declare_blockers(state, blocks, action.get('hybrid_choices'))
            state.blockers_declared = True
            # After blockers are declared, the active player receives priority.
            # Without this handoff, the defending player can be re-queried in declare_blockers
            # and re-submit block actions indefinitely.
            state.priority_player = state.active_player
            state.passed_priority = set()

        elif kind == "combat_damage":
            if state.stack:
                reject("Resolve the stack before combat damage")
                return
            combat.combat_damage(state)

        if not effect_cast:
            apply_state_based_actions(state)
            if kind in {'foretell', 'suspend'} and not (state.pending_mechanic_choice or state.pending_replacement_choice
                                          or state.pending_trigger_order):
                state.priority_player = player_id

    def legal_moves(self, state: MatchState, player_id: int) -> list[dict]:
        from rules_engine.query_context import rule_query_scope
        with rule_query_scope(state):
            return legal_moves(state, player_id)

    def _handle_pregame_action(self, state: MatchState, player_id: int, action: dict) -> None:
        kind = action.get("type")
        player = state.players[player_id]
        if kind == "mulligan" and state.mulligan_count.get(player_id, 0) >= 7:
            return
        state.mulligan_declarations[player_id] = kind
        if kind == "mulligan":
            state.log.append(f"{player.name} declares a mulligan.")
        if kind == "keep_hand":
            bottom = action.get("bottom_card_ids", [])
            need_bottom = max(0, state.mulligan_count.get(player_id, 0) - state.mulligan_bottomed.get(player_id, 0))
            chosen = [cid for cid in bottom if cid in player.hand][:need_bottom]
            if len(chosen) < need_bottom:
                chosen += _auto_bottom_cards(state, player_id, need_bottom - len(chosen), exclude=set(chosen))
            for cid in reversed(chosen):
                if cid in player.hand:
                    player.hand.remove(cid)
                    player.library.insert(0, cid)
                    state.cards[cid].move_to_zone(Zone.LIBRARY)
            state.kept_hands.add(player_id)
            state.mulligan_bottomed[player_id] = state.mulligan_count.get(player_id, 0)
            state.log.append(f"{player.name} keeps hand.")
        actor = pregame_actor(state)
        if actor is not None:
            state.priority_player = actor
            return
        # Finish the entire declaration round before changing any mulligan hand.
        mulliganers = [pid for pid in (state.active_player, 3 - state.active_player)
                       if state.mulligan_declarations.get(pid) == "mulligan"]
        for pid in mulliganers:
            player = state.players[pid]
            while player.hand:
                cid = player.hand.pop()
                player.library.append(cid)
                state.cards[cid].move_to_zone(Zone.LIBRARY)
            rng = getattr(state, "rng", None)
            if rng is None:
                import random
                rng = random
            rng.shuffle(player.library)
            state.mulligan_count[pid] = state.mulligan_count.get(pid, 0) + 1
        for pid in mulliganers:
            draw_card(state, pid, 7)
            state.log.append(f"{state.players[pid].name} takes a mulligan to {7 - state.mulligan_count[pid]}.")
        state.mulligan_declarations.clear()
        if mulliganers:
            self._begin_mulligan_bottom(state, mulliganers)
            return
        if len(state.kept_hands) == 2:
            from rules_engine.opening_hand import begin_opening_hand_choices
            if not begin_opening_hand_choices(state):
                self._finish_pregame(state)
        else:
            state.priority_player = pregame_actor(state)

    def _finish_pregame(self, state: MatchState) -> None:
        state.pregame_pending = False
        state.trigger_staging = False
        state.priority_player = state.active_player
        state.step = Step.UNTAP
        self._apply_step_start_actions(state)
        state.log.append("Pregame complete. Proceeding to turn structure.")
        self.next_step(state)

    def _begin_mulligan_bottom(self, state: MatchState, players: list[int]) -> None:
        pid = players[0]
        count = state.mulligan_count[pid]
        state.pending_mechanic_choice = {
            "kind": "mulligan_bottom", "player_id": pid,
            "options": list(state.players[pid].hand), "count": count, "min_count": count,
            "remaining_players": players[1:],
            "label": f"Player {pid}: choose {count} cards to bottom before declaring again (bottom-most first)",
        }
        state.priority_player = pid

    def _finish_mulligan_bottom(self, state: MatchState, player_id: int, action: dict) -> bool:
        pending = state.pending_mechanic_choice
        ids = action.get("card_ids")
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or len(ids) != pending["count"] or any(not isinstance(cid, str) for cid in ids)
                or len(set(ids)) != len(ids)
                or any(cid not in pending["options"] or cid not in state.players[player_id].hand for cid in ids)):
            return False
        player = state.players[player_id]
        for cid in reversed(ids):
            player.hand.remove(cid)
            player.library.insert(0, cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        state.mulligan_bottomed[player_id] = state.mulligan_count[player_id]
        state.log.append(f"{player.name} bottoms {len(ids)} card(s) after mulligan redraw.")
        if pending["remaining_players"]:
            self._begin_mulligan_bottom(state, pending["remaining_players"])
        else:
            state.pending_mechanic_choice = None
            state.priority_player = pregame_actor(state)
        return True


def _auto_bottom_cards(state: MatchState, player_id: int, count: int, exclude: set[str] | None = None) -> list[str]:
    from rules_engine.mana import parse_mana_cost

    exclude = exclude or set()
    hand_cards = [state.cards[cid] for cid in state.players[player_id].hand if cid not in exclude]
    scored = []
    for card in hand_cards:
        land_bias = -3 if "Land" in effective_types(state, card) else 0
        cmc = mana_value(card.mana_cost, is_land=("Land" in effective_types(state, card)))
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
