from __future__ import annotations

from itertools import permutations

from game_state.state import MatchState, Step, Zone
from rules_engine.cast_choice import build_cast_hints
from rules_engine.continuous import effective_power, has_keyword
from rules_engine.costs import activated_cost_available, check_cost_option_available, collect_cost_options, parse_activated_cost
from rules_engine.cycling import cycling_cost, cycling_is_variable, cycling_variant
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.oracle_effects import extract_activated_abilities, extract_loyalty_abilities
from rules_engine.library_permissions import top_library_creature_for_type
from rules_engine.restrictions import card_cant_attack, can_cast_in_current_timing


def legal_moves(state: MatchState, player_id: int) -> list[dict]:
    if state.winner is not None:
        return []
    pending_order = getattr(state, "pending_trigger_order", None)
    if pending_order:
        if int(pending_order.get("current_controller", -1)) != player_id:
            return []
        group = list((pending_order.get("groups") or {}).get(str(player_id), []))
        ids = [str(trigger.get("_choice_id")) for trigger in group]
        labels = {str(trigger.get("_choice_id")): str(trigger.get("label", "Triggered ability")) for trigger in group}
        orders = list(permutations(ids)) if len(ids) <= 6 else [tuple(ids)]
        return [
            {
                "type": "choose_trigger_order",
                "trigger_order": list(order),
                "trigger_labels": [labels.get(choice_id, choice_id) for choice_id in order],
                "event": pending_order.get("event"),
            }
            for order in orders
        ]
    pending = getattr(state, "pending_replacement_choice", None)
    if pending:
        if int(pending.get("player_id", -1)) != player_id:
            return []
        return [
            {
                "type": "choose_replacement",
                "event": pending.get("event"),
                "replacement_source_id": option.get("source_id"),
                "replacement_name": option.get("name"),
            }
            for option in (pending.get("options") or [])
        ]
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
        restricted_attackers: list[dict] = []
        attackers = [
            cid
            for cid in player.battlefield
            if "Creature" in state.cards[cid].types
            and not state.cards[cid].tapped
            and (not state.cards[cid].summoning_sick or has_keyword(state, cid, "haste"))
            and not has_keyword(state, cid, "defender")
            and not card_cant_attack(state, cid)
        ]
        for cid in player.battlefield:
            c = state.cards[cid]
            if "Creature" not in c.types:
                continue
            if c.tapped:
                restricted_attackers.append({"type": "attack_restricted", "card_id": cid, "card_name": c.name, "reason": "Tapped"})
            elif c.summoning_sick and not has_keyword(state, cid, "haste"):
                restricted_attackers.append({"type": "attack_restricted", "card_id": cid, "card_name": c.name, "reason": "Summoning sick"})
            elif has_keyword(state, cid, "defender"):
                restricted_attackers.append({"type": "attack_restricted", "card_id": cid, "card_name": c.name, "reason": "Defender can't attack"})
            elif card_cant_attack(state, cid):
                restricted_attackers.append({"type": "attack_restricted", "card_id": cid, "card_name": c.name, "reason": "Can't attack"})
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
        moves.extend(restricted_attackers)
    if (
        state.step == Step.DECLARE_BLOCKERS
        and state.active_player != player_id
        and state.attackers
        and not getattr(state, "blockers_declared", False)
    ):
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
        cycle_cost = cycling_cost(card.oracle_text, allow_variable=True)
        if cycle_cost:
            x_values = range(0, 21) if cycling_is_variable(cycle_cost) else range(1)
            for x_value in x_values:
                if not can_pay_with_pool_and_lands(
                    state, player_id, cycle_cost, card_name=card.name, x_value=x_value
                ):
                    continue
                cycle_move = {
                    "type": "cycle_card",
                    "card_id": cid,
                    "card_name": card.name,
                    "mana_cost": cycle_cost,
                }
                variant = cycling_variant(card.oracle_text)
                if variant:
                    cycle_move["cycling_variant"] = variant
                if cycling_is_variable(cycle_cost):
                    cycle_move["x_value"] = x_value
                moves.append(cycle_move)
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
                            "sacrifice_kind": o.sacrifice_kind,
                        }
                        for o in available_options
                    ],
                    "target_hints": hints,
                }
            )

    # Cards granted temporary play permission by effects such as Light Up the
    # Stage remain in exile but are legal sources for the same actions.
    for cid in list(player.exile):
        if int(player.exile_play_until.get(cid, 0) or 0) < int(state.turn):
            continue
        card = state.cards[cid]
        max_land_plays = compute_max_land_plays_this_turn(state, player_id)
        used_land_plays = max(
            int(getattr(player, "lands_played_this_turn", 0)),
            int(getattr(player, "land_plays_recorded_on_turn", 0)),
        ) if getattr(player, "last_land_play_turn", 0) == state.turn else 0
        if (
            _is_land_card(card)
            and used_land_plays < max_land_plays
            and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}
            and state.active_player == player_id
        ):
            moves.append({"type": "play_land", "card_id": cid, "from_exile": True})
        elif not _is_land_card(card) and _can_cast_spell(state, card, player_id):
            timing_ok, timing_reason = can_cast_in_current_timing(state, card, player_id)
            if not timing_ok:
                continue
            options = collect_cost_options(state, player_id, card)
            available_options = [o for o in options if check_cost_option_available(state, player_id, card, o)]
            if not available_options:
                continue
            hints = build_cast_hints(state, card, player_id)
            if "target" in (card.oracle_text or "").lower() and not _has_any_target_options(hints):
                continue
            moves.append(
                {
                    "type": "cast_spell",
                    "card_id": cid,
                    "card_name": card.name,
                    "mana_cost": card.mana_cost,
                    "from_exile": True,
                    "cost_options": [
                        {"id": o.id, "label": o.label, "mana_cost": o.mana_cost, "pay_life": o.pay_life,
                         "discard_cards": o.discard_cards, "sacrifice_creatures": o.sacrifice_creatures, "sacrifice_kind": o.sacrifice_kind}
                        for o in available_options
                    ],
                    "target_hints": hints,
                }
            )

    # Realmwalker-style permissions allow only the revealed top creature of
    # the chosen type to be cast from the library. It is not a normal hand or
    # land-play permission and therefore gets its own explicit source flag.
    top_card = top_library_creature_for_type(state, player_id)
    if top_card is not None and _can_cast_spell(state, top_card, player_id):
        timing_ok, _ = can_cast_in_current_timing(state, top_card, player_id)
        options = collect_cost_options(state, player_id, top_card)
        available_options = [o for o in options if check_cost_option_available(state, player_id, top_card, o)]
        if timing_ok and available_options:
            moves.append(
                {
                    "type": "cast_spell",
                    "card_id": top_card.id,
                    "card_name": top_card.name,
                    "mana_cost": top_card.mana_cost,
                    "from_library": True,
                    "cost_options": [
                        {
                            "id": o.id,
                            "label": o.label,
                            "mana_cost": o.mana_cost,
                            "pay_life": o.pay_life,
                            "discard_cards": o.discard_cards,
                            "sacrifice_creatures": o.sacrifice_creatures,
                            "sacrifice_kind": o.sacrifice_kind,
                        }
                        for o in available_options
                    ],
                    "target_hints": build_cast_hints(state, top_card, player_id),
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
                if ability.get("x_cost"):
                    next_loyalty = card.loyalty or 0
                else:
                    next_loyalty = (card.loyalty or 0) + int(ability["delta"])
                if next_loyalty < 0:
                    continue
                hints_card = type("LoyaltyOracleProxy", (), {"oracle_text": ability["text"], "mana_cost": "", "name": card.name})()
                hints = build_cast_hints(state, hints_card, player_id)
                if ability.get("x_cost"):
                    hints["requires_x_value"] = True
                moves.append(
                    {
                        "type": "activate_loyalty",
                        "card_id": cid,
                        "card_name": card.name,
                        "ability_index": idx,
                        "ability_label": ability["label"],
                        "ability_delta": ability["delta"],
                        "ability_x_cost": bool(ability.get("x_cost")),
                        "ability_x_sign": int(ability.get("x_sign", 0) or 0),
                        "target_hints": hints,
                    }
                )

    # Activated abilities expose common tap/mana/life/discard/sacrifice costs.
    for cid in player.battlefield:
        card = state.cards[cid]
        for ability in extract_activated_abilities(card):
            cost = ability["mana_cost"]
            parsed_cost = parse_activated_cost(cost)
            if not parsed_cost.supported or not activated_cost_available(state, player_id, cid, cost):
                continue
            proxy = type("ActivatedOracleProxy", (), {"oracle_text": ability["text"], "mana_cost": "", "name": card.name})()
            hints = build_cast_hints(state, proxy, player_id)
            moves.append(
                {
                    "type": "activate_ability",
                    "card_id": cid,
                    "card_name": card.name,
                    "ability_index": ability["index"],
                    "ability_label": ability["label"],
                    "mana_cost": cost,
                    "target_hints": hints,
                }
            )
    # Equipment equip abilities (sorcery speed only).
    if state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack:
        own_creatures = [cid for cid in player.battlefield if "Creature" in state.cards[cid].types]
        for cid in player.battlefield:
            card = state.cards[cid]
            if "Artifact" not in card.types:
                continue
            equip_cost = _extract_equip_cost(card.oracle_text or "")
            if not equip_cost:
                continue
            if not can_pay_with_pool_and_lands(state, player_id, equip_cost):
                continue
            if own_creatures:
                moves.append(
                    {
                        "type": "equip",
                        "card_id": cid,
                        "card_name": card.name,
                        "mana_cost": equip_cost,
                        "targets": [{"id": c, "name": state.cards[c].name} for c in own_creatures],
                    }
                )

    # Vehicle crew is a tap cost that turns the artifact into a creature until
    # end of turn. The creature selection is explicit so human and AI actions
    # use the same legality contract.
    from rules_engine.oracle_effects import crew_value
    for vehicle_id in player.battlefield:
        vehicle = state.cards[vehicle_id]
        crew = crew_value(vehicle)
        if crew is None or "Artifact" not in vehicle.types or "Creature" in vehicle.types:
            continue
        candidates = [
            cid
            for cid in player.battlefield
            if cid != vehicle_id
            and "Creature" in state.cards[cid].types
            and not state.cards[cid].tapped
        ]
        if candidates and sum(max(0, effective_power(state, cid)) for cid in candidates) >= crew:
            moves.append(
                {
                    "type": "crew",
                    "card_id": vehicle_id,
                    "card_name": vehicle.name,
                    "crew_value": crew,
                    "crew_candidates": [
                        {"id": cid, "name": state.cards[cid].name, "power": effective_power(state, cid)}
                        for cid in candidates
                    ],
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
        for key in [
            "player_targets", "creature_targets", "planeswalker_targets", "stack_targets",
            "graveyard_spell_targets", "graveyard_creature_targets", "graveyard_permanent_targets",
            "aura_targets",
        ]
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


def _extract_equip_cost(oracle_text: str) -> str:
    text = oracle_text or ""
    import re
    m = re.search(r"Equip\s+(\{[^}]+\}(?:\{[^}]+\})*)", text, flags=re.IGNORECASE)
    if not m:
        return ""
    return m.group(1).upper()
