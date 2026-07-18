from __future__ import annotations

from game_state.state import MatchState, Step, TURN_STEPS, Zone, assign_static_order_on_battlefield_entry, draw_card
from rules_engine import combat
from rules_engine.cast_choice import build_cast_hints, enrich_divide_total, validate_cast_choice
from rules_engine.costs import apply_activated_costs, apply_additional_costs, check_cost_option_available, collect_cost_options, normalize_cost_choice
from rules_engine.cycling import cycling_cost, cycling_is_variable, cycling_variant
from rules_engine.mana import add_generic_to_cost, auto_pay_cost, mana_value
from rules_engine.mana import land_mana_amount
from rules_engine.move_generator import legal_moves
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.oracle_effects import extract_activated_abilities, extract_loyalty_abilities
from rules_engine.ability_model import build_ability_spec
from rules_engine.priority import pass_priority
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.targeting import validate_hexproof_shroud_targets, validate_protection_targets
from rules_engine.events import emit_event
from rules_engine.restrictions import can_cast_in_current_timing
from rules_engine.ward import ward_tax_for_targets
from rules_engine.attachments import attach_if_legal
from effects.registry import resolve_effect


class RulesEngine:
    def next_step(self, state: MatchState) -> None:
        if state.pregame_pending:
            return
        if state.winner is not None:
            return
        if state.stack:
            resolve_top_of_stack(state)
            apply_state_based_actions(state)
            state.priority_player = state.active_player
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
            elif state.step == Step.DECLARE_BLOCKERS:
                state.blockers_declared = False

        self._apply_step_start_actions(state)
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
            before = len(player.hand)
            draw_card(state, state.active_player)
            after = len(player.hand)
            state.log.append(f"{player.name} draws a card. Hand {before}->{after}.")
        elif state.step == Step.DRAW and state.turn == 1:
            state.log.append(f"{player.name} skips draw on turn 1 (on the play rule).")
        elif state.step == Step.END_STEP:
            emit_event(state, "begin_step", {"step": "end_step", "active_player": state.active_player})
        elif state.step == Step.CLEANUP:
            self._clear_marked_damage(state)
            self._clear_prevention_shields(state)
            self._revert_expired_control_changes(state)
            self._enforce_cleanup_hand_size(state, state.active_player)

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
        for _ in range(discard_count):
            cid = player.hand.pop(0)
            player.graveyard.append(cid)
            state.cards[cid].zone = Zone.GRAVEYARD
            state.log.append(f"{player.name} discards {state.cards[cid].name} during cleanup.")

    def _has_no_max_hand_size_effect(self, state: MatchState, player_id: int) -> bool:
        player = state.players[player_id]
        for cid in player.battlefield:
            card = state.cards[cid]
            oracle = (card.oracle_text or "").lower()
            if "no maximum hand size" in oracle:
                return True
        return False

    def take_action(self, state: MatchState, player_id: int, action: dict) -> None:
        if state.winner is not None:
            return
        kind = action.get("type")

        if state.pregame_pending:
            self._handle_pregame_action(state, player_id, action)
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
                    state.priority_player = state.active_player
                else:
                    self.next_step(state)
            apply_state_based_actions(state)
            return

        if state.priority_player != player_id:
            return

        player = state.players[player_id]
        if kind == "play_land":
            cid = action["card_id"]
            from_exile = bool(action.get("from_exile"))
            allowed_source = cid in player.exile and player.exile_play_until.get(cid, 0) >= state.turn if from_exile else cid in player.hand
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
            if allowed_source and used_land_plays < max_land_plays and _is_land_card(state.cards[cid]):
                (player.exile if from_exile else player.hand).remove(cid)
                player.exile_play_until.pop(cid, None)
                player.battlefield.append(cid)
                player.lands_played_this_turn = used_land_plays + 1
                player.land_plays_recorded_on_turn = used_land_plays + 1
                player.last_land_play_turn = state.turn
                state.cards[cid].zone = Zone.BATTLEFIELD
                state.cards[cid].summoning_sick = False
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
            allowed_source = cid in player.exile and player.exile_play_until.get(cid, 0) >= state.turn if from_exile else cid in player.hand
            if allowed_source:
                card = state.cards[cid]
                timing_ok, timing_reason = can_cast_in_current_timing(state, card, player_id)
                if not timing_ok:
                    state.log.append(f"{player.name} cannot cast {card.name}: {timing_reason}")
                    apply_state_based_actions(state)
                    return
                if _is_land_card(card):
                    state.log.append(f"{player.name} cannot cast land card {card.name} as a spell.")
                    apply_state_based_actions(state)
                    return
                options = collect_cost_options(state, player_id, card)
                chosen = normalize_cost_choice(action, options)
                # Extract x_value early — needed for cost checking and payment
                at_targets = action.get("targets", {}) if isinstance(action, dict) else {}
                x_value = int(at_targets.get("x_value", 0) or 0)
                if not check_cost_option_available(state, player_id, card, chosen, x_value=x_value):
                    explicit_choice = bool(((action.get("cost_choice") or {}).get("id")))
                    if not explicit_choice:
                        chosen = next(
                            (
                                opt
                                for opt in options
                                if check_cost_option_available(state, player_id, card, opt, x_value=x_value)
                            ),
                            chosen,
                        )
                    if not check_cost_option_available(state, player_id, card, chosen, x_value=x_value):
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
                hints = build_cast_hints(state, face_card, player_id)
                ok, error = validate_cast_choice(hints, action_targets)
                if not ok:
                    state.log.append(f"Invalid targets for {card.name}: {error}")
                    apply_state_based_actions(state)
                    return
                ok_prot, err_prot = validate_protection_targets(state, face_card, action_targets)
                if not ok_prot:
                    state.log.append(f"Invalid targets for {card.name}: {err_prot}")
                    apply_state_based_actions(state)
                    return
                ok_hs, err_hs = validate_hexproof_shroud_targets(state, player_id, action_targets)
                if not ok_hs:
                    state.log.append(f"Invalid targets for {card.name}: {err_hs}")
                    apply_state_based_actions(state)
                    return
                target_ids: list[str] = []
                if action_targets.get("target_card_id"):
                    target_ids.append(action_targets["target_card_id"])
                target_ids.extend([x for x in (action_targets.get("target_card_ids") or []) if x not in target_ids])
                ward_tax = ward_tax_for_targets(state, player_id, target_ids)
                adjusted_cost = add_generic_to_cost(chosen.mana_cost, ward_tax)
                paid = auto_pay_cost(state, player_id, adjusted_cost, is_land=("Land" in card.types), card_name=card.name, x_value=x_value)
                if not paid:
                    if ward_tax > 0:
                        state.log.append(f"{player.name} cannot pay ward tax ({ward_tax}) for {card.name}.")
                    else:
                        state.log.append(f"{player.name} cannot pay mana cost for {card.name}.")
                    apply_state_based_actions(state)
                    return
                if not apply_additional_costs(state, player_id, chosen, cid):
                    state.log.append(f"{player.name} failed additional costs for {card.name}.")
                    apply_state_based_actions(state)
                    return
                ability = build_ability_spec(state, face_card, player_id, action_targets=action_targets)
                effect_key, payload = ability.effect.key, ability.effect.payload

                (player.exile if from_exile else player.hand).remove(cid)
                player.exile_play_until.pop(cid, None)
                card.zone = Zone.STACK
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
                state.log.append(f"Invalid cycling X value for {card.name}.")
                apply_state_based_actions(state)
                return
            if not cycle_cost or not auto_pay_cost(state, player_id, cycle_cost, card_name=card.name, x_value=x_value):
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
            if not apply_activated_costs(state, player_id, cid, cost):
                state.log.append(f"{player.name} cannot pay activation cost for {state.cards[cid].name}.")
                apply_state_based_actions(state)
                return
            action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
            proxy = type("ActivatedOracleProxy", (), {"oracle_text": ability["text"], "name": state.cards[cid].name, "mana_cost": ""})()
            resolved = build_ability_spec(state, proxy, player_id, action_targets=action_targets)
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{state.cards[cid].name} ability",
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
                state.log.append(f"{pw.name} does not have enough loyalty for that ability.")
                apply_state_based_actions(state)
                return
            pw.loyalty = next_loyalty
            state.loyalty_activated_this_turn.add(cid)
            action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
            proxy = type("LoyaltyOracleProxy", (), {"oracle_text": ability["text"], "name": pw.name, "mana_cost": ""})()
            if ability.get("x_cost") and "x_value" not in action_targets:
                action_targets = dict(action_targets)
                action_targets["x_value"] = max(0, min(current_loyalty, int(action_targets.get("x_value", 0) or 0)))
            ok_hs, err_hs = validate_hexproof_shroud_targets(state, player_id, action_targets)
            if not ok_hs:
                state.log.append(f"Invalid targets for {pw.name}: {err_hs}")
                apply_state_based_actions(state)
                return
            ok_prot, err_prot = validate_protection_targets(state, pw, action_targets)
            if not ok_prot:
                state.log.append(f"Invalid targets for {pw.name}: {err_prot}")
                apply_state_based_actions(state)
                return
            ability = build_ability_spec(state, proxy, player_id, action_targets=action_targets)
            effect_key, payload = ability.effect.key, ability.effect.payload
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{pw.name} loyalty ability",
                effect_key=effect_key,
                payload=payload,
            )

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
                state.log.append(f"{player.name} cannot pay equip cost for {state.cards[cid].name}.")
                apply_state_based_actions(state)
                return
            if attach_if_legal(state, cid, target_id):
                state.log.append(f"{player.name} equips {state.cards[cid].name} to {state.cards[target_id].name}.")
            else:
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
            if state.mulligan_count.get(player_id, 0) >= 3:
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
            for cid in chosen:
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


def _is_land_card(card) -> bool:
    if "Land" in getattr(card, "types", []):
        return True
    type_line = (getattr(card, "type_line", "") or "").lower()
    if "land" in type_line:
        return True
    oracle = (getattr(card, "oracle_text", "") or "").lower()
    mana_cost = (getattr(card, "mana_cost", "") or "").strip()
    nonland_typed = any(
        t in set(getattr(card, "types", []))
        for t in ["Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker"]
    )
    if not mana_cost and not nonland_typed and (("{t}:" in oracle and "add {" in oracle) or "add one mana of any color" in oracle):
        return True
    name = (getattr(card, "name", "") or "").strip().lower()
    return name in {"island", "swamp", "mountain", "forest", "plains"}


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
    faces = list(getattr(card, "card_faces", []) or [])
    if not faces:
        return card
    try:
        index = int(selected_face_index if selected_face_index is not None else getattr(card, "selected_face_index", 0) or 0)
    except Exception:
        index = 0
    if index < 0 or index >= len(faces):
        index = 0
    face = faces[index] or {}
    proxy = type("CardFaceProxy", (), {})()
    for attr in [
        "id",
        "owner",
        "controller",
        "zone",
        "tapped",
        "summoning_sick",
        "entered_turn",
        "counters",
        "keywords",
        "attached_to",
        "static_order",
        "instance_order",
        "selected_face_index",
        "card_faces",
    ]:
        setattr(proxy, attr, getattr(card, attr, None))
    proxy.name = str(face.get("name") or card.name)
    proxy.oracle_text = str(face.get("oracle_text") or card.oracle_text or "")
    proxy.mana_cost = str(face.get("mana_cost") or card.mana_cost or "")
    proxy.type_line = str(face.get("type_line") or card.type_line or "")
    proxy.power = face.get("power") if face.get("power") is not None else getattr(card, "power", None)
    proxy.toughness = face.get("toughness") if face.get("toughness") is not None else getattr(card, "toughness", None)
    proxy.loyalty = getattr(card, "loyalty", None)
    proxy.types = list(getattr(card, "types", []) or [])
    proxy.image_uri = face.get("image_uri") or getattr(card, "image_uri", None)
    proxy.selected_face_index = index
    return proxy
