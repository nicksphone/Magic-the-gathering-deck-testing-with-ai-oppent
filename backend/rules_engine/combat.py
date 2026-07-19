from __future__ import annotations

import re

from game_state.state import MatchState, Zone
from rules_engine.colors import card_color_names
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.events import emit_event
from rules_engine.prevention import consume_card_prevention_shield, consume_player_prevention_shield
from rules_engine.protection import protected_from_source
from rules_engine.replacement import damage_cant_be_prevented, replace_die_zone, replacement_options
from rules_engine.restrictions import (
    card_cant_attack,
    card_cant_attack_alone,
    card_cant_block,
    card_must_attack_if_able,
    card_must_block_if_able,
)

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"


def declare_attackers(state: MatchState, attacker_ids: list[str], attack_targets: dict[str, str] | None = None) -> None:
    attack_targets = attack_targets or {}
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
    state.attack_targets = legal_targets
    if legal:
        names = ", ".join(
            f"{state.cards[c].name} -> {_defender_label(state, state.attack_targets.get(c, f'player:{defender}'))}"
            for c in legal
        )
        state.log.append(f"Attackers declared: {names}")
        for cid in legal:
            emit_event(
                state,
                "attack_declared",
                {
                    "card_id": cid,
                    "controller": state.cards[cid].controller,
                    "attack_target": state.attack_targets.get(cid, f"player:{defender}"),
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
    default_defender = 1 if state.active_player == 2 else 2
    _combat_damage_step(state, default_defender, first_strike_only=True)
    _remove_dead_creatures(state)
    _combat_damage_step(state, default_defender, first_strike_only=False)
    _remove_dead_creatures(state)

    state.attackers = []
    state.attack_targets = {}
    state.blocks = {}
    state.attackers_declared = False
    state.blockers_declared = False


def _combat_damage_step(state: MatchState, default_defender: int, first_strike_only: bool) -> None:
    for attacker in list(state.attackers):
        if attacker not in state.cards:
            continue
        atk = state.cards[attacker]
        if atk.zone != Zone.BATTLEFIELD:
            continue
        atk_has_fs = has_keyword(state, attacker, "first strike") or has_keyword(state, attacker, "double strike")
        if first_strike_only and not atk_has_fs:
            continue
        if not first_strike_only and has_keyword(state, attacker, "first strike") and not has_keyword(state, attacker, "double strike"):
            continue

        blocks = [b for b in state.blocks.get(attacker, []) if b in state.cards and state.cards[b].zone == Zone.BATTLEFIELD]
        defender_key = state.attack_targets.get(attacker, f"player:{default_defender}")
        if not blocks:
            dealt = _deal_unblocked_damage(state, defender_key, effective_power(state, attacker), source_id=attacker)
            if dealt > 0 and has_keyword(state, attacker, "lifelink"):
                state.players[atk.controller].life += dealt
            if dealt > 0:
                emit_event(
                    state,
                    "combat_damage_dealt",
                    {"source_card_id": attacker, "target_key": defender_key, "target_player": int(defender_key.split(":", 1)[1]) if defender_key.startswith("player:") else None, "amount": dealt},
                )
            continue

        atk_power = effective_power(state, attacker)
        remaining = atk_power
        atk_has_deathtouch = has_keyword(state, attacker, "deathtouch")
        for blocker_id in blocks:
            if remaining <= 0:
                break
            blocker = state.cards[blocker_id]
            if blocker.toughness is None:
                continue
            if _damage_prevented_by_protection(state, attacker, blocker_id):
                continue
            lethal = 1 if atk_has_deathtouch else _remaining_lethal_damage(state, blocker_id)
            dealt = min(remaining, lethal)
            _mark_creature_damage(state, blocker_id, dealt, deathtouch=atk_has_deathtouch, source_id=attacker)
            if dealt > 0 and has_keyword(state, attacker, "lifelink"):
                state.players[atk.controller].life += dealt
            if dealt > 0:
                emit_event(
                    state,
                    "combat_damage_dealt",
                    {"source_card_id": attacker, "target_card_id": blocker_id, "amount": dealt},
                )
            remaining -= dealt

        if has_keyword(state, attacker, "trample") and remaining > 0:
            dealt = _deal_unblocked_damage(state, defender_key, remaining, source_id=attacker)
            if dealt > 0 and has_keyword(state, attacker, "lifelink"):
                state.players[atk.controller].life += dealt

        atk_damage_taken = 0
        got_deathtouch_from_blocker = False
        for blocker_id in blocks:
            blk = state.cards[blocker_id]
            blk_has_fs = has_keyword(state, blocker_id, "first strike") or has_keyword(state, blocker_id, "double strike")
            if first_strike_only and not blk_has_fs:
                continue
            if not first_strike_only and has_keyword(state, blocker_id, "first strike") and not has_keyword(state, blocker_id, "double strike"):
                continue
            blk_power = effective_power(state, blocker_id)
            if _damage_prevented_by_protection(state, blocker_id, attacker):
                continue
            atk_damage_taken += blk_power
            if blk_power > 0 and has_keyword(state, blocker_id, "deathtouch"):
                got_deathtouch_from_blocker = True
            if blk_power > 0 and has_keyword(state, blocker_id, "lifelink"):
                state.players[blk.controller].life += blk_power
        if atk_damage_taken > 0:
            _mark_creature_damage(state, attacker, atk_damage_taken, deathtouch=got_deathtouch_from_blocker, source_id=blocks[0] if len(blocks) == 1 else None)


def _remove_dead_creatures(state: MatchState) -> None:
    dead: list[str] = []
    for cid, card in state.cards.items():
        if card.zone != Zone.BATTLEFIELD or "Creature" not in card.types:
            continue
        if _creature_is_lethally_damaged(state, cid):
            dead.append(cid)
    for cid in dead:
        card = state.cards[cid]
        battlefield_owner = state.players[card.controller]
        zone_owner = state.players[getattr(card, "owner", card.controller)]
        if cid in battlefield_owner.battlefield:
            choice_players = set(getattr(state, "replacement_choice_players", set()) or set())
            human_choice = getattr(state, "replacement_choice_required", False) and (
                not choice_players or card.controller in choice_players
            )
            options = replacement_options(state, "die_zone", target_card_id=cid)
            if human_choice and len(options) > 1:
                state.pending_replacement_choice = {
                    "resume_kind": "combat_die",
                    "player_id": card.controller,
                    "event": "die_zone",
                    "target_card_id": cid,
                    "options": options,
                }
                state.priority_player = card.controller
                state.passed_priority = set()
                state.log.append(
                    f"Replacement choice required for combat death; {state.players[card.controller].name} must choose one of {len(options)} effects."
                )
                return
            emit_event(state, "leaves_battlefield", {"card_id": cid, "controller": card.controller})
            battlefield_owner.battlefield.remove(cid)
            destination = replace_die_zone(state, card.controller, cid)
            if destination == "exile":
                zone_owner.exile.append(cid)
                card.zone = Zone.EXILE
                state.log.append(f"{card.name} is exiled instead of dying.")
                continue
            zone_owner.graveyard.append(cid)
            card.zone = Zone.GRAVEYARD
            state.log.append(f"{card.name} dies in combat.")
            emit_event(state, "permanent_dies", {"card_id": cid, "controller": card.controller})
            emit_event(state, "creature_dies", {"card_id": cid, "controller": card.controller})


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
        card.zone = Zone.EXILE
        state.log.append(f"{card.name} is exiled instead of dying in combat.")
        return
    zone_owner.graveyard.append(card_id)
    card.zone = Zone.GRAVEYARD
    state.log.append(f"{card.name} dies in combat.")
    emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
    emit_event(state, "creature_dies", {"card_id": card_id, "controller": card.controller})


def _can_block_attacker(state: MatchState, attacker, blocker) -> bool:
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
    state.players[pid].life -= post
    return post


def _mark_creature_damage(
    state: MatchState,
    card_id: str,
    amount: int,
    deathtouch: bool = False,
    source_id: str | None = None,
) -> None:
    if amount <= 0:
        return
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
        return
    card.counters[DMG_MARK_KEY] = int(card.counters.get(DMG_MARK_KEY, 0)) + int(post)
    if deathtouch:
        card.counters[DEATHTOUCH_MARK_KEY] = 1


def _remaining_lethal_damage(state: MatchState, card_id: str) -> int:
    card = state.cards[card_id]
    toughness = effective_toughness(state, card_id)
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    return max(1, toughness - marked)


def _creature_is_lethally_damaged(state: MatchState, card_id: str) -> bool:
    card = state.cards[card_id]
    if card.toughness is None:
        return False
    if has_keyword(state, card_id, "indestructible"):
        return False
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    if marked >= int(effective_toughness(state, card_id)):
        return True
    if int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0:
        return True
    return False
