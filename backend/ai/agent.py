from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from ai.endgame_policy import should_force_closure
from ai.heuristics import evaluate_board
from ai.log_priors import load_log_priors
from ai.matchup_profiles import profile_for
from game_state.state import MatchState
from rules_engine.engine import RulesEngine
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.mana import can_pay_with_pool_and_lands, parse_mana_cost


@dataclass
class AIDecision:
    action: dict
    reasoning: str


class AIAgent:
    _log_priors_cache: dict | None = None

    def __init__(self, difficulty: str = "strong", archetype: str = "Midrange", opponent_archetype: str | None = None):
        self.difficulty = difficulty.lower()
        self.archetype = archetype
        self.opponent_archetype = opponent_archetype
        self.matchup_profile = profile_for(archetype, opponent_archetype)
        self.engine = RulesEngine()
        if AIAgent._log_priors_cache is None:
            AIAgent._log_priors_cache = load_log_priors()

    def choose_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> AIDecision:
        if getattr(state, "pregame_pending", False):
            return self.choose_mulligan_action(state, player_id)
        if not legal_moves:
            return AIDecision(action={"type": "pass_priority"}, reasoning="No legal actions")
        if _step_key(getattr(state, "step", "")) == "declare_blockers" and getattr(state, "active_player", player_id) != player_id:
            if bool(getattr(state, "blocks", {})):
                return AIDecision(action={"type": "pass_priority"}, reasoning="Blocks already declared; pass priority")
        if _step_key(getattr(state, "step", "")) == "declare_attackers" and getattr(state, "active_player", player_id) == player_id:
            forced_attack = self._forced_progress_attack(state, legal_moves, player_id)
            if forced_attack is not None:
                return AIDecision(action=forced_attack, reasoning="Late-game progress attack to avoid stall timeout")

        forced_land = self._choose_forced_land_play(state, legal_moves, player_id)
        if forced_land is not None:
            return AIDecision(action=forced_land, reasoning="Prioritize reliable land development on own main phase")

        forced_stabilize = self._forced_burn_stabilization_line(state, legal_moves, player_id)
        if forced_stabilize is not None:
            return AIDecision(action=forced_stabilize, reasoning="Burn matchup stabilization: remove pressure before value lines")

        stack_interaction = self._forced_stack_interaction(state, legal_moves, player_id)
        if stack_interaction is not None:
            return AIDecision(action=stack_interaction, reasoning="Answer threatening stack item with available interaction")

        endstep_draw = self._forced_endstep_card_advantage(state, legal_moves, player_id)
        if endstep_draw is not None:
            return AIDecision(action=endstep_draw, reasoning="Use opponent end step for instant-speed card advantage")

        closure = self._choose_forced_closure_action(state, legal_moves, player_id)
        if closure is not None:
            return AIDecision(action=closure, reasoning="Force late-game proactive line to avoid control stall/timeouts")

        sorted_moves = self._rank_moves(state, legal_moves, player_id)
        if self._should_break_stall(state, legal_moves, player_id):
            proactive = self._best_proactive_non_pass(sorted_moves, state)
            if proactive is not None:
                proactive = self._materialize_action(state, proactive, player_id)
                if not proactive.get("_invalid_ai_choice") and not self._is_unplayable_x_action(proactive):
                    return AIDecision(action=proactive, reasoning="Break pass-loop by selecting proactive legal action")
        if self.difficulty == "casual":
            ranked_candidates = sorted_moves[min(1, len(sorted_moves) - 1) :]
        else:
            ranked_candidates = sorted_moves
        move = None
        for cand in ranked_candidates:
            materialized = self._materialize_action(state, cand, player_id)
            if materialized.get("_invalid_ai_choice"):
                continue
            if self._is_action_obviously_illegal(state, materialized, player_id):
                continue
            if self._is_unplayable_x_action(materialized):
                continue
            move = materialized
            break
        if move is None:
            move = {"type": "pass_priority"}
        move = self._avoid_pass_with_main_phase_options(state, legal_moves, player_id, move)
        if move.get("type") == "block" and not move.get("blocks"):
            return AIDecision(action={"type": "pass_priority"}, reasoning="No profitable/legal block assignment; pass")
        if move.get("type") == "attack" and not (move.get("attackers") or []):
            return AIDecision(action={"type": "pass_priority"}, reasoning="No favorable attacks; pass priority")

        return AIDecision(action=move, reasoning=f"{self.archetype} plan selected best-scoring move")

    def _forced_progress_attack(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        turn = int(getattr(state, "turn", 1) or 1)
        if turn < 20:
            return None
        attack_moves = [m for m in legal_moves if m.get("type") == "attack"]
        if not attack_moves:
            return None
        move = dict(attack_moves[0])
        options = list(move.get("options") or move.get("attackers") or [])
        if not options:
            return None
        chosen = self._choose_attackers(state, options, player_id)
        if not chosen:
            chosen = self._fallback_progress_attackers(state, options, player_id)
        if not chosen:
            return None
        move["attackers"] = chosen
        return move

    def _fallback_progress_attackers(self, state: MatchState, candidates: list[str], player_id: int) -> list[str]:
        opp_id = 1 if player_id == 2 else 2
        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        opp_blockers = [
            cid
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        ]
        out: list[str] = []
        for cid in candidates:
            card = state.cards.get(cid)
            if not card:
                continue
            p = _eff_pow(state, cid)
            t = _eff_tgh(state, cid)
            if p <= 0:
                continue
            kws = {str(k).lower() for k in (getattr(card, "keywords", []) or [])}
            evasive = bool(kws.intersection({"flying", "trample", "deathtouch", "menace"}))
            dies_to_any = any(_eff_pow(state, b) >= t for b in opp_blockers)
            trades_up = any(_eff_tgh(state, b) <= p for b in opp_blockers)
            if evasive or not dies_to_any or trades_up or p >= 3:
                out.append(cid)
        return out

    def _choose_forced_closure_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if getattr(state, "active_player", player_id) != player_id:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if not should_force_closure(turn, self.archetype, self.opponent_archetype):
            return None

        # Look for non-pass cast lines that actually advance board/card quality.
        cast_moves = [m for m in legal_moves if m.get("type") == "cast_spell"]
        if not cast_moves:
            return None

        candidates: list[tuple[float, dict]] = []
        for m in cast_moves:
            cid = m.get("card_id")
            card = state.cards.get(cid) if cid else None
            if not card:
                continue
            text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
            # Do not force pure stack-dependent counters when stack is empty.
            if "counter target spell" in text and not (getattr(state, "stack", []) or []):
                continue
            materialized = self._materialize_action(state, m, player_id)
            if materialized.get("_invalid_ai_choice") or self._is_unplayable_x_action(materialized):
                continue
            score = self._closure_spell_score(card, text)
            candidates.append((score, materialized))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        # Require meaningful proactive value.
        if candidates[0][0] < 1.0:
            return None
        return candidates[0][1]

    def _closure_spell_score(self, card, text: str) -> float:
        score = 0.0
        types = set(getattr(card, "types", []) or [])
        if "Planeswalker" in types:
            score += 5.0
        if "Creature" in types:
            p = int(getattr(card, "power", 0) or 0)
            t = int(getattr(card, "toughness", 0) or 0)
            score += min(6.0, p * 0.9 + t * 0.25)
        if "draw" in text or "deluge" in text or "consider" in text:
            score += 1.8
        if "token" in text or "create " in text:
            score += 1.5
        if "shark typhoon" in text:
            score += 2.2
        if "counter target spell" in text:
            score -= 2.5
        return score

    def _forced_stack_interaction(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo", "Midrange"}:
            return None
        if getattr(state, "priority_player", player_id) != player_id:
            return None
        if not (getattr(state, "stack", []) or []):
            return None
        cast_moves = [m for m in legal_moves if m.get("type") == "cast_spell"]
        if not cast_moves:
            return None
        if self._best_stack_threat_score(state, player_id) < 2.0:
            return None
        best: tuple[float, dict] | None = None
        for move in cast_moves:
            cid = move.get("card_id")
            card = state.cards.get(cid) if cid else None
            if not card:
                continue
            text = f"{(getattr(card, 'name', '') or '').lower()} {(getattr(card, 'oracle_text', '') or '').lower()}"
            score = 0.0
            if "counter target spell" in text:
                score += 7.0
            elif any(k in text for k in ["destroy target", "exile target", "deals"]):
                score += 2.5
            if score <= 0.0:
                continue
            mat = self._materialize_action(state, move, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if best is None or score > best[0]:
                best = (score, mat)
        return best[1] if best else None

    def _forced_endstep_card_advantage(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo"}:
            return None
        if getattr(state, "priority_player", player_id) != player_id:
            return None
        if getattr(state, "active_player", player_id) == player_id:
            return None
        if _step_key(getattr(state, "step", "")) != "end_step":
            return None
        if getattr(state, "stack", []) or []:
            return None
        candidates: list[dict] = []
        for move in legal_moves:
            if move.get("type") != "cast_spell":
                continue
            cid = move.get("card_id")
            card = state.cards.get(cid) if cid else None
            if not card:
                continue
            if "Instant" not in (getattr(card, "types", []) or []):
                continue
            text = f"{(getattr(card, 'name', '') or '').lower()} {(getattr(card, 'oracle_text', '') or '').lower()}"
            if not any(k in text for k in ["draw", "deluge", "consider", "scry"]):
                continue
            mat = self._materialize_action(state, move, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            candidates.append(mat)
        return candidates[0] if candidates else None

    def _forced_burn_stabilization_line(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if not self._is_burn_matchup():
            return None
        if getattr(state, "active_player", player_id) != player_id:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = [
            cid
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        ]
        if not opp_creatures:
            return None
        cast_moves = [m for m in legal_moves if m.get("type") == "cast_spell"]
        best: tuple[float, dict] | None = None
        for move in cast_moves:
            cid = move.get("card_id")
            card = state.cards.get(cid) if cid else None
            if not card:
                continue
            tags = self._spell_tags(card)
            if "removal" not in tags and "sweeper" not in tags:
                continue
            mat = self._materialize_action(state, move, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            text = f"{(getattr(card, 'name', '') or '').lower()} {(getattr(card, 'oracle_text', '') or '').lower()}"
            score = 0.0
            if "sweeper" in tags:
                score += 5.0 if len(opp_creatures) >= 2 else 1.0
            if "removal" in tags:
                score += 3.0
            if any(k in text for k in ["exile", "destroy"]):
                score += 0.8
            if best is None or score > best[0]:
                best = (score, mat)
        return best[1] if best else None

    def _choose_forced_land_play(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        step = _step_key(getattr(state, "step", ""))
        own_main = step in {"precombat_main", "postcombat_main"}
        if not own_main:
            return None
        if getattr(state, "stack", []) or []:
            return None
        # Must be active player to play lands — skip the defensive fallback otherwise
        if getattr(state, "active_player", player_id) != player_id:
            return None
        land_moves = [m for m in legal_moves if m.get("type") == "play_land"]
        if land_moves:
            return self._best_land_move(state, land_moves, player_id)
        player = state.players[player_id]
        if self._remaining_land_plays(state, player_id) <= 0:
            return None
        # Defensive fallback for legal-move omissions.
        if not land_moves:
            # Defensive fallback for legal-move omissions: derive land plays from hand.
            for cid in list(getattr(player, "hand", [])):
                card = state.cards.get(cid)
                if card and _card_looks_like_land(card):
                    land_moves.append({"type": "play_land", "card_id": cid})
        if not land_moves:
            return None
        return self._best_land_move(state, land_moves, player_id)

    def choose_mulligan_action(self, state: MatchState, player_id: int) -> AIDecision:
        player = state.players[player_id]
        hand = [state.cards[cid] for cid in player.hand]
        lands = sum(1 for c in hand if _card_looks_like_land(c))
        early_spells = 0
        cheap_interaction = 0
        colored_pips = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for c in hand:
            if _card_looks_like_land(c):
                continue
            cost = parse_mana_cost(c.mana_cost)
            cmc = cost["generic"] + sum(cost[x] for x in ["W", "U", "B", "R", "G"])
            if cmc <= 2:
                early_spells += 1
            text = f"{(getattr(c, 'name', '') or '').lower()} {(getattr(c, 'oracle_text', '') or '').lower()}"
            if cmc <= 2 and any(k in text for k in ["counter target spell", "destroy target", "exile target", "deals"]):
                cheap_interaction += 1
            for sym in ["W", "U", "B", "R", "G"]:
                colored_pips[sym] += int(cost[sym] or 0)
        likely_sources = self._opening_color_sources_from_hand(hand)
        missing_primary_color = any(v >= 2 and likely_sources.get(k, 0) == 0 for k, v in colored_pips.items())
        mulligans = state.mulligan_count.get(player_id, 0)
        min_lands, max_lands = self._preferred_land_window()
        too_land_light = lands < min_lands
        too_land_heavy = lands > max_lands
        quality = (1.0 - min(abs(lands - 3), 3) / 3) * 0.65 + min(early_spells / 2, 1.0) * 0.25 + (0.1 if not missing_primary_color else 0.0)
        if mulligans < 2 and (too_land_light or too_land_heavy):
            return AIDecision(
                action={"type": "mulligan"},
                reasoning=f"Opening hand outside {min_lands}-{max_lands} land window for {self.archetype}",
            )
        if mulligans < 2 and missing_primary_color and lands <= 3:
            return AIDecision(action={"type": "mulligan"}, reasoning="Missing key color access in opening hand")
        if mulligans < 2 and quality < 0.45:
            return AIDecision(action={"type": "mulligan"}, reasoning="Opening hand quality too low")
        if mulligans < 2 and self._is_burn_matchup() and (lands < 2 or cheap_interaction == 0):
            return AIDecision(action={"type": "mulligan"}, reasoning="Burn matchup requires stable mana and early interaction")
        return AIDecision(action={"type": "keep_hand", "bottom_card_ids": []}, reasoning="Keep acceptable hand")

    def _preferred_land_window(self) -> tuple[int, int]:
        arche = self.archetype
        if arche in {"Control", "Counter-heavy"}:
            return (3, 5)
        if arche in {"Ramp"}:
            return (3, 5)
        if arche in {"Aggro", "Burn", "Tempo", "Tribal", "Tokens"}:
            return (2, 4)
        return (2, 5)

    def _rank_moves(self, state: MatchState, moves: list[dict], player_id: int) -> list[dict]:
        in_main = _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}
        own_main_sorcery_window = (
            in_main
            and getattr(state, "active_player", player_id) == player_id
            and not (getattr(state, "stack", []) or [])
        )
        castable_creature_moves = []
        for m in moves:
            if m.get("type") != "cast_spell":
                continue
            cid = m.get("card_id")
            card = state.cards.get(cid) if cid else None
            if card and "Creature" in card.types:
                castable_creature_moves.append(m)

        def score(move: dict) -> float:
            mtype = move.get("type")
            base = evaluate_board(state, player_id)
            stack_items = getattr(state, "stack", []) or []
            cast_moves = [m for m in moves if m.get("type") == "cast_spell"]
            if mtype == "cast_spell":
                name = move.get("card_name", "").lower()
                base += self._cast_bias(state, move, player_id)
                if "bolt" in name or "spike" in name:
                    base += 6 if self.archetype in {"Burn", "Aggro", "Tempo"} else 3
                if "counterspell" in name:
                    if stack_items:
                        base += (9 if self.archetype in {"Control", "Counter-heavy", "Tempo"} else 4) + self._best_stack_threat_score(
                            state, player_id
                        )
                    else:
                        base -= 2
            elif mtype == "play_land":
                base += 8
            elif mtype == "tap_land_for_mana":
                # Avoid floating mana loops: only tap proactively if it helps convert to a cast now.
                if cast_moves:
                    base += 0.4
                else:
                    base -= 3.0
            elif mtype == "attack":
                base += self._attack_bias(state, move, player_id)
            elif mtype == "block":
                base += self._block_bias(state, move, player_id)
            elif mtype == "pass_priority":
                base += self._pass_bias(state, player_id)
                if own_main_sorcery_window and castable_creature_moves:
                    # Avoid stalling with threats stranded in hand when we can safely deploy.
                    base -= 2.6
            if self.difficulty in {"master", "master_plus"}:
                base += self._simulate_delta(state, move, player_id)
            if self.difficulty == "master_plus":
                base += self._rollout_delta(state, move, player_id)
            return base

        ranked = sorted(moves, key=score, reverse=True)
        normalized = []
        for move in ranked:
            if move.get("type") == "attack" and "attackers" not in move:
                move = move.copy()
                move["attackers"] = move.get("options", [])
            normalized.append(move)
        return normalized

    def _simulate_delta(self, state: MatchState, move: dict, player_id: int) -> float:
        # Two-ply lookahead: own action value minus opponent best reply value.
        try:
            before = evaluate_board(state, player_id)
            sim_state = copy.deepcopy(state)
            self.engine.take_action(sim_state, player_id, move)
            self._approximate_resolution_for_creature_cast(sim_state, move, player_id)
            after = evaluate_board(sim_state, player_id)
            opp_id = 1 if player_id == 2 else 2
            opp_moves = self.engine.legal_moves(sim_state, sim_state.priority_player)
            if sim_state.priority_player == opp_id and opp_moves:
                best_reply = self._best_reply_delta(sim_state, opp_moves, player_id, opp_id)
            else:
                best_reply = 0.0
            return (after - before) * 0.7 - best_reply * 0.5
        except Exception:
            return 0.0

    def _best_reply_delta(self, sim_state: MatchState, opp_moves: list[dict], eval_for_player: int, opp_id: int) -> float:
        worst = 0.0
        before = evaluate_board(sim_state, eval_for_player)
        for reply in opp_moves[:8]:
            try:
                branch = copy.deepcopy(sim_state)
                self.engine.take_action(branch, opp_id, reply)
                delta = before - evaluate_board(branch, eval_for_player)
                if delta > worst:
                    worst = delta
            except Exception:
                continue
        return worst

    def _attack_bias(self, state: MatchState, move: dict, player_id: int) -> float:
        attackers = move.get("options") or move.get("attackers") or []
        if not attackers:
            return -1.0
        opp_id = 1 if player_id == 2 else 2
        attack_power = sum((state.cards[c].power or 0) for c in attackers if c in state.cards)
        opp_block_power = sum(
            (state.cards[c].power or 0)
            for c in state.players[opp_id].battlefield
            if c in state.cards and "Creature" in state.cards[c].types and not state.cards[c].tapped
        )
        opp_blockers = sum(
            1
            for c in state.players[opp_id].battlefield
            if c in state.cards and "Creature" in state.cards[c].types and not state.cards[c].tapped
        )
        race_pressure = max(0, 20 - state.players[opp_id].life) * 0.2
        role = self._board_role(state, player_id)
        archetype_bias = 5 if self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} else 2
        if role == "defend":
            archetype_bias -= 2.2
        elif role == "race":
            archetype_bias += 1.4
        unblocked_bonus = 3.5 if opp_blockers == 0 else 0.0
        lethal_bonus = 20.0 if attack_power >= state.players[opp_id].life else 0.0
        return archetype_bias + attack_power * 0.8 - opp_block_power * 0.35 + race_pressure + unblocked_bonus + lethal_bonus

    def _pass_bias(self, state: MatchState, player_id: int) -> float:
        has_instant_like = False
        for cid in state.players[player_id].hand:
            c = state.cards.get(cid)
            if not c:
                continue
            keywords = [k.lower() for k in (getattr(c, "keywords", []) or [])]
            if "Instant" in c.types or "flash" in keywords:
                has_instant_like = True
                break
        if getattr(state, "stack", []) or []:
            return -2.0
        if self._can_deploy_major_threat(state, player_id):
            return -1.2
        if self._should_force_proactive_control_line(state, player_id):
            return -2.1
        if self._is_burn_matchup() and getattr(state, "active_player", player_id) == player_id and _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}:
            return -1.0
        if has_instant_like and self.archetype in {"Control", "Counter-heavy", "Tempo"}:
            return 1.8 + float(self.matchup_profile.get("holdup_bias", 0.0))
        if self._should_hold_up_interaction(state, player_id):
            return 1.4 + float(self.matchup_profile.get("holdup_bias", 0.0))
        return 0.3 - float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.25

    def _should_hold_up_interaction(self, state: MatchState, player_id: int) -> bool:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo"}:
            return False
        if self._can_deploy_major_threat(state, player_id):
            return False
        if getattr(state, "active_player", player_id) != player_id:
            return False
        opp_id = 1 if player_id == 2 else 2
        opp_untapped = sum(
            1
            for cid in state.players[opp_id].battlefield
            if "Land" in (state.cards.get(cid).types if cid in state.cards else []) and not state.cards[cid].tapped
        )
        # If opponent cannot realistically represent interaction, be more proactive.
        if opp_untapped <= 1:
            return False
        if self._should_force_proactive_control_line(state, player_id):
            return False
        has_counter = any(
            "counter target spell" in f"{(state.cards[cid].name or '').lower()} {(state.cards[cid].oracle_text or '').lower()}"
            for cid in state.players[player_id].hand
            if cid in state.cards
        )
        return has_counter and opp_untapped >= 2 and float(self.matchup_profile.get("holdup_bias", 0.0)) >= -0.2

    def _block_bias(self, state: MatchState, move: dict, player_id: int) -> float:
        blocker_ids = [x["id"] for x in (move.get("blockers") or [])]
        attacker_ids = [x["id"] for x in (move.get("attackers") or [])]
        if not blocker_ids or not attacker_ids:
            return -0.8
        threatened = sum((state.cards.get(cid).power or 0) for cid in attacker_ids if cid in state.cards)
        life = state.players[player_id].life
        lethal_pressure = 4.0 if threatened >= life else 0.0
        profitable = 0.0
        for aid in attacker_ids:
            atk = state.cards.get(aid)
            if not atk:
                continue
            atk_pow = atk.power or 0
            atk_tgh = atk.toughness or 0
            best = 0.0
            for bid in blocker_ids:
                blk = state.cards.get(bid)
                if not blk:
                    continue
                blk_pow = blk.power or 0
                blk_tgh = blk.toughness or 0
                score = 0.0
                if blk_pow >= atk_tgh:
                    score += 1.6
                if blk_tgh > atk_pow:
                    score += 0.8
                if atk_pow > 0:
                    score += min(atk_pow, 4) * 0.2
                if score > best:
                    best = score
            profitable += best
        arche_bonus = 0.8 if self.archetype in {"Control", "Midrange", "Ramp"} else 0.3
        if self.archetype in {"Aggro", "Burn", "Tempo"} and life > 8:
            arche_bonus -= 0.4
        # Penalize blocking with mana-producing creatures
        mana_penalty = 0.0
        for bid in blocker_ids:
            blk = state.cards.get(bid)
            if blk:
                blk_text = (getattr(blk, "oracle_text", "") or "").lower()
                if ("{t}" in blk_text or "(t)" in blk_text) and ("add " in blk_text or "adds " in blk_text):
                    mana_penalty += 3.5
        return profitable + lethal_pressure + arche_bonus - mana_penalty

    def _cast_bias(self, state: MatchState, move: dict, player_id: int) -> float:
        cid = move.get("card_id")
        card = state.cards.get(cid) if cid else None
        if not card:
            return 0.0
        if self._should_hold_up_interaction(state, player_id) and "Instant" not in card.types and not self._is_major_threat_card(card):
            return -1.4
        is_creature = "Creature" in card.types
        arche = self.archetype
        tags = self._spell_tags(card)
        my_creatures = sum(
            1
            for perm_id in state.players[player_id].battlefield
            if "Creature" in state.cards.get(perm_id, type("X", (), {"types": []})()).types
        )
        early_turn = state.turn <= 4
        in_main = _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}
        own_main_sorcery_window = (
            in_main
            and getattr(state, "active_player", player_id) == player_id
            and not (getattr(state, "stack", []) or [])
        )
        mana_req = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=("Land" in card.types))
        cmc = mana_req["generic"] + sum(mana_req[c] for c in ["W", "U", "B", "R", "G"])
        mana_cost_text = (getattr(card, "mana_cost", "") or "").upper()
        x_value = 0
        if "{X}" in mana_cost_text:
            x_value = self._choose_x_value(state, player_id, mana_cost_text)
            if x_value <= 0:
                # Avoid invalid X=0 loops for spells that need explicit positive X targeting.
                return -8.0
            x_penalty = self._x_spell_timing_penalty(state, card, player_id, x_value)
            if x_penalty <= -3.5:
                return x_penalty
        power = getattr(card, "power", 0) or 0
        is_big_threat = power >= 4 or cmc >= 4

        if is_creature:
            if arche in {"Aggro", "Tribal", "Tokens", "Tempo"}:
                bonus = 4.0
                if in_main:
                    bonus += 1.2
                if my_creatures < 2:
                    bonus += 2.0
                if early_turn:
                    bonus += 1.0
                return bonus
            if arche in {"Midrange", "Ramp", "Aristocrats"}:
                bonus = 2.0 + (0.8 if my_creatures < 2 else 0.0)
                if is_big_threat and (my_creatures < 2 or state.turn >= 5):
                    bonus += 2.2
                if arche == "Ramp" and state.turn >= 4 and is_big_threat:
                    bonus += 1.2
                return bonus
            if arche in {"Control", "Counter-heavy"}:
                bonus = 0.8
                if is_big_threat and (my_creatures == 0 or state.turn >= 6):
                    bonus += 3.0
                if own_main_sorcery_window and is_big_threat:
                    bonus += 0.7
                return bonus
            return 1.2

        if "creature_deploy_topdeck" in tags:
            bonus = 3.6
            if arche in {"Tribal", "Aggro", "Midrange", "Tempo", "Ramp"}:
                bonus += 2.2
            if len(state.players[player_id].hand) <= 2:
                bonus += 1.4
            if state.turn >= 4:
                bonus += 0.8
            return bonus

        if arche in {"Control", "Counter-heavy"}:
            bonus = 0.0
            opp_id = 1 if player_id == 2 else 2
            opp_creatures = sum(
                1
                for cid in state.players[opp_id].battlefield
                if cid in state.cards and "Creature" in state.cards[cid].types
            )
            opp_untapped_lands = sum(
                1
                for cid in state.players[opp_id].battlefield
                if cid in state.cards and "Land" in state.cards[cid].types and not state.cards[cid].tapped
            )
            if "counter" in tags:
                bonus += 5.5 if getattr(state, "stack", []) else -2.5
            if "draw" in tags:
                bonus += 2.2
                if "Instant" in card.types:
                    on_opp_turn = getattr(state, "active_player", player_id) != player_id
                    in_end = _step_key(getattr(state, "step", "")) == "end_step"
                    if on_opp_turn or in_end:
                        bonus += 2.4
                # Be proactive when opponent is tapped down and interaction risk is low.
                if opp_untapped_lands <= 1 and own_main_sorcery_window:
                    bonus += 1.1
                if own_main_sorcery_window and self._should_force_proactive_control_line(state, player_id):
                    bonus += 1.0
                if self._is_burn_matchup() and state.turn <= 4 and opp_creatures > 0:
                    bonus -= 2.0
            if "removal" in tags:
                bonus += 2.0
                # Don't fire premium removal into empty/low-pressure board states.
                if opp_creatures == 0:
                    bonus -= 2.5
                elif own_main_sorcery_window and self._should_force_proactive_control_line(state, player_id):
                    bonus += 0.8
                if self._is_burn_matchup() and opp_creatures > 0:
                    bonus += 2.4
            if self._is_burn_matchup() and "counter" in tags and state.turn <= 3 and not (getattr(state, "stack", []) or []):
                bonus -= 0.8
            if self._is_burn_matchup() and "sweeper" in f"{(getattr(card, 'name', '') or '').lower()} {(getattr(card, 'oracle_text', '') or '').lower()}":
                if opp_creatures >= 2:
                    bonus += 2.8
                else:
                    bonus -= 1.2
            if ("Planeswalker" in set(getattr(card, "types", []) or []) or is_big_threat) and own_main_sorcery_window:
                if self._should_force_proactive_control_line(state, player_id):
                    bonus += 2.3
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus

        if arche in {"Midrange"}:
            bonus = 0.0
            if "removal" in tags:
                bonus += 2.0
            if "draw" in tags:
                bonus += 1.2
            if "burn" in tags and state.players[1 if player_id == 2 else 2].life <= 6:
                bonus += 1.5
            return bonus

        if arche in {"Ramp"}:
            bonus = 0.0
            if "ramp" in tags:
                bonus += 4.0 if early_turn else 1.0
            if "draw" in tags:
                bonus += 1.5
            return bonus

        if arche in {"Tokens"}:
            bonus = 0.0
            if "token" in tags:
                bonus += 5.5
            if "anthem" in tags:
                bonus += 5.0 if my_creatures >= 2 else 2.2
            if "Enchantment" in card.types:
                bonus += 3.2
                if state.turn <= 4:
                    bonus += 1.2
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus

        if arche in {"Reanimator"}:
            bonus = 0.0
            if "reanimate" in tags:
                bonus += 4.0
            if "discard" in tags or "mill" in tags:
                bonus += 2.0
            return bonus

        if arche in {"Aristocrats", "Drain"}:
            bonus = 0.0
            if "drain" in tags:
                bonus += 3.2
            if "sacrifice" in tags:
                bonus += 2.4
            return bonus

        if arche in {"Tempo"}:
            bonus = 0.0
            if "counter" in tags:
                bonus += 3.6 if getattr(state, "stack", []) else -1.4
            if "removal" in tags:
                bonus += 1.8
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus

        if arche in {"Aggro", "Tribal", "Tokens", "Tempo"} and my_creatures == 0 and early_turn and in_main:
            return -1.8
        # Log-driven priors: leverage observed tournament/simulation cast timing.
        return self._historical_cast_timing_bias(state, card)

    def _historical_cast_timing_bias(self, state: MatchState, card) -> float:
        priors = AIAgent._log_priors_cache or {}
        cards = priors.get("cards") if isinstance(priors, dict) else None
        if not isinstance(cards, dict):
            return 0.0
        key = str(getattr(card, "name", "") or "").strip().lower()
        row = cards.get(key)
        if not isinstance(row, dict):
            return 0.0
        casts = int(row.get("casts", 0) or 0)
        if casts < 6:
            return 0.0
        turn = int(getattr(state, "turn", 1) or 1)
        preferred_min = int(row.get("preferred_min_turn", 1) or 1)
        early_rate = float(row.get("early_turn_cast_rate", 0.0) or 0.0)
        late_rate = float(row.get("late_turn_cast_rate", 0.0) or 0.0)
        text = (getattr(card, "oracle_text", "") or "").lower()
        non_creature = "Creature" not in set(getattr(card, "types", []) or [])
        # Slow-play/control heuristics from logs: punish premature timing on low-early cards.
        if turn < preferred_min and early_rate <= 0.2 and non_creature:
            severity = min(3.5, max(0.6, (preferred_min - turn) * 0.8))
            if "counter target spell" in text and not (getattr(state, "stack", []) or []):
                severity += 0.8
            return -severity
        # Reward cards historically skewed late once the game is developed.
        if turn >= preferred_min and late_rate >= 0.45:
            return 0.8
        return 0.0

    def _x_spell_timing_penalty(self, state: MatchState, card, player_id: int, x_value: int) -> float:
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        if x_value <= 0:
            return -8.0
        # Token X-spells (e.g. Secure the Wastes): avoid low-impact early casts.
        if "create x" in text and "token" in text:
            if x_value <= 1:
                return -7.0
            if x_value == 2 and turn < 7:
                return -4.0
            if x_value <= 3 and self.archetype in {"Control", "Counter-heavy"} and opp_life > 8:
                return -2.0
        # Draw-X spells should usually wait for meaningful value.
        if "draw x" in text and x_value <= 1:
            return -3.0
        # X-damage with tiny X is usually poor unless lethal.
        if "deals x damage" in text and x_value <= 1 and opp_life > x_value:
            return -2.5
        return 0.0

    def _approximate_resolution_for_creature_cast(self, sim_state: MatchState, move: dict, player_id: int) -> None:
        if move.get("type") != "cast_spell":
            return
        cid = move.get("card_id")
        if not cid:
            return
        card = sim_state.cards.get(cid)
        if not card or "Creature" not in card.types:
            return
        if not getattr(sim_state, "stack", []):
            return
        # Approximation: if both players pass, creature resolves and enters battlefield.
        # This prevents lookahead from systematically undervaluing creature development.
        if sim_state.priority_player != player_id:
            return
        opp_id = 1 if player_id == 2 else 2
        self.engine.take_action(sim_state, player_id, {"type": "pass_priority"})
        self.engine.take_action(sim_state, opp_id, {"type": "pass_priority"})

    def _spell_tags(self, card) -> set[str]:
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        tags: set[str] = set()
        if "counter target spell" in text or "counterspell" in text:
            tags.add("counter")
        if any(k in text for k in ["destroy all creatures", "wrath", "damnation", "supreme verdict"]):
            tags.add("sweeper")
        if "draw" in text:
            tags.add("draw")
        if "destroy target" in text or "exile target" in text or "deals" in text:
            tags.add("removal")
        if any(k in text for k in ["bolt", "spike", "shock", "lava"]):
            tags.add("burn")
        if "add {" in text or any(k in text for k in ["cultivate", "rampant", "llanowar", "mana dork"]):
            tags.add("ramp")
        if "create" in text and "token" in text:
            tags.add("token")
        if "look at the top" in text and "creature cards" in text and "onto the battlefield" in text:
            tags.add("creature_deploy_topdeck")
        if "creatures you control get" in text or "+1/+1" in text:
            tags.add("anthem")
        if "enchantment" in text:
            tags.add("enchantment")
        if "return target creature card from your graveyard" in text or "reanimate" in text:
            tags.add("reanimate")
        if "discard" in text:
            tags.add("discard")
        if "mill" in text:
            tags.add("mill")
        if "sacrifice" in text:
            tags.add("sacrifice")
        if "lose" in text and "gain" in text:
            tags.add("drain")
        return tags

    def _materialize_action(self, state: MatchState, move: dict, player_id: int) -> dict:
        mtype = move.get("type")
        if mtype == "attack":
            out = dict(move)
            candidates = list(move.get("options") or out.get("attackers") or [])
            if candidates:
                out["attackers"] = self._choose_attackers(state, candidates, player_id)
            return out
        if mtype == "block":
            out = dict(move)
            attackers = list(move.get("attackers") or [])
            blockers = list(move.get("blockers") or [])
            if attackers and blockers and not out.get("blocks"):
                out["blocks"] = self._choose_blocks(state, attackers, blockers)
            return out
        if mtype not in {"cast_spell", "activate_loyalty"}:
            return move
        out = dict(move)
        hints = move.get("target_hints") or {}
        targets = dict((move.get("targets") or {}))
        cost_options = move.get("cost_options") or []
        if cost_options and not (move.get("cost_choice") or {}).get("id"):
            out["cost_choice"] = {"id": cost_options[0]["id"]}
        tags: set[str] = set()
        cid = move.get("card_id")
        card = state.cards.get(cid) if cid else None
        if card:
            tags = self._spell_tags(card)
        opponent = 1 if player_id == 2 else 2

        stack_targets = hints.get("stack_targets") or []
        if stack_targets and not targets.get("target_stack_id"):
            # For counters/interaction, target the most threatening spell on stack.
            if "counter" in tags:
                best = self._choose_best_stack_target_id(state, player_id, stack_targets)
                targets["target_stack_id"] = best or stack_targets[-1]["id"]
            else:
                # Default to top-of-stack for most non-counter interactions.
                targets["target_stack_id"] = stack_targets[-1]["id"]

        player_targets = hints.get("player_targets") or []
        if player_targets and targets.get("target_player") is None and not targets.get("target_card_id"):
            if "gain" in tags and "drain" not in tags:
                targets["target_player"] = player_id
            else:
                targets["target_player"] = opponent

        creature_targets = hints.get("creature_targets") or []
        if creature_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(creature_targets, key=lambda t: self._creature_threat_score(state, t.get("id"), player_id), default=None)
            if best:
                targets["target_card_id"] = best["id"]

        planeswalker_targets = hints.get("planeswalker_targets") or []
        if planeswalker_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            targets["target_card_id"] = planeswalker_targets[0]["id"]

        if hints.get("supports_divide") and not targets.get("target_distribution"):
            if creature_targets:
                # Put first point on highest-threat creature by default.
                best = max(creature_targets, key=lambda t: self._creature_threat_score(state, t.get("id"), player_id), default=None)
                if best:
                    targets["target_distribution"] = {best["id"]: 1}
            elif player_targets:
                targets["target_distribution"] = {str(opponent): 1}
            targets.setdefault("divide_total", 1)

        if hints.get("modes") and not targets.get("mode_text") and not targets.get("mode_texts"):
            if hints.get("choose_two_modes"):
                targets["mode_texts"] = list(hints["modes"][:2])
            else:
                targets["mode_text"] = hints["modes"][0]

        mana_cost = move.get("mana_cost") or getattr(card, "mana_cost", "") or ""
        if "{X}" in mana_cost.upper() and "x_value" not in targets:
            targets["x_value"] = self._choose_x_value(state, player_id, mana_cost)
        elif hints.get("requires_x_value") and "x_value" not in targets:
            if mtype == "activate_loyalty" and cid:
                loyalty_now = int(getattr(state.cards.get(cid), "loyalty", 0) or 0)
                targets["x_value"] = max(0, min(3, loyalty_now))
            else:
                targets["x_value"] = 1

        requires_x = bool(hints.get("requires_x_value"))
        if card:
            mana_text = (getattr(card, "mana_cost", "") or "").upper()
            oracle_text = (getattr(card, "oracle_text", "") or "").lower()
            if "{X}" in mana_text or (" x " in f" {oracle_text} " and "target" in oracle_text):
                requires_x = True

        if requires_x:
            try:
                xv = int(targets.get("x_value", 0) or 0)
            except Exception:
                xv = 0
            if xv <= 0:
                out["_invalid_ai_choice"] = True

        out["targets"] = targets
        return out

    def _choose_blocks(self, state: MatchState, attackers: list[dict], blockers: list[dict]) -> dict[str, str | list[str]]:
        available = [b["id"] for b in blockers if b.get("id") in state.cards]
        if not available:
            return {}
        assignments: dict[str, str | list[str]] = {}
        player_id = getattr(state, "priority_player", None)
        if player_id not in getattr(state, "players", {}):
            player_id = None
            for bid in available:
                blk = state.cards.get(bid)
                ctrl = getattr(blk, "controller", None)
                if ctrl in getattr(state, "players", {}):
                    player_id = ctrl
                    break
            if player_id is None:
                player_id = 1
        incoming_total = sum(
            (state.cards[a["id"]].power or 0)
            for a in attackers
            if a.get("id") in state.cards
        )
        life = state.players[player_id].life if player_id in state.players else 20
        lethal_pressure = incoming_total >= life
        prevented = 0
        sorted_attackers = sorted(
            [a for a in attackers if a.get("id") in state.cards],
            key=lambda a: (state.cards[a["id"]].power or 0),
            reverse=True,
        )
        for a in sorted_attackers:
            aid = a["id"]
            atk = state.cards.get(aid)
            if not atk:
                continue
            atk_pow = atk.power or 0
            atk_tgh = atk.toughness or 0
            atk_has_trample = "trample" in {str(k).lower() for k in (getattr(atk, "keywords", []) or [])}
            atk_has_deathtouch = "deathtouch" in {str(k).lower() for k in (getattr(atk, "keywords", []) or [])}
            required_blockers = 2 if self._requires_two_or_more_blockers(atk) else 1
            best_bid = None
            best_score = -999.0
            scored: list[tuple[float, str]] = []
            for bid in available:
                blk = state.cards.get(bid)
                if not blk:
                    continue
                blk_pow = blk.power or 0
                blk_tgh = blk.toughness or 0
                score = 0.0
                # Primary value: prevent face damage.
                score += (atk_pow or 0) * 1.15
                if blk_pow >= atk_tgh:
                    score += 2.2
                if blk_tgh > atk_pow:
                    score += 1.0
                if atk_has_trample and blk_tgh <= atk_pow:
                    score -= 0.7
                if atk_has_deathtouch:
                    score -= 0.6
                if blk_tgh <= atk_pow and blk_pow < atk_tgh:
                    # Pure chump trades are less desirable unless needed.
                    score -= 1.4
                score += min(atk_pow, 5) * 0.25
                # Penalize blocking with mana-producing creatures — they're
                # worth more untapped than the damage they prevent, especially early game.
                blk_text = (getattr(blk, "oracle_text", "") or "").lower()
                if ("{t}" in blk_text or "(t)" in blk_text) and ("add " in blk_text or "adds " in blk_text):
                    score -= 3.5
                scored.append((score, bid))
                if score > best_score:
                    best_score = score
                    best_bid = bid
            threshold = -0.8 if lethal_pressure else 0.45
            if required_blockers == 2:
                scored.sort(reverse=True)
                if len(scored) < 2:
                    continue
                pair = [scored[0][1], scored[1][1]]
                pair_score = scored[0][0] + scored[1][0]
                if pair_score <= threshold * 2:
                    continue
                assignments[aid] = pair
                prevented += max(0, atk_pow)
                for bid in pair:
                    if bid in available:
                        available.remove(bid)
                if not available:
                    break
                # If we have prevented enough to avoid lethal and remaining trades are poor, stop.
                if lethal_pressure and incoming_total - prevented < life:
                    lethal_pressure = False
                continue

            if best_bid is not None and best_score > threshold:
                assignments[aid] = best_bid
                prevented += max(0, atk_pow)
                available.remove(best_bid)
                if not available:
                    break
                # If we have prevented enough to avoid lethal and remaining trades are poor, stop.
                if lethal_pressure and incoming_total - prevented < life:
                    lethal_pressure = False
        return assignments

    def _requires_two_or_more_blockers(self, attacker) -> bool:
        keywords = {str(k).lower() for k in (getattr(attacker, "keywords", []) or [])}
        if "menace" in keywords:
            return True
        text = (getattr(attacker, "oracle_text", "") or "").lower()
        return "can't be blocked except by two or more creatures" in text or "cannot be blocked except by two or more creatures" in text

    def _choose_attackers(self, state: MatchState, candidates: list[str], player_id: int) -> list[str]:
        opp_id = 1 if player_id == 2 else 2
        opp_blockers = [
            cid
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        ]
        if not opp_blockers:
            return list(candidates)

        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        opp_life = state.players[opp_id].life
        chosen: list[str] = []
        my_life = state.players[player_id].life
        race_mode = my_life <= 7 or opp_life <= 6
        for cid in candidates:
            card = state.cards.get(cid)
            if not card:
                continue
            atk_pow = _eff_pow(state, cid)
            atk_tgh = _eff_tgh(state, cid)
            atk_kw = {str(k).lower() for k in (getattr(card, "keywords", []) or [])}
            has_trample = "trample" in atk_kw
            has_deathtouch = "deathtouch" in atk_kw
            if atk_pow <= 0:
                continue

            dies_to_some = any(_eff_pow(state, b) >= atk_tgh for b in opp_blockers)
            kills_some = any(_eff_tgh(state, b) <= atk_pow for b in opp_blockers)
            favorable_trade = kills_some and (not dies_to_some or atk_pow >= 2)
            # Avoid obvious bad attacks with small bodies into larger blockers.
            if atk_pow <= 1 and dies_to_some and not kills_some and opp_life > 1 and not has_trample:
                continue
            # General anti-suicide rule for all archetypes.
            # Aggro can still pressure in race/lethal setups, but should not throw creatures away for no value.
            if (
                dies_to_some
                and not favorable_trade
                and not has_deathtouch
                and not has_trample
                and opp_life > atk_pow
                and not race_mode
            ):
                continue

            chosen.append(cid)

        # Tactical crackback safety: avoid attacks that expose an immediate lethal swing.
        if chosen and not race_mode:
            safe = self._remove_high_risk_attackers(state, chosen, candidates, player_id)
            if safe:
                chosen = safe

        # If nothing qualifies but we have lethal on board, send all.
        if not chosen:
            total_power = sum((state.cards[c].power or 0) for c in candidates if c in state.cards)
            if total_power >= opp_life:
                return list(candidates)
        return chosen

    def _creature_threat_score(self, state: MatchState, creature_id: str | None, player_id: int) -> float:
        if not creature_id or creature_id not in state.cards:
            return -999.0
        card = state.cards[creature_id]
        if "Creature" not in (getattr(card, "types", []) or []):
            return -500.0
        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        power = max(0, _eff_pow(state, creature_id))
        toughness = max(0, _eff_tgh(state, creature_id))
        kws = {str(k).lower() for k in (getattr(card, "keywords", []) or [])}
        score = power * 1.2 + toughness * 0.35
        if "flying" in kws or "trample" in kws or "menace" in kws:
            score += 1.8
        if "deathtouch" in kws:
            score += 1.2
        if "lifelink" in kws:
            score += 1.0
        if "ward" in (getattr(card, "oracle_text", "") or "").lower() or "hexproof" in kws:
            score += 1.0
        # Prefer removing immediate lethal/race pressure.
        me = state.players[player_id]
        if power >= me.life:
            score += 5.0
        return score

    def _remove_high_risk_attackers(self, state: MatchState, chosen: list[str], candidates: list[str], player_id: int) -> list[str]:
        opp_id = 1 if player_id == 2 else 2
        from rules_engine.continuous import effective_power as _eff_pow
        from rules_engine.continuous import effective_toughness as _eff_tgh

        def _crackback_risk(attackers: list[str]) -> int:
            # Approximate worst-case next turn damage by untapped opposing creatures.
            # We discount by likely defenders we keep back after this attack.
            our_remaining = [
                cid
                for cid in state.players[player_id].battlefield
                if cid in state.cards and "Creature" in state.cards[cid].types and cid not in attackers
            ]
            our_block_value = sum(max(0, _eff_pow(state, cid)) for cid in our_remaining if not state.cards[cid].tapped)
            opp_attack_value = sum(
                max(0, _eff_pow(state, cid))
                for cid in state.players[opp_id].battlefield
                if cid in state.cards and "Creature" in state.cards[cid].types and not state.cards[cid].tapped
            )
            return max(0, opp_attack_value - int(our_block_value * 0.6))

        my_life = int(state.players[player_id].life or 0)
        current = list(chosen)
        while current:
            risk = _crackback_risk(current)
            if risk < my_life:
                return current
            # pull back weakest attacker first
            weakest = min(current, key=lambda cid: (_eff_pow(state, cid), _eff_tgh(state, cid)))
            current.remove(weakest)
        return []

    def _choose_x_value(self, state: MatchState, player_id: int, mana_cost: str) -> int:
        pool_total = sum((state.players[player_id].mana_pool or {}).values())
        untapped_lands = sum(
            1
            for cid in state.players[player_id].battlefield
            if "Land" in state.cards.get(cid, type("X", (), {"types": []})()).types and not state.cards[cid].tapped
        )
        upper = max(0, pool_total + untapped_lands)
        for x in range(upper, 0, -1):
            cost = re.sub(r"\{X\}", f"{{{x}}}", mana_cost, flags=re.IGNORECASE)
            if can_pay_with_pool_and_lands(state, player_id, cost):
                return x
        return 0

    def _is_unplayable_x_action(self, action: dict) -> bool:
        if action.get("type") != "cast_spell":
            return False
        targets = action.get("targets") or {}
        if "x_value" not in targets:
            return False
        try:
            xv = int(targets.get("x_value", 0) or 0)
        except Exception:
            xv = 0
        return xv <= 0

    def _rollout_delta(self, state: MatchState, move: dict, player_id: int) -> float:
        # Lightweight rollout approximation for deeper tactical planning.
        try:
            sim = copy.deepcopy(state)
            self.engine.take_action(sim, player_id, move)
        except Exception:
            return 0.0
        if sim.winner == player_id:
            return 100.0
        if sim.winner is not None and sim.winner != player_id:
            return -100.0
        total = 0.0
        samples = 3
        plies = 6
        for _ in range(samples):
            branch = copy.deepcopy(sim)
            total += self._rollout_playout(branch, player_id, plies)
        return total / samples

    def _rollout_playout(self, state: MatchState, eval_for_player: int, plies: int) -> float:
        for _ in range(max(0, plies)):
            if state.winner is not None:
                break
            pid = state.priority_player
            legal = self.engine.legal_moves(state, pid)
            if not legal:
                break
            chosen = self._pick_rollout_move(state, legal, pid)
            try:
                self.engine.take_action(state, pid, chosen)
            except Exception:
                break
            if state.step == state.step.COMBAT_DAMAGE:
                try:
                    self.engine.take_action(state, state.active_player, {"type": "combat_damage"})
                except Exception:
                    break
        if state.winner == eval_for_player:
            return 40.0
        if state.winner is not None and state.winner != eval_for_player:
            return -40.0
        return evaluate_board(state, eval_for_player) * 0.05

    def _pick_rollout_move(self, state: MatchState, legal: list[dict], player_id: int) -> dict:
        # Fast rollout policy (no nested simulations).
        has_cast = any(m.get("type") == "cast_spell" for m in legal)

        def quick_score(move: dict) -> float:
            mtype = move.get("type")
            base = 0.0
            if mtype == "cast_spell":
                name = str(move.get("card_name", "")).lower()
                if "counterspell" in name and getattr(state, "stack", []):
                    base += 3 + self._best_stack_threat_score(state, player_id) * 0.5
                if any(k in name for k in ["bolt", "shock", "spike"]):
                    base += 4
            elif mtype == "attack":
                base += 3
            elif mtype == "play_land":
                base += 2
            elif mtype == "tap_land_for_mana":
                base += 0.2 if has_cast else -2.5
            elif mtype == "activate_loyalty":
                base += 2.5
            elif mtype == "pass_priority":
                base -= 0.2
            return base

        ranked = sorted(legal, key=quick_score, reverse=True)
        top = ranked[: min(3, len(ranked))]
        return top[0]

    def _best_land_move(self, state: MatchState, land_moves: list[dict], player_id: int) -> dict:
        demand = self._color_demand(state, player_id)
        current_sources = self._current_color_sources(state, player_id)

        def score_land(move: dict) -> float:
            cid = move.get("card_id")
            if not cid or cid not in state.cards:
                return -999.0
            card = state.cards[cid]
            produced = self._land_colors(card)
            if not produced:
                return 0.0
            score = 0.0
            for color, need in demand.items():
                if need > 0 and color in produced:
                    score += 1.5 + need * 0.2
            for color in produced:
                if current_sources.get(color, 0) == 0 and demand.get(color, 0) > 0:
                    score += 3.5
            score += len(produced) * 0.15
            return score

        return max(land_moves, key=score_land)

    def _remaining_land_plays(self, state: MatchState, player_id: int) -> int:
        player = state.players[player_id]
        max_land_plays = compute_max_land_plays_this_turn(state, player_id)
        if getattr(player, "last_land_play_turn", 0) == state.turn:
            used = max(
                int(getattr(player, "lands_played_this_turn", 0)),
                int(getattr(player, "land_plays_recorded_on_turn", 0)),
            )
        else:
            used = 0
        return max(0, int(max_land_plays) - int(used))

    def _should_break_stall(self, state: MatchState, legal_moves: list[dict], player_id: int) -> bool:
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "stack", []) or []:
            return False
        non_pass = [m for m in legal_moves if m.get("type") != "pass_priority"]
        if not non_pass:
            return False
        if any(m.get("type") == "play_land" for m in non_pass):
            return True
        # Control-style decks may pass to hold interaction, but once mana/turn grows
        # they should proactively advance board/card advantage.
        if self.archetype in {"Control", "Counter-heavy"}:
            hand_size = len(getattr(state.players[player_id], "hand", []))
            if getattr(state, "turn", 1) < 6 and hand_size < 6 and not self._should_force_proactive_control_line(state, player_id):
                return False
        return True

    def _should_force_proactive_control_line(self, state: MatchState, player_id: int) -> bool:
        """Push control decks to convert resources instead of over-passing in developed boards."""
        if self.archetype not in {"Control", "Counter-heavy"}:
            return False
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "stack", []) or []:
            return False
        turn = int(getattr(state, "turn", 1) or 1)
        hand_size = len(getattr(state.players[player_id], "hand", []))
        untapped_lands = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Land" in state.cards[cid].types and not state.cards[cid].tapped
        )
        # Late game or near hand-cap should proactively deploy card advantage/threats.
        return turn >= 6 and (hand_size >= 6 or untapped_lands >= 5)

    def _is_burn_matchup(self) -> bool:
        own = (self.archetype or "").strip().lower()
        opp = (self.opponent_archetype or "").strip().lower()
        return own in {"control", "counter-heavy"} and opp in {"burn", "aggro", "tempo"}

    def _best_proactive_non_pass(self, ranked_moves: list[dict], state: MatchState) -> dict | None:
        non_pass = [m for m in ranked_moves if m.get("type") not in {"pass_priority", "tap_land_for_mana", "tap_lands_bulk"}]
        if not non_pass:
            return None
        if getattr(state, "stack", []) or []:
            for move in non_pass:
                if move.get("type") == "cast_spell":
                    cid = move.get("card_id")
                    card = state.cards.get(cid) if cid else None
                    if card and self._is_counter_card(card):
                        return move
            return non_pass[0]
        for move in non_pass:
            if move.get("type") != "cast_spell":
                return move
            cid = move.get("card_id")
            card = state.cards.get(cid) if cid else None
            text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower() if card else ""
            if "counter target spell" in text:
                continue
            return move
        return non_pass[0]

    def _avoid_pass_with_main_phase_options(self, state: MatchState, legal_moves: list[dict], player_id: int, chosen: dict) -> dict:
        if chosen.get("type") != "pass_priority":
            return chosen
        if getattr(state, "active_player", player_id) != player_id:
            return chosen
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return chosen
        if getattr(state, "stack", []) or []:
            return chosen

        meaningful = [m for m in legal_moves if m.get("type") in {"play_land", "cast_spell", "activate_loyalty", "attack"}]
        if not meaningful:
            return chosen

        ranked = self._rank_moves(state, legal_moves, player_id)
        proactive = self._best_proactive_non_pass(ranked, state)
        if proactive is None:
            return chosen
        proactive = self._materialize_action(state, proactive, player_id)
        if proactive.get("_invalid_ai_choice") or self._is_unplayable_x_action(proactive):
            return chosen
        if self._is_action_obviously_illegal(state, proactive, player_id):
            return chosen
        if proactive.get("type") == "attack" and not (proactive.get("attackers") or []):
            return chosen
        return proactive

    def _is_action_obviously_illegal(self, state: MatchState, action: dict, player_id: int) -> bool:
        kind = action.get("type")
        if kind == "play_land":
            cid = action.get("card_id")
            if not cid:
                return True
            player = state.players[player_id]
            if cid not in player.hand:
                return True
            card = state.cards.get(cid)
            if not card or "Land" not in (getattr(card, "types", []) or []):
                return True
            if getattr(state, "active_player", player_id) != player_id:
                return True
            if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
                return True
            if (getattr(state, "stack", []) or []):
                return True
            if self._remaining_land_plays(state, player_id) <= 0:
                return True
        return False

    def _is_major_threat_card(self, card) -> bool:
        types = set(getattr(card, "types", []) or [])
        if "Planeswalker" in types:
            return True
        if "Creature" in types:
            power = int(getattr(card, "power", 0) or 0)
            mana_cost = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=False)
            cmc = mana_cost["generic"] + sum(mana_cost[c] for c in ["W", "U", "B", "R", "G"])
            return power >= 4 or cmc >= 5
        return False

    def _can_deploy_major_threat(self, state: MatchState, player_id: int) -> bool:
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if getattr(state, "stack", []) or []:
            return False
        turn = int(getattr(state, "turn", 1) or 1)
        for cid in getattr(state.players[player_id], "hand", []):
            card = state.cards.get(cid)
            if not card or not self._is_major_threat_card(card):
                continue
            if can_pay_with_pool_and_lands(state, player_id, getattr(card, "mana_cost", "")):
                # Preserve early-game hold-up discipline; deploy in developed states.
                return turn >= 5
        return False

    def _color_demand(self, state: MatchState, player_id: int) -> dict[str, int]:
        demand = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for cid in state.players[player_id].hand:
            card = state.cards.get(cid)
            if not card or "Land" in card.types:
                continue
            cost = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=False)
            cmc = cost["generic"] + sum(cost[c] for c in ["W", "U", "B", "R", "G"])
            weight = 2 if cmc <= 2 else (1 if cmc <= 4 else 0)
            for c in ["W", "U", "B", "R", "G"]:
                if cost[c] > 0:
                    demand[c] += weight * cost[c]
            text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
            if "counter target spell" in text:
                demand["U"] += 2
        return demand

    def _opening_color_sources_from_hand(self, hand: list) -> dict[str, int]:
        sources = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for c in hand:
            if not _card_looks_like_land(c):
                continue
            for sym in self._land_colors(c):
                if sym in sources:
                    sources[sym] += 1
        return sources

    def _board_role(self, state: MatchState, player_id: int) -> str:
        opp_id = 1 if player_id == 2 else 2
        my_life = int(getattr(state.players[player_id], "life", 20) or 20)
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        my_power = sum(
            max(0, int(getattr(state.cards.get(cid), "power", 0) or 0))
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        )
        opp_power = sum(
            max(0, int(getattr(state.cards.get(cid), "power", 0) or 0))
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        )
        if opp_life <= 7 or (my_power >= opp_life and opp_life <= 10):
            return "race"
        if my_life <= 8 and opp_power > my_power:
            return "defend"
        return "normal"

    def _current_color_sources(self, state: MatchState, player_id: int) -> dict[str, int]:
        sources = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for cid in state.players[player_id].battlefield:
            card = state.cards.get(cid)
            if not card or "Land" not in card.types:
                continue
            for c in self._land_colors(card):
                if c in sources:
                    sources[c] += 1
        return sources

    def _land_colors(self, card) -> set[str]:
        colors: set[str] = set()
        type_line = (getattr(card, "type_line", "") or "").lower()
        name = (getattr(card, "name", "") or "").lower()
        oracle = (getattr(card, "oracle_text", "") or "").upper()
        mapping = {"plains": "W", "island": "U", "swamp": "B", "mountain": "R", "forest": "G"}
        for basic, sym in mapping.items():
            if basic in type_line or basic in name:
                colors.add(sym)
        for sym in re.findall(r"\{([WUBRG])\}", oracle):
            colors.add(sym)
        return colors

    def _is_counter_card(self, card) -> bool:
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        return "counter target spell" in text or "counterspell" in text

    def _choose_best_stack_target_id(self, state: MatchState, player_id: int, candidates: list[dict]) -> str | None:
        best_id = None
        best_score = -999.0
        for c in candidates:
            sid = c.get("id")
            if not sid:
                continue
            score = self._stack_item_threat_score(state, sid, player_id)
            if score > best_score:
                best_score = score
                best_id = sid
        return best_id

    def _best_stack_threat_score(self, state: MatchState, player_id: int) -> float:
        items = getattr(state, "stack", []) or []
        if not items:
            return 0.0
        return max(self._stack_item_threat_score(state, it.id, player_id) for it in items)

    def _stack_item_threat_score(self, state: MatchState, stack_item_id: str, player_id: int) -> float:
        item = next((x for x in (getattr(state, "stack", []) or []) if getattr(x, "id", None) == stack_item_id), None)
        if item is None:
            return 0.0
        source = state.cards.get(getattr(item, "source_card_id", ""))
        if source is None:
            return 1.0
        score = 0.0
        types = set(getattr(source, "types", []) or [])
        if "Planeswalker" in types:
            score += 8.0
        if "Creature" in types:
            p = int(getattr(source, "power", 0) or 0)
            t = int(getattr(source, "toughness", 0) or 0)
            score += min(7.0, p * 0.9 + t * 0.3)
        mana_cost = parse_mana_cost(getattr(source, "mana_cost", ""), is_land=False)
        cmc = mana_cost["generic"] + sum(mana_cost[c] for c in ["W", "U", "B", "R", "G"])
        score += min(5.0, cmc * 0.45)
        text = f"{getattr(source, 'name', '')} {getattr(source, 'oracle_text', '')}".lower()
        if any(k in text for k in ["destroy all", "exile all", "sweeper", "wrath", "damnation"]):
            score += 6.0
        if any(k in text for k in ["draw", "memory deluge", "dig through", "treasure cruise"]):
            score += 2.2
        if any(k in text for k in ["counter target spell"]):
            score += 1.4
        controller = getattr(item, "controller", None)
        if controller == player_id:
            score -= 10.0
        return score


def _step_key(step) -> str:
    value = getattr(step, "value", step)
    s = str(value or "").strip()
    if s.startswith("Step."):
        s = s.split(".", 1)[1]
    return s.lower()


def _card_looks_like_land(card) -> bool:
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
    return any(basic in name for basic in ["island", "swamp", "mountain", "forest", "plains"])
