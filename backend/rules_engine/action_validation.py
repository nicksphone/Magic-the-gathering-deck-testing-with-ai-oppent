"""Checked, copy-on-write actions for external callers, using engine legality."""
from rules_engine.type_effects import effective_types
from copy import deepcopy
import re

from game_state.state import Step, Zone


class ActionRejected(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ActionRejected(reason)


def unique_ids(ids: list[str], allowed, count: int | None = None) -> None:
    require(isinstance(ids, list) and all(isinstance(cid, str) for cid in ids), "Card IDs must be strings")
    require(len(ids) == len(set(ids)), "Card selections cannot contain duplicates")
    require(all(cid in allowed for cid in ids), "Selection contains an unavailable card")
    require(count is None or len(ids) == count, "Incorrect number of selected cards")


def require_declared_targets(card, hints: dict, targets: dict, controller: int, *, spell: bool = False) -> None:
    """External actions must declare choices, not rely on legacy auto-targets."""
    if 'linked_target_pairs' in hints:
        from rules_engine.linked_targets import validate_linked_choice
        valid, message = validate_linked_choice(hints, targets)
        require(valid, message)
        return
    if spell and not set(getattr(card, "types", [])).intersection({"Instant", "Sorcery"}):
        from rules_engine.costs import casting_method
        from rules_engine.attachments import is_aura
        if is_aura(card):
            require(bool(targets.get("target_card_id")), "Announce an Aura attachment target")
        # Permanent spells do not target using their later activated/triggered
        # ability text. Aura attachment targets are the supported exception.
        return
    modes = targets.get("mode_texts") or ([targets["mode_text"]] if targets.get("mode_text") else [])
    require(not hints.get("modes") or bool(modes), "Announce the selected mode")
    if targets.get("mode_targets") is not None:
        require(set(targets["mode_targets"]) == set(modes), "Announce targets for each selected mode")
        for mode in modes:
            require_declared_targets(card, {}, {"mode_text": mode, **targets["mode_targets"][mode]}, controller, spell=spell)
        return
    text = " ".join(modes).lower() if modes else card.oracle_text.lower()
    permanent = bool(targets.get("target_card_id") or targets.get("target_card_ids") or targets.get("target_distribution"))
    from rules_engine.targeting import single_player_permanent_alternative

    alternative = single_player_permanent_alternative(text)
    if alternative:
        player = targets.get("target_player") is not None
        require(player != permanent, "Announce exactly one player or permanent target")
        if player and "opponent" in alternative:
            require(targets["target_player"] != controller, "Target must be an opponent")
        return
    if "any target" in text:
        if text.count("target") == 1:
            selected = (
                int(targets.get("target_player") is not None)
                + int(bool(targets.get("target_card_id")))
                + len(targets.get("target_card_ids") or [])
                + len(targets.get("target_distribution") or {})
            )
            require(selected == 1, "Announce exactly one player or permanent target")
        else:
            require(permanent or targets.get("target_player") is not None, "Announce a target")
    if "target player" in text or "target opponent" in text:
        require(targets.get("target_player") is not None, "Announce a target player")
        require("target opponent" not in text or targets["target_player"] != controller, "Target must be an opponent")
    if re.search(r"\btarget (?:[\w-]+ ){0,4}(?:creature|permanent|land|artifact|enchantment|planeswalker)\b(?!\s+spell)", text) and not re.search(r"up to (?:\d+|one|two|three) target", text):
        require(permanent, "Announce a permanent target")
    if re.search(r"\btarget (?:(?:noncreature|creature|artifact|enchantment|planeswalker|instant|sorcery) )?spell\b", text) or "target activated ability" in text or "target triggered ability" in text:
        require(bool(targets.get("target_stack_id")), "Announce a stack target")


def checked_action(state, rules, player_id: int, action: dict):
    # Even legality helpers run on the copy: no rejected request changes the
    # authoritative state, RNG, logs, cost payments or pending continuations.
    candidate = deepcopy(state)
    validate_action(candidate, rules, player_id, action)
    if action['type'] == 'pass_priority' and not candidate.stack and not candidate.pregame_pending:
        from game_state.state import Step
        from rules_engine.combat_requirements import best_required_attack, attack_requirement_score, best_required_blocks, block_requirement_score
        if candidate.step == Step.DECLARE_ATTACKERS and not candidate.attackers_declared:
            optimum = best_required_attack(candidate)
            require(not optimum or attack_requirement_score(candidate, optimum[0]) == 0,
                    'Declare required attackers before passing')
        if candidate.step == Step.DECLARE_BLOCKERS and not candidate.blockers_declared:
            optimum = best_required_blocks(candidate)
            require(not optimum or block_requirement_score(candidate, optimum) == 0,
                    'Declare required blockers before passing')
    if action['type'] == 'attack':
        from rules_engine.restrictions import card_cant_attack_alone
        require(all(candidate.cards[cid].zone == Zone.BATTLEFIELD and candidate.cards[cid].controller == player_id
                    for cid in action['attackers']), 'An attacker must be controlled on the battlefield')
        require(len(action['attackers']) != 1 or not card_cant_attack_alone(candidate, action['attackers'][0]),
                'An attacker cannot attack alone')
        from rules_engine.declaration_limits import attackers_within_limits
        from rules_engine.combat_requirements import best_required_attack, attack_requirement_score
        require(attackers_within_limits(candidate, action['attackers'], action.get('attack_targets')), 'Attacker declaration exceeds a static combat limit')
        optimum = best_required_attack(candidate)
        require(optimum is None or attack_requirement_score(candidate, action['attackers']) >= attack_requirement_score(candidate, optimum[0]),
                'Declare attackers that satisfy the maximum possible requirements')
        from rules_engine.combat_payments import attack_payment_state, attack_payment_view
        symbols = attack_payment_view(candidate, action['attackers'], action.get('attack_targets'))['hybrid_symbols']
        choices = action.get('hybrid_choices')
        require(not symbols or choices is not None, 'Choose each hybrid attack payment branch explicitly')
        require(choices is None or len(choices) == len(symbols) and all(
            branch in symbol['choices'] for branch, symbol in zip(choices, symbols)), 'Invalid hybrid attack payment branch')
        require(attack_payment_state(candidate, action['attackers'], action.get('attack_targets'), choices) is not None,
                'Cannot pay the declared attack costs')
    elif action['type'] == 'block':
        from rules_engine.declaration_limits import blockers_within_limits
        from rules_engine.combat_requirements import best_required_blocks, block_requirement_score
        blocks = {aid: bids if isinstance(bids, list) else [bids] for aid, bids in action['blocks'].items()}
        from rules_engine.combat import _can_block_attacker, _minimum_blockers_required, _max_attackers_blockable_by_creature
        from rules_engine.restrictions import card_cant_block, card_cant_block_alone
        selected = {bid for bids in blocks.values() for bid in bids}
        for aid, bids in blocks.items():
            require(not bids or len(bids) >= _minimum_blockers_required(candidate, aid), 'Illegal block assignment')
            for bid in bids:
                card = candidate.cards[bid]
                require(card.zone == Zone.BATTLEFIELD and card.controller == player_id and not card.tapped
                        and 'Creature' in effective_types(state, card) and not card_cant_block(candidate, bid)
                        and _can_block_attacker(candidate, candidate.cards[aid], card), 'Illegal block assignment')
        require(len(selected) != 1 or not card_cant_block_alone(candidate, next(iter(selected))), 'Illegal block assignment')
        require(all(sum(bid in bids for bids in blocks.values()) <= _max_attackers_blockable_by_creature(candidate, candidate.cards[bid])
                    for bid in selected), 'Illegal block assignment')
        require(blockers_within_limits(candidate, blocks), 'Blocker declaration exceeds a static combat limit')
        optimum = best_required_blocks(candidate, volunteered=selected)
        require(optimum is None or block_requirement_score(candidate, blocks) >= block_requirement_score(candidate, optimum),
                'Declare blockers that satisfy the maximum possible requirements')
        from rules_engine.combat_payments import block_payment_view, block_payment_state
        symbols = block_payment_view(candidate, sorted(selected))['hybrid_symbols']
        choices = action.get('hybrid_choices')
        require(not symbols or choices is not None, 'Choose each hybrid block payment branch explicitly')
        require(choices is None or len(choices) == len(symbols) and all(
            branch in symbol['choices'] for branch, symbol in zip(choices, symbols)), 'Invalid hybrid block payment branch')
        require(block_payment_state(candidate, sorted(selected), choices) is not None, 'Cannot pay the declared block costs')
    rules.take_action(candidate, player_id, action, reject_invalid=True)
    if action["type"] == "attack":
        remaining = {cid for cid in action['attackers'] if candidate.cards[cid].zone == Zone.BATTLEFIELD
                     and candidate.cards[cid].controller == player_id and 'Creature' in effective_types(candidate, candidate.cards[cid])}
        require(remaining.issubset(candidate.attackers), "An attacker cannot attack in this declaration")
    if action["type"] == "block":
        for attacker, blockers in action["blocks"].items():
            remaining = {bid for bid in blockers if candidate.cards[bid].zone == Zone.BATTLEFIELD
                         and candidate.cards[bid].controller == player_id and 'Creature' in effective_types(candidate, candidate.cards[bid])}
            require(remaining.issubset(candidate.blocks.get(attacker, [])), "Illegal block assignment")
    return candidate


def validate_action(state, rules, player_id: int, action: dict) -> None:
    from rules_engine.costs import casting_method
    require(player_id in state.players, "Invalid player")
    require(state.winner is None, "Game is already over")
    kind = action["type"]
    pending = state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order
    if not state.pregame_pending and not pending:
        require(state.priority_player == player_id, "This player does not have priority")
    moves = rules.legal_moves(state, player_id)
    available = [move for move in moves if move["type"] == kind]
    if kind == 'cast_spell':
        from rules_engine.ability_model import unsupported_spell_reason
        source = state.cards.get(action.get('card_id'))
        if source is not None and source.owner == player_id and source.zone != Zone.LIBRARY:
            reason = unsupported_spell_reason(source, {**action.get('targets', {}), **{
                key: action[key] for key in ('selected_face_index',) if key in action}})
            require(reason is None, reason or '')
        bestowed = casting_method((action.get('cost_choice') or {}).get('id', '')) == 'bestow'
        available = [move for move in available if (move.get('cast_variant') == 'bestow') == bestowed]
    if kind in {"tap_land_for_mana", "tap_lands_bulk", "tap_nonland_for_mana", 'activate_mana_ability'}:
        require(not state.pregame_pending and not pending, "Mana actions cannot interrupt a pending choice")
        require(state.step != Step.CLEANUP or state.cleanup_repeat_required, "No mana actions during ordinary cleanup")
        if kind == 'activate_mana_ability':
            from rules_engine.mana_abilities import mana_ability_views
            from rules_engine.costs import parse_activated_cost, activated_cost_selection, activated_cost_available
            from rules_engine.mana import hybrid_payment_symbols
            card = state.cards.get(action.get('card_id'))
            require(card is not None and card.id in state.players[player_id].battlefield and card.controller == player_id,
                    'Mana source must be a permanent you control')
            bundle = action.get('output_bundle')
            matching = [view for view in mana_ability_views(state, card)
                        if view['ability_index'] == action.get('ability_index')
                        and (action.get('color') in view['outputs'] if bundle is None else
                             any(option['color'] == action.get('color') and option['output_bundle'] == bundle
                                 for option in view.get('output_options', [])))]
            require(bool(matching),
                    'Mana ability, color or activation payment is not legal')
            options = [option for option in matching[0].get('output_options', [])
                       if option['color'] == action['color']]
            require(len(options) <= 1 or bundle is not None, 'Choose the complete mana output vector explicitly')
            cost_text = matching[0]['cost_text']
            cost = parse_activated_cost(cost_text)
            require('{X}' not in cost.mana_cost.upper(), 'Variable mana production is not supported by this contract')
            payments = action.get('payment_choices') or {}
            require(not cost.discard_cards or payments.get('discard_card_ids') is not None,
                    'Choose each discarded payment card explicitly')
            require(not cost.sacrifice_creatures or cost.sacrifice_source
                    or payments.get('sacrifice_card_ids') is not None,
                    'Choose each sacrificed payment card explicitly')
            require(activated_cost_selection(state, player_id, card.id, cost, action.get('payment_choices')) is not None,
                    'Invalid selected mana ability resources')
            symbols = hybrid_payment_symbols(cost.mana_cost)
            branches = action.get('hybrid_choices')
            require(not symbols or branches is not None, 'Choose each hybrid mana payment branch explicitly')
            require(branches is None or len(branches) == len(symbols) and all(
                branch in symbol['choices'] for branch, symbol in zip(branches, symbols)),
                'Invalid hybrid mana ability payment branch')
            require(activated_cost_available(state, player_id, card.id, cost_text,
                    hybrid_choices=branches, payment_choices=action.get('payment_choices'),
                    ability_kind='mana', ability_index=action['ability_index']),
                    'Selected mana ability payment is not affordable')
        else:
            validate_tap(state, player_id, action)
            if kind == 'tap_nonland_for_mana':
                from rules_engine.mana_abilities import mana_ability_views
                from rules_engine.costs import parse_activated_cost
                from rules_engine.mana import hybrid_payment_symbols
                matching = [view for view in mana_ability_views(state, state.cards[action['card_id']])
                            if action['color'] in view['outputs'] and (
                                view['outputs'][action['color']] > 0 or
                                sum(view.get('output_bundles', {}).get(action['color'], {}).values()) > 0)]
                require(len(matching) <= 1, 'Choose the mana ability index explicitly; use activate_mana_ability')
                for view in matching:
                    cost = parse_activated_cost(view['cost_text'])
                    require(not cost.discard_cards and not (cost.sacrifice_creatures and not cost.sacrifice_source)
                            and not hybrid_payment_symbols(cost.mana_cost) and '{X}' not in cost.mana_cost.upper(),
                            'Legacy mana action cannot choose payments; use activate_mana_ability')
                    require(all(len(bundle) <= 1 for bundle in view.get('base_output_bundles', [])),
                            'Announce the complete mixed mana vector; use activate_mana_ability')
        return
    # Declaring no attackers is legal even when the move generator has none.
    if kind == "attack" and not action["attackers"]:
        require(state.step == Step.DECLARE_ATTACKERS and state.active_player == player_id and not state.attackers_declared, "Not an attacker declaration window")
        require(not action.get("attack_targets"), "Attack targets require selected attackers")
        require(not action.get("bands"), "Bands require selected attackers")
        return
    require(bool(available), "Action is not currently legal")
    for key in ("card_id", "ability_index", "return_card_id", "replacement_source_id", "stack_id", "target_card_id"):
        if kind == "equip" and key == "target_card_id":
            continue  # Equipment targets are choices inside move["targets"], checked below.
        if key in action:
            available = [move for move in available if move.get(key) == action[key]]
    require(bool(available), "Action references an unavailable card, ability or choice")
    move = available[0]
    player = state.players[player_id]
    targets = action.get("targets", {})
    if targets.get("target_stack_id"):
        require(any(item.id == targets["target_stack_id"] for item in state.stack), "Target stack item is unavailable")
    for key in ("target_card_ids", "target_card_id"):
        ids = targets.get(key) or []
        ids = [ids] if isinstance(ids, str) else ids
        require(all(cid in state.cards for cid in ids), "Target card is unavailable")
    for choice in (targets.get("mode_targets") or {}).values():
        require(not choice.get("target_card_id") or choice["target_card_id"] in state.cards, "Mode target card is unavailable")
        require(not choice.get("target_stack_id") or any(item.id == choice["target_stack_id"] for item in state.stack), "Mode stack target is unavailable")
    require(all(cid in state.cards or cid in {"1", "2"} for cid in targets.get("target_distribution", {})), "Distribution target is unavailable")
    if kind in {"play_land", "cast_spell"}:
        for flag in ("from_exile", "from_library", "from_graveyard"):
            require(bool(action.get(flag)) == bool(move.get(flag)), "Card source zone does not match the legal action")
    if kind == "keep_hand":
        ids = action.get("bottom_card_ids", [])
        unique_ids(ids, player.hand, max(0, state.mulligan_count.get(player_id, 0) - state.mulligan_bottomed.get(player_id, 0)))
    elif kind == "play_land":
        face = action.get("selected_face_index", 0) or 0
        require(any(item.get("selected_face_index", 0) == face and item.get("entry_choice") == action.get("entry_choice") for item in available), "Selected land face or entry choice is unavailable")
    elif kind == "mulligan":
        require(state.mulligan_count.get(player_id, 0) < 7, "Cannot mulligan below zero opening cards")
    elif kind == "choose_mechanic":
        pending = state.pending_mechanic_choice
        if pending["kind"] == "combat_damage":
            from rules_engine.combat import valid_damage_assignment
            require(valid_damage_assignment(state, player_id, action), "Invalid combat damage assignment")
        elif pending["kind"] in {"draw", "land_entry", "saga_entry", "note_creature_type"}:
            require(action.get("choice_id") in pending["options"], "Unavailable draw choice")
        elif pending["kind"] in {"topdeck_put", "search_library", "proliferate", "scry", "surveil", "land_from_hand"} or (pending['kind'] == 'discard' and pending.get('min_count') == 0):
            unique_ids(action.get("card_ids", []), pending["options"])
            require(len(action.get("card_ids", [])) <= pending["count"], "Too many topdeck cards selected")
        else:
            unique_ids(action.get("card_ids", []), pending["options"], pending["count"])
    elif kind == "choose_trigger_order":
        group = state.pending_trigger_order["groups"].get(str(player_id), [])
        expected = [str(trigger["_choice_id"]) for trigger in group]
        unique_ids(action["trigger_order"], expected, len(expected))
    elif kind == "choose_trigger_target":
        require((action.get("target_card_id") is None) != (action.get("target_player") is None), "Choose exactly one trigger target")
        require(any(move.get("stack_id") == action["stack_id"] and move.get("target_card_id") == action.get("target_card_id") and move.get("target_player") == action.get("target_player") for move in available), "Unavailable trigger target")
    elif kind == "choose_optional_effect":
        require(any(move.get("stack_id") == action["stack_id"] and move.get("accept") is action["accept"] for move in available), "Unavailable optional effect choice")
    elif kind == "attack":
        unique_ids(action["attackers"], move.get("options", []))
        defenders = {item["id"] for item in move.get("defenders", [])}
        require(all(cid in action["attackers"] and target in defenders for cid, target in action.get("attack_targets", {}).items()), "Invalid attack target")
        from rules_engine.combat import valid_attack_bands
        require(valid_attack_bands(state, action["attackers"], action.get("attack_targets", {}), action.get("bands", [])), "Invalid attacking band")
    elif kind == "block":
        attackers = {item["id"] for item in move["attackers"]}
        blockers = {item["id"] for item in move["blockers"]}
        for attacker, ids in action["blocks"].items():
            require(attacker in attackers, "Unavailable attacking creature")
            unique_ids(ids, blockers)
    elif kind == "crew":
        unique_ids(action["crew_card_ids"], {item["id"] for item in move["crew_candidates"]})
    elif kind == "equip":
        require(action["target_card_id"] in {item["id"] for item in move["targets"]}, "Unavailable equipment target")
    elif kind == "cycle_card":
        require(any(item.get("x_value", 0) == action.get("x_value", 0) for item in available), "Unavailable cycling cost")
    elif kind == "activate_ability":
        from rules_engine.costs import activated_cost_available, restricted_x_color
        mana_cost = move["mana_cost"]
        require(targets.get("x_value") is None or (type(targets["x_value"]) is int and targets["x_value"] >= 0), "X value must be a non-negative integer")
        if "{X}" in mana_cost:
            require(targets.get("x_value") is not None, "X value is required for this activated cost")
        else:
            require(targets.get("x_value") is None, "This activated cost does not have a chosen X")
        require(activated_cost_available(
            state, player_id, action["card_id"], mana_cost,
            action.get("hybrid_choices"), int(targets.get("x_value") or 0),
            restricted_x_color(move.get("ability_label", "")),
            ability_index=move['ability_index'],
            payment_choices=action.get('payment_choices'),
        ), "Cannot pay activation costs")
    elif kind == "activate_loyalty" and targets.get("x_value") is not None:
        from rules_engine.oracle_effects import extract_loyalty_abilities
        require(extract_loyalty_abilities(state.cards[action["card_id"]])[action["ability_index"]].get("x_cost"), "This ability does not have a chosen X")
    elif kind == "cast_spell":
        from rules_engine.attachments import is_aura
        from rules_engine.costs import collect_cost_options
        from rules_engine.engine import _select_face_for_cast
        face = action.get("selected_face_index", action.get("targets", {}).get("selected_face_index"))
        if face is not None:
            require(0 <= face < len(state.cards[action["card_id"]].card_faces), "Selected card face is unavailable")
            require(not face or state.cards[action["card_id"]].layout not in {"transform", "meld", "flip", "double_faced_token"}, "This back face cannot be cast directly")
        face_card = _select_face_for_cast(state.cards[action["card_id"]], face)
        if casting_method((action.get('cost_choice') or {}).get('id', '')) == 'bestow':
            from rules_engine.bestow import bestow_cast_view
            face_card = bestow_cast_view(face_card)
        if state.cards[action["card_id"]].layout in {"modal_dfc", "adventure", "split"}:
            require(any(item.get("selected_face_index", 0) == (face or 0) for item in available), "Selected face is not currently castable")
        options = collect_cost_options(state, player_id, face_card,
            without_mana=bool(state.pending_mechanic_choice and state.pending_mechanic_choice['kind'] in {'effect_cast', 'suspend_cast'}))
        choice = (action.get("cost_choice") or {}).get("id")
        require(not choice or any(option.id == choice for option in options), "Unknown casting cost option")
        hybrid_choices = action.get("hybrid_choices")
        if hybrid_choices is not None:
            from rules_engine.mana import hybrid_payment_symbols, can_pay_with_pool_and_lands
            require(bool(choice), "Select a casting cost option for hybrid payment")
            option = next(option for option in options if option.id == choice)
            symbols = hybrid_payment_symbols(option.mana_cost)
            require(bool(symbols), "Selected cost has no supported hybrid symbols")
            require(len(hybrid_choices) == len(symbols), "Choose one branch for each hybrid symbol")
            require(all(branch in symbol["choices"] for branch, symbol in zip(hybrid_choices, symbols)), "Invalid hybrid payment branch")
            require(can_pay_with_pool_and_lands(
                state, player_id, option.mana_cost, card_name=face_card.name,
                x_value=int(targets.get("x_value") or 0), spell_types=set(effective_types(state, face_card)),
                oracle_text=face_card.oracle_text or "",
                spell_is_aura=is_aura(face_card),
                cast_resource_card=face_card, resource_choices=action.get('resource_payment'),
                spell_kicked=option.kicked,
                source_card_id=face_card.id, target_card_id=targets.get('target_card_id'),
                hybrid_choices=hybrid_choices,
                reserved_life=option.pay_life + (int(targets.get("x_value") or 0) if option.pay_life_x else 0),
            ), "Cannot pay the selected hybrid branches")
        if targets.get("x_value") is not None:
            require("{X}" in face_card.mana_cost.upper() or any(
                '{X}' in option.mana_cost.upper() or option.pay_life_x or option.discard_x
                for option in options if not choice or option.id == choice), "This casting cost does not have a chosen X")
    if kind == "activate_loyalty":
        require(action.get("hybrid_choices") is None, "Loyalty abilities do not use hybrid payment choices")
    if kind == "activate_ability" and action.get("hybrid_choices") is not None:
        from rules_engine.costs import parse_activated_cost
        from rules_engine.mana import can_pay_with_pool_and_lands, hybrid_payment_symbols
        cost = parse_activated_cost(move["mana_cost"])
        choices = action["hybrid_choices"]
        symbols = hybrid_payment_symbols(cost.mana_cost)
        require(bool(symbols), "Activated ability has no supported hybrid symbols")
        require(len(choices) == len(symbols), "Choose one branch for each hybrid symbol")
        require(all(branch in symbol["choices"] for branch, symbol in zip(choices, symbols)), "Invalid hybrid payment branch")
        from rules_engine.costs import activated_cost_available
        require(activated_cost_available(state, player_id, action['card_id'], move['mana_cost'], choices,
                int(targets.get('x_value') or 0), restricted_x_color(move.get('ability_label', '')), ability_index=move['ability_index'], payment_choices=action.get('payment_choices')),
                "Cannot pay the selected hybrid branches")


def validate_tap(state, player_id: int, action: dict) -> None:
    from rules_engine.mana import _nonland_mana_source_colors, land_can_produce_mana
    from rules_engine.mana_abilities import tap_only_outputs
    player = state.players[player_id]
    if action["type"] == "tap_nonland_for_mana":
        cid = action["card_id"]
        require(cid in player.battlefield, "Mana source must be a permanent you control")
        colors = _nonland_mana_source_colors(state, cid, state.cards[cid])
        require(action["color"] in colors, "Mana source cannot produce the selected color now")
        return
    if action["type"] == "tap_land_for_mana":
        ids = [action["card_id"]]
    else:
        ids = [cid for cid in player.battlefield if state.cards[cid].name.strip().lower() == action["land_name"].strip().lower()
               and land_can_produce_mana(state, cid, free_only=False)
               and (not action.get("color") or action["color"] in tap_only_outputs(state, state.cards[cid]))]
        require(len(ids) >= action["count"], "Not enough untapped matching lands")
        ids = ids[:action["count"]]
    for cid in ids:
        card = state.cards.get(cid)
        require(cid in player.battlefield and card is not None and land_can_produce_mana(state, cid, free_only=False), "Mana source must be a ready land you control")
        from rules_engine.costs import activated_cost_available
        require(activated_cost_available(state, player_id, cid, '{T}', ability_kind='mana'), 'Cannot pay mana ability costs')
        colors = tap_only_outputs(state, card)
        require(not action.get("color") or action["color"] in colors, "Land cannot produce the selected color")
