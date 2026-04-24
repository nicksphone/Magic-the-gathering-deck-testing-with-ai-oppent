from __future__ import annotations

import copy
from dataclasses import dataclass

from ai.heuristics import evaluate_board
from game_state.state import MatchState
from rules_engine.engine import RulesEngine
from rules_engine.mana import parse_mana_cost


@dataclass
class AIDecision:
    action: dict
    reasoning: str


class AIAgent:
    def __init__(self, difficulty: str = "strong", archetype: str = "Midrange"):
        self.difficulty = difficulty.lower()
        self.archetype = archetype
        self.engine = RulesEngine()

    def choose_action(self, state: MatchState, legal_moves: list[dict], player_id: int) -> AIDecision:
        if getattr(state, "pregame_pending", False):
            return self.choose_mulligan_action(state, player_id)
        if not legal_moves:
            return AIDecision(action={"type": "pass_priority"}, reasoning="No legal actions")

        sorted_moves = self._rank_moves(state, legal_moves, player_id)
        if self.difficulty == "casual":
            move = sorted_moves[min(1, len(sorted_moves) - 1)]
        elif self.difficulty == "master":
            move = sorted_moves[0]
        else:
            move = sorted_moves[0]

        return AIDecision(action=move, reasoning=f"{self.archetype} plan selected best-scoring move")

    def choose_mulligan_action(self, state: MatchState, player_id: int) -> AIDecision:
        player = state.players[player_id]
        hand = [state.cards[cid] for cid in player.hand]
        lands = sum(1 for c in hand if "Land" in c.types)
        early_spells = 0
        for c in hand:
            if "Land" in c.types:
                continue
            cost = parse_mana_cost(c.mana_cost)
            cmc = cost["generic"] + sum(cost[x] for x in ["W", "U", "B", "R", "G"])
            if cmc <= 2:
                early_spells += 1
        quality = (1.0 - min(abs(lands - 3), 3) / 3) * 0.7 + min(early_spells / 2, 1.0) * 0.3
        if state.mulligan_count.get(player_id, 0) < 2 and quality < 0.45:
            return AIDecision(action={"type": "mulligan"}, reasoning="Opening hand quality too low")
        return AIDecision(action={"type": "keep_hand", "bottom_card_ids": []}, reasoning="Keep acceptable hand")

    def _rank_moves(self, state: MatchState, moves: list[dict], player_id: int) -> list[dict]:
        def score(move: dict) -> float:
            mtype = move.get("type")
            base = evaluate_board(state, player_id)
            if mtype == "cast_spell":
                name = move.get("card_name", "").lower()
                if "bolt" in name or "spike" in name:
                    base += 6 if self.archetype in {"Burn", "Aggro", "Tempo"} else 3
                if "counterspell" in name:
                    if state.stack:
                        base += 8 if self.archetype in {"Control", "Counter-heavy", "Tempo"} else 4
                    else:
                        base -= 2
            elif mtype == "play_land":
                base += 5
            elif mtype == "tap_land_for_mana":
                base += 3
            elif mtype == "attack":
                base += self._attack_bias(state, move, player_id)
            elif mtype == "pass_priority":
                base += self._pass_bias(state, player_id)
            if self.difficulty == "master":
                base += self._simulate_delta(state, move, player_id)
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
        race_pressure = max(0, 20 - state.players[opp_id].life) * 0.2
        archetype_bias = 5 if self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} else 2
        return archetype_bias + attack_power * 0.8 - opp_block_power * 0.35 + race_pressure

    def _pass_bias(self, state: MatchState, player_id: int) -> float:
        has_instant_like = False
        for cid in state.players[player_id].hand:
            c = state.cards.get(cid)
            if not c:
                continue
            if "Instant" in c.types or "flash" in [k.lower() for k in c.keywords]:
                has_instant_like = True
                break
        if state.stack:
            return -2.0
        if has_instant_like and self.archetype in {"Control", "Counter-heavy", "Tempo"}:
            return 1.8
        return 0.3
