from __future__ import annotations
from rules_engine.type_effects import effective_types

from itertools import permutations

from game_state.state import MatchState, Step, Zone, pregame_actor
from rules_engine.ability_model import build_ability_spec
from rules_engine.activation_modifiers import activation_cost_view, payable_crew_group
from rules_engine.cast_choice import build_cast_hints, has_available_targets_for_action, available_cast_options_and_hints
from rules_engine.card_types import is_land_card as _is_land_card
from rules_engine.continuous import effective_power, has_keyword, printed_abilities_suppressed
from rules_engine.costs import activated_cost_available, check_cost_option_available, collect_cost_options, parse_activated_cost, restricted_x_color
from rules_engine.cycling import cycling_cost, cycling_is_variable, cycling_variant
from rules_engine.entry import land_entry_options
from rules_engine.land_rules import compute_max_land_plays_this_turn
from rules_engine.mana import can_pay_with_pool_and_lands, hybrid_payment_symbols
from rules_engine.oracle_effects import extract_activated_abilities, extract_loyalty_abilities
from rules_engine.library_permissions import top_library_creature_for_type
from rules_engine.restrictions import card_cant_attack, can_activate_in_current_timing, can_cast_in_current_timing, split_second_active
from rules_engine.zone_actions import is_departed_token


def _land_moves(state: MatchState, player_id: int, card, move: dict) -> list[dict]:
    options = land_entry_options(state, player_id, card)
    return [{**move, "entry_choice": choice} for choice in options] if options else [move]


def _cost_option_view(option, state=None, player_id=None, card_id=None) -> dict:
    view = {
        "id": option.id,
        "label": option.label,
        "mana_cost": option.mana_cost,
        "hybrid_symbols": hybrid_payment_symbols(option.mana_cost),
        "pay_life": option.pay_life,
        "pay_life_x": option.pay_life_x,
        "discard_cards": option.discard_cards,
        "discard_x": option.discard_x,
        "discard_all": option.discard_all,
        "sacrifice_all": option.sacrifice_all,
        "sacrifice_creatures": option.sacrifice_creatures,
        "sacrifice_kind": option.sacrifice_kind,
        "exile_graveyard": option.exile_graveyard,
        "additional_cost_group": option.additional_cost_group,
        "kicked": option.kicked,
        "kicker_base_id": option.kicker_base_id,
    }
    if state is not None and (option.discard_cards or option.sacrifice_creatures or option.discard_x or option.discard_all or option.sacrifice_all):
        from rules_engine.costs import additional_cost_candidates
        view.update(additional_cost_candidates(state, player_id, card_id, option))
    if state is not None:
        from rules_engine.kicker import kicker_surfaces, spell_kicker_view
        card = state.cards[card_id]
        if kicker_surfaces(card.oracle_text):
            view['target_hints'] = build_cast_hints(state, spell_kicker_view(card, option.kicked), player_id)
    return view


def legal_moves(state: MatchState, player_id: int) -> list[dict]:
    if state.winner is not None:
        return []
    if state.pending_mechanic_choice:
        pending = state.pending_mechanic_choice
        if pending['kind'] == 'effect_cast':
            from rules_engine.effect_casts import cast_moves
            return cast_moves(state, player_id)
        labels = {cid: state.cards[cid].name if cid in state.cards else (pending.get("option_labels") or {}).get(cid, "Draw normally") for cid in pending.get("options", [])}
        type_lines = {cid: state.cards[cid].type_line or " ".join(effective_types(state, state.cards[cid]))
                      for cid in pending.get("options", []) if cid in state.cards}
        if pending["kind"] == "each_player_discard":
            return [{"type": "choose_mechanic", "kind": pending["kind"], "player_id": player_id,
                     "options": list(pending["options"]), "count": pending["count"],
                     "label": pending["label"], "option_labels": labels,
                     "option_type_lines": type_lines}] if pending["player_id"] == player_id else []
        return [{"type": "choose_mechanic", **pending, "option_labels": labels,
                 "option_type_lines": type_lines}] if pending["player_id"] == player_id else []
    pending_order = getattr(state, "pending_trigger_order", None)
    if pending_order:
        if int(pending_order.get("current_controller", -1)) != player_id:
            return []
        if pending_order.get("phase") == "optional":
            return [
                {"type": "choose_optional_effect", "stack_id": pending_order["current_stack_id"], "accept": accept}
                for accept in (True, False)
            ]
        if pending_order.get("phase") == "targets":
            from rules_engine.events import trigger_target_options
            item = next((item for item in state.stack if item.id == pending_order.get("current_stack_id")), None)
            return [
                {"type": "choose_trigger_target", "stack_id": item.id, **option}
                for option in trigger_target_options(state, item)
            ] if item else []
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
        if player_id != pregame_actor(state):
            return []
        moves = [{"type": "keep_hand"}]
        if state.mulligan_count.get(player_id, 0) < 7:
            moves.append({"type": "mulligan", "current_mulligans": state.mulligan_count.get(player_id, 0)})
        return moves
    if state.step == Step.UNTAP:
        return []
    moves: list[dict] = [{"type": "pass_priority"}]
    if state.step == Step.CLEANUP and (state.cleanup_pending or not state.cleanup_repeat_required):
        return moves
    player = state.players[player_id]

    if state.priority_player != player_id:
        return moves
    from rules_engine.mana_abilities import mana_ability_views
    for cid in player.battlefield:
        for ability in mana_ability_views(state, state.cards[cid]):
            moves.append({'type': 'activate_mana_ability', 'card_id': cid,
                          'card_name': state.cards[cid].name, **ability})
    from rules_engine.keyword_actions import ninjutsu_moves
    from rules_engine.foretell import action_options as foretell_options
    for cid in player.hand:
        card = state.cards[cid]
        options = foretell_options(state, player_id, card)
        if options:
            moves.append({'type': 'foretell', 'card_id': cid, 'card_name': card.name, **options})
    if not split_second_active(state):
        moves.extend(ninjutsu_moves(state, player_id))

    if state.step == Step.DECLARE_ATTACKERS and state.active_player == player_id and not getattr(state, "attackers_declared", False):
        restricted_attackers: list[dict] = []
        attackers = [
            cid
            for cid in player.battlefield
            if "Creature" in effective_types(state, state.cards[cid])
            and not state.cards[cid].tapped
            and (not state.cards[cid].summoning_sick or has_keyword(state, cid, "haste"))
            and not has_keyword(state, cid, "defender")
            and not card_cant_attack(state, cid)
        ]
        for cid in player.battlefield:
            c = state.cards[cid]
            if "Creature" not in effective_types(state, c):
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
                if "Planeswalker" in effective_types(state, state.cards[cid]) and state.cards[cid].zone == Zone.BATTLEFIELD
            )
            from rules_engine.declaration_limits import declaration_limit_view
            from rules_engine.combat_payments import attack_tax_sources, attack_payment_view
            moves.append({"type": "attack", "options": attackers, "defenders": defenders,
                          'attack_taxes': attack_tax_sources(state),
                          'attack_costs': {cid: {target['id']: attack_payment_view(state, [cid], {cid: target['id']})
                                                for target in defenders} for cid in attackers},
                          'declaration_limits': declaration_limit_view(state, 'attack')})
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
            if "Creature" in effective_types(state, state.cards[cid]) and not state.cards[cid].tapped
        ]
        attacker_opts = [{"id": cid, "name": state.cards[cid].name} for cid in state.attackers]
        blocker_opts = [{"id": cid, "name": state.cards[cid].name} for cid in blockers]
        from rules_engine.declaration_limits import declaration_limit_view
        from rules_engine.combat_requirements import target_block_requirements
        from rules_engine.combat_payments import block_payment_view, block_tax_sources
        moves.append({"type": "block", "attackers": attacker_opts, "blockers": blocker_opts,
                      'target_requirements': target_block_requirements(state),
                      'block_taxes': block_tax_sources(state),
                      'block_costs': {bid: block_payment_view(state, [bid]) for bid in blockers},
                      'declaration_limits': declaration_limit_view(state, 'block')})

    for cid in list(player.hand) + list(player.graveyard):
        card = state.cards[cid]
        if is_departed_token(card):
            continue
        cycle_cost = cycling_cost(card.oracle_text, allow_variable=True)
        if cycle_cost and cid in player.hand and not split_second_active(state):
            x_values = range(0, 21) if cycling_is_variable(cycle_cost) else range(1)
            for x_value in x_values:
                if not can_pay_with_pool_and_lands(
                    state, player_id, cycle_cost, card_name=card.name, x_value=x_value,
                    payment_kind="activation", payment_types=set(effective_types(state, card)),
                    source_card_id=cid, ability_kind='cycling',
                ):
                    continue
                cycle_move = {
                    "type": "cycle_card",
                    "card_id": cid,
                    "card_name": card.name,
                    "mana_cost": cycle_cost,
                    'activation_costs': activation_cost_view(state, player_id, cid, cycle_cost, ability_kind='cycling', x_value=x_value),
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
            and cid in player.hand
            and used_land_plays < max_land_plays
            and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}
            and state.active_player == player_id
            and not state.stack
        ):
            moves.extend(_land_moves(state, player_id, card, {"type": "play_land", "card_id": cid}))
        elif (
            card.zone in {Zone.HAND, Zone.GRAVEYARD}
            and not _is_land_card(card)
            and card.layout != "split"
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
            available_options, hints = available_cast_options_and_hints(state, card, player_id)
            if not available_options:
                continue
            if not has_available_targets_for_action(hints):
                continue
            moves.append(
                {
                    "type": "cast_spell",
                    "card_id": cid,
                    "card_name": card.name,
                    "from_graveyard": card.zone == Zone.GRAVEYARD,
                    "mana_cost": card.mana_cost,
                    "cost_options": [_cost_option_view(o, state, player_id, cid) for o in available_options],
                    "target_hints": hints,
                }
            )

    # Cards granted temporary play permission by effects such as Light Up the
    # Stage remain in exile but are legal sources for the same actions.
    from rules_engine.card_faces import exile_candidates, exile_permission
    for cid in exile_candidates(state, player_id):
        if not exile_permission(state, player_id, cid):
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
            and not state.stack
        ):
            moves.extend(_land_moves(state, player_id, card, {"type": "play_land", "card_id": cid, "from_exile": True}))
        elif not _is_land_card(card) and card.layout != "split" and _can_cast_spell(state, card, player_id):
            timing_ok, timing_reason = can_cast_in_current_timing(state, card, player_id)
            if not timing_ok:
                continue
            available_options, hints = available_cast_options_and_hints(state, card, player_id)
            if not available_options:
                continue
            if not has_available_targets_for_action(hints):
                continue
            moves.append(
                {
                    "type": "cast_spell",
                    "card_id": cid,
                    "card_name": card.name,
                    "mana_cost": card.mana_cost,
                    "from_exile": True,
                    "cost_options": [_cost_option_view(o, state, player_id, cid) for o in available_options],
                    "target_hints": hints,
                }
            )

    # Realmwalker-style permissions allow only the revealed top creature of
    # the chosen type to be cast from the library. It is not a normal hand or
    # land-play permission and therefore gets its own explicit source flag.
    top_card = top_library_creature_for_type(state, player_id)
    if top_card is not None and _can_cast_spell(state, top_card, player_id):
        timing_ok, _ = can_cast_in_current_timing(state, top_card, player_id)
        available_options, hints = available_cast_options_and_hints(state, top_card, player_id)
        if timing_ok and available_options and has_available_targets_for_action(hints):
            moves.append(
                {
                    "type": "cast_spell",
                    "card_id": top_card.id,
                    "card_name": top_card.name,
                    "mana_cost": top_card.mana_cost,
                    "from_library": True,
                    "cost_options": [_cost_option_view(o, state, player_id, top_card.id) for o in available_options],
                    "target_hints": hints,
                }
            )

    # Planeswalker loyalty abilities: sorcery speed, once per planeswalker each turn.
    if state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack:
        for cid in player.battlefield:
            card = state.cards[cid]
            if "Planeswalker" not in effective_types(state, card):
                continue
            if printed_abilities_suppressed(state, cid):
                continue
            if cid in state.loyalty_activated_this_turn:
                continue
            if not activated_cost_available(state, player_id, cid, '', ability_kind='loyalty'):
                continue
            abilities = extract_loyalty_abilities(card)
            for idx, ability in enumerate(abilities):
                if ability.get("x_cost"):
                    next_loyalty = card.loyalty or 0
                else:
                    next_loyalty = (card.loyalty or 0) + int(ability["delta"])
                if next_loyalty < 0:
                    continue
                from rules_engine.counter_placement import counter_placement_forbidden
                if next_loyalty > (card.loyalty or 0) and counter_placement_forbidden(state, 'loyalty', target_card_id=cid):
                    continue
                hints_card = type("LoyaltyOracleProxy", (), {"id": cid, "oracle_text": ability["text"], "mana_cost": "", "name": card.name})()
                hints = build_cast_hints(state, hints_card, player_id)
                if not has_available_targets_for_action(hints):
                    continue
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
                        'activation_costs': activation_cost_view(state, player_id, cid, '', ability_kind='loyalty'),
                        "ability_x_cost": bool(ability.get("x_cost")),
                        "ability_x_sign": int(ability.get("x_sign", 0) or 0),
                        "target_hints": hints,
                    }
                )

    # Source-bound discard abilities activate from hand; other supported forms from battlefield.
    from rules_engine.oracle_effects import activation_source_eligible
    for cid in [*player.battlefield, *player.hand]:
        card = state.cards[cid]
        if printed_abilities_suppressed(state, cid):
            continue
        for ability in extract_activated_abilities(card):
            if not activation_source_eligible(state, player_id, cid, ability):
                continue
            if not can_activate_in_current_timing(state, ability["text"], player_id):
                continue
            cost = ability["mana_cost"]
            parsed_cost = parse_activated_cost(cost)
            if (not parsed_cost.supported or not activated_cost_available(
                    state, player_id, cid, cost, restricted_x_color=restricted_x_color(ability["text"]), ability_index=ability['index'])):
                continue
            proxy = type("ActivatedOracleProxy", (), {"id": cid, "oracle_text": ability["text"], "mana_cost": "", "name": card.name})()
            if build_ability_spec(state, proxy, player_id, report_unsupported=False).effect.key == "noop":
                continue
            hints = build_cast_hints(state, proxy, player_id)
            if not has_available_targets_for_action(hints):
                continue
            if "{X}" in parsed_cost.mana_cost:
                hints["requires_x_value"] = True
            moves.append(
                {
                    "type": "activate_ability",
                    "card_id": cid,
                    "card_name": card.name,
                    "ability_index": ability["index"],
                    "ability_label": ability["label"],
                    "mana_cost": cost,
                    'activation_costs': activation_cost_view(state, player_id, cid, parsed_cost.mana_cost, ability_index=ability['index']),
                    "hybrid_symbols": hybrid_payment_symbols(parsed_cost.mana_cost),
                    "target_hints": hints,
                }
            )
    # Equipment equip abilities (sorcery speed only).
    if state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack:
        own_creatures = [cid for cid in player.battlefield if "Creature" in effective_types(state, state.cards[cid])]
        for cid in player.battlefield:
            card = state.cards[cid]
            if "Artifact" not in effective_types(state, card):
                continue
            if printed_abilities_suppressed(state, cid):
                continue
            equip_cost = _extract_equip_cost(card.oracle_text or "")
            if not equip_cost:
                continue
            from rules_engine.attachments import attachment_target_is_legal, is_equipment
            from rules_engine.targeting import validate_hexproof_shroud_targets
            if not is_equipment(card):
                continue
            targets = [target for target in own_creatures if attachment_target_is_legal(state, card, target)
                       and validate_hexproof_shroud_targets(state, player_id, {"target_card_id": target}, card)[0]
                       and can_pay_with_pool_and_lands(state, player_id, equip_cost,
                           payment_kind="activation", payment_types=set(effective_types(state, card)), ability_kind="equip",
                           source_card_id=cid, target_card_id=target)]
            if targets:
                moves.append(
                    {
                        "type": "equip",
                        "card_id": cid,
                        "card_name": card.name,
                        "mana_cost": equip_cost,
                        "targets": [{"id": c, "name": state.cards[c].name} for c in targets],
                    }
                )

    # Crew costs are paid now; the animation ability resolves on the stack.
    from rules_engine.oracle_effects import crew_value
    for vehicle_id in player.battlefield:
        vehicle = state.cards[vehicle_id]
        if printed_abilities_suppressed(state, vehicle_id) or split_second_active(state):
            continue
        crew = crew_value(vehicle)
        if crew is None or "Artifact" not in effective_types(state, vehicle):
            continue
        candidates = [
            cid
            for cid in player.battlefield
            if cid != vehicle_id
            and "Creature" in effective_types(state, state.cards[cid])
            and not state.cards[cid].tapped
        ]
        if sum(max(0, effective_power(state, cid)) for cid in candidates) >= crew:
            suggested = payable_crew_group(state, player_id, vehicle_id, crew, candidates)
            if suggested is None:
                continue
            moves.append(
                {
                    "type": "crew",
                    "card_id": vehicle_id,
                    "card_name": vehicle.name,
                    "crew_value": crew,
                    'suggested_crew_card_ids': suggested,
                    'activation_costs': activation_cost_view(state, player_id, vehicle_id, '', ability_kind='crew'),
                    "crew_candidates": [
                        {"id": cid, "name": state.cards[cid].name, "power": effective_power(state, cid)}
                        for cid in candidates
                    ],
                }
            )

    # Face choices have independent timing, costs and target surfaces.
    from rules_engine.card_faces import select_cast_face
    for cid in list(player.hand) + list(player.graveyard) + exile_candidates(state, player_id):
        original = state.cards[cid]
        if is_departed_token(original):
            continue
        if original.layout not in {"modal_dfc", "adventure", "split"}:
            continue
        for index in range(0 if original.layout == "split" else 1, len(original.card_faces)):
            if original.zone == Zone.EXILE and not exile_permission(state, player_id, cid, index):
                continue
            face = select_cast_face(original, index)
            if "Land" in effective_types(state, face):
                if original.layout == "modal_dfc" and original.zone in {Zone.HAND, Zone.EXILE} and state.active_player == player_id and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and not state.stack:
                    used = max(player.lands_played_this_turn, player.land_plays_recorded_on_turn) if player.last_land_play_turn == state.turn else 0
                    if used < compute_max_land_plays_this_turn(state, player_id):
                        moves.extend(_land_moves(state, player_id, face, {"type": "play_land", "card_id": cid, "card_name": face.name,
                                      "selected_face_index": index, "from_exile": original.zone == Zone.EXILE}))
                continue
            if not can_cast_in_current_timing(state, face, player_id)[0]:
                continue
            options, hints = available_cast_options_and_hints(state, face, player_id)
            if not options or not has_available_targets_for_action(hints):
                continue
            moves.append({"type": "cast_spell", "card_id": cid, "card_name": face.name,
                          "selected_face_index": index, "mana_cost": face.mana_cost,
                          "from_exile": original.zone == Zone.EXILE,
                          "from_graveyard": original.zone == Zone.GRAVEYARD,
                          "cost_options": [vars(option) for option in options], "target_hints": hints})
    from rules_engine.bestow import bestow_cost, bestow_cast_view
    for cid in list(player.hand) + exile_candidates(state, player_id):
        original = state.cards[cid]
        if is_departed_token(original):
            continue
        indices = range(len(original.card_faces)) if original.layout in {'modal_dfc', 'adventure', 'split'} else [0]
        for index in indices:
            if original.zone == Zone.EXILE and not exile_permission(state, player_id, cid, index):
                continue
            face = select_cast_face(original, index)
            if not bestow_cost(face):
                continue
            view = bestow_cast_view(face)
            if not can_cast_in_current_timing(state, view, player_id)[0]:
                continue
            options, hints = available_cast_options_and_hints(state, view, player_id)
            if options and has_available_targets_for_action(hints):
                moves.append({'type': 'cast_spell', 'card_id': cid, 'card_name': view.name,
                    'cast_variant': 'bestow', 'mana_cost': view.mana_cost,
                    'from_exile': original.zone == Zone.EXILE,
                    **({'selected_face_index': index} if original.card_faces else {}),
                    'cost_options': [_cost_option_view(option, state, player_id, cid) for option in options], 'target_hints': hints})
    return moves


def _can_cast_spell(state: MatchState, card, player_id: int) -> bool:
    if state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN} and state.active_player == player_id and not state.stack:
        return True
    if "Instant" in effective_types(state, card):
        return True
    if has_keyword(state, card.id, "flash"):
        return True
    return False


def _extract_equip_cost(oracle_text: str) -> str:
    text = oracle_text or ""
    import re
    m = re.search(r"Equip\s+(\{[^}]+\}(?:\{[^}]+\})*)", text, flags=re.IGNORECASE)
    if not m:
        return ""
    return m.group(1).upper()
