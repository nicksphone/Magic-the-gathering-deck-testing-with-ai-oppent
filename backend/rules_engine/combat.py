from __future__ import annotations

import re

from game_state.state import MatchState, Step, Zone
from rules_engine.colors import card_color_names
from rules_engine.continuous import KNOWN_KEYWORDS, effective_power, effective_toughness, has_keyword
from rules_engine.events import emit_event, emit_event_batch
from rules_engine.prevention import consume_card_prevention_shield, consume_player_prevention_shield
from rules_engine.protection import protected_from_source
from rules_engine.replacement import damage_cant_be_prevented, replace_die_zone
from rules_engine.restrictions import (
    card_cant_attack,
    card_cant_attack_alone,
    card_cant_block,
    card_must_attack_if_able,
    card_must_block_if_able,
)

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"
BLOCK_ONLY_KEYWORD_RE = re.compile(r"\bcan block only creatures with ([a-z][a-z ]*?)(?:[.\n]|$)", re.IGNORECASE)


def valid_attack_bands(state: MatchState, attackers: list[str], targets: dict[str, str], bands: list[list[str]]) -> bool:
    defender = 1 if state.active_player == 2 else 2
    seen: set[str] = set()
    for band in bands:
        if len(band) < 2 or len(set(band)) != len(band):
            return False
        if any(cid not in attackers or cid in seen or cid not in state.cards for cid in band):
            return False
        seen.update(band)
        if sum(not has_keyword(state, cid, "banding") for cid in band) > 1:
            return False
        if len({targets.get(cid, f"player:{defender}") for cid in band}) != 1:
            return False
    return True


def declare_attackers(state: MatchState, attacker_ids: list[str], attack_targets: dict[str, str] | None = None, bands: list[list[str]] | None = None) -> None:
    attack_targets = attack_targets or {}
    bands = bands or []
    if not valid_attack_bands(state, attacker_ids, attack_targets, bands):
        raise ValueError("Invalid attacking band")
    legal: list[str] = []
    legal_targets: dict[str, str] = {}
    defender = 1 if state.active_player == 2 else 2
    valid_defenders = _valid_defenders(state, defender)
    requested = list(attacker_ids)
    must_attack: list[str] = []
    for cid in state.players[state.active_player].battlefield:
        card = state.cards[cid]
        if (
            "Creature" in card.types
            and card.zone == Zone.BATTLEFIELD
            and not card.tapped
            and (not card.summoning_sick or has_keyword(state, cid, "haste"))
            and not has_keyword(state, cid, "defender")
            and not card_cant_attack(state, cid)
            and card_must_attack_if_able(state, cid)
        ):
            must_attack.append(cid)
    for cid in must_attack:
        if cid not in requested:
            requested.append(cid)

    for cid in requested:
        if cid not in state.cards:
            continue
        card = state.cards[cid]
        if card.controller != state.active_player:
            continue
        if card.zone != Zone.BATTLEFIELD:
            continue
        if "Creature" not in card.types:
            continue
        if card.tapped:
            continue
        if card.summoning_sick and not has_keyword(state, cid, "haste"):
            continue
        if has_keyword(state, cid, "defender"):
            continue
        if card_cant_attack(state, cid):
            continue
        legal.append(cid)
        desired = attack_targets.get(cid, f"player:{defender}")
        legal_targets[cid] = desired if desired in valid_defenders else f"player:{defender}"
        if not has_keyword(state, cid, "vigilance"):
            card.tapped = True
    if len(legal) == 1 and card_cant_attack_alone(state, legal[0]):
        lone = legal[0]
        state.log.append(f"{state.cards[lone].name} can't attack alone.")
        legal = []
        legal_targets = {}
    state.attackers = legal
    state.attack_bands = [list(band) for band in bands if all(cid in legal for cid in band)]
    state.combat_damage_resolved = False
    state.combat_damage_stage = "none"
    state.first_strike_damage_ids = set()
    state.attack_targets = legal_targets
    if legal:
        names = ", ".join(
            f"{state.cards[c].name} -> {_defender_label(state, state.attack_targets.get(c, f'player:{defender}'))}"
            for c in legal
        )
        state.log.append(f"Attackers declared: {names}")
        for index, cid in enumerate(legal):
            emit_event(
                state,
                "attack_declared",
                {
                    "card_id": cid,
                    "controller": state.cards[cid].controller,
                    "attack_target": state.attack_targets.get(cid, f"player:{defender}"),
                    "attack_group_first": index == 0,
                },
            )


def declare_blockers(state: MatchState, blocks: dict[str, str | list[str]]) -> None:
    defender = 1 if state.active_player == 2 else 2
    legal: dict[str, list[str]] = {}
    blocker_assignments: dict[str, int] = {}
    for attacker, blockers in blocks.items():
        if attacker not in state.attackers:
            continue
        blocker_list = blockers if isinstance(blockers, list) else [blockers]
        picked: list[str] = []
        for blocker in blocker_list:
            if blocker not in state.cards:
                continue
            block_card = state.cards[blocker]
            assigned = int(blocker_assignments.get(blocker, 0))
            block_cap = _max_attackers_blockable_by_creature(block_card)
            if assigned >= block_cap:
                continue
            if block_card.controller != defender:
                continue
            if block_card.tapped:
                continue
            if "Creature" not in block_card.types:
                continue
            if card_cant_block(state, blocker):
                continue
            atk_card = state.cards[attacker]
            if not _can_block_attacker(state, atk_card, block_card):
                continue
            picked.append(blocker)
            blocker_assignments[blocker] = assigned + 1
        if picked:
            legal[attacker] = picked
    # Menace: must be blocked by two or more creatures.
    for attacker in list(legal.keys()):
        atk_card = state.cards.get(attacker)
        min_blockers = _minimum_blockers_required(state, attacker) if atk_card else 1
        if atk_card and len(legal[attacker]) < min_blockers:
            legal.pop(attacker, None)

    # Enforce "must block each combat if able" for unassigned blockers.
    for blocker_id in state.players[defender].battlefield:
        card = state.cards[blocker_id]
        if blocker_assignments.get(blocker_id, 0) > 0:
            continue
        if "Creature" not in card.types or card.tapped or card_cant_block(state, blocker_id):
            continue
        if not card_must_block_if_able(state, blocker_id):
            continue
        for attacker_id in state.attackers:
            atk_card = state.cards.get(attacker_id)
            if not atk_card or atk_card.zone != Zone.BATTLEFIELD:
                continue
            min_blockers = _minimum_blockers_required(state, attacker_id)
            current = legal.get(attacker_id, [])
            if len(current) >= max(min_blockers, 1):
                continue
            if not _can_block_attacker(state, atk_card, card):
                continue
            legal.setdefault(attacker_id, []).append(blocker_id)
            blocker_assignments[blocker_id] = blocker_assignments.get(blocker_id, 0) + 1
            break
    # A legal direct block of one band member blocks every member, regardless
    # of whether the blocker could have blocked those other members directly.
    for band in state.attack_bands:
        members = [cid for cid in band if cid in state.attackers and state.cards[cid].zone == Zone.BATTLEFIELD]
        shared = list(dict.fromkeys(bid for cid in members for bid in legal.get(cid, [])))
        for cid in members:
            if shared:
                legal[cid] = list(shared)
    state.blocks = legal
    _apply_block_combat_abilities(state)
    for attacker_id, blocker_ids in legal.items():
        for blocker_id in blocker_ids:
            emit_event(
                state,
                "block_declared",
                {
                    "attacker_id": attacker_id,
                    "blocker_id": blocker_id,
                    "controller": state.cards[blocker_id].controller,
                },
            )


def _apply_block_combat_abilities(state: MatchState) -> None:
    """Apply Bushido, Rampage, and Flanking as blockers become declared."""
    for attacker_id, blocker_ids in state.blocks.items():
        attacker = state.cards.get(attacker_id)
        if attacker is None:
            continue
        bushido = _combat_keyword_value(attacker, "bushido")
        if bushido:
            _add_combat_modifier(attacker, bushido, bushido)
        rampage = _combat_keyword_value(attacker, "rampage")
        if rampage and len(blocker_ids) > 1:
            amount = rampage * (len(blocker_ids) - 1)
            _add_combat_modifier(attacker, amount, amount)
        if _has_combat_keyword(attacker, "flanking"):
            for blocker_id in blocker_ids:
                blocker = state.cards.get(blocker_id)
                if blocker is not None and not _has_combat_keyword(blocker, "flanking"):
                    _add_combat_modifier(blocker, -1, -1)
        for blocker_id in blocker_ids:
            blocker = state.cards.get(blocker_id)
            if blocker is None:
                continue
            blocker_bushido = _combat_keyword_value(blocker, "bushido")
            if blocker_bushido:
                _add_combat_modifier(blocker, blocker_bushido, blocker_bushido)


def _combat_keyword_value(card, keyword: str) -> int:
    text = (getattr(card, "oracle_text", "") or "").lower()
    match = re.search(rf"\b{re.escape(keyword)}\s+(\d+)\b", text)
    return int(match.group(1)) if match else 0


def _has_combat_keyword(card, keyword: str) -> bool:
    text = (getattr(card, "oracle_text", "") or "").lower()
    return keyword in text or keyword in {str(item).lower() for item in (getattr(card, "keywords", []) or [])}


def _add_combat_modifier(card, power: int, toughness: int) -> None:
    counters = getattr(card, "counters", {})
    counters["__eot_power"] = int(counters.get("__eot_power", 0) or 0) + int(power)
    counters["__eot_toughness"] = int(counters.get("__eot_toughness", 0) or 0) + int(toughness)


def combat_damage(state: MatchState) -> None:
    """Resolve both substeps for direct callers that do not manage priority."""
    if state.combat_damage_resolved:
        return
    if state.combat_damage_stage != "first":
        begin_combat_damage(state)
    if state.combat_damage_stage == "first" and not state.pending_mechanic_choice and not state.pending_replacement_choice and not state.pending_trigger_order:
        finish_combat_damage(state)


def _assigns_damage(state: MatchState, cid: str, first_only: bool) -> bool:
    return cid in state.first_strike_damage_ids if first_only else cid not in state.first_strike_damage_ids or has_keyword(state, cid, "double strike")


def _assignment_options(state: MatchState, cid: str, first_only: bool) -> list[str]:
    card = state.cards.get(cid)
    if not card or card.zone != Zone.BATTLEFIELD or not _assigns_damage(state, cid, first_only):
        return []
    if cid in state.attackers:
        blockers = [bid for bid in state.blocks.get(cid, []) if bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD]
        if len(blockers) > 1 or (blockers and has_keyword(state, cid, "trample")):
            defender = 1 if state.active_player == 2 else 2
            return blockers + ([state.attack_targets.get(cid, f"player:{defender}")] if has_keyword(state, cid, "trample") else [])
        return []
    attackers = [aid for aid in state.attackers if cid in state.blocks.get(aid, []) and aid in state.cards and state.cards[aid].zone == Zone.BATTLEFIELD]
    return attackers if len(attackers) > 1 else []


def _assignment_controller(state: MatchState, cid: str) -> int:
    source = state.cards[cid]
    if cid in state.attackers:
        blockers = state.blocks.get(cid, [])
        if any(bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD and has_keyword(state, bid, "banding") for bid in blockers):
            return 1 if state.active_player == 2 else 2
    elif any(aid in state.cards and state.cards[aid].zone == Zone.BATTLEFIELD and has_keyword(state, aid, "banding")
             for aid in state.attackers if cid in state.blocks.get(aid, [])):
        return state.active_player
    return source.controller


def _offer_damage_assignment(state: MatchState) -> None:
    source = state.combat_assignment_queue[0]
    card = state.cards[source]
    chooser = _assignment_controller(state, source)
    options = _assignment_options(state, source, state.combat_damage_stage == "first")
    labels = {cid: state.cards[cid].name if cid in state.cards else _defender_label(state, cid) for cid in options}
    state.pending_mechanic_choice = {
        "kind": "combat_damage", "player_id": chooser, "source_id": source,
        "source_name": card.name, "stage": state.combat_damage_stage,
        "options": options, "option_labels": labels,
        "count": max(0, effective_power(state, source)),
        "can_restart": any(_assignment_controller(state, cid) == chooser for cid in state.combat_damage_assignments),
        "label": f"Assign {card.name}'s combat damage",
    }
    state.priority_player = state.pending_mechanic_choice["player_id"]
    state.passed_priority = set()


def _resolve_damage_step(state: MatchState) -> None:
    state.trigger_staging = True
    state.trigger_staging_event = "combat_damage_step"
    first_only = state.combat_damage_stage == "first"
    defender = 1 if state.active_player == 2 else 2
    _combat_damage_step(state, defender, state.first_strike_damage_ids, first_strike_only=first_only)
    if not first_only:
        state.combat_damage_resolved = True
    if state.pending_replacement_choice or state.pending_mechanic_choice:
        (state.pending_replacement_choice or state.pending_mechanic_choice)["combat_damage_needs_sba"] = True
        return
    _remove_dead_creatures(state)
    if not state.pending_replacement_choice and not state.pending_trigger_order and not state.pending_mechanic_choice:
        state.priority_player = state.active_player
        state.passed_priority = set()


def _prepare_damage_step(state: MatchState) -> None:
    state.combat_damage_assignments = {}
    first_only = state.combat_damage_stage == "first"
    blockers = list(dict.fromkeys(bid for bids in state.blocks.values() for bid in bids))
    sources = list(state.attackers) + blockers
    state.combat_assignment_queue = [
        cid for cid in sources
        if cid in state.cards and _assignment_controller(state, cid) in state.mechanic_choice_players
        and effective_power(state, cid) > 0 and _assignment_options(state, cid, first_only)
    ]
    if state.combat_assignment_queue:
        _offer_damage_assignment(state)
    else:
        _resolve_damage_step(state)


def _trample_assignments_legal(state: MatchState, assignments: dict[str, dict[str, int]]) -> bool:
    first_only = state.combat_damage_stage == "first"
    assigned_to_blocker: dict[str, int] = {}
    deathtouch_blockers: set[str] = set()
    for attacker in state.attackers:
        if attacker not in state.cards or state.cards[attacker].zone != Zone.BATTLEFIELD or not _assigns_damage(state, attacker, first_only):
            continue
        amounts = assignments.get(attacker)
        if amounts is None:
            blockers = [bid for bid in state.blocks.get(attacker, []) if bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD]
            amounts = {blockers[0]: max(0, effective_power(state, attacker))} if len(blockers) == 1 and not has_keyword(state, attacker, "trample") else {}
        for blocker_id in state.blocks.get(attacker, []):
            dealt = amounts.get(blocker_id, 0)
            assigned_to_blocker[blocker_id] = assigned_to_blocker.get(blocker_id, 0) + dealt
            if dealt > 0 and has_keyword(state, attacker, "deathtouch"):
                deathtouch_blockers.add(blocker_id)
    for attacker, amounts in assignments.items():
        if attacker not in state.attackers or not has_keyword(state, attacker, "trample"):
            continue
        blockers = [bid for bid in state.blocks.get(attacker, []) if bid in state.cards and state.cards[bid].zone == Zone.BATTLEFIELD]
        defender = state.attack_targets.get(attacker, f"player:{2 if state.active_player == 1 else 1}")
        if amounts.get(defender, 0) <= 0:
            continue
        for blocker_id in blockers:
            card = state.cards[blocker_id]
            lethal = max(0, effective_toughness(state, blocker_id) - int(card.counters.get(DMG_MARK_KEY, 0)))
            if blocker_id not in deathtouch_blockers and assigned_to_blocker.get(blocker_id, 0) < lethal:
                return False
    return True


def valid_damage_assignment(state: MatchState, player_id: int, action: dict) -> bool:
    pending = state.pending_mechanic_choice
    if not pending or pending.get("kind") != "combat_damage" or pending.get("player_id") != player_id:
        return False
    if state.step != Step.COMBAT_DAMAGE or state.combat_damage_stage != pending.get("stage"):
        return False
    if action.get("choice_id") == "restart":
        return bool(pending.get("can_restart")) and action.get("damage_assignment") is None
    amounts = action.get("damage_assignment")
    source = pending.get("source_id")
    if source not in state.cards or state.cards[source].zone != Zone.BATTLEFIELD:
        return False
    options = _assignment_options(state, source, state.combat_damage_stage == "first")
    if not isinstance(amounts, dict) or set(amounts) != set(options):
        return False
    if any(type(amount) is not int or amount < 0 for amount in amounts.values()):
        return False
    power = max(0, effective_power(state, source))
    if sum(amounts.values()) != power or power != pending.get("count"):
        return False
    if source in state.attackers and not any(cid in state.attackers for cid in state.combat_assignment_queue[1:]):
        projected = {**state.combat_damage_assignments, source: amounts}
        if not _trample_assignments_legal(state, projected):
            return False
    return True


def finish_damage_assignment(state: MatchState, player_id: int, action: dict) -> bool:
    if not valid_damage_assignment(state, player_id, action):
        return False
    if action.get("choice_id") == "restart":
        state.combat_damage_assignments = {
            cid: amounts for cid, amounts in state.combat_damage_assignments.items()
            if _assignment_controller(state, cid) != player_id
        }
        blockers = list(dict.fromkeys(bid for bids in state.blocks.values() for bid in bids))
        first_only = state.combat_damage_stage == "first"
        state.combat_assignment_queue = [
            cid for cid in list(state.attackers) + blockers
            if cid in state.cards and cid not in state.combat_damage_assignments
            and _assignment_controller(state, cid) in state.mechanic_choice_players
            and effective_power(state, cid) > 0 and _assignment_options(state, cid, first_only)
        ]
        _offer_damage_assignment(state)
        return True
    amounts = action["damage_assignment"]
    source = state.pending_mechanic_choice["source_id"]
    state.combat_damage_assignments[source] = dict(amounts)
    state.combat_assignment_queue.pop(0)
    state.pending_mechanic_choice = None
    if state.combat_assignment_queue:
        _offer_damage_assignment(state)
    else:
        _resolve_damage_step(state)
    return True


def begin_combat_damage(state: MatchState) -> None:
    if state.combat_damage_stage != "none" or state.combat_damage_resolved:
        return
    combatants = set(state.attackers)
    combatants.update(blocker for blockers in state.blocks.values() for blocker in blockers)
    first_ids = {
        cid for cid in combatants
        if cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
        and (has_keyword(state, cid, "first strike") or has_keyword(state, cid, "double strike"))
    }
    state.first_strike_damage_ids = first_ids
    if first_ids:
        state.combat_damage_stage = "first"
    else:
        state.combat_damage_stage = "regular"
    _prepare_damage_step(state)


def finish_combat_damage(state: MatchState) -> None:
    if state.combat_damage_stage != "first" or state.combat_damage_resolved:
        return
    state.combat_damage_stage = "regular"
    _prepare_damage_step(state)


def _combat_damage_step(state: MatchState, default_defender: int, first_ids: set[str], first_strike_only: bool) -> None:
    def assigns_damage(cid: str) -> bool:
        return _assigns_damage(state, cid, first_strike_only)

    damage_events: list[dict] = []
    lifelink_gains: dict[str, tuple[int, int]] = {}

    def record_lifelink(source_id: str, controller: int, amount: int) -> None:
        if amount <= 0 or not has_keyword(state, source_id, "lifelink"):
            return
        previous = lifelink_gains.get(source_id, (controller, 0))[1]
        lifelink_gains[source_id] = (controller, previous + amount)
    # All sources assign damage from the same pre-damage game state.
    attacker_power = {
        cid: max(0, effective_power(state, cid))
        for cid in state.attackers
        if cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
    }
    blocker_damage_remaining = {
        cid: max(0, effective_power(state, cid))
        for blockers in state.blocks.values() for cid in blockers
        if cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
    }
    for attacker in list(state.attackers):
        if attacker not in state.cards:
            continue
        atk = state.cards[attacker]
        if atk.zone != Zone.BATTLEFIELD:
            continue

        blocks = [b for b in state.blocks.get(attacker, []) if b in state.cards and state.cards[b].zone == Zone.BATTLEFIELD]
        defender_key = state.attack_targets.get(attacker, f"player:{default_defender}")
        if not blocks:
            if not assigns_damage(attacker):
                continue
            # A blocked creature stays blocked when its blockers leave combat.
            if state.blocks.get(attacker) and not has_keyword(state, attacker, "trample"):
                continue
            dealt = _deal_unblocked_damage(state, defender_key, attacker_power[attacker], source_id=attacker)
            record_lifelink(attacker, atk.controller, dealt)
            if dealt > 0:
                damage_events.append({"source_card_id": attacker, "target_key": defender_key, "target_player": int(defender_key.split(":", 1)[1]) if defender_key.startswith("player:") else None, "amount": dealt})
            continue

        if assigns_damage(attacker):
            remaining = attacker_power[attacker]
            atk_has_deathtouch = has_keyword(state, attacker, "deathtouch")
            allocation = state.combat_damage_assignments.get(attacker)
            if allocation is None:
                allocation = {}
                for blocker_id in blocks:
                    dealt = min(remaining, 1 if atk_has_deathtouch else _remaining_lethal_damage(state, blocker_id))
                    allocation[blocker_id] = dealt
                    remaining -= dealt
                if has_keyword(state, attacker, "trample"):
                    allocation[defender_key] = remaining
                elif blocks and remaining > 0:
                    allocation[blocks[0]] += remaining
            for blocker_id in blocks:
                dealt = allocation.get(blocker_id, 0)
                if dealt <= 0 or _damage_prevented_by_protection(state, attacker, blocker_id):
                    continue
                actual = _mark_creature_damage(state, blocker_id, dealt, deathtouch=atk_has_deathtouch, source_id=attacker)
                record_lifelink(attacker, atk.controller, actual)
                if actual > 0:
                    damage_events.append({"source_card_id": attacker, "target_card_id": blocker_id, "amount": actual})
            if has_keyword(state, attacker, "trample") and allocation.get(defender_key, 0) > 0:
                dealt = _deal_unblocked_damage(state, defender_key, allocation[defender_key], source_id=attacker)
                record_lifelink(attacker, atk.controller, dealt)
                if dealt > 0:
                    damage_events.append({"source_card_id": attacker, "target_key": defender_key, "target_player": int(defender_key.split(":", 1)[1]) if defender_key.startswith("player:") else None, "amount": dealt})

        for blocker_id in blocks:
            blk = state.cards[blocker_id]
            if not assigns_damage(blocker_id):
                continue
            assigned = state.combat_damage_assignments.get(blocker_id)
            blk_power = assigned.get(attacker, 0) if assigned is not None else blocker_damage_remaining.get(blocker_id, 0)
            blocker_damage_remaining[blocker_id] = max(0, blocker_damage_remaining.get(blocker_id, 0) - blk_power)
            if blk_power <= 0:
                continue
            if _damage_prevented_by_protection(state, blocker_id, attacker):
                continue
            actual = _mark_creature_damage(state, attacker, blk_power, deathtouch=has_keyword(state, blocker_id, "deathtouch"), source_id=blocker_id)
            record_lifelink(blocker_id, blk.controller, actual)
            if actual > 0:
                damage_events.append({"source_card_id": blocker_id, "target_card_id": attacker, "amount": actual})
    emit_event_batch(state, "combat_damage_dealt", damage_events)
    gain_effects = []
    for source_id, (controller, amount) in lifelink_gains.items():
        gain_effects.append({"effect_key": "gain_life", "payload": {
            "target_player": controller, "amount": amount, "__source_card_id": source_id,
        }})
    if gain_effects:
        from effects.registry import resolve_effect
        resolve_effect(state, state.active_player, "effect_sequence", {"effects": gain_effects})


def _remove_dead_creatures(state: MatchState) -> None:
    from rules_engine.state_based_actions import apply_state_based_actions

    apply_state_based_actions(state)


def resume_combat_die_replacement(state: MatchState, card_id: str, replacement_source_id: str) -> None:
    """Resume a combat death after a human replacement choice."""
    card = state.cards.get(card_id)
    if not card or card.zone != Zone.BATTLEFIELD:
        return
    battlefield_owner = state.players[card.controller]
    zone_owner = state.players[getattr(card, "owner", card.controller)]
    if card_id not in battlefield_owner.battlefield:
        return
    emit_event(state, "leaves_battlefield", {"card_id": card_id, "controller": card.controller})
    battlefield_owner.battlefield.remove(card_id)
    destination = replace_die_zone(state, card.controller, card_id, replacement_source_id)
    if destination == "exile":
        zone_owner.exile.append(card_id)
        card.move_to_zone(Zone.EXILE)
        state.log.append(f"{card.name} is exiled instead of dying in combat.")
        return
    zone_owner.graveyard.append(card_id)
    card.zone = Zone.GRAVEYARD
    state.log.append(f"{card.name} dies in combat.")
    emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
    emit_event(state, "creature_dies", {"card_id": card_id, "controller": card.controller})


def _can_block_attacker(state: MatchState, attacker, blocker) -> bool:
    only_keyword = BLOCK_ONLY_KEYWORD_RE.search(getattr(blocker, "oracle_text", "") or "")
    if only_keyword:
        required = only_keyword.group(1).strip().lower()
        if required in KNOWN_KEYWORDS and not has_keyword(state, attacker.id, required):
            return False
    # Flying can only be blocked by flying or reach.
    if has_keyword(state, attacker.id, "flying"):
        if not (has_keyword(state, blocker.id, "flying") or has_keyword(state, blocker.id, "reach")):
            return False
    # Shadow creatures can only block or be blocked by other shadow creatures.
    attacker_has_shadow = has_keyword(state, attacker.id, "shadow")
    blocker_has_shadow = has_keyword(state, blocker.id, "shadow")
    if attacker_has_shadow != blocker_has_shadow:
        return False
    # Fear: blocked only by artifact creatures and/or black creatures.
    if has_keyword(state, attacker.id, "fear"):
        blocker_colors = card_color_names(state.cards.get(blocker.id))
        if "Artifact" not in (getattr(blocker, "types", []) or []) and "black" not in blocker_colors:
            return False
    # Intimidate: blocked only by artifact creatures and/or creatures sharing a color.
    if has_keyword(state, attacker.id, "intimidate"):
        blocker_colors = card_color_names(state.cards.get(blocker.id))
        attacker_colors = card_color_names(state.cards.get(attacker.id))
        shares_color = bool(attacker_colors & blocker_colors)
        if "Artifact" not in (getattr(blocker, "types", []) or []) and not shares_color:
            return False
    # Landwalk: unblockable if defending player controls relevant land type.
    if _attacker_has_active_landwalk_with_state(state, attacker, blocker.controller):
        return False
    # Protection prevents blocking from protected qualities.
    if protected_from_source(state, attacker.id, blocker):
        return False
    return True


def _damage_prevented_by_protection(state: MatchState, source_id: str, target_id: str) -> bool:
    source = state.cards[source_id]
    return protected_from_source(state, target_id, source)


def _minimum_blockers_required(state: MatchState, attacker_id: str) -> int:
    attacker = state.cards[attacker_id]
    min_blockers = 2 if has_keyword(state, attacker_id, "menace") else 1
    if has_keyword(state, attacker_id, "menace"):
        min_blockers = max(min_blockers, 2)
    text = (getattr(attacker, "oracle_text", "") or "").lower()
    if "can't be blocked except by two or more creatures" in text or "cannot be blocked except by two or more creatures" in text:
        min_blockers = max(min_blockers, 2)
    for phrase, value in _NUMBER_WORDS.items():
        token = f"can't be blocked except by {phrase} or more creatures"
        token2 = f"cannot be blocked except by {phrase} or more creatures"
        if token in text or token2 in text:
            min_blockers = max(min_blockers, value)
    return min_blockers


def _max_attackers_blockable_by_creature(blocker) -> int:
    text = (getattr(blocker, "oracle_text", "") or "").lower()
    if "can block any number of creatures" in text:
        return 99
    if "can block an additional creature each combat" in text:
        return 2
    for phrase, value in _NUMBER_WORDS.items():
        token = f"can block {phrase} additional creatures each combat"
        if token in text:
            return 1 + value
    return 1


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _attacker_has_active_landwalk_with_state(state: MatchState, attacker, defending_player_id: int) -> bool:
    walks = [
        "islandwalk", "swampwalk", "mountainwalk", "forestwalk", "plainswalk",
        "nonbasic landwalk", "snow landwalk", "desertwalk", "wasteswalk", "legendary landwalk",
    ]
    active_walks = [w for w in walks if has_keyword(state, attacker.id, w)]
    if not active_walks:
        return False
    defender_bf = state.players[defending_player_id].battlefield
    for cid in defender_bf:
        card = state.cards[cid]
        tl = (card.type_line or "").lower()
        nm = (card.name or "").lower()
        for walk in active_walks:
            if walk == "nonbasic landwalk" and "land" in tl and "basic" not in tl:
                return True
            if walk == "snow landwalk" and "snow" in tl and "land" in tl:
                return True
            if walk == "legendary landwalk" and "legendary" in tl and "land" in tl:
                return True
            subtype = walk.replace(" landwalk", "").replace("walk", "")
            if subtype in tl or subtype in nm:
                return True
    return False


def _valid_defenders(state: MatchState, defending_player: int) -> set[str]:
    out = {f"player:{defending_player}"}
    for cid in state.players[defending_player].battlefield:
        card = state.cards[cid]
        if "Planeswalker" in card.types and card.zone == Zone.BATTLEFIELD:
            out.add(f"planeswalker:{cid}")
    return out


def _defender_label(state: MatchState, key: str) -> str:
    if key.startswith("planeswalker:"):
        cid = key.split(":", 1)[1]
        card = state.cards.get(cid)
        if card:
            return card.name
    if key.startswith("player:"):
        pid = int(key.split(":", 1)[1])
        return state.players[pid].name
    return key


def _deal_unblocked_damage(state: MatchState, defender_key: str, amount: int, source_id: str | None = None) -> int:
    if amount <= 0:
        return 0
    if defender_key.startswith("planeswalker:"):
        cid = defender_key.split(":", 1)[1]
        card = state.cards.get(cid)
        if card and "Planeswalker" in card.types and card.zone == Zone.BATTLEFIELD:
            if source_id is not None and source_id in state.cards and _damage_prevented_by_protection(state, source_id, cid):
                state.log.append(f"{card.name} prevents {amount} damage.")
                return 0
            card.loyalty = (card.loyalty or 0) - amount
            state.log.append(f"{card.name} loses {amount} loyalty.")
            return amount
        # PW left battlefield — damage disappears, does NOT redirect to player
        return 0
    pid = int(defender_key.split(":", 1)[1]) if defender_key.startswith("player:") else 2
    prevention_locked = source_id is not None and source_id in state.cards and damage_cant_be_prevented(
        state,
        source_card_id=source_id,
        target_player=pid,
        combat=True,
    )
    post, prevented = (amount, 0) if prevention_locked else consume_player_prevention_shield(state, pid, amount)
    if prevented > 0:
        state.log.append(f"{state.players[pid].name} prevents {prevented} damage.")
    if post <= 0:
        return 0
    from rules_engine.damage_results import apply_player_damage
    apply_player_damage(state, pid, post, source_id, combat=True)
    return post


def _mark_creature_damage(
    state: MatchState,
    card_id: str,
    amount: int,
    deathtouch: bool = False,
    source_id: str | None = None,
) -> int:
    if amount <= 0:
        return 0
    card = state.cards[card_id]
    prevention_locked = source_id is not None and source_id in state.cards and damage_cant_be_prevented(
        state,
        source_card_id=source_id,
        target_card_id=card_id,
        combat=True,
    )
    post, prevented = (amount, 0) if prevention_locked else consume_card_prevention_shield(card, amount)
    if prevented > 0:
        state.log.append(f"{card.name} prevents {prevented} damage.")
    if post <= 0:
        return 0
    from rules_engine.damage_results import apply_creature_damage
    apply_creature_damage(state, card_id, int(post), source_id)
    if deathtouch:
        card.counters[DEATHTOUCH_MARK_KEY] = 1
    return int(post)


def _remaining_lethal_damage(state: MatchState, card_id: str) -> int:
    card = state.cards[card_id]
    toughness = effective_toughness(state, card_id)
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    return max(1, toughness - marked)
