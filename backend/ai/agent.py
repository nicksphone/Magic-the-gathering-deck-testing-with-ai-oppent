from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from ai.endgame_policy import should_force_closure, should_force_inevitability_line
from ai.heuristics import evaluate_board
from ai.log_priors import load_log_priors
from ai.matchup_profiles import profile_for
from game_state.state import MatchState, Zone
from rules_engine.engine import RulesEngine
from rules_engine import combat
from rules_engine.continuous import effective_keywords
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.mana import can_pay_with_pool_and_lands, mana_value, parse_mana_cost


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
        self._main_pass_signature_counts: dict[tuple, int] = {}
        if AIAgent._log_priors_cache is None:
            AIAgent._log_priors_cache = load_log_priors()

    def choose_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> AIDecision:
        legal_moves = [move for move in legal_moves if not str(move.get("type", "")).endswith("_restricted")]
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

        forced_stabilize = self._forced_sweeper_stabilization_line(state, legal_moves, player_id)
        if forced_stabilize is not None:
            return AIDecision(action=forced_stabilize, reasoning="Burn matchup stabilization: remove pressure before value lines")

        stack_interaction = self._forced_stack_interaction(state, legal_moves, player_id)
        if stack_interaction is not None:
            return AIDecision(action=stack_interaction, reasoning="Answer threatening stack item with available interaction")

        endstep_draw = self._forced_endstep_card_advantage(state, legal_moves, player_id)
        if endstep_draw is not None:
            return AIDecision(action=endstep_draw, reasoning="Use opponent end step for instant-speed card advantage")
        tempo_closure = self._choose_forced_tempo_noncontrol_closure_action(state, legal_moves, player_id)
        if tempo_closure is not None:
            return AIDecision(action=tempo_closure, reasoning="Tempo non-control closure: force proactive conversion to avoid stalls")

        inevitability = self._choose_forced_inevitability_action(state, legal_moves, player_id)
        if inevitability is not None:
            return AIDecision(action=inevitability, reasoning="Control endgame planner selected long-game conversion line")
        closure = self._choose_forced_closure_action(state, legal_moves, player_id)
        if closure is not None:
            return AIDecision(action=closure, reasoning="Force late-game proactive line to avoid control stall/timeouts")

        strategic = self._strategic_plan_action(state, legal_moves, player_id)
        if strategic is not None:
            return AIDecision(action=strategic, reasoning="Complex-board strategic planner selected best line")

        sorted_moves = self._rank_moves(state, legal_moves, player_id)
        if self._should_break_stall(state, legal_moves, player_id):
            proactive = self._best_proactive_non_pass(sorted_moves, state, player_id)
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

    def _strategic_plan_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.difficulty not in {"master", "master_plus"}:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if not self._is_complex_board_state(state, player_id):
            return None
        if turn < 8 and self.archetype not in {"Control", "Counter-heavy", "Midrange", "Ramp", "Tempo"}:
            return None
        if turn < 6 and len(state.players[player_id].battlefield) + len(state.players[1 if player_id == 2 else 2].battlefield) < 12:
            return None
        proactive_legal = [
            mv
            for mv in legal_moves
            if mv.get("type") in {"cast_spell", "activate_ability", "activate_loyalty", "cycle_card", "equip", "attack"}
        ]
        if not proactive_legal:
            return None
        candidates = []
        search_depth = self._strategic_search_depth(state, player_id)
        beam_limit = 6 if search_depth > 1 else 8
        for mv in self._rank_moves(state, legal_moves, player_id)[:beam_limit]:
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            candidates.append(mat)
        if not candidates:
            return None
        scored: list[tuple[float, dict]] = []
        for mv in candidates:
            score = self._strategic_line_score(state, mv, player_id, depth=search_depth)
            scored.append((score, mv))
        scored.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        top = scored[0][1]
        if top.get("type") == "pass_priority":
            for _, mv in scored:
                if mv.get("type") in {"cast_spell", "activate_loyalty", "attack"}:
                    return mv
            return None
        return top

    def _strategic_search_depth(self, state: MatchState, player_id: int) -> int:
        """Choose a bounded tactical horizon without making every turn expensive."""
        if self.difficulty == "master_plus":
            return 2
        if self.difficulty != "master":
            return 1
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        board_size = len(getattr(state.players[player_id], "battlefield", []) or []) + len(
            getattr(state.players[opp_id], "battlefield", []) or []
        )
        if turn >= 10 and board_size >= 14:
            return 2
        return 1

    def _is_complex_board_state(self, state: MatchState, player_id: int) -> bool:
        if getattr(state, "pregame_pending", False):
            return False
        opp_id = 1 if player_id == 2 else 2
        my_bf = len(state.players[player_id].battlefield)
        opp_bf = len(state.players[opp_id].battlefield)
        both_hands = len(state.players[player_id].hand) + len(state.players[opp_id].hand)
        stack_size = len(getattr(state, "stack", []) or [])
        turn = int(getattr(state, "turn", 1) or 1)
        return my_bf + opp_bf >= 10 or both_hands >= 10 or stack_size >= 2 or turn >= 10

    def _strategic_line_score(self, state: MatchState, move: dict, player_id: int, depth: int) -> float:
        try:
            sim = copy.deepcopy(state)
            self.engine.take_action(sim, player_id, move)
            if sim.step == sim.step.COMBAT_DAMAGE:
                self.engine.take_action(sim, sim.active_player, {"type": "combat_damage"})
        except Exception:
            return -9999.0
        score = evaluate_board(sim, player_id)
        score += self._strategic_features(sim, player_id)
        score += self._stack_two_ply_value(sim, player_id)
        if depth <= 0 or sim.winner is not None:
            return score
        pid = sim.priority_player
        legal = sorted(self.engine.legal_moves(sim, pid), key=lambda mv: self._move_sort_key(mv))
        if not legal:
            return score
        beam: list[tuple[float, dict]] = []
        for cand in legal[:6]:
            try:
                nxt = copy.deepcopy(sim)
                self.engine.take_action(nxt, pid, cand)
                if nxt.step == nxt.step.COMBAT_DAMAGE:
                    self.engine.take_action(nxt, nxt.active_player, {"type": "combat_damage"})
                val = evaluate_board(nxt, player_id) + self._strategic_features(nxt, player_id) + self._stack_two_ply_value(
                    nxt, player_id
                )
                beam.append((val, cand))
            except Exception:
                continue
        if not beam:
            return score
        beam.sort(key=lambda x: x[0], reverse=(pid == player_id))
        # Opponent turn: assume best line against us; own turn: assume best for us.
        chosen = beam[0][1] if pid == player_id else beam[-1][1]
        return 0.6 * score + 0.4 * self._strategic_line_score(sim, chosen, player_id, depth - 1)

    def _stack_two_ply_value(self, state: MatchState, player_id: int) -> float:
        """Depth-limited stack planner for counter wars; only runs while stack is active."""
        stack_items = list(getattr(state, "stack", []) or [])
        if not stack_items or getattr(state, "winner", None) is not None:
            return 0.0
        pid = getattr(state, "priority_player", player_id)
        legal = self.engine.legal_moves(state, pid)
        if not legal:
            return 0.0
        top_actions = self._strategic_top_actions(state, legal, pid, limit=3)
        if not top_actions:
            return 0.0
        maximizing = pid == player_id
        best = -9999.0 if maximizing else 9999.0
        for act in top_actions:
            try:
                sim = copy.deepcopy(state)
                self.engine.take_action(sim, pid, act)
            except Exception:
                continue
            immediate = evaluate_board(sim, player_id) + self._strategic_features(sim, player_id)
            if getattr(sim, "winner", None) is not None or not (getattr(sim, "stack", []) or []):
                val = immediate
            else:
                reply_pid = getattr(sim, "priority_player", pid)
                reply_legal = self.engine.legal_moves(sim, reply_pid)
                replies = self._strategic_top_actions(sim, reply_legal, reply_pid, limit=2)
                if not replies:
                    val = immediate
                else:
                    reply_vals: list[float] = []
                    for rep in replies:
                        try:
                            nxt = copy.deepcopy(sim)
                            self.engine.take_action(nxt, reply_pid, rep)
                            reply_vals.append(evaluate_board(nxt, player_id) + self._strategic_features(nxt, player_id))
                        except Exception:
                            continue
                    if not reply_vals:
                        val = immediate
                    elif reply_pid == player_id:
                        val = max(reply_vals)
                    else:
                        val = min(reply_vals)
            best = max(best, val) if maximizing else min(best, val)
        if best in {-9999.0, 9999.0}:
            return 0.0
        return 0.2 * best

    def _strategic_top_actions(self, state: MatchState, legal_moves: list[dict], player_id: int, limit: int) -> list[dict]:
        ranked = self._rank_moves(state, legal_moves, player_id)
        picked: list[dict] = []
        for mv in ranked[: max(1, limit * 2)]:
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            picked.append(mat)
            if len(picked) >= limit:
                break
        return picked

    def _move_sort_key(self, move: dict) -> tuple:
        def _ids(values: object) -> str:
            if not isinstance(values, list):
                return ""
            out: list[str] = []
            for item in values:
                if isinstance(item, dict):
                    out.append(str(item.get("id") or item.get("name") or ""))
                else:
                    out.append(str(item))
            return ",".join(sorted(out))

        cost_choice = move.get("cost_choice")
        cost_choice_id = str(cost_choice.get("id")) if isinstance(cost_choice, dict) and cost_choice.get("id") is not None else ""
        return (
            str(move.get("type") or ""),
            str(move.get("card_name") or ""),
            str(move.get("card_name") or ""),
            str(move.get("ability_index") if move.get("ability_index") is not None else ""),
            str(move.get("ability_label") or ""),
            str(move.get("target_card_name") or ""),
            str(move.get("target_player_name") or ""),
            str(move.get("target_stack_label") or ""),
            cost_choice_id,
            str((move.get("targets") or {}).get("x_value", "")),
            _ids(move.get("attackers")),
            _ids(move.get("blockers")),
            _ids(move.get("options")),
        )

    def _strategic_features(self, state: MatchState, player_id: int) -> float:
        opp = 1 if player_id == 2 else 2
        my_life = int(getattr(state.players[player_id], "life", 20) or 20)
        opp_life = int(getattr(state.players[opp], "life", 20) or 20)
        my_hand = len(state.players[player_id].hand)
        opp_hand = len(state.players[opp].hand)
        my_untapped = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Land" in state.cards[cid].types and not state.cards[cid].tapped
        )
        opp_untapped = sum(
            1
            for cid in state.players[opp].battlefield
            if cid in state.cards and "Land" in state.cards[cid].types and not state.cards[cid].tapped
        )
        f = 0.0
        f += (my_life - opp_life) * 0.25
        f += (my_hand - opp_hand) * 0.35
        if self.archetype in {"Control", "Counter-heavy"}:
            f += min(3.0, my_untapped * 0.25)
            f -= max(0.0, opp_untapped - 2) * 0.2
        if self.archetype in {"Aggro", "Burn", "Tempo"}:
            f += max(0.0, 14 - opp_life) * 0.2
        if state.winner == player_id:
            f += 200.0
        elif state.winner is not None and state.winner != player_id:
            f -= 200.0
        return f

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
            kws = set(effective_keywords(state, cid))
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

    def _forced_sweeper_stabilization_line(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if getattr(state, "active_player", player_id) != player_id:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        opp_id = 1 if player_id == 2 else 2
        own_creatures = [
            cid
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        ]
        opp_creatures = [
            cid
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        ]
        if not opp_creatures:
            return None
        opp_power = sum((state.cards[cid].power or 0) for cid in opp_creatures)
        own_life = int(getattr(state.players[player_id], "life", 20) or 20)
        should_force = (
            len(opp_creatures) >= 3
            or opp_power >= max(3, own_life // 2)
            or len(own_creatures) <= 1
            or self.archetype in {"Control", "Counter-heavy", "Midrange"}
        )
        if not should_force:
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
                score += 6.0 if len(opp_creatures) >= 3 else 3.0
                score += min(opp_power, 8) * 0.4
                if own_creatures:
                    score += 1.5
            if "removal" in tags:
                score += 2.0
            if any(k in text for k in ["exile", "destroy"]):
                score += 0.8
            if "destroy all creatures" in text or "exile all creatures" in text:
                score += 3.0
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
        profile = self._opening_hand_profile(hand)
        lands = int(profile["lands"])
        cheap_interaction = int(profile["cheap_interaction"])
        likely_sources = profile["sources"]
        missing_primary_color = bool(profile["missing_primary_color"])
        mulligans = state.mulligan_count.get(player_id, 0)
        min_lands, max_lands = self._preferred_land_window()
        too_land_light = lands < min_lands
        too_land_heavy = lands > max_lands
        quality = float(profile["quality"])
        critical_miss = bool(profile["critical_miss"])
        if critical_miss and mulligans < 2:
            return AIDecision(action={"type": "mulligan"}, reasoning=profile["critical_reason"])
        if mulligans < 2 and too_land_light:
            # Keep a few borderline 2-land action hands when the deck can actually
            # convert them into development, draw, or acceleration.
            if not (
                lands >= 2
                and (
                    (self.archetype == "Ramp" and int(profile.get("ramp_spells", 0)) + int(profile.get("draw_spells", 0)) >= 1)
                    or (
                        self.archetype in {"Control", "Counter-heavy"}
                        and int(profile.get("draw_spells", 0)) + int(profile.get("counter_spells", 0)) + int(profile.get("removal_spells", 0)) >= 2
                    )
                )
            ):
                return AIDecision(
                    action={"type": "mulligan"},
                    reasoning=f"Opening hand outside {min_lands}-{max_lands} land window for {self.archetype}",
                )
        if mulligans < 2 and too_land_heavy:
            return AIDecision(
                action={"type": "mulligan"},
                reasoning=f"Opening hand outside {min_lands}-{max_lands} land window for {self.archetype}",
            )
        if mulligans < 2 and missing_primary_color and lands <= 3:
            return AIDecision(action={"type": "mulligan"}, reasoning="Missing key color access in opening hand")
        arche_quality_floor = 0.42
        if self.archetype in {"Control", "Counter-heavy", "Ramp"}:
            arche_quality_floor = 0.46
        elif self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"}:
            arche_quality_floor = 0.44
        if mulligans < 2 and quality < arche_quality_floor:
            return AIDecision(action={"type": "mulligan"}, reasoning="Opening hand quality too low")
        if mulligans < 2 and self._is_burn_matchup() and (lands < 2 or cheap_interaction == 0):
            return AIDecision(action={"type": "mulligan"}, reasoning="Burn matchup requires stable mana and early interaction")
        return AIDecision(action={"type": "keep_hand", "bottom_card_ids": []}, reasoning="Keep acceptable hand")

    def _opening_hand_profile(self, hand: list) -> dict[str, object]:
        lands = 0
        early_spells = 0
        early_pressure = 0
        cheap_interaction = 0
        draw_spells = 0
        counter_spells = 0
        removal_spells = 0
        ramp_spells = 0
        token_spells = 0
        engine_spells = 0
        threats = 0
        creatures = 0
        colored_pips = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for c in hand:
            if _card_looks_like_land(c):
                lands += 1
                for sym in self._land_colors(c):
                    if sym in colored_pips:
                        colored_pips[sym] += 1
                continue
            mana_cost = getattr(c, "mana_cost", "") or ""
            cost = parse_mana_cost(mana_cost, is_land=False)
            cmc = mana_value(mana_cost, is_land=False)
            text = f"{(getattr(c, 'name', '') or '').lower()} {(getattr(c, 'oracle_text', '') or '').lower()}"
            types = set(getattr(c, "types", []) or [])
            if cmc <= 2:
                early_spells += 1
            if cmc <= 3 and (
                "Creature" in types
                or "counter target spell" in text
                or "destroy target" in text
                or "exile target" in text
                or "deal" in text
                or ("create" in text and "token" in text)
            ):
                early_pressure += 1
            if cmc <= 2 and any(k in text for k in ["counter target spell", "destroy target", "exile target", "deals", "deal", "remove target"]):
                cheap_interaction += 1
            if "draw" in text or "scry" in text or "consider" in text or "memory deluge" in text:
                draw_spells += 1
            if "counter target spell" in text or "counterspell" in text:
                counter_spells += 1
            if "destroy target" in text or "exile target" in text or "deals" in text:
                removal_spells += 1
            if "cultivate" in text or "ramp" in text or "add {" in text or "search your library for a land" in text:
                ramp_spells += 1
            if "create" in text and "token" in text:
                token_spells += 1
            if any(k in text for k in ["whenever", "at the beginning", "landfall", "magecraft", "prowess", "artifact or enchantment", "another permanent enters the battlefield", "another permanent dies"]):
                engine_spells += 1
            if "Creature" in types:
                creatures += 1
                if cmc <= 3 or int(getattr(c, "power", 0) or 0) >= 3:
                    threats += 1
            for sym in ["W", "U", "B", "R", "G"]:
                colored_pips[sym] += int(cost[sym] or 0)

        likely_sources = self._opening_color_sources_from_hand(hand)
        missing_primary_color = any(v >= 2 and likely_sources.get(k, 0) == 0 for k, v in colored_pips.items())
        arche = self.archetype
        opp = (self.opponent_archetype or "").strip().lower()
        curve_fit = 1.0 - min(abs(lands - (3 if arche in {"Control", "Counter-heavy", "Ramp"} else 2 if arche in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} else 3)), 3) / 3
        action_density = min((early_spells + draw_spells + counter_spells + removal_spells + ramp_spells + token_spells + engine_spells) / 5.0, 1.6)
        quality = curve_fit * 0.55 + action_density * 0.3 + (0.15 if not missing_primary_color else 0.0)
        quality += min(0.2, threats * 0.05)

        critical_miss = False
        critical_reason = "Opening hand quality too low"
        if arche in {"Control", "Counter-heavy"}:
            quality += min(0.2, (draw_spells + counter_spells + removal_spells) * 0.04)
            if opp in {"aggro", "burn", "tempo"} and lands <= 3 and cheap_interaction == 0:
                critical_miss = True
                critical_reason = "Control hand lacks early interaction against pressure"
            elif lands <= 2 and draw_spells + counter_spells == 0:
                critical_miss = True
                critical_reason = "Control hand is too land-light without card selection"
            elif lands >= 6 and draw_spells + counter_spells == 0:
                critical_miss = True
                critical_reason = "Control hand is too land-heavy without action"
        elif arche == "Ramp":
            quality += min(0.2, (ramp_spells + draw_spells) * 0.05)
            if lands <= 2 and ramp_spells == 0:
                critical_miss = True
                critical_reason = "Ramp hand needs either stable lands or an accelerator"
            elif lands >= 6 and ramp_spells + draw_spells == 0:
                critical_miss = True
                critical_reason = "Ramp hand is too land-heavy without ramp or draw"
        elif arche in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"}:
            quality += min(0.2, (creatures + early_spells + cheap_interaction) * 0.04)
            if lands <= 1:
                critical_miss = True
                critical_reason = "Aggro hand is too land-light"
            elif early_pressure == 0:
                critical_miss = True
                critical_reason = "Aggro hand lacks early pressure"
        else:
            quality += min(0.15, (threats + draw_spells + removal_spells + ramp_spells) * 0.03)
            if lands <= 2 and threats + draw_spells + removal_spells == 0:
                critical_miss = True
                critical_reason = "Midrange hand lacks playable early action"

        return {
            "lands": lands,
            "cheap_interaction": cheap_interaction,
            "sources": likely_sources,
            "missing_primary_color": missing_primary_color,
            "quality": round(quality, 3),
            "draw_spells": draw_spells,
            "counter_spells": counter_spells,
            "removal_spells": removal_spells,
            "ramp_spells": ramp_spells,
            "token_spells": token_spells,
            "engine_spells": engine_spells,
            "creatures": creatures,
            "threats": threats,
            "early_spells": early_spells,
            "early_pressure": early_pressure,
            "critical_miss": critical_miss,
            "critical_reason": critical_reason,
        }

    def _current_hand_profile(self, state: MatchState, player_id: int) -> dict[str, object]:
        hand = [state.cards[cid] for cid in getattr(state.players[player_id], "hand", []) if cid in state.cards]
        profile = self._opening_hand_profile(hand)
        action_density = int(
            int(profile["cheap_interaction"])
            + min(3, int(profile["lands"]))
            + min(2, int(float(profile["quality"]) * 2))
        )
        profile["action_density"] = action_density
        return profile

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
            elif mtype == "cycle_card":
                # Cycling is a card-selection action, not a spell cast. Keep
                # it below a playable land/threat, but prefer it to passing
                # when the card is low-impact or the hand needs filtering.
                base += 2.0
                card = state.cards.get(move.get("card_id"))
                if card and "Land" in getattr(card, "types", []):
                    base -= 2.0
                if len(state.players[player_id].hand) <= 3:
                    base += 1.5
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
            elif mtype == "activate_ability":
                base += 2.5
                label = str(move.get("ability_label", "")).lower()
                if "look at the top" in label or "draw" in label or "search" in label:
                    base += 4.0
            elif mtype == "pass_priority":
                base += self._pass_bias(state, player_id)
                if own_main_sorcery_window and castable_creature_moves:
                    # Avoid stalling with threats stranded in hand when we can safely deploy.
                    base -= 2.6
            base += self._matchup_move_adjustment(state, move, player_id)
            if self.difficulty in {"master", "master_plus"}:
                base += self._simulate_delta(state, move, player_id)
            if self.difficulty == "master_plus":
                base += self._rollout_delta(state, move, player_id)
            return base

        ranked = sorted(moves, key=lambda mv: (score(mv), self._move_sort_key(mv)), reverse=True)
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
            self._approximate_resolution_for_ramp_spell(sim_state, move, player_id)
            self._approximate_resolution_for_activated_action(sim_state, move, player_id)
            after = evaluate_board(sim_state, player_id)
            opp_id = 1 if player_id == 2 else 2
            opp_moves = sorted(
                self.engine.legal_moves(sim_state, sim_state.priority_player),
                key=lambda mv: self._move_sort_key(mv),
            )
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
        archetype_bias += float(self.matchup_profile.get("proactive_bias", 0.0)) * 1.2
        risk_penalty = 0.0
        if role in {"defend", "stabilize"}:
            archetype_bias -= 2.2
            risk_penalty += 1.2
        elif role == "race":
            archetype_bias += 1.4
        elif role == "convert":
            archetype_bias += 1.2
        # Safer aggression: avoid low-output swings into clearly superior blockers.
        if opp_blockers > 0 and attack_power > 0:
            if attack_power < (opp_block_power * 0.6):
                risk_penalty += 2.2
            if role in {"defend", "stabilize"}:
                risk_penalty += 1.8
            if self.archetype in {"Aggro", "Tempo"} and attack_power <= 2 and opp_block_power >= 4:
                risk_penalty += 1.6
        unblocked_bonus = 3.5 if opp_blockers == 0 else 0.0
        if role == "convert" and opp_blockers > 0:
            unblocked_bonus += 0.8
        lethal_bonus = 20.0 if attack_power >= state.players[opp_id].life else 0.0
        risk_penalty += max(0.0, -float(self.matchup_profile.get("risk_tolerance", 0.0))) * 0.9
        return archetype_bias + attack_power * 0.8 - opp_block_power * 0.35 + race_pressure + unblocked_bonus + lethal_bonus - risk_penalty

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
        if self._should_force_inevitability_plan(state, player_id):
            return -1.3
        if self._should_force_proactive_control_line(state, player_id):
            return -2.1
        if self._is_burn_matchup() and getattr(state, "active_player", player_id) == player_id and _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}:
            return -1.0
        hand_profile = self._current_hand_profile(state, player_id)
        role = self._board_role(state, player_id)
        if int(hand_profile["action_density"]) >= 3 and role in {"normal", "convert", "race"}:
            return -0.2 - float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.2
        if role in {"stabilize", "defend"} and self.archetype in {"Control", "Counter-heavy", "Tempo", "Midrange"}:
            return 1.7 + float(self.matchup_profile.get("holdup_bias", 0.0))
        if role == "convert" and self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"}:
            return -0.8 + float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.2
        if self.archetype == "Tempo":
            opp = (self.opponent_archetype or "").strip()
            if opp in {"Burn", "Aggro", "Midrange", "Ramp", "Drain", "Aristocrats", "Tokens", "Tribal"}:
                if getattr(state, "active_player", player_id) == player_id and _step_key(getattr(state, "step", "")) in {"precombat_main", "postcombat_main"}:
                    turn = int(getattr(state, "turn", 1) or 1)
                    if turn <= 6:
                        return -1.6
        has_urgent_interaction = self._has_urgent_interaction(state, player_id)
        has_castable_value = self._has_castable_value_spell(state, player_id)
        if has_instant_like and self.archetype in {"Control", "Counter-heavy", "Tempo"}:
            if has_castable_value and not has_urgent_interaction:
                return -0.4 + float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.2
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
        if self._has_castable_value_spell(state, player_id) and not self._has_urgent_interaction(state, player_id):
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

    def _matchup_move_adjustment(self, state: MatchState, move: dict, player_id: int) -> float:
        delta = 0.0
        mtype = move.get("type")
        role = self._board_role(state, player_id)
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        opp_board_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        opp_board_power = sum(
            max(0, int(getattr(state.cards.get(cid), "power", 0) or 0))
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        my_board_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        if mtype == "cast_spell":
            cid = move.get("card_id")
            card = state.cards.get(cid) if cid else None
            if card:
                tags = self._spell_tags(card)
                if "draw" in tags or "removal" in tags or "counter" in tags:
                    delta += float(self.matchup_profile.get("holdup_bias", 0.0)) * 0.35
                if "token" in tags or "ramp" in tags:
                    delta += float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.45
                if self.archetype in {"Control", "Counter-heavy"} and self.opponent_archetype in {"Aggro", "Burn"} and "counter" in tags:
                    delta += 0.5
                if self.archetype in {"Tempo"} and self.opponent_archetype in {"Control", "Counter-heavy"} and ("counter" in tags or "removal" in tags):
                    delta += 0.4
                if role in {"stabilize", "defend"} and any(tag in tags for tag in {"removal", "counter", "draw", "sweeper"}):
                    delta += 1.2
                    if opp_board_creatures > 0:
                        delta += min(opp_board_power, 6) * 0.15
                if role in {"race", "convert"} and any(tag in tags for tag in {"token", "burn", "attack", "anthem"}):
                    delta += 1.0
                    if my_board_creatures >= opp_board_creatures:
                        delta += 0.3
                if self.archetype == "Ramp" and "ramp" in tags:
                    delta += 3.0
                    if turn <= 5:
                        delta += 1.2
                    if role in {"normal", "stabilize"}:
                        delta += 0.3
                if self.archetype == "Ramp" and "draw" in tags and turn >= 5:
                    delta += 0.3
                if self.archetype in {"Control", "Counter-heavy"} and "sweeper" in tags and opp_board_creatures >= 2:
                    delta += 1.5
                if self.archetype in {"Aggro", "Burn", "Tempo"} and "burn" in tags and opp_board_power > 0:
                    delta += min(opp_board_power, 6) * 0.12
        elif mtype == "attack":
            delta += float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.35
        elif mtype == "pass_priority":
            delta -= float(self.matchup_profile.get("proactive_bias", 0.0)) * 0.25
        return delta

    def _has_urgent_interaction(self, state: MatchState, player_id: int) -> bool:
        if self.archetype not in {"Control", "Counter-heavy", "Tempo"}:
            return False
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        stack_live = bool(getattr(state, "stack", []) or [])
        for cid in state.players[player_id].hand:
            card = state.cards.get(cid)
            if not card:
                continue
            if not self._can_pay_card_cost(state, player_id, card):
                continue
            tags = self._spell_tags(card)
            if stack_live and "counter" in tags:
                return True
            if opp_creatures > 0 and "removal" in tags:
                return True
        return False

    def _has_castable_value_spell(self, state: MatchState, player_id: int) -> bool:
        for cid in state.players[player_id].hand:
            card = state.cards.get(cid)
            if not card or "Land" in (getattr(card, "types", []) or []):
                continue
            if not self._can_pay_card_cost(state, player_id, card):
                continue
            if self._is_major_threat_card(card):
                return True
            tags = self._spell_tags(card)
            if any(tag in tags for tag in {"draw", "removal", "counter", "ramp", "token"}):
                return True
        return False

    def _can_pay_card_cost(self, state: MatchState, player_id: int, card) -> bool:
        try:
            return bool(can_pay_with_pool_and_lands(state, player_id, getattr(card, "mana_cost", "")))
        except Exception:
            return False

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
        role = self._board_role(state, player_id)
        if self._modal_face_options(card):
            _, face_score = self._select_modal_face_index(state, card, player_id)
        else:
            face_score = 0.0
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
            x_value = self._choose_x_value(state, player_id, mana_cost_text, card=card)
            if x_value <= 0:
                # Avoid invalid X=0 loops for spells that need explicit positive X targeting.
                return -8.0
            x_penalty = self._x_spell_timing_penalty(state, card, player_id, x_value)
            if x_penalty <= -3.5:
                return x_penalty
        power = getattr(card, "power", 0) or 0
        is_big_threat = power >= 4 or cmc >= 4
        if face_score:
            bonus_face = face_score * 0.45
            if own_main_sorcery_window and face_score <= 0.0 and state.turn <= 4:
                bonus_face -= 0.8
        else:
            bonus_face = 0.0

        if is_creature:
            if arche in {"Aggro", "Tribal", "Tokens", "Tempo"}:
                bonus = 4.0
                if in_main:
                    bonus += 1.2
                if my_creatures < 2:
                    bonus += 2.0
                if early_turn:
                    bonus += 1.0
                return bonus + bonus_face
            if arche in {"Midrange", "Ramp", "Aristocrats"}:
                bonus = 2.0 + (0.8 if my_creatures < 2 else 0.0)
                if is_big_threat and (my_creatures < 2 or state.turn >= 5):
                    bonus += 2.2
                if arche == "Ramp" and state.turn >= 4 and is_big_threat:
                    bonus += 1.2
                return bonus + bonus_face
            if arche in {"Control", "Counter-heavy"}:
                bonus = 0.8
                if is_big_threat and (my_creatures == 0 or state.turn >= 6):
                    bonus += 3.0
                if own_main_sorcery_window and is_big_threat:
                    bonus += 0.7
                if "recursion" in tags:
                    bonus += self._graveyard_recursion_bonus(state, player_id)
                return bonus + bonus_face
            return 1.2 + bonus_face

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
                if self._should_force_inevitability_plan(state, player_id):
                    bonus += 1.4
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
            if "recursion" in tags:
                bonus += self._graveyard_recursion_bonus(state, player_id)
            if "removal" in tags:
                bonus += 2.0
                # Don't fire premium removal into empty/low-pressure board states.
                if opp_creatures == 0:
                    bonus -= 2.5
                elif own_main_sorcery_window and self._should_force_proactive_control_line(state, player_id):
                    bonus += 0.8
                if self._is_burn_matchup() and opp_creatures > 0:
                    bonus += 2.4
                creature_targets = (move.get("target_hints") or {}).get("creature_targets") or []
                if creature_targets:
                    target_threat = max(
                        (
                            self._creature_threat_score(state, t.get("id"), player_id)
                            for t in creature_targets
                            if t.get("id")
                        ),
                        default=0.0,
                    )
                    bonus += min(3.5, max(0.0, target_threat) * 0.35)
                if self._is_burn_matchup() and "counter" in tags and state.turn <= 3 and not (getattr(state, "stack", []) or []):
                    bonus -= 0.8
                if self._is_burn_matchup() and "sweeper" in f"{(getattr(card, 'name', '') or '').lower()} {(getattr(card, 'oracle_text', '') or '').lower()}":
                    if opp_creatures >= 2:
                        bonus += 2.8
                    else:
                        bonus -= 1.2
            if "engine" in tags:
                if self.archetype in {"Control", "Counter-heavy", "Midrange", "Tokens", "Aristocrats", "Drain"}:
                    bonus += 1.7
                if self.archetype in {"Tempo", "Aggro", "Burn"} and own_main_sorcery_window:
                    bonus += 0.4
                if role in {"stabilize", "convert"}:
                    bonus += 0.8
            if ("Planeswalker" in set(getattr(card, "types", []) or []) or is_big_threat) and own_main_sorcery_window:
                if self._should_force_proactive_control_line(state, player_id):
                    bonus += 2.3
                if self._should_force_inevitability_plan(state, player_id):
                    bonus += 1.6
            if self._should_force_inevitability_plan(state, player_id):
                if "discard" in tags or "mill" in tags:
                    bonus += 1.7
                if "counter" in tags and not (getattr(state, "stack", []) or []):
                    bonus -= 1.0
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus + bonus_face

        if arche in {"Midrange"}:
            bonus = 0.0
            # Midrange: prefer board development on-curve, hold premium removal for real pressure.
            if "Creature" in set(getattr(card, "types", []) or []):
                bonus += 1.6
                if 2 <= cmc <= 4 and state.turn <= 6:
                    bonus += 1.2
            if "removal" in tags:
                bonus += 2.0
                opp_id = 1 if player_id == 2 else 2
                opp_creatures = sum(
                    1
                    for ocid in state.players[opp_id].battlefield
                    if ocid in state.cards and "Creature" in state.cards[ocid].types
                )
                if opp_creatures == 0:
                    bonus -= 2.2
            if "draw" in tags:
                bonus += 1.2
            if "burn" in tags and state.players[1 if player_id == 2 else 2].life <= 6:
                bonus += 1.5
            if "engine" in tags:
                bonus += 1.0
            return bonus + bonus_face

        if arche in {"Ramp"}:
            bonus = 0.0
            if "ramp" in tags:
                bonus += 4.0 if early_turn else 1.0
            opp_id = 1 if player_id == 2 else 2
            opp_creatures = sum(
                1
                for ocid in state.players[opp_id].battlefield
                if ocid in state.cards and "Creature" in state.cards[ocid].types
            )
            # Under pressure, stabilize before greed.
            if state.players[player_id].life <= 10 and opp_creatures >= 2 and "ramp" in tags:
                bonus -= 2.0
            if "removal" in tags and opp_creatures > 0:
                bonus += 2.0
            if "Creature" in set(getattr(card, "types", []) or []) and cmc >= 5 and state.turn >= 5:
                bonus += 1.8
            if "draw" in tags:
                bonus += 1.5
            if "engine" in tags:
                bonus += 0.8
            return bonus + bonus_face

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
            if "engine" in tags:
                bonus += 1.6
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus + bonus_face

        if arche in {"Reanimator"}:
            bonus = 0.0
            if "reanimate" in tags:
                bonus += 4.0
            if "discard" in tags or "mill" in tags:
                bonus += 2.0
            return bonus + bonus_face

        if arche in {"Aristocrats", "Drain"}:
            bonus = 0.0
            if "drain" in tags:
                bonus += 3.2
            if "sacrifice" in tags:
                bonus += 2.4
            if "engine" in tags:
                bonus += 1.6
            # Deploy engine pieces before pure payoff where possible.
            text = f"{(getattr(card, 'name', '') or '').lower()} {(getattr(card, 'oracle_text', '') or '').lower()}"
            if any(k in text for k in ["blood artist", "zulaport", "cauldron familiar", "witch's oven", "priest of forgotten gods"]):
                bonus += 2.2
            return bonus + bonus_face

        if arche in {"Tempo"}:
            bonus = 0.0
            if "Creature" in set(getattr(card, "types", []) or []) and cmc <= 2:
                bonus += 2.4
            if "counter" in tags:
                bonus += 3.6 if getattr(state, "stack", []) else -1.4
            if "removal" in tags:
                bonus += 1.8
            if "engine" in tags:
                bonus += 0.9
            # Tempo: prefer threat+protection lines when threat already on board.
            my_creatures_now = sum(
                1
                for pid in state.players[player_id].battlefield
                if pid in state.cards and "Creature" in state.cards[pid].types
            )
            if my_creatures_now > 0 and "counter" in tags and (getattr(state, "stack", []) or []):
                bonus += 1.0
            if "{X}" in mana_cost_text:
                bonus += self._x_spell_timing_penalty(state, card, player_id, x_value)
            return bonus + bonus_face

        if arche in {"Aggro", "Tribal", "Tokens", "Tempo"} and my_creatures == 0 and early_turn and in_main:
            return -1.8 + bonus_face
        # Log-driven priors: leverage observed tournament/simulation cast timing.
        return self._historical_cast_timing_bias(state, card, player_id) + bonus_face

    def _graveyard_recursion_bonus(self, state: MatchState, player_id: int) -> float:
        targets = sum(
            1
            for grave_id in getattr(state.players[player_id], "graveyard", []) or []
            if grave_id in state.cards
            and bool(set(getattr(state.cards[grave_id], "types", []) or []) & {"Instant", "Sorcery"})
        )
        # Graveyard-casting threats are premium only when a qualifying spell
        # is available to recast; otherwise preserve mana for another line.
        return 3.0 if targets else -1.5

    def _historical_cast_timing_bias(self, state: MatchState, card, player_id: int) -> float:
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
        role = self._board_role(state, player_id)
        role_rows = row.get("board_roles")
        if isinstance(role_rows, dict):
            role_row = role_rows.get(role)
            if not isinstance(role_row, dict) and role in {"stabilize", "defend"}:
                role_row = role_rows.get("control")
            if isinstance(role_row, dict):
                role_casts = int(role_row.get("casts", 0) or 0)
                if role_casts >= 3:
                    row = role_row
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

    def _approximate_resolution_for_ramp_spell(self, sim_state: MatchState, move: dict, player_id: int) -> None:
        if move.get("type") != "cast_spell":
            return
        cid = move.get("card_id")
        if not cid:
            return
        card = sim_state.cards.get(cid)
        if not card:
            return
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        if "land" not in text and "cultivate" not in text and "ramp" not in text and "search your library" not in text:
            return
        if "put a land card from your hand onto the battlefield" not in text and "search your library for" not in text:
            return
        land_ids = [
            lid
            for lid in list(sim_state.players[player_id].library)
            if lid in sim_state.cards and "Land" in sim_state.cards[lid].types
        ]
        if not land_ids:
            return

        first = land_ids[0]
        if first in sim_state.players[player_id].library:
            sim_state.players[player_id].library.remove(first)
            sim_state.players[player_id].battlefield.append(first)
            land = sim_state.cards[first]
            land.zone = Zone.BATTLEFIELD
            land.controller = player_id
            land.tapped = True
            land.summoning_sick = False

        if "put it into your hand" in text or "put that card into your hand" in text or "put it into your hand" in text:
            if len(land_ids) > 1:
                second = land_ids[1]
                if second in sim_state.players[player_id].library:
                    sim_state.players[player_id].library.remove(second)
                    sim_state.players[player_id].hand.append(second)
                    land2 = sim_state.cards[second]
                    land2.zone = Zone.HAND
                    land2.controller = player_id

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
        if "attack" in text:
            tags.add("attack")
        if "block" in text:
            tags.add("block")
        if "look at the top" in text and "creature cards" in text and "onto the battlefield" in text:
            tags.add("creature_deploy_topdeck")
        if "creatures you control get" in text or "+1/+1" in text:
            tags.add("anthem")
        if "enchantment" in text:
            tags.add("enchantment")
        if "return target creature card from your graveyard" in text or "reanimate" in text:
            tags.add("reanimate")
        if "from your graveyard" in text and any(word in text for word in ["cast", "return", "play"]):
            tags.add("recursion")
        if "discard" in text:
            tags.add("discard")
        if "mill" in text:
            tags.add("mill")
        if "sacrifice" in text:
            tags.add("sacrifice")
        if "dies" in text:
            tags.add("death")
        if "lose" in text and "gain" in text:
            tags.add("drain")
        if any(k in text for k in ["whenever", "at the beginning", "landfall", "magecraft", "prowess", "artifact or enchantment", "another permanent enters the battlefield", "another permanent dies"]):
            tags.add("engine")
        return tags

    def _modal_face_options(self, card) -> list[dict]:
        return list(getattr(card, "card_faces", []) or [])

    def _modal_face_proxy(self, card, face: dict) -> object:
        proxy = type("ModalFaceProxy", (), {})()
        proxy.name = str(face.get("name") or getattr(card, "name", ""))
        proxy.oracle_text = str(face.get("oracle_text") or getattr(card, "oracle_text", "") or "")
        proxy.mana_cost = str(face.get("mana_cost") or getattr(card, "mana_cost", "") or "")
        proxy.types = self._types_from_type_line(str(face.get("type_line") or getattr(card, "type_line", "") or ""))
        return proxy

    def _types_from_type_line(self, type_line: str) -> list[str]:
        tl = (type_line or "").strip()
        if not tl:
            return []
        parts = tl.split("—", 1)
        primary = parts[0]
        if "-" in primary:
            primary = primary.split("-", 1)[0]
        return [part.strip() for part in primary.split() if part.strip()]

    def _score_modal_face(self, state: MatchState, card, face: dict, player_id: int) -> float:
        proxy = self._modal_face_proxy(card, face)
        tags = self._spell_tags(proxy)
        text = f"{proxy.name} {proxy.oracle_text}".lower()
        mana_req = parse_mana_cost(getattr(proxy, "mana_cost", ""), is_land=False)
        cmc = mana_req["generic"] + sum(mana_req[c] for c in ["W", "U", "B", "R", "G"])
        score = 0.0
        types = set(getattr(proxy, "types", []) or [])
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        my_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        early_turn = int(getattr(state, "turn", 1) or 1) <= 4
        board_pressure = max(0, opp_creatures - my_creatures)
        if "burn" in tags or "damage" in text:
            score += 1.4
        if "draw" in tags:
            score += 1.2
            if self.archetype in {"Control", "Counter-heavy"} and opp_life > 10:
                score += 0.8
            if self.archetype == "Tempo" and my_creatures > 0:
                score += 0.3
        if "counter" in tags:
            score += 2.1 if getattr(state, "stack", []) else -1.0
            if self.archetype in {"Control", "Counter-heavy", "Tempo"} and getattr(state, "stack", []):
                score += 0.8
        if "removal" in tags:
            score += 1.8 if opp_creatures > 0 else -1.0
            if opp_creatures >= 2:
                score += 0.5
        if "token" in tags:
            score += 1.0
        if "attack" in tags:
            score += 0.6
            if self.archetype in {"Aggro", "Tempo", "Tokens", "Tribal"}:
                score += 0.7
        if "block" in tags:
            score += 0.5
            if self.archetype in {"Control", "Counter-heavy", "Midrange"}:
                score += 0.5
        if "Creature" in types:
            score += 0.5
            if self.archetype in {"Aggro", "Tempo", "Tribal", "Tokens"}:
                score += 1.3 if cmc <= 3 else 0.7
                if my_creatures == 0:
                    score += 0.9
                if early_turn:
                    score += 0.5
                if "flash" in text or "haste" in text:
                    score += 0.4
            elif self.archetype in {"Midrange", "Ramp"}:
                if cmc <= 4 or (getattr(proxy, "power", None) or 0) + (getattr(proxy, "toughness", None) or 0) >= 4:
                    score += 1.0
                if early_turn and cmc >= 4:
                    score -= 0.3
            else:
                # Control and counter-heavy decks should only value the creature face
                # when it meaningfully stabilizes the board or carries immediate utility.
                if my_creatures == 0 and opp_creatures == 0 and cmc <= 3:
                    score += 0.4
                else:
                    score -= 0.2
                if early_turn and cmc >= 4:
                    score -= 0.8
                if "flash" in text or "lifelink" in text or "flying" in text:
                    score += 0.3
        if cmc <= 2:
            score += 0.5
        if self.archetype in {"Control", "Counter-heavy"} and any(k in tags for k in {"draw", "counter", "removal"}):
            score += 1.3
            if board_pressure > 0:
                score += min(0.9, board_pressure * 0.35)
        if self.archetype in {"Burn", "Aggro"} and ("damage" in text or "burn" in tags):
            score += 1.2
        if self.archetype == "Tempo" and (cmc <= 2 or "counter" in tags):
            score += 0.9
        if self.archetype in {"Midrange", "Ramp"} and "Creature" in types and cmc <= 3:
            score += 0.7
        turn = int(getattr(state, "turn", 1) or 1)
        if turn <= 3 and score < 1.0:
            score -= 1.5
        if turn >= 6 and "Creature" in types and my_creatures <= opp_creatures:
            score += 0.6
        if turn >= 6 and ("draw" in tags or "counter" in tags or "removal" in tags):
            score += 0.4
        if cmc >= 5 and early_turn:
            score -= 0.5
        if self.archetype in {"Control", "Counter-heavy"} and "Creature" in types and not any(k in tags for k in {"draw", "counter", "removal"}):
            score -= 0.1
        return score

    def _select_modal_face_index(self, state: MatchState, card, player_id: int) -> tuple[int, float]:
        faces = self._modal_face_options(card)
        if len(faces) <= 1:
            return 0, 0.0
        scored: list[tuple[float, int]] = []
        for idx, face in enumerate(faces):
            scored.append((self._score_modal_face(state, card, face, player_id), idx))
        scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        best_score, best_idx = scored[0]
        if best_score <= 0.0:
            return 0, best_score
        return best_idx, best_score

    def _score_mode_text(self, state: MatchState, card, mode_text: str, player_id: int) -> float:
        text = (mode_text or "").lower()
        tags = self._spell_tags(card)
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        my_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        turn = int(getattr(state, "turn", 1) or 1)
        role = self._board_role(state, player_id)
        board_pressure = opp_creatures - my_creatures
        score = 0.0
        if "counter" in text:
            score += 3.2 if getattr(state, "stack", []) else 0.2
            if self.archetype in {"Control", "Counter-heavy", "Tempo"}:
                score += 1.4
            if role in {"stabilize", "defend"} and getattr(state, "stack", []):
                score += 0.8
        if "destroy" in text or "exile" in text or "bounce" in text:
            score += 2.2 if opp_creatures > 0 else -0.6
            if opp_creatures >= 2:
                score += 0.4
            if self.archetype in {"Control", "Counter-heavy", "Tempo", "Midrange"}:
                score += 0.6
            if role in {"stabilize", "defend"}:
                score += 0.6
            if board_pressure > 0:
                score += min(1.0, board_pressure * 0.25)
        if "draw" in text:
            score += 1.6
            if self.archetype in {"Control", "Counter-heavy"} and opp_life > 10:
                score += 0.8
            if self.archetype in {"Tempo", "Aggro"} and my_creatures > 0:
                score += 0.2
            if role in {"normal", "control"} and board_pressure <= 0:
                score += 0.2
        if "create" in text and "token" in text:
            score += 1.7
            if self.archetype in {"Aggro", "Tokens", "Tribal", "Tempo"}:
                score += 1.0
                if my_creatures == 0:
                    score += 0.7
            elif self.archetype in {"Control", "Counter-heavy"}:
                score += 0.25 if opp_creatures > my_creatures else -0.4
            if role in {"race", "convert"}:
                score += 0.7
        if "damage" in text or "burn" in tags:
            score += 1.3
            if self.archetype in {"Burn", "Aggro", "Tempo"}:
                score += 0.8
            elif opp_life <= 6:
                score += 0.6
            if role == "race":
                score += 0.5
        if "gain" in text or "life" in text:
            score += 0.7
            if self.archetype in {"Control", "Counter-heavy"} and state.players[player_id].life <= 10:
                score += 0.5
            if role in {"stabilize", "defend"} and state.players[player_id].life <= 12:
                score += 0.4
        if "attack" in text:
            score += 0.7
            if role == "convert":
                score += 0.5
        if "block" in text:
            score += 0.5
            if role in {"stabilize", "defend"}:
                score += 0.3
        if "dies" in text or "sacrifice" in text:
            score += 0.8
            if self.archetype in {"Aristocrats", "Drain"}:
                score += 0.9
            if role in {"stabilize", "convert"}:
                score += 0.2
        if "ramp" in tags or "add mana" in text:
            score += 1.0
            if self.archetype in {"Ramp", "Midrange"}:
                score += 1.4
            if role in {"normal", "convert"} and turn <= 5:
                score += 0.4
        if "discard" in text or "mill" in text:
            score += 1.1
            if self.archetype in {"Control", "Counter-heavy"}:
                score += 0.5
            if role in {"stabilize", "defend"}:
                score += 0.3
        if turn <= 3 and score < 1.0:
            score -= 1.0
        if turn >= 6 and ("draw" in text or "counter" in text or "destroy" in text or "exile" in text):
            score += 0.4
        return score

    def _select_mode_text(self, state: MatchState, card, modes: list[str], player_id: int) -> str:
        if not modes:
            return ""
        scored = [(self._score_mode_text(state, card, mode, player_id), idx, mode) for idx, mode in enumerate(modes)]
        scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        best_score, _, best_mode = scored[0]
        if best_score <= 0.0:
            return modes[0]
        return best_mode

    def _select_mode_texts(self, state: MatchState, card, modes: list[str], player_id: int) -> list[str]:
        if len(modes) <= 2:
            scored = sorted(
                [(self._score_mode_text(state, card, mode, player_id), idx, mode) for idx, mode in enumerate(modes)],
                key=lambda item: (item[0], -item[1]),
                reverse=True,
            )
            return [mode for _, _, mode in scored]
        scored = sorted(
            [(self._score_mode_text(state, card, mode, player_id), idx, mode) for idx, mode in enumerate(modes)],
            key=lambda item: (item[0], -item[1]),
            reverse=True,
        )
        return [scored[0][2], scored[1][2]]

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
            if mtype == "cast_spell" and self._modal_face_options(card):
                selected_face_index, _ = self._select_modal_face_index(state, card, player_id)
                out["selected_face_index"] = selected_face_index
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
            best = max(
                creature_targets,
                key=lambda t: (self._creature_threat_score(state, t.get("id"), player_id), str(t.get("name") or t.get("label") or "")),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]

        land_targets = hints.get("land_targets") or []
        if land_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            # Prefer a basic land that is currently untapped so an animation
            # loyalty line can attack or continue producing mana afterward.
            best_land = max(
                land_targets,
                key=lambda t: (
                    int(not bool(getattr(state.cards.get(t.get("id")), "tapped", False))),
                    str(t.get("name") or ""),
                ),
                default=None,
            )
            if best_land:
                targets["target_card_id"] = best_land["id"]
                targets["target_card_name"] = best_land.get("name") or ""
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        graveyard_creature_targets = hints.get("graveyard_creature_targets") or []
        if graveyard_creature_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                graveyard_creature_targets,
                key=lambda t: (
                    self._graveyard_creature_reanimation_score(state, t.get("id"), player_id),
                    str(t.get("name") or t.get("label") or ""),
                ),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        graveyard_permanent_targets = hints.get("graveyard_permanent_targets") or []
        if graveyard_permanent_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                graveyard_permanent_targets,
                key=lambda t: (
                    self._noncreature_permanent_threat_score(state, t.get("id"), player_id),
                    str(t.get("name") or t.get("label") or ""),
                ),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        planeswalker_targets = hints.get("planeswalker_targets") or []
        if planeswalker_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            targets["target_card_id"] = planeswalker_targets[0]["id"]

        noncreature_permanent_targets = (
            (hints.get("artifact_targets") or [])
            + (hints.get("enchantment_targets") or [])
            + (hints.get("noncreature_permanent_targets") or [])
        )
        if noncreature_permanent_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            best = max(
                noncreature_permanent_targets,
                key=lambda t: (
                    self._noncreature_permanent_threat_score(state, t.get("id"), player_id),
                    str(t.get("name") or t.get("label") or ""),
                ),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]
                targets["target_card_name"] = best.get("name") or best.get("label") or ""

        library_search = hints.get("library_search") or {}
        search_candidates = list(library_search.get("candidates") or [])
        if search_candidates and not targets.get("search_card_ids"):
            # Search choices are now validated by the rules engine. Select the
            # strongest legal count rather than retrying the same invalid cast.
            max_count = int(library_search.get("max_count", 0) or 0)
            selected_count = max_count if max_count > 0 else 1
            selected_count = min(selected_count, len(search_candidates))
            ordered = sorted(search_candidates, key=lambda item: (str(item.get("name") or ""), str(item.get("id") or "")))
            targets["search_card_ids"] = [item["id"] for item in ordered[:selected_count]]

        if hints.get("supports_divide") and not targets.get("target_distribution"):
            if creature_targets:
                # Put first point on highest-threat creature by default.
                best = max(
                    creature_targets,
                    key=lambda t: (self._creature_threat_score(state, t.get("id"), player_id), str(t.get("name") or t.get("label") or "")),
                    default=None,
                )
                if best:
                    targets["target_distribution"] = {best["id"]: 1}
            elif player_targets:
                targets["target_distribution"] = {str(opponent): 1}
            targets.setdefault("divide_total", 1)

        if hints.get("modes") and not targets.get("mode_text") and not targets.get("mode_texts"):
            if hints.get("choose_two_modes"):
                targets["mode_texts"] = self._select_mode_texts(state, card, list(hints["modes"]), player_id)
            else:
                targets["mode_text"] = self._select_mode_text(state, card, list(hints["modes"]), player_id)

        mana_cost = move.get("mana_cost") or getattr(card, "mana_cost", "") or ""
        if "{X}" in mana_cost.upper() and "x_value" not in targets:
            targets["x_value"] = self._choose_x_value(state, player_id, mana_cost, card=card)
        elif hints.get("requires_x_value") and "x_value" not in targets:
            if mtype == "activate_loyalty" and cid:
                loyalty_now = int(getattr(state.cards.get(cid), "loyalty", 0) or 0)
                targets["x_value"] = max(0, min(3, loyalty_now))
            else:
                targets["x_value"] = self._choose_x_value(state, player_id, mana_cost, card=card) or 0

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
        searched = self._search_block_assignments(state, attackers, blockers)
        if searched is not None:
            return searched
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
        role = self._board_role(state, player_id)
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
            atk_has_trample = "trample" in set(effective_keywords(state, aid))
            atk_has_deathtouch = "deathtouch" in set(effective_keywords(state, aid))
            required_blockers = 2 if self._requires_two_or_more_blockers(state, atk) else 1
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
                if blk_pow < atk_tgh and blk_tgh <= atk_pow:
                    score -= 0.9
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
                    if lethal_pressure or role in {"stabilize", "defend"}:
                        score += 1.8
                if role in {"stabilize", "defend"}:
                    score += 0.35
                elif role == "convert" and not lethal_pressure:
                    score -= 0.2
                if atk_pow >= life:
                    score += 1.4
                elif atk_pow >= max(3, life // 2):
                    score += 0.6
                if atk_has_trample and blk_tgh > atk_pow:
                    score += 0.7
                scored.append((score, bid))
                if score > best_score:
                    best_score = score
                    best_bid = bid
            if role in {"stabilize", "defend"}:
                threshold = -0.5 if lethal_pressure else 0.15
            elif role == "convert":
                threshold = -0.4 if lethal_pressure else 0.65
            else:
                threshold = -0.6 if lethal_pressure else 0.4
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

    def _search_block_assignments(
        self,
        state: MatchState,
        attackers: list[dict],
        blockers: list[dict],
    ) -> dict[str, str | list[str]] | None:
        """Evaluate small-board blocker assignments by resolving cloned combat."""
        if self.difficulty not in {"master", "master_plus"}:
            return None
        attacker_ids = [item["id"] for item in attackers if item.get("id") in state.cards]
        blocker_ids = [item["id"] for item in blockers if item.get("id") in state.cards]
        if not attacker_ids or not blocker_ids or len(attacker_ids) > 4 or len(blocker_ids) > 5:
            return None
        defender = getattr(state, "priority_player", None)
        if defender not in getattr(state, "players", {}):
            defender = state.cards[blocker_ids[0]].controller
        choices: dict[str, list[str | None]] = {}
        for bid in blocker_ids:
            blocker = state.cards[bid]
            legal_targets = [
                aid
                for aid in attacker_ids
                if combat._can_block_attacker(state, state.cards[aid], blocker)
            ]
            choices[bid] = [None, *legal_targets]

        assignments: list[dict[str, str]] = []

        def visit(index: int, current: dict[str, str]) -> None:
            if index >= len(blocker_ids):
                counts: dict[str, int] = {}
                for aid in current.values():
                    counts[aid] = counts.get(aid, 0) + 1
                if any(
                    self._requires_two_or_more_blockers(state, state.cards[aid]) and counts.get(aid, 0) < 2
                    for aid in attacker_ids
                ):
                    return
                assignments.append(dict(current))
                return
            bid = blocker_ids[index]
            for aid in choices[bid]:
                if aid is None:
                    visit(index + 1, current)
                else:
                    current[bid] = aid
                    visit(index + 1, current)
                    current.pop(bid, None)

        visit(0, {})
        if not assignments or len(assignments) > 4096:
            return None
        best: tuple[float, tuple[tuple[str, str], ...], dict[str, str | list[str]]] | None = None
        initial_life = state.players[defender].life
        for assignment in assignments:
            try:
                sim = copy.deepcopy(state)
                self.engine.take_action(sim, defender, {"type": "block", "blocks": assignment})
                self.engine.take_action(sim, sim.active_player, {"type": "combat_damage"})
            except Exception:
                continue
            score = evaluate_board(sim, defender)
            score += (sim.players[defender].life - initial_life) * 4.0
            if sim.winner == defender:
                score += 1000.0
            elif sim.winner is not None:
                score -= 1000.0
            normalized: dict[str, str | list[str]] = {}
            for aid in attacker_ids:
                assigned = sorted(bid for bid, target in assignment.items() if target == aid)
                if assigned:
                    normalized[aid] = assigned if len(assigned) > 1 else assigned[0]
            key = tuple(sorted(assignment.items()))
            candidate = (score, key, normalized)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        return best[2] if best is not None else None

    def _requires_two_or_more_blockers(self, state, attacker) -> bool:
        attacker_id = getattr(attacker, "id", None)
        keywords = (
            set(effective_keywords(state, attacker_id))
            if attacker_id and attacker_id in getattr(state, "cards", {})
            else {str(k).lower() for k in (getattr(attacker, "keywords", []) or [])}
        )
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
        hand_profile = self._current_hand_profile(state, player_id)
        role = self._board_role(state, player_id)
        race_mode = my_life <= 7 or opp_life <= 6
        board_pressure = sum(
            max(0, _eff_pow(state, cid))
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        ) - sum(
            max(0, _eff_pow(state, cid))
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        )
        commit_attack = (
            role in {"race", "convert"}
            or (role == "normal" and int(hand_profile["action_density"]) >= 3 and board_pressure <= 0)
            or (self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} and int(hand_profile["action_density"]) >= 2)
        )
        for cid in candidates:
            card = state.cards.get(cid)
            if not card:
                continue
            atk_pow = _eff_pow(state, cid)
            atk_tgh = _eff_tgh(state, cid)
            atk_kw = set(effective_keywords(state, cid))
            has_trample = "trample" in atk_kw
            has_deathtouch = "deathtouch" in atk_kw
            if atk_pow <= 0:
                continue

            dies_to_some = any(_eff_pow(state, b) >= atk_tgh for b in opp_blockers)
            kills_some = any(_eff_tgh(state, b) <= atk_pow for b in opp_blockers)
            favorable_trade = kills_some and (not dies_to_some or atk_pow >= 2)
            # Avoid obvious bad attacks with small bodies into larger blockers.
            if (
                atk_pow <= 1
                and opp_blockers
                and not has_trample
                and not has_deathtouch
                and opp_life > 1
                and not race_mode
                and not commit_attack
            ):
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
                and not commit_attack
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
        kws = set(effective_keywords(state, creature_id))
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

    def _choose_x_value(self, state: MatchState, player_id: int, mana_cost: str, card=None) -> int:
        pool_total = sum((state.players[player_id].mana_pool or {}).values())
        untapped_lands = sum(
            1
            for cid in state.players[player_id].battlefield
            if "Land" in state.cards.get(cid, type("X", (), {"types": []})()).types and not state.cards[cid].tapped
        )
        upper = max(0, pool_total + untapped_lands)
        floor = self._minimum_useful_x_value(state, player_id, card, mana_cost)
        scored: list[tuple[float, int]] = []
        for x in range(upper, 0, -1):
            cost = re.sub(r"\{X\}", f"{{{x}}}", mana_cost, flags=re.IGNORECASE)
            if x >= floor and can_pay_with_pool_and_lands(state, player_id, cost):
                scored.append((self._score_x_value(state, player_id, card, mana_cost, x, upper, floor), x))
        if not scored:
            text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
            interactive_x = any(k in text for k in ["target", "destroy", "exile", "counter", "tap"])
            if interactive_x:
                for x in range(1, upper + 1):
                    cost = re.sub(r"\{X\}", f"{{{x}}}", mana_cost, flags=re.IGNORECASE)
                    if can_pay_with_pool_and_lands(state, player_id, cost):
                        return x
            for x in range(max(1, floor), upper + 1):
                cost = re.sub(r"\{X\}", f"{{{x}}}", mana_cost, flags=re.IGNORECASE)
                if can_pay_with_pool_and_lands(state, player_id, cost):
                    return x
            return 0
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][1]

    def _score_x_value(self, state: MatchState, player_id: int, card, mana_cost: str, x_value: int, upper: int, floor: int) -> float:
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        turn = int(getattr(state, "turn", 1) or 1)
        opp_id = 1 if player_id == 2 else 2
        opp = state.players[opp_id]
        me = state.players[player_id]
        opp_creatures = sum(
            1
            for cid in opp.battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        my_creatures = sum(
            1
            for cid in me.battlefield
            if cid in state.cards and "Creature" in state.cards[cid].types
        )
        score = 0.0
        if "create x" in text and "token" in text:
            # Token makers should scale with pressure, but seasoned pilots avoid
            # dumping the entire mana pool into low-value early boards.
            score += x_value * 0.75
            if self.archetype in {"Control", "Counter-heavy"}:
                score += 0.35 if x_value >= 2 else -0.5
                if turn < 6:
                    score -= max(0.0, (x_value - 2) * 0.45)
                    if x_value >= 4 and opp_creatures == 0 and my_creatures == 0:
                        score -= (x_value - 3) * 0.8
                if opp_creatures == 0 and my_creatures == 0:
                    score -= 0.8 if x_value > 2 else 0.0
            elif self.archetype in {"Aggro", "Tokens", "Tribal", "Tempo"}:
                score += 0.45 if x_value >= 2 else -0.25
                if opp_creatures > my_creatures:
                    score += 0.4
            if opp_life := int(getattr(opp, "life", 20) or 20):
                if opp_life <= 6:
                    score += min(1.4, x_value * 0.25)
                elif turn < 6 and opp_life > 10:
                    score -= max(0.0, (x_value - 2) * 0.3)
        elif "draw x" in text:
            score += x_value * 0.55
            if self.archetype in {"Control", "Counter-heavy"}:
                score += 0.7 if x_value >= 2 else -0.5
                if turn < 6:
                    score -= max(0.0, (x_value - 1) * 0.35)
            if len(getattr(me, "hand", []) or []) <= 2 and turn >= 6:
                score += min(1.0, x_value * 0.2)
        elif "deal x damage" in text or "deals x damage" in text or "lose x life" in text:
            opp_life = int(getattr(opp, "life", 20) or 20)
            score += x_value * 0.85
            if opp_life <= x_value:
                score += 2.0
            if self.archetype in {"Burn", "Aggro", "Tempo"}:
                score += 0.35 if x_value >= 2 else -0.2
            elif self.archetype in {"Control", "Counter-heavy"}:
                score += 0.15 if x_value >= 2 else -0.1
        else:
            score += x_value * 0.4

        if x_value == upper:
            score -= 0.2 if upper > 2 else 0.0
        if x_value <= floor + 1:
            score += 0.15
        return score

    def _minimum_useful_x_value(self, state: MatchState, player_id: int, card, mana_cost: str) -> int:
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        turn = int(getattr(state, "turn", 1) or 1)
        if "create x" in text and "token" in text:
            return 3 if self.archetype in {"Control", "Counter-heavy"} and turn < 7 else 2
        if "draw x" in text:
            return 3 if turn < 6 else 2
        if "mill x" in text or "search your library for x" in text:
            return 2
        if "deals x damage" in text or "deal x damage" in text or "lose x life" in text:
            opp_id = 1 if player_id == 2 else 2
            opp_life = int(getattr(state.players.get(opp_id), "life", 20) or 20)
            return 1 if opp_life <= 3 else 2
        if "{x}" in mana_cost.lower():
            if self.archetype in {"Control", "Counter-heavy"} and turn < 5:
                return 2
            return 1
        return 1

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

    def _approximate_resolution_for_activated_action(self, state: MatchState, move: dict, player_id: int) -> None:
        """Resolve simulated abilities only when the opponent has no response."""
        if move.get("type") not in {"activate_ability", "cycle_card"}:
            return
        for _ in range(8):
            if not getattr(state, "stack", []):
                return
            priority_pid = state.priority_player
            legal = self.engine.legal_moves(state, priority_pid)
            non_pass = [m for m in legal if m.get("type") != "pass_priority"]
            if priority_pid != player_id and non_pass:
                return
            self.engine.take_action(state, priority_pid, {"type": "pass_priority"})

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
            elif mtype == "cycle_card":
                base += 1.5 + min(2.0, float(move.get("x_value", 0) or 0) * 0.15)
            elif mtype == "pass_priority":
                base -= 0.2
            return base

        ranked = sorted(legal, key=lambda mv: (quick_score(mv), self._move_sort_key(mv)), reverse=True)
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

        return max(land_moves, key=lambda mv: (score_land(mv), self._move_sort_key(mv)))

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

    def _should_force_inevitability_plan(self, state: MatchState, player_id: int) -> bool:
        if getattr(state, "active_player", player_id) != player_id:
            return False
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return False
        if getattr(state, "stack", []) or []:
            return False
        if not should_force_inevitability_line(
            int(getattr(state, "turn", 1) or 1),
            self.archetype,
            self.opponent_archetype,
        ):
            return False
        me = state.players[player_id]
        opp_id = 1 if player_id == 2 else 2
        opp = state.players[opp_id]
        my_long = len(getattr(me, "library", []) or []) + len(getattr(me, "hand", []) or []) + len(getattr(me, "graveyard", []) or [])
        opp_long = len(getattr(opp, "library", []) or []) + len(getattr(opp, "hand", []) or []) + len(getattr(opp, "graveyard", []) or [])
        my_life = int(getattr(me, "life", 20) or 20)
        opp_life = int(getattr(opp, "life", 20) or 20)
        return my_long >= opp_long - 2 and my_life >= opp_life - 4

    def _choose_forced_inevitability_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if not self._should_force_inevitability_plan(state, player_id):
            return None
        scored: list[tuple[float, dict]] = []
        for mv in legal_moves:
            mtype = mv.get("type")
            if mtype not in {"cast_spell", "activate_loyalty", "attack"}:
                continue
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            score = 0.0
            if mtype == "activate_loyalty":
                score += 4.8
            if mtype == "attack":
                attackers = list(mat.get("attackers") or [])
                if not attackers:
                    continue
                score += 1.6 + min(2.0, float(len(attackers)) * 0.5)
            if mtype == "cast_spell":
                cid = mat.get("card_id")
                card = state.cards.get(cid) if cid else None
                if not card:
                    continue
                tags = self._spell_tags(card)
                if "draw" in tags:
                    score += 4.0
                if "discard" in tags or "mill" in tags:
                    score += 3.0
                if "counter" in tags:
                    score -= 2.4
                if "removal" in tags:
                    opp_id = 1 if player_id == 2 else 2
                    opp_creatures = sum(
                        1
                        for ocid in state.players[opp_id].battlefield
                        if ocid in state.cards and "Creature" in state.cards[ocid].types
                    )
                    score += 2.2 if opp_creatures > 0 else -1.3
                if "Planeswalker" in set(getattr(card, "types", []) or []):
                    score += 3.6
                if "Creature" in set(getattr(card, "types", []) or []):
                    power = int(getattr(card, "power", 0) or 0)
                    score += min(2.8, power * 0.5)
            scored.append((score, mat))
        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        top = scored[0][1]
        if top.get("type") == "attack" and not (top.get("attackers") or []):
            return None
        return top

    def _choose_forced_tempo_noncontrol_closure_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        if self.archetype != "Tempo":
            return None
        opp = (self.opponent_archetype or "").strip()
        if opp in {"Control", "Counter-heavy"}:
            return None
        if getattr(state, "active_player", player_id) != player_id:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if turn < 8:
            return None
        ranked = self._rank_moves(state, legal_moves, player_id)
        for mv in ranked:
            if mv.get("type") == "attack":
                mat = self._materialize_action(state, mv, player_id)
                if mat.get("attackers"):
                    return mat
        for mv in ranked:
            if mv.get("type") != "cast_spell":
                continue
            mat = self._materialize_action(state, mv, player_id)
            if mat.get("_invalid_ai_choice") or self._is_unplayable_x_action(mat):
                continue
            if self._is_action_obviously_illegal(state, mat, player_id):
                continue
            cid = mat.get("card_id")
            card = state.cards.get(cid) if cid else None
            tags = self._spell_tags(card) if card else set()
            # Prefer threat/removal/draw conversion, avoid empty-stack hold-up counters.
            if "counter" in tags and not (getattr(state, "stack", []) or []):
                continue
            return mat
        return None

    def _best_proactive_non_pass(self, ranked_moves: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        non_pass = [m for m in ranked_moves if m.get("type") not in {"pass_priority", "tap_land_for_mana", "tap_lands_bulk"}]
        if not non_pass:
            return None
        burn_convert = self._best_burn_conversion_cast(non_pass, state, player_id)
        if burn_convert is not None:
            return burn_convert
        tempo_convert = self._best_tempo_threat_first_cast(non_pass, state, player_id)
        if tempo_convert is not None:
            return tempo_convert
        cheap = self._best_cheap_proactive_cast(non_pass, state, player_id)
        if cheap is not None:
            return cheap
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

        meaningful = [m for m in legal_moves if m.get("type") in {"play_land", "cast_spell", "cycle_card", "activate_loyalty", "attack"}]
        if not meaningful:
            return chosen

        # Cross-archetype anti-stall: repeated same-board main-phase passes with options
        # should force resource conversion.
        if self._should_force_conversion_after_repeated_main_pass(state, player_id):
            ranked = self._rank_moves(state, legal_moves, player_id)
            proactive = self._best_proactive_non_pass(ranked, state, player_id)
            if proactive is not None:
                proactive = self._materialize_action(state, proactive, player_id)
                if (
                    not proactive.get("_invalid_ai_choice")
                    and not self._is_unplayable_x_action(proactive)
                    and not self._is_action_obviously_illegal(state, proactive, player_id)
                    and (proactive.get("type") != "attack" or bool(proactive.get("attackers") or []))
                ):
                    return proactive

        ranked = self._rank_moves(state, legal_moves, player_id)
        early_cheap = self._best_cheap_proactive_cast(
            [m for m in ranked if m.get("type") not in {"pass_priority", "tap_land_for_mana", "tap_lands_bulk"}],
            state,
            player_id,
        )
        if early_cheap is not None:
            early_cheap = self._materialize_action(state, early_cheap, player_id)
            if (
                not early_cheap.get("_invalid_ai_choice")
                and not self._is_unplayable_x_action(early_cheap)
                and not self._is_action_obviously_illegal(state, early_cheap, player_id)
            ):
                return early_cheap
        if ranked and ranked[0].get("type") == "pass_priority":
            return chosen
        proactive = self._best_proactive_non_pass(ranked, state, player_id)
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

    def _should_force_conversion_after_repeated_main_pass(self, state: MatchState, player_id: int) -> bool:
        hand = [str(getattr(state.cards.get(cid), "name", cid)) for cid in (getattr(state.players[player_id], "hand", []) or [])]
        hand_key = tuple(sorted(hand)[:4])
        my_lands = sum(
            1
            for cid in (getattr(state.players[player_id], "battlefield", []) or [])
            if cid in state.cards and "Land" in (getattr(state.cards[cid], "types", []) or [])
        )
        opp_id = 1 if player_id == 2 else 2
        opp_creatures = sum(
            1
            for cid in (getattr(state.players[opp_id], "battlefield", []) or [])
            if cid in state.cards and "Creature" in (getattr(state.cards[cid], "types", []) or [])
        )
        sig = (player_id, int(getattr(state, "turn", 1) or 1), hand_key, my_lands, opp_creatures)
        cur = int(self._main_pass_signature_counts.get(sig, 0) or 0) + 1
        self._main_pass_signature_counts[sig] = cur
        return cur >= 2

    def _best_cheap_proactive_cast(self, non_pass: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        turn = int(getattr(state, "turn", 1) or 1)
        if turn > 4:
            return None
        # If opponent is mostly tapped early, value proactive cheap development.
        me = getattr(state, "active_player", None)
        pid = player_id if player_id in {1, 2} else (me if me in {1, 2} else 1)
        opp_id = 1 if pid == 2 else 2
        opp_untapped_lands = sum(
            1
            for cid in (getattr(state.players[opp_id], "battlefield", []) or [])
            if cid in state.cards and "Land" in (getattr(state.cards[cid], "types", []) or []) and not state.cards[cid].tapped
        )
        if opp_untapped_lands > 2:
            return None
        scored: list[tuple[float, dict]] = []
        for mv in non_pass:
            if mv.get("type") != "cast_spell":
                continue
            cid = mv.get("card_id")
            card = state.cards.get(cid) if cid else None
            if not card:
                continue
            mana_text = str(getattr(card, "mana_cost", "") or "")
            if "{X}" in mana_text.upper():
                continue
            mana_req = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=False)
            cmc = mana_value(getattr(card, "mana_cost", ""), is_land=False)
            if cmc > 2:
                continue
            tags = self._spell_tags(card)
            score = 0.0
            if "Creature" in set(getattr(card, "types", []) or []):
                score += 3.2
            if "draw" in tags:
                score += 2.4
            if "token" in tags:
                score += 2.2
            if "counter" in tags and not (getattr(state, "stack", []) or []):
                score -= 3.0
            if "removal" in tags:
                opp_creatures = sum(
                    1
                    for x in (getattr(state.players[opp_id], "battlefield", []) or [])
                    if x in state.cards and "Creature" in (getattr(state.cards[x], "types", []) or [])
                )
                score += 1.2 if opp_creatures > 0 else -1.5
            scored.append((score, mv))
        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        return scored[0][1]

    def _best_tempo_threat_first_cast(self, non_pass: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        if self.archetype not in {"Tempo"}:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        turn = int(getattr(state, "turn", 1) or 1)
        if turn > 5:
            return None
        choices: list[tuple[float, dict]] = []
        for mv in non_pass:
            if mv.get("type") != "cast_spell":
                continue
            cid = mv.get("card_id")
            card = state.cards.get(cid) if cid else None
            if not card:
                continue
            types = set(getattr(card, "types", []) or [])
            mana_req = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=False)
            cmc = mana_req["generic"] + sum(mana_req[c] for c in ["W", "U", "B", "R", "G"])
            if "Creature" in types and cmc <= 2:
                choices.append((4.0 - cmc * 0.2, mv))
            else:
                tags = self._spell_tags(card)
                if "counter" in tags and not (getattr(state, "stack", []) or []):
                    choices.append((-2.5, mv))
        if not choices:
            return None
        choices.sort(key=lambda x: (x[0], self._move_sort_key(x[1])), reverse=True)
        top_score, top = choices[0]
        return top if top_score > 0 else None

    def _best_burn_conversion_cast(self, non_pass: list[dict], state: MatchState, player_id: int | None = None) -> dict | None:
        if self.archetype not in {"Burn"}:
            return None
        if _step_key(getattr(state, "step", "")) not in {"precombat_main", "postcombat_main"}:
            return None
        if getattr(state, "stack", []) or []:
            return None
        pid = player_id if player_id in {1, 2} else getattr(state, "active_player", 1)
        opp_id = 1 if pid == 2 else 2
        opp_life = int(getattr(state.players[opp_id], "life", 20) or 20)
        burn_spells: list[tuple[float, dict]] = []
        for mv in non_pass:
            if mv.get("type") != "cast_spell":
                continue
            cid = mv.get("card_id")
            card = state.cards.get(cid) if cid else None
            if not card:
                continue
            text = f"{(getattr(card, 'name', '') or '').lower()} {(getattr(card, 'oracle_text', '') or '').lower()}"
            dmg = self._burn_damage_estimate(text)
            if dmg <= 0:
                continue
            score = float(dmg)
            if opp_life <= dmg:
                score += 10.0  # immediate lethal
            elif opp_life <= dmg + 3:
                score += 3.5   # two-turn clock compression
            burn_spells.append((score, mv))
        if not burn_spells:
            return None
        burn_spells.sort(key=lambda x: x[0], reverse=True)
        return burn_spells[0][1]

    def _burn_damage_estimate(self, text: str) -> int:
        t = text.lower()
        if any(k in t for k in ["lava spike", "lightning bolt", "boros charm", "rift bolt"]):
            return 3
        if any(k in t for k in ["lightning helix", "wizard's lightning", "skewer the critics"]):
            return 3
        if any(k in t for k in ["shock", "play with fire"]):
            return 2
        if "searing blaze" in t:
            return 3
        return 0

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
            cmc = mana_value(getattr(card, "mana_cost", ""), is_land=False)
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
                opp_id = 1 if player_id == 2 else 2
                opp_creatures = sum(
                    1
                    for oid in getattr(state.players[opp_id], "battlefield", [])
                    if oid in state.cards and "Creature" in state.cards[oid].types
                )
                # Preserve early-game hold-up discipline, but deploy sooner when the board is clear.
                if turn >= 5:
                    return True
                if turn >= 4 and opp_creatures <= 1:
                    return True
        return False

    def _color_demand(self, state: MatchState, player_id: int) -> dict[str, int]:
        demand = {c: 0 for c in ["W", "U", "B", "R", "G"]}
        for cid in state.players[player_id].hand:
            card = state.cards.get(cid)
            if not card or "Land" in card.types:
                continue
            cost = parse_mana_cost(getattr(card, "mana_cost", ""), is_land=False)
            cmc = mana_value(getattr(card, "mana_cost", ""), is_land=False)
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
            if cid in state.cards and "Creature" in getattr(state.cards[cid], "types", []) and not getattr(state.cards[cid], "tapped", False)
        )
        opp_power = sum(
            max(0, int(getattr(state.cards.get(cid), "power", 0) or 0))
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in getattr(state.cards[cid], "types", []) and not getattr(state.cards[cid], "tapped", False)
        )
        my_creatures = sum(
            1
            for cid in state.players[player_id].battlefield
            if cid in state.cards and "Creature" in getattr(state.cards[cid], "types", []) and not getattr(state.cards[cid], "tapped", False)
        )
        opp_creatures = sum(
            1
            for cid in state.players[opp_id].battlefield
            if cid in state.cards and "Creature" in getattr(state.cards[cid], "types", []) and not getattr(state.cards[cid], "tapped", False)
        )
        hand_delta = len(getattr(state.players[player_id], "hand", []) or []) - len(getattr(state.players[opp_id], "hand", []) or [])
        if opp_life <= 7 or (my_power >= opp_life and opp_life <= 10):
            return "race"
        if my_life <= 8 and opp_power > my_power + 1:
            return "stabilize"
        if opp_power >= my_power + 3 and opp_creatures >= my_creatures and my_life <= 12:
            return "stabilize"
        if my_power >= opp_power + 2 and my_creatures >= opp_creatures and my_life > 8:
            return "convert"
        if hand_delta >= 2 and opp_power <= my_power and my_life > 10:
            return "control"
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

    def _noncreature_permanent_threat_score(self, state: MatchState, card_id: str | None, player_id: int) -> float:
        if not card_id or card_id not in state.cards:
            return 0.0
        card = state.cards[card_id]
        opp_id = 1 if player_id == 2 else 2
        controller = getattr(card, "controller", None)
        if controller == player_id:
            return -10.0
        score = 0.0
        types = set(getattr(card, "types", []) or [])
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        if "Planeswalker" in types:
            score += 8.0
        if "Artifact" in types:
            score += 3.0
        if "Enchantment" in types:
            score += 3.0
        if any(k in text for k in ["you can't", "players can't", "your opponents can't"]):
            score += 4.0
        if any(k in text for k in ["draw", "at the beginning of", "whenever"]):
            score += 1.5
        if any(k in text for k in ["creatures you control get", "+1/+1", "anthem"]):
            score += 2.2
        if any(k in text for k in ["sacrifice", "exile", "destroy"]):
            score += 1.0
        if any(k in text for k in ["treasure", "add {", "create token"]):
            score += 1.3
        # Matchup-aware importance boosts.
        if self.archetype in {"Aggro", "Burn", "Tempo"} and any(k in text for k in ["lifelink", "gain life", "can't lose life"]):
            score += 3.2
        if self.archetype in {"Control", "Counter-heavy"} and any(k in text for k in ["draw", "search your library", "return target"]):
            score += 2.2
        if self.archetype in {"Tokens", "Tribal"} and any(k in text for k in ["creatures you control get", "token"]):
            score += 2.2
        # If permanent belongs to opponent battlefield, it's usually a real target.
        if card_id in getattr(state.players[opp_id], "battlefield", []):
            score += 0.8
        return score

    def _graveyard_creature_reanimation_score(self, state: MatchState, card_id: str | None, player_id: int) -> float:
        if not card_id or card_id not in state.cards:
            return 0.0
        card = state.cards[card_id]
        score = float(getattr(card, "power", 0) or 0) * 0.9 + float(getattr(card, "toughness", 0) or 0) * 0.3
        if "legendary" in " ".join(getattr(card, "types", [])).lower():
            score += 0.5
        text = f"{getattr(card, 'name', '')} {getattr(card, 'oracle_text', '')}".lower()
        if any(k in text for k in ["draw", "counter", "remove", "destroy", "exile", "return"]):
            score += 0.4
        return score

    def _choose_best_stack_target_id(self, state: MatchState, player_id: int, candidates: list[dict]) -> str | None:
        best_id = None
        best_score = -999.0
        best_tiebreak = ""
        for c in candidates:
            sid = c.get("id")
            if not sid:
                continue
            score = self._stack_item_threat_score(state, sid, player_id)
            tiebreak = str(c.get("label") or c.get("name") or sid)
            if score > best_score or (score == best_score and (best_id is None or tiebreak < best_tiebreak)):
                best_score = score
                best_id = sid
                best_tiebreak = tiebreak
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
        if "Artifact" in types:
            score += 2.8
        if "Enchantment" in types:
            score += 2.8
        if "Creature" in types:
            p = int(getattr(source, "power", 0) or 0)
            t = int(getattr(source, "toughness", 0) or 0)
            score += min(7.0, p * 0.9 + t * 0.3)
        mana_cost = parse_mana_cost(getattr(source, "mana_cost", ""), is_land=False)
        cmc = mana_value(getattr(source, "mana_cost", ""), is_land=False)
        score += min(5.0, cmc * 0.45)
        text = f"{getattr(source, 'name', '')} {getattr(source, 'oracle_text', '')}".lower()
        if any(k in text for k in ["destroy all", "exile all", "sweeper", "wrath", "damnation"]):
            score += 6.0
        if any(k in text for k in ["draw", "memory deluge", "dig through", "treasure cruise"]):
            score += 2.2
        if any(k in text for k in ["counter target spell"]):
            score += 1.4
        if any(k in text for k in ["you can't", "players can't", "your opponents can't"]):
            score += 4.0
        if any(k in text for k in ["creatures you control get", "+1/+1"]):
            score += 2.0
        if any(k in text for k in ["at the beginning of", "whenever", "draw"]):
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
