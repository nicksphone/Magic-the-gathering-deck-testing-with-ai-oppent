from __future__ import annotations

from game_state.state import MatchState, Step, Zone
from rules_engine.cast_choice import build_cast_hints
from rules_engine.continuous import has_keyword
from rules_engine.costs import check_cost_option_available, collect_cost_options
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.oracle_effects import extract_loyalty_abilities
from rules_engine.restrictions import card_cant_attack, can_cast_in_current_timing


def legal_moves(state: MatchState, player_id: int) -> list[dict]:
    if state.winner is not None:
        return []
    if state.pregame_pending:
        if player_id in state.kept_hands:
            return []
        return [
            {"type": "keep_hand"},
            {"type": "mulligan", "current_mulligans": state.mulligan_count.get(player_id, 0)},
        ]
    moves: list[dict] = [{"type": "pass_priority"}]
    player = state.players[player_id]

    if state.priority_player != player_id:
        return moves

    if state.step == Step.DECLARE_ATTACKERS and state.active_player == player_id and not getattr(state, "attackers_declared", False):
        attackers = [
            cid
            for cid in player.battlefield
            if "Creature" in state.cards[cid].types
            and not state.cards[cid].tapped
            and (not state.cards[cid].summoning_sick or has_keyword(state, cid, "haste"))
            and not has_keyword(state, cid, "defender")
            and not card_cant_attack(state, cid)
        ]
        if attackers:
            defender_id = 1 if state.active_player == 2 else 2
            defenders = [{"id": f"player:{defender_id}", "label": state.players[defender_id].name, "kind": "player"}]
            defenders.extend(
                {
                    "id": f"planeswalker:{cid}",
                    "label": state.cards[cid].name,
                    "kind": "planeswalker",
                }
                for cid in state.players[defender_id].battlefield
                if "Planeswalker" in state.cards[cid].types and state.cards[cid].zone == Zone.BATTLEFIELD
            )
            moves.append({"type": "attack", "options": attackers, "defenders": defenders})
    if state.step == Step.DECLARE_BLOCKERS and state.active_player != player_id and state.attackers:
        blockers = [
            cid
            for cid in player.battlefield
            if "Creature" in state.cards[cid].types and not state.cards[cid].tapped
        ]
        attacker_opts = [{"id": cid, "name": state.cards[cid].name} for cid in state.attackers]
        blocker_opts = [{"id": cid, "name": state.cards[cid].name} for cid in blockers]
        moves.append({"type": "block", "attackers": attacker_opts, "blockers": blocker_opts})

    for cid in list(player.hand):
        card = state.cards[cid]
        max_land_plays = compute_max_land_plays_this_turn(state, player_id)
        if getattr(player, "last_land_play_turn", 0) == state.turn:
            used_land_plays = max(
                int(getattr(player, "lands_played_this_turn", 0)),
                int(getattr(player, "land_plays_recorded_on_turn", 0)),
            )
        else:
            # Ignore stale counter drift from older turns; only this-turn land records matter.
            used_land_plays = 0
        if (
            _is_land_card(card)
            and used_land_plays < max_land_plays
            and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}
            and state.active_player == player_id
        ):
            moves.append({"type": "play_land", "card_id": cid})
        elif (
            card.zone == Zone.HAND
            and not _is_land_card(card)
            and _can_cast_spell(state, card, player_id)
        ):
            timing_ok, timing_reason = can_cast_in_current_timing(state, card, player_id)
            if not timing_ok:
                moves.append(
                    {
                        "type": "cast_spell_restricted",
                        "card_id": cid,
                        "card_name": card.name,
                        "reason": timing_reason,
                    }
                )
                continue
            options = collect_cost_options(state, player_id, card)
            available_options = [o for o in options if check_cost_option_available(state, player_id, card, o)]
            if not available_options:
                continue
            hints = build_cast_hints(state, card, player_id)
            oracle = (card.oracle_text or "").lower()
            if "target" in oracle and not _has_any_target_options(hints):
                continue
            moves.append(
                {
                    "type": "cast_spell",
                    "card_id": cid,
                    "card_name": card.name,
                    "mana_cost": card.mana_cost,
                    "cost_options": [
                        {
                            "id": o.id,
                            "label": o.label,
                            "mana_cost": o.mana_cost,
                            "pay_life": o.pay_life,
                            "discard_cards": o.discard_cards,
                            "sacrifice_creatures": o.sacrifice_creatures,
                        }
                        for o in available_options
                    ],
                    "target_hints": hints,
                }
            )

    # Planeswalker loyalty abilities: sorcery speed, once per planeswalker each turn.
    if state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack:
        for cid in player.battlefield:
            card = state.cards[cid]
            if "Planeswalker" not in card.types:
                continue
            if cid in state.loyalty_activated_this_turn:
                continue
            abilities = extract_loyalty_abilities(card)
            for idx, ability in enumerate(abilities):
                next_loyalty = (card.loyalty or 0) + int(ability["delta"])
                if next_loyalty < 0:
                    continue
                hints_card = type("LoyaltyOracleProxy", (), {"oracle_text": ability["text"], "mana_cost": "", "name": card.name})()
                hints = build_cast_hints(state, hints_card, player_id)
                if ability["delta"] < 0 and "x" in ability["text"].lower():
                    hints["requires_x_value"] = True
                moves.append(
                    {
                        "type": "activate_loyalty",
                        "card_id": cid,
                        "card_name": card.name,
                        "ability_index": idx,
                        "ability_label": ability["label"],
                        "ability_delta": ability["delta"],
                        "target_hints": hints,
                    }
                )

    return moves


def _can_cast_spell(state: MatchState, card, player_id: int) -> bool:
    if state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack:
        return True
    if "Instant" in card.types:
        return True
    if has_keyword(state, card.id, "flash"):
        return True
    return False


def _has_any_target_options(hints: dict) -> bool:
    return any(
        bool(hints.get(key))
        for key in ["player_targets", "creature_targets", "planeswalker_targets", "stack_targets"]
    )


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
