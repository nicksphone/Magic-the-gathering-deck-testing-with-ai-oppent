from __future__ import annotations

import json
import hashlib
import random
from itertools import combinations
from collections import Counter

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.replay_tools import classify_first_divergence, first_log_divergence
from rules_engine.mana import parse_mana_cost
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from game_state.state import MatchFactory


class AnalyticsService:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.engine = RulesEngine()

    def run_batch(
        self,
        deck_a: list[dict],
        deck_b: list[dict],
        matches: int = 100,
        difficulty: str = "master",
        max_ticks: int = 6000,
        progress_callback=None,
    ) -> dict:
        stats = Counter()
        turn_counts = []
        play_win = 0
        resolved_play_games = 0
        opener_quality_a: list[float] = []
        opener_quality_b: list[float] = []
        anomaly_counts: Counter = Counter()
        top_errors: Counter = Counter()
        replay_fingerprint_parts: list[str] = []
        first_game_log: list[str] = []
        second_game_log: list[str] = []
        game_results: list[dict[str, object]] = []

        for i in range(matches):
            seed = self._batch_seed(deck_a, deck_b, i, difficulty)
            deck_a_on_play = i % 2 == 0
            if deck_a_on_play:
                state = MatchFactory.from_decks(deck_a, deck_b, player_a_name="Deck A", player_b_name="Deck B", seed=seed)
            else:
                state = MatchFactory.from_decks(deck_b, deck_a, player_a_name="Deck B", player_b_name="Deck A", seed=seed)
            opener_quality_a.append(self._opening_hand_quality(state, 1))
            opener_quality_b.append(self._opening_hand_quality(state, 2))
            a_agent = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_a))
            b_agent = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_b))
            ticks = 0
            while state.winner is None and ticks < max_ticks:
                if state.pregame_pending:
                    pid = 1 if 1 not in state.kept_hands else 2
                else:
                    pid = state.priority_player
                legal = self.engine.legal_moves(state, pid)
                if deck_a_on_play:
                    agent = a_agent if pid == 1 else b_agent
                else:
                    agent = b_agent if pid == 1 else a_agent
                decision = agent.choose_action(state, legal, pid)
                # Safety: if AI returns an action not in legal moves, treat as pass
                legal_types = {m["type"] for m in legal}
                if decision.action.get("type") not in legal_types:
                    decision.action = {"type": "pass_priority"}
                self.engine.take_action(state, pid, decision.action)
                if state.step == state.step.COMBAT_DAMAGE:
                    self.engine.take_action(state, state.active_player, {"type": "combat_damage"})
                ticks += 1

            winner = state.winner
            if winner in (1, 2):
                deck_a_won = (winner == 1 and deck_a_on_play) or (winner == 2 and not deck_a_on_play)
                if deck_a_won:
                    stats["wins_1"] += 1
                else:
                    stats["wins_2"] += 1
                if deck_a_on_play:
                    resolved_play_games += 1
                    if deck_a_won:
                        play_win += 1
            else:
                stats["timeouts"] += 1
            self._scan_log_for_anomalies(state.log, anomaly_counts, top_errors)
            if i == 0:
                first_game_log = list(state.log)
            elif i == 1:
                second_game_log = list(state.log)
            game_results.append(
                {
                    "game_index": i,
                    "seed": seed,
                    "winner": winner,
                    "turns": state.turn,
                    "timeout": winner is None,
                    "deck_a_on_play": deck_a_on_play,
                }
            )
            replay_fingerprint_parts.append(f"{i}:{winner or 0}:{state.turn}")
            turn_counts.append(state.turn)
            if progress_callback is not None:
                try:
                    progress_callback(i + 1, matches)
                except Exception:
                    pass

        total = matches
        wins_a = stats["wins_1"]
        wins_b = stats["wins_2"]
        result = {
            "matches": matches,
            "win_rate_deck_a": round((wins_a / total) * 100, 2),
            "win_rate_deck_b": round((wins_b / total) * 100, 2),
            "timeouts": int(stats["timeouts"]),
            "draw_play_advantage_deck_a": round((play_win / max(1, resolved_play_games)) * 100, 2),
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
            "anomalies": {
                "timeouts": int(anomaly_counts["timeouts"]),
                "invalid_targets": int(anomaly_counts["invalid_targets"]),
                "cost_failures": int(anomaly_counts["cost_failures"]),
                "additional_cost_failures": int(anomaly_counts["additional_cost_failures"]),
                "repeated_error_bursts": int(anomaly_counts["repeated_error_bursts"]),
                "stall_pass_streaks": int(anomaly_counts["stall_pass_streaks"]),
                "missed_land_windows": int(anomaly_counts["missed_land_windows"]),
            },
            "top_errors": [{"message": m, "count": n} for m, n in top_errors.most_common(10)],
            "game_results": game_results,
            "first_divergence": self.compare_replay_logs(first_game_log, second_game_log) if second_game_log else None,
            "sample_turn_summaries": self._extract_turn_summaries(first_game_log),
            "sample_log_excerpt": first_game_log[:12],
            "deterministic_replay_fingerprint": hashlib.sha256("|".join(replay_fingerprint_parts).encode("utf-8")).hexdigest(),
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

    def run_ai_diagnostics(
        self,
        deck_pool: list[dict],
        matches_per_pair: int = 5,
        difficulty: str = "master",
        max_ticks: int = 6000,
    ) -> dict:
        if len(deck_pool) < 2:
            return {
                "deck_count": len(deck_pool),
                "pairs_tested": 0,
                "games": 0,
                "global_anomalies": {},
                "top_errors": [],
                "suspicious_matchups": [],
            }

        global_counts: Counter = Counter()
        top_errors: Counter = Counter()
        suspicious: list[dict] = []
        total_games = 0

        for left, right in combinations(deck_pool, 2):
            pair_counts: Counter = Counter()
            pair_turns: list[int] = []
            pair_games = 0
            pair_first_player_wins = 0
            first_game_log: list[str] = []

            for game_idx in range(matches_per_pair):
                state = MatchFactory.from_decks(left["mainboard"], right["mainboard"], player_a_name=left["name"], player_b_name=right["name"])
                a_agent = AIAgent(difficulty=difficulty, archetype=guess_archetype(left["mainboard"]))
                b_agent = AIAgent(difficulty=difficulty, archetype=guess_archetype(right["mainboard"]))
                ticks = 0
                while state.winner is None and ticks < max_ticks:
                    pid = 1 if state.pregame_pending and 1 not in state.kept_hands else (2 if state.pregame_pending else state.priority_player)
                    legal = self.engine.legal_moves(state, pid)
                    if not legal:
                        pair_counts["no_legal_moves"] += 1
                        self.engine.take_action(state, pid, {"type": "pass_priority"})
                    else:
                        agent = a_agent if pid == 1 else b_agent
                        decision = agent.choose_action(state, legal, pid)
                        # Safety: if AI returns an action not in legal moves, treat as pass
                        legal_types = {m["type"] for m in legal}
                        if decision.action.get("type") not in legal_types:
                            decision.action = {"type": "pass_priority"}
                        self.engine.take_action(state, pid, decision.action)
                    if state.step == state.step.COMBAT_DAMAGE:
                        self.engine.take_action(state, state.active_player, {"type": "combat_damage"})
                    ticks += 1

                if state.winner is None:
                    pair_counts["timeouts"] += 1
                elif state.winner == 1 and game_idx % 2 == 0:
                    pair_first_player_wins += 1

                self._scan_log_for_anomalies(state.log, pair_counts, top_errors)
                if game_idx == 0:
                    first_game_log = list(state.log)
                pair_turns.append(state.turn)
                pair_games += 1
                total_games += 1

            global_counts.update(pair_counts)
            avg_turns = round(sum(pair_turns) / max(1, len(pair_turns)), 2)
            suspicious.append(
                {
                    "deck_a": left["name"],
                    "deck_b": right["name"],
                    "games": pair_games,
                    "avg_turns": avg_turns,
                    "timeouts": int(pair_counts["timeouts"]),
                    "invalid_targets": int(pair_counts["invalid_targets"]),
                    "cost_failures": int(pair_counts["cost_failures"]),
                    "repeated_error_bursts": int(pair_counts["repeated_error_bursts"]),
                    "draw_play_advantage_deck_a": round((pair_first_player_wins / max(1, pair_games // 2 or 1)) * 100, 2),
                    "turn_summaries": self._extract_turn_summaries(first_game_log),
                }
            )

        suspicious.sort(
            key=lambda x: (x["timeouts"] * 5 + x["invalid_targets"] * 3 + x["cost_failures"] * 2 + x["repeated_error_bursts"]),
            reverse=True,
        )
        result = {
            "deck_count": len(deck_pool),
            "pairs_tested": len(suspicious),
            "games": total_games,
            "global_anomalies": {
                "timeouts": int(global_counts["timeouts"]),
                "invalid_targets": int(global_counts["invalid_targets"]),
                "cost_failures": int(global_counts["cost_failures"]),
                "additional_cost_failures": int(global_counts["additional_cost_failures"]),
                "no_legal_moves": int(global_counts["no_legal_moves"]),
                "repeated_error_bursts": int(global_counts["repeated_error_bursts"]),
                "stall_pass_streaks": int(global_counts["stall_pass_streaks"]),
                "missed_land_windows": int(global_counts["missed_land_windows"]),
            },
            "top_errors": [{"message": msg, "count": count} for msg, count in top_errors.most_common(20)],
            "suspicious_matchups": suspicious[:20],
        }
        self.repo.save_snapshot("ai_diagnostics", result)
        return result

    @staticmethod
    def decode_match_log(raw: str) -> list[str]:
        return json.loads(raw)

    @staticmethod
    def compare_replay_logs(left_log: list[str], right_log: list[str]) -> dict:
        drift = first_log_divergence(left_log, right_log)
        return classify_first_divergence(drift)

    @staticmethod
    def _extract_turn_summaries(log: list[str], max_turns: int = 8) -> list[dict]:
        summaries: list[dict] = []
        seen_turns: set[int] = set()
        for line in log:
            if not line.startswith("AI TRACE "):
                continue
            try:
                trace = json.loads(line[len("AI TRACE ") :])
            except Exception:
                continue
            turn = trace.get("turn")
            try:
                turn_num = int(turn)
            except Exception:
                continue
            if turn_num in seen_turns:
                continue
            seen_turns.add(turn_num)
            action = trace.get("action") or {}
            life = trace.get("life") or {}
            summaries.append(
                {
                    "turn": turn_num,
                    "pid": trace.get("pid"),
                    "step": trace.get("step"),
                    "action_type": action.get("type"),
                    "card_name": action.get("card_name"),
                    "hand_size": len(trace.get("hand") or []),
                    "battlefield_size": len(trace.get("battlefield") or []),
                    "opp_battlefield_size": len(trace.get("opp_battlefield") or []),
                    "life": {
                        "self": life.get("self"),
                        "opp": life.get("opp"),
                    },
                    "mana_pool": dict(trace.get("mana_pool") or {}),
                    "reasoning": trace.get("reasoning", ""),
                }
            )
            if len(summaries) >= max_turns:
                break
        return summaries

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

    @staticmethod
    def _batch_seed(deck_a: list[dict], deck_b: list[dict], game_index: int, difficulty: str) -> int:
        payload = json.dumps(
            {
                "deck_a": deck_a,
                "deck_b": deck_b,
                "game_index": int(game_index),
                "difficulty": difficulty.lower(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)

    def _scan_log_for_anomalies(self, log: list[str], out: Counter, top_errors: Counter) -> None:
        error_lines: list[str] = []
        consecutive_passes = 0
        for line in log:
            low = line.lower()
            if "passes priority" in low:
                consecutive_passes += 1
                if consecutive_passes >= 4:
                    out["stall_pass_streaks"] += 1
                    consecutive_passes = 0
            else:
                consecutive_passes = 0
            if "invalid targets for" in low:
                out["invalid_targets"] += 1
                error_lines.append(line.strip())
            if "cannot satisfy chosen costs for" in low or "cannot pay mana cost for" in low:
                out["cost_failures"] += 1
                error_lines.append(line.strip())
            if "failed additional costs for" in low:
                out["additional_cost_failures"] += 1
                error_lines.append(line.strip())
            if "missed land-play window" in low or "land in hand but no land play available" in low:
                out["missed_land_windows"] += 1
                error_lines.append(line.strip())
        for e in error_lines:
            top_errors[e] += 1
        # Detect repeated consecutive error bursts, which usually indicate AI stall loops.
        streak = 1
        for i in range(1, len(error_lines)):
            if error_lines[i] == error_lines[i - 1]:
                streak += 1
                if streak >= 3:
                    out["repeated_error_bursts"] += 1
                    streak = 1
            else:
                streak = 1
