from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from ai.heuristics import evaluate_board
from game_state.state import MatchState
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands, parse_mana_cost


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
        if _step_key(getattr(state, "step", "")) == "declare_blockers" and getattr(state, "active_player", player_id) != player_id:
            if bool(getattr(state, "blocks", {})):
                return AIDecision(action={"type": "pass_priority"}, reasoning="Blocks already declared; pass priority")

        forced_land = self._choose_forced_land_play(state, legal_moves, player_id)
        if forced_land is not None:
            return AIDecision(action=forced_land, reasoning="Prioritize reliable land development on own main phase")

        sorted_moves = self._rank_moves(state, legal_moves, player_id)
        if self.difficulty == "casual":
            move = sorted_moves[min(1, len(sorted_moves) - 1)]
        elif self.difficulty in {"master", "master_plus"}:
            move = sorted_moves[0]
        else:
            move = sorted_moves[0]
        move = self._materialize_action(state, move, player_id)
        if move.get("type") == "block" and not move.get("blocks"):
            return AIDecision(action={"type": "pass_priority"}, reasoning="No profitable/legal block assignment; pass")
        if move.get("type") == "attack" and not (move.get("attackers") or []):
            return AIDecision(action={"type": "pass_priority"}, reasoning="No favorable attacks; pass priority")

        return AIDecision(action=move, reasoning=f"{self.archetype} plan selected best-scoring move")

    def _choose_forced_land_play(self, state: MatchState, legal_moves: list[dict], player_id: int) -> dict | None:
        step = _step_key(getattr(state, "step", ""))
        own_main = step in {"precombat_main", "postcombat_main"} and getattr(state, "active_player", player_id) == player_id
        if not own_main:
            return None
        if getattr(state, "stack", []) or []:
            return None
        player = state.players[player_id]
        if getattr(player, "lands_played_this_turn", 0) >= 1:
            return None
        land_moves = [m for m in legal_moves if m.get("type") == "play_land"]
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
        for c in hand:
            if _card_looks_like_land(c):
                continue
            cost = parse_mana_cost(c.mana_cost)
            cmc = cost["generic"] + sum(cost[x] for x in ["W", "U", "B", "R", "G"])
            if cmc <= 2:
                early_spells += 1
        mulligans = state.mulligan_count.get(player_id, 0)
        min_lands, max_lands = self._preferred_land_window()
        too_land_light = lands < min_lands
        too_land_heavy = lands > max_lands
        quality = (1.0 - min(abs(lands - 3), 3) / 3) * 0.7 + min(early_spells / 2, 1.0) * 0.3
        if mulligans < 2 and (too_land_light or too_land_heavy):
            return AIDecision(
                action={"type": "mulligan"},
                reasoning=f"Opening hand outside {min_lands}-{max_lands} land window for {self.archetype}",
            )
        if mulligans < 2 and quality < 0.45:
            return AIDecision(action={"type": "mulligan"}, reasoning="Opening hand quality too low")
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
                        base += 8 if self.archetype in {"Control", "Counter-heavy", "Tempo"} else 4
                    else:
                        base -= 2
            elif mtype == "play_land":
                base += 5
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
        archetype_bias = 5 if self.archetype in {"Aggro", "Burn", "Tempo", "Tokens", "Tribal"} else 2
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
        if has_instant_like and self.archetype in {"Control", "Counter-heavy", "Tempo"}:
            return 1.8
        return 0.3

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
        return profitable + lethal_pressure + arche_bonus

    def _cast_bias(self, state: MatchState, move: dict, player_id: int) -> float:
        cid = move.get("card_id")
        card = state.cards.get(cid) if cid else None
        if not card:
            return 0.0
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
            if "counter" in tags:
                bonus += 5.5 if getattr(state, "stack", []) else -2.5
            if "draw" in tags:
                bonus += 2.2
                if "Instant" in card.types:
                    on_opp_turn = getattr(state, "active_player", player_id) != player_id
                    in_end = _step_key(getattr(state, "step", "")) == "end_step"
                    if on_opp_turn or in_end:
                        bonus += 2.4
            if "removal" in tags:
                bonus += 2.0
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
            return bonus

        if arche in {"Aggro", "Tribal", "Tokens", "Tempo"} and my_creatures == 0 and early_turn and in_main:
            return -1.8
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
            # Prefer top-of-stack by default.
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
                key=lambda t: (state.cards.get(t["id"]).power or 0, state.cards.get(t["id"]).toughness or 0),
                default=None,
            )
            if best:
                targets["target_card_id"] = best["id"]

        planeswalker_targets = hints.get("planeswalker_targets") or []
        if planeswalker_targets and not targets.get("target_card_id") and not (targets.get("target_card_ids") or []):
            targets["target_card_id"] = planeswalker_targets[0]["id"]

        if hints.get("supports_divide") and not targets.get("target_distribution"):
            if creature_targets:
                targets["target_distribution"] = {creature_targets[0]["id"]: 1}
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
                if blk_tgh <= atk_pow and blk_pow < atk_tgh:
                    # Pure chump trades are less desirable unless needed.
                    score -= 1.4
                score += min(atk_pow, 5) * 0.25
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

        opp_life = state.players[opp_id].life
        chosen: list[str] = []
        for cid in candidates:
            card = state.cards.get(cid)
            if not card:
                continue
            atk_pow = card.power or 0
            atk_tgh = card.toughness or 0
            if atk_pow <= 0:
                continue

            dies_to_some = any((state.cards[b].power or 0) >= atk_tgh for b in opp_blockers)
            kills_some = any((state.cards[b].toughness or 0) <= atk_pow for b in opp_blockers)
            # Avoid obvious bad attacks with small bodies into larger blockers.
            if atk_pow <= 1 and dies_to_some and not kills_some and opp_life > 1:
                continue
            # General anti-suicide rule unless aggression/lethal pressure justifies it.
            if dies_to_some and not kills_some and self.archetype not in {"Aggro", "Burn", "Tempo"} and opp_life > atk_pow + 2:
                continue

            chosen.append(cid)

        # If nothing qualifies but we have lethal on board, send all.
        if not chosen:
            total_power = sum((state.cards[c].power or 0) for c in candidates if c in state.cards)
            if total_power >= opp_life:
                return list(candidates)
        return chosen

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
                    base += 3
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
