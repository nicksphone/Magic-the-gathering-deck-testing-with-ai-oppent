from __future__ import annotations

from game_state.state import MatchState, Zone
from rules_engine.events import emit_event

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"


def declare_attackers(state: MatchState, attacker_ids: list[str], attack_targets: dict[str, str] | None = None) -> None:
    attack_targets = attack_targets or {}
    legal: list[str] = []
    legal_targets: dict[str, str] = {}
    defender = 1 if state.active_player == 2 else 2
    valid_defenders = _valid_defenders(state, defender)
    for cid in attacker_ids:
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
        if card.summoning_sick and "haste" not in [k.lower() for k in card.keywords]:
            continue
        legal.append(cid)
        desired = attack_targets.get(cid, f"player:{defender}")
        legal_targets[cid] = desired if desired in valid_defenders else f"player:{defender}"
        card.tapped = True
    state.attackers = legal
    state.attack_targets = legal_targets
    if legal:
        names = ", ".join(
            f"{state.cards[c].name} -> {_defender_label(state, state.attack_targets.get(c, f'player:{defender}'))}"
            for c in legal
        )
        state.log.append(f"Attackers declared: {names}")


def declare_blockers(state: MatchState, blocks: dict[str, str | list[str]]) -> None:
    defender = 1 if state.active_player == 2 else 2
    legal: dict[str, list[str]] = {}
    used_blockers: set[str] = set()
    for attacker, blockers in blocks.items():
        if attacker not in state.attackers:
            continue
        blocker_list = blockers if isinstance(blockers, list) else [blockers]
        picked: list[str] = []
        for blocker in blocker_list:
            if blocker not in state.cards or blocker in used_blockers:
                continue
            block_card = state.cards[blocker]
            if block_card.controller != defender:
                continue
            if block_card.tapped:
                continue
            if "Creature" not in block_card.types:
                continue
            atk_card = state.cards[attacker]
            if not _can_block_attacker(atk_card, block_card):
                continue
            picked.append(blocker)
            used_blockers.add(blocker)
        if picked:
            legal[attacker] = picked
    # Menace: must be blocked by two or more creatures.
    for attacker in list(legal.keys()):
        atk_card = state.cards.get(attacker)
        if atk_card and _has_keyword(atk_card, "menace") and len(legal[attacker]) < 2:
            for blocker in legal[attacker]:
                used_blockers.discard(blocker)
            legal.pop(attacker, None)
    state.blocks = legal


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


def _combat_damage_step(state: MatchState, default_defender: int, first_strike_only: bool) -> None:
    for attacker in list(state.attackers):
        if attacker not in state.cards:
            continue
        atk = state.cards[attacker]
        if atk.zone != Zone.BATTLEFIELD:
            continue
        atk_has_fs = _has_keyword(atk, "first strike") or _has_keyword(atk, "double strike")
        if first_strike_only and not atk_has_fs:
            continue
        if not first_strike_only and _has_keyword(atk, "first strike") and not _has_keyword(atk, "double strike"):
            continue

        blocks = [b for b in state.blocks.get(attacker, []) if b in state.cards and state.cards[b].zone == Zone.BATTLEFIELD]
        defender_key = state.attack_targets.get(attacker, f"player:{default_defender}")
        if not blocks:
            dealt = _deal_unblocked_damage(state, defender_key, atk.power or 0)
            if dealt > 0 and _has_keyword(atk, "lifelink"):
                state.players[atk.controller].life += dealt
            continue

        atk_power = atk.power or 0
        remaining = atk_power
        atk_has_deathtouch = _has_keyword(atk, "deathtouch")
        for blocker_id in blocks:
            if remaining <= 0:
                break
            blocker = state.cards[blocker_id]
            if blocker.toughness is None:
                continue
            lethal = 1 if atk_has_deathtouch else _remaining_lethal_damage(blocker)
            dealt = min(remaining, lethal)
            _mark_creature_damage(blocker, dealt, deathtouch=atk_has_deathtouch)
            if dealt > 0 and _has_keyword(atk, "lifelink"):
                state.players[atk.controller].life += dealt
            remaining -= dealt

        if _has_keyword(atk, "trample") and remaining > 0:
            dealt = _deal_unblocked_damage(state, defender_key, remaining)
            if dealt > 0 and _has_keyword(atk, "lifelink"):
                state.players[atk.controller].life += dealt

        atk_damage_taken = 0
        got_deathtouch_from_blocker = False
        for blocker_id in blocks:
            blk = state.cards[blocker_id]
            blk_has_fs = _has_keyword(blk, "first strike") or _has_keyword(blk, "double strike")
            if first_strike_only and not blk_has_fs:
                continue
            if not first_strike_only and _has_keyword(blk, "first strike") and not _has_keyword(blk, "double strike"):
                continue
            blk_power = blk.power or 0
            atk_damage_taken += blk_power
            if blk_power > 0 and _has_keyword(blk, "deathtouch"):
                got_deathtouch_from_blocker = True
            if blk_power > 0 and _has_keyword(blk, "lifelink"):
                state.players[blk.controller].life += blk_power
        if atk_damage_taken > 0:
            _mark_creature_damage(atk, atk_damage_taken, deathtouch=got_deathtouch_from_blocker)


def _remove_dead_creatures(state: MatchState) -> None:
    dead: list[str] = []
    for cid, card in state.cards.items():
        if card.zone != Zone.BATTLEFIELD or "Creature" not in card.types:
            continue
        if _creature_is_lethally_damaged(card):
            dead.append(cid)
    for cid in dead:
        card = state.cards[cid]
        owner = state.players[card.controller]
        if cid in owner.battlefield:
            owner.battlefield.remove(cid)
            owner.graveyard.append(cid)
            card.zone = Zone.GRAVEYARD
            state.log.append(f"{card.name} dies in combat.")
            emit_event(state, "creature_dies", {"card_id": cid, "controller": card.controller})


def _has_keyword(card, keyword: str) -> bool:
    return keyword.lower() in [k.lower() for k in card.keywords]


def _can_block_attacker(attacker, blocker) -> bool:
    # Flying can only be blocked by flying or reach.
    if _has_keyword(attacker, "flying"):
        return _has_keyword(blocker, "flying") or _has_keyword(blocker, "reach")
    return True


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


def _deal_unblocked_damage(state: MatchState, defender_key: str, amount: int) -> None:
    if amount <= 0:
        return 0
    if defender_key.startswith("planeswalker:"):
        cid = defender_key.split(":", 1)[1]
        card = state.cards.get(cid)
        if card and "Planeswalker" in card.types and card.zone == Zone.BATTLEFIELD:
            card.loyalty = (card.loyalty or 0) - amount
            state.log.append(f"{card.name} loses {amount} loyalty.")
            return amount
    pid = int(defender_key.split(":", 1)[1]) if defender_key.startswith("player:") else 2
    state.players[pid].life -= amount
    return amount


def _mark_creature_damage(card, amount: int, deathtouch: bool = False) -> None:
    if amount <= 0:
        return
    card.counters[DMG_MARK_KEY] = int(card.counters.get(DMG_MARK_KEY, 0)) + int(amount)
    if deathtouch:
        card.counters[DEATHTOUCH_MARK_KEY] = 1


def _remaining_lethal_damage(card) -> int:
    toughness = card.toughness or 0
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    return max(1, toughness - marked)


def _creature_is_lethally_damaged(card) -> bool:
    if card.toughness is None:
        return False
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    if marked >= int(card.toughness):
        return True
    if int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0:
        return True
    return False
