from __future__ import annotations

from game_state.state import MatchState, Step, TURN_STEPS, Zone, draw_card
from rules_engine import combat
from rules_engine.cast_choice import build_cast_hints, enrich_divide_total, validate_cast_choice
from rules_engine.costs import apply_additional_costs, check_cost_option_available, collect_cost_options, normalize_cost_choice
from rules_engine.mana import auto_pay_cost
from rules_engine.move_generator import legal_moves
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.oracle_effects import extract_loyalty_abilities, infer_effect_from_oracle
from rules_engine.priority import pass_priority
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.events import emit_event


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
            state.turn += 1
            state.active_player = 1 if state.active_player == 2 else 2
            state.step = TURN_STEPS[0]
            state.loyalty_activated_this_turn = set()
            for cid in state.players[state.active_player].battlefield:
                state.cards[cid].summoning_sick = False
            state.players[state.active_player].lands_played_this_turn = 0
            state.players[state.active_player].max_land_plays_this_turn = compute_max_land_plays_this_turn(
                state, state.active_player
            )
            state.players[state.active_player].land_plays_recorded_on_turn = 0
        else:
            state.step = TURN_STEPS[idx + 1]
            if state.step == Step.DECLARE_ATTACKERS:
                state.attackers_declared = False

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
            emit_event(state, "begin_step", {"step": "upkeep", "active_player": state.active_player})
        elif state.step == Step.DRAW and state.turn > 1:
            draw_card(state, state.active_player)
            state.log.append(f"{player.name} draws a card.")
        elif state.step == Step.END_STEP:
            emit_event(state, "begin_step", {"step": "end_step", "active_player": state.active_player})
        elif state.step == Step.CLEANUP:
            self._clear_marked_damage(state)
            self._clear_prevention_shields(state)
            self._enforce_cleanup_hand_size(state, state.active_player)

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
            player.max_land_plays_this_turn = compute_max_land_plays_this_turn(state, player_id)
            max_land_plays = max(1, int(getattr(player, "max_land_plays_this_turn", 1)))
            if getattr(player, "last_land_play_turn", 0) != state.turn:
                player.last_land_play_turn = state.turn
                player.land_plays_recorded_on_turn = 0
            used_land_plays = max(
                int(getattr(player, "lands_played_this_turn", 0)),
                int(getattr(player, "land_plays_recorded_on_turn", 0)),
            )
            if cid in player.hand and used_land_plays < max_land_plays and _is_land_card(state.cards[cid]):
                player.hand.remove(cid)
                player.battlefield.append(cid)
                player.lands_played_this_turn = used_land_plays + 1
                player.land_plays_recorded_on_turn = used_land_plays + 1
                player.last_land_play_turn = state.turn
                state.cards[cid].zone = Zone.BATTLEFIELD
                state.cards[cid].summoning_sick = False
                state.log.append(f"{player.name} plays {state.cards[cid].name}.")

        elif kind == "tap_land_for_mana":
            cid = action["card_id"]
            if cid in player.battlefield and not state.cards[cid].tapped and "Land" in state.cards[cid].types:
                state.cards[cid].tapped = True
                color = _infer_mana_from_land(state.cards[cid].name)
                player.mana_pool[color] += 1
                state.log.append(f"{player.name} taps {state.cards[cid].name} for {color}.")

        elif kind == "tap_lands_bulk":
            land_name = str(action.get("land_name", "")).strip().lower()
            count = max(0, int(action.get("count", 0)))
            if land_name and count > 0:
                tapped = 0
                produced = None
                for cid in list(player.battlefield):
                    card = state.cards[cid]
                    if tapped >= count:
                        break
                    if "Land" not in card.types or card.tapped:
                        continue
                    if card.name.strip().lower() != land_name:
                        continue
                    card.tapped = True
                    color = _infer_mana_from_land(card.name)
                    player.mana_pool[color] += 1
                    produced = color
                    tapped += 1
                if tapped > 0 and produced:
                    state.log.append(
                        f"{player.name} taps {tapped}x {action.get('land_name')} for {tapped} {produced}."
                    )

        elif kind == "cast_spell":
            cid = action["card_id"]
            if cid in player.hand:
                card = state.cards[cid]
                if _is_land_card(card):
                    state.log.append(f"{player.name} cannot cast land card {card.name} as a spell.")
                    apply_state_based_actions(state)
                    return
                options = collect_cost_options(state, player_id, card)
                chosen = normalize_cost_choice(action, options)
                if not check_cost_option_available(state, player_id, card, chosen):
                    explicit_choice = bool(((action.get("cost_choice") or {}).get("id")))
                    if not explicit_choice:
                        chosen = next(
                            (
                                opt
                                for opt in options
                                if check_cost_option_available(state, player_id, card, opt)
                            ),
                            chosen,
                        )
                    if not check_cost_option_available(state, player_id, card, chosen):
                        state.log.append(f"{player.name} cannot satisfy chosen costs for {card.name}.")
                        apply_state_based_actions(state)
                        return
                action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
                action_targets = enrich_divide_total(card, action_targets)
                hints = build_cast_hints(state, card, player_id)
                ok, error = validate_cast_choice(hints, action_targets)
                if not ok:
                    state.log.append(f"Invalid targets for {card.name}: {error}")
                    apply_state_based_actions(state)
                    return
                paid = auto_pay_cost(state, player_id, chosen.mana_cost, is_land=("Land" in card.types), card_name=card.name)
                if not paid:
                    state.log.append(f"{player.name} cannot pay mana cost for {card.name}.")
                    apply_state_based_actions(state)
                    return
                if not apply_additional_costs(state, player_id, chosen, cid):
                    state.log.append(f"{player.name} failed additional costs for {card.name}.")
                    apply_state_based_actions(state)
                    return
                effect_key, payload = infer_effect_from_oracle(state, card, player_id, action_targets=action_targets)

                player.hand.remove(cid)
                card.zone = Zone.STACK
                add_to_stack(state, source_card_id=cid, controller=player_id, label=card.name, effect_key=effect_key, payload=payload)

        elif kind == "attack":
            ids = action.get("attackers", [])
            attack_targets = action.get("attack_targets", {})
            combat.declare_attackers(state, ids, attack_targets if isinstance(attack_targets, dict) else {})
            state.attackers_declared = True

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
            next_loyalty = (pw.loyalty or 0) + int(ability["delta"])
            if next_loyalty < 0:
                state.log.append(f"{pw.name} does not have enough loyalty for that ability.")
                apply_state_based_actions(state)
                return
            pw.loyalty = next_loyalty
            state.loyalty_activated_this_turn.add(cid)
            action_targets = action.get("targets", {}) if isinstance(action, dict) else {}
            proxy = type("LoyaltyOracleProxy", (), {"oracle_text": ability["text"], "name": pw.name, "mana_cost": ""})()
            effect_key, payload = infer_effect_from_oracle(state, proxy, player_id, action_targets=action_targets)
            add_to_stack(
                state,
                source_card_id=cid,
                controller=player_id,
                label=f"{pw.name} loyalty ability",
                effect_key=effect_key,
                payload=payload,
            )

        elif kind == "block":
            blocks = action.get("blocks", {})
            combat.declare_blockers(state, blocks)

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


def _infer_mana_from_land(name: str) -> str:
    n = name.lower()
    dual_pref = {
        "hallowed fountain": "U",
        "sacred foundry": "R",
        "watery grave": "U",
        "blood crypt": "B",
        "overgrown tomb": "B",
        "breeding pool": "U",
        "stomping ground": "R",
        "steam vents": "U",
        "godless shrine": "W",
        "temple garden": "W",
    }
    if n in dual_pref:
        return dual_pref[n]
    if "plains" in n:
        return "W"
    if "island" in n:
        return "U"
    if "swamp" in n:
        return "B"
    if "mountain" in n:
        return "R"
    if "forest" in n:
        return "G"
    return "C"


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
        req = parse_mana_cost(card.mana_cost, is_land=("Land" in card.types))
        cmc = req["generic"] + sum(req[c] for c in ["W", "U", "B", "R", "G"])
        score = cmc + land_bias
        scored.append((score, card.id))
    scored.sort(reverse=True)
    return [cid for _, cid in scored[: max(0, count)]]
