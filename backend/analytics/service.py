from __future__ import annotations

import json
import random
from collections import Counter

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from rules_engine.mana import parse_mana_cost
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from game_state.state import MatchFactory


class AnalyticsService:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.engine = RulesEngine()

    def run_batch(self, deck_a: list[dict], deck_b: list[dict], matches: int = 100, difficulty: str = "master") -> dict:
        stats = Counter()
        turn_counts = []
        play_win = 0
        opener_quality_a: list[float] = []
        opener_quality_b: list[float] = []

        for i in range(matches):
            state = MatchFactory.from_decks(deck_a, deck_b, player_a_name="Deck A", player_b_name="Deck B")
            opener_quality_a.append(self._opening_hand_quality(state, 1))
            opener_quality_b.append(self._opening_hand_quality(state, 2))
            a_agent = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_a))
            b_agent = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_b))
            max_ticks = 500
            ticks = 0
            while state.winner is None and ticks < max_ticks:
                pid = state.priority_player
                legal = self.engine.legal_moves(state, pid)
                agent = a_agent if pid == 1 else b_agent
                decision = agent.choose_action(state, legal, pid)
                self.engine.take_action(state, pid, decision.action)
                if state.step == state.step.COMBAT_DAMAGE:
                    self.engine.take_action(state, state.active_player, {"type": "combat_damage"})
                ticks += 1

            winner = state.winner or 1
            stats[f"wins_{winner}"] += 1
            if winner == 1 and i % 2 == 0:
                play_win += 1
            turn_counts.append(state.turn)

        total = matches
        result = {
            "matches": matches,
            "win_rate_deck_a": round((stats["wins_1"] / total) * 100, 2),
            "win_rate_deck_b": round((stats["wins_2"] / total) * 100, 2),
            "draw_play_advantage_deck_a": round((play_win / max(1, matches // 2)) * 100, 2),
            "average_turns": round(sum(turn_counts) / max(1, len(turn_counts)), 2),
            "mulligan_stats": {
                "deck_a_avg_opening_hand_quality": round(sum(opener_quality_a) / max(1, len(opener_quality_a)), 2),
                "deck_b_avg_opening_hand_quality": round(sum(opener_quality_b) / max(1, len(opener_quality_b)), 2),
            },
            "deck_consistency": {
                "deck_a_curve_stability": round(self._curve_stability(deck_a), 3),
                "deck_b_curve_stability": round(self._curve_stability(deck_b), 3),
            },
            "matchup": {
                "deck_a_archetype": guess_archetype(deck_a),
                "deck_b_archetype": guess_archetype(deck_b),
            },
        }
        self.repo.save_snapshot("batch_simulation", result)
        return result

    def aggregate_history(self) -> dict:
        rows = self.repo.list_matches()
        if not rows:
            return {"matches": 0, "win_rates": {}, "avg_turns": 0}
        wins = Counter(r.winner for r in rows)
        turns = [r.turns for r in rows]
        return {
            "matches": len(rows),
            "win_rates": dict(wins),
            "avg_turns": round(sum(turns) / len(turns), 2),
        }

    @staticmethod
    def decode_match_log(raw: str) -> list[str]:
        return json.loads(raw)

    def _opening_hand_quality(self, state, player_id: int) -> float:
        hand = [state.cards[cid] for cid in state.players[player_id].hand]
        lands = sum(1 for c in hand if "Land" in c.types)
        cheap_spells = 0
        for c in hand:
            if "Land" in c.types:
                continue
            cost = parse_mana_cost(c.mana_cost)
            cmc = cost["generic"] + sum(cost[x] for x in ["W", "U", "B", "R", "G"])
            if cmc <= 2:
                cheap_spells += 1
        land_score = 1.0 - min(abs(lands - 3), 3) / 3
        spell_score = min(cheap_spells / 3, 1.0)
        return (land_score * 0.6 + spell_score * 0.4) * 10

    def _curve_stability(self, deck: list[dict]) -> float:
        expanded = []
        for item in deck:
            expanded.extend([item] * int(item["quantity"]))
        if not expanded:
            return 0.0
        sample_scores = []
        for _ in range(20):
            hand = random.sample(expanded, k=min(7, len(expanded)))
            cmcs = []
            for item in hand:
                cost = parse_mana_cost(item.get("mana_cost", ""))
                cmcs.append(cost["generic"] + sum(cost[x] for x in ["W", "U", "B", "R", "G"]))
            if not cmcs:
                sample_scores.append(0.0)
                continue
            avg = sum(cmcs) / len(cmcs)
            variance = sum((x - avg) ** 2 for x in cmcs) / len(cmcs)
            sample_scores.append(1 / (1 + variance))
        return sum(sample_scores) / len(sample_scores)
