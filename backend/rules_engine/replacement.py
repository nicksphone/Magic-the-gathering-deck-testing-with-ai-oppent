from __future__ import annotations

import re


def _battlefield_oracle_texts(state, controller: int | None = None):
    ordered: list[tuple[tuple[int, int, int, str], object, str]] = []
    battlefield_index = _battlefield_position_map(state)
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            if controller is not None and card.controller != controller:
                continue
            order_key = (
                -int(getattr(card, "static_order", 0) or 0),
                -int(getattr(card, "entered_turn", 0) or 0),
                -int(battlefield_index.get(cid, 0) or 0),
                -int(getattr(card, "instance_order", 0) or 0),
                str(cid),
            )
            ordered.append((order_key, card, (card.oracle_text or "").lower()))
    for _, card, text in sorted(ordered, key=lambda item: item[0]):
        yield card, text


def _battlefield_position_map(state) -> dict[str, int]:
    positions: dict[str, int] = {}
    position = 0
    for pid in sorted(state.players):
        for cid in state.players[pid].battlefield:
            positions[cid] = position
            position += 1
    return positions


def _matches_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


_PLAYER_DAMAGE_PREVENTION_RE = re.compile(
    r"if a source would deal damage to (?:you|you or (?:a|an|target) (?:permanent|creature) you control|(?:a|an|target) (?:permanent|creature) you control), prevent 1 of that damage"
)
_PERMANENT_DAMAGE_PREVENTION_RE = re.compile(
    r"if a source would deal damage to (?:you or (?:a|an|target) (?:permanent|creature) you control|(?:a|an|target) (?:permanent|creature) you control|(?:a|an|target) permanent you control|(?:a|an|target) creature you control), prevent 1 of that damage"
)
_DIE_EXILE_RE = re.compile(
    r"if a (?:non-token|nontoken|another )?(?:creature|permanent|artifact|enchantment|artifact or enchantment) you control would die, exile it instead"
    r"|if an? artifact or enchantment you control would die, exile it instead"
)


def apply_damage_replacements(
    state,
    target_player: int | None,
    amount: int,
    replacement_source_id: str | None = None,
) -> int:
    out = int(amount)
    if target_player is None:
        return out
    candidates = [
        (card, text)
        for card, text in _battlefield_oracle_texts(state, controller=target_player)
        if _PLAYER_DAMAGE_PREVENTION_RE.search(text)
    ]
    chosen = _choose_replacement_candidate(state, candidates, replacement_source_id, "damage to player")
    if chosen is not None:
        out = max(0, out - 1)
    return out


def apply_permanent_damage_replacements(
    state,
    target_card_id: str,
    amount: int,
    replacement_source_id: str | None = None,
) -> int:
    out = int(amount)
    if target_card_id not in state.cards:
        return out
    target = state.cards[target_card_id]
    candidates = [
        (card, text)
        for card, text in _battlefield_oracle_texts(state, controller=target.controller)
        if _PERMANENT_DAMAGE_PREVENTION_RE.search(text)
    ]
    chosen = _choose_replacement_candidate(state, candidates, replacement_source_id, f"damage to {target.name}")
    if chosen is not None:
        out = max(0, out - 1)
    return out


def replace_noncombat_damage_to_creature(
    state,
    source_card_id: str | None,
    target_card_id: str | None,
    amount: int,
) -> object | None:
    """Apply source-controlled noncombat damage replacement to a creature.

    Effects such as Soul-Scar Mage replace the event rather than reducing its
    amount. The replacement is applied once, and the resulting counters are
    checked by the normal state-based action path in the caller.
    """
    if not source_card_id or source_card_id not in state.cards or not target_card_id or target_card_id not in state.cards:
        return None
    source = state.cards[source_card_id]
    target = state.cards[target_card_id]
    if "Creature" not in (getattr(target, "types", []) or []) or source.controller == target.controller or amount <= 0:
        return None
    candidates = [
        (card, text)
        for card, text in _battlefield_oracle_texts(state, controller=source.controller)
        if (
            "would deal noncombat damage to a creature an opponent controls" in text
            or "would deal noncombat damage to a creature your opponent controls" in text
            or "would deal noncombat damage to target creature an opponent controls" in text
        )
    ]
    chosen = _choose_replacement_candidate(state, candidates, None, f"noncombat damage to {target.name}")
    if chosen is None:
        return None
    target.counters["-1/-1"] = int(target.counters.get("-1/-1", 0)) + int(amount)
    state.log.append(f"{chosen.name} replaces {amount} noncombat damage to {target.name} with -1/-1 counters.")
    return chosen


def _choose_replacement_candidate(
    state,
    candidates: list[tuple[object, str]],
    requested_source_id: str | None,
    event_label: str,
) -> object | None:
    """Choose one applicable replacement; later timestamp wins by default.

    A caller can provide the affected player's explicit source choice. The
    deterministic fallback is intentional for AI and replay callers; unlike
    the old loop, it never applies multiple mutually exclusive replacements
    to the same event without re-evaluation.
    """
    if not candidates:
        return None
    chosen = next(
        (card for card, _ in candidates if requested_source_id and str(getattr(card, "id", "")) == str(requested_source_id)),
        candidates[0][0],
    )
    if len(candidates) > 1:
        state.log.append(
            f"Replacement choice for {event_label}: {getattr(chosen, 'name', 'replacement')} selected from {len(candidates)} applicable effect(s)."
        )
    return chosen


def damage_cant_be_prevented(
    state,
    source_card_id: str | None = None,
    target_player: int | None = None,
    target_card_id: str | None = None,
    combat: bool = False,
) -> bool:
    if bool(getattr(state, "turn_damage_cant_be_prevented", False)):
        return True
    source = state.cards[source_card_id] if source_card_id and source_card_id in state.cards else None
    for card, text in _battlefield_oracle_texts(state):
        if _matches_phrase(text, ("damage can't be prevented", "damage cannot be prevented")):
            return True
        if combat and _matches_phrase(text, ("combat damage can't be prevented", "combat damage cannot be prevented")):
            return True
        if target_player == card.controller and _matches_phrase(
            text,
            (
                "damage that would be dealt to you can't be prevented",
                "damage that would be dealt to you cannot be prevented",
                "damage dealt to you can't be prevented",
                "damage dealt to you cannot be prevented",
            ),
        ):
            return True
        if target_player is not None and target_player != card.controller and _matches_phrase(
            text,
            (
                "damage that would be dealt to your opponents can't be prevented",
                "damage that would be dealt to your opponents cannot be prevented",
            ),
        ):
            return True
        if target_card_id and target_card_id in state.cards:
            target = state.cards[target_card_id]
            if target.controller == card.controller and _matches_phrase(
                text,
                (
                    "damage that would be dealt to permanents you control can't be prevented",
                    "damage that would be dealt to permanents you control cannot be prevented",
                    "damage dealt to permanents you control can't be prevented",
                    "damage dealt to permanents you control cannot be prevented",
                ),
            ):
                return True
        if source and source.controller == card.controller and _matches_phrase(
            text,
            (
                "damage that would be dealt by sources you control can't be prevented",
                "damage that would be dealt by sources you control cannot be prevented",
            ),
        ):
            return True
        if source and source.id == card.id and _matches_phrase(
            text,
            (
                "damage dealt by this creature can't be prevented",
                "damage dealt by this creature cannot be prevented",
                "damage dealt by this source can't be prevented",
                "damage dealt by this source cannot be prevented",
            ),
        ):
            return True
    return False


def replace_gain_life(
    state,
    target_player: int,
    amount: int,
    replacement_source_id: str | None = None,
) -> tuple[str, dict] | None:
    candidates = [
        (card, text)
        for card, text in _battlefield_oracle_texts(state, controller=target_player)
        if "if you would gain life, draw that many cards instead" in text
    ]
    card = _choose_replacement_candidate(state, candidates, replacement_source_id, "life gain")
    if card is not None:
        return (
            "draw_cards",
            {
                "target_player": target_player,
                "amount": int(amount),
                "__replacement_source": card.name,
                "__replacement_source_id": card.id,
            },
        )
    return None


def replace_draw_cards(
    state,
    target_player: int,
    amount: int,
    replacement_source_id: str | None = None,
) -> tuple[str, dict] | None:
    candidates = [
        (card, text)
        for card, text in _battlefield_oracle_texts(state, controller=target_player)
        if "if you would draw a card, gain 1 life instead" in text
    ]
    card = _choose_replacement_candidate(state, candidates, replacement_source_id, "card draw")
    if card is not None:
        return (
            "gain_life",
            {
                "target_player": target_player,
                "amount": int(amount),
                "__replacement_source": card.name,
                "__replacement_source_id": card.id,
            },
        )
    return None


def replace_die_zone(state, controller: int, card_id: str) -> str:
    """Return destination zone for a dying permanent: 'graveyard' or 'exile'."""
    target = state.cards.get(card_id)
    is_token = bool(target and (getattr(target, "is_token", False) or "token" in {str(t).lower() for t in (target.types or [])}))
    for card, text in _battlefield_oracle_texts(state, controller=controller):
        if is_token and ("nontoken" in text or "non-token" in text):
            continue
        if _matches_phrase(
            text,
            (
                "if a permanent you control would die, exile it instead",
                "if a non-token permanent you control would die, exile it instead",
                "if a nontoken permanent you control would die, exile it instead",
                "if a permanent would die, exile it instead",
                "if a creature you control would die, exile it instead",
                "if another creature you control would die, exile it instead",
                "if a nontoken creature you control would die, exile it instead",
                "if a non-token creature you control would die, exile it instead",
            ),
        ):
            return "exile"
        if _DIE_EXILE_RE.search(text):
            return "exile"
    return "graveyard"


def player_cant_gain_life(state, target_player: int) -> bool:
    if int(target_player) in set(getattr(state, "turn_cant_gain_life", set()) or set()):
        return True
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            text = (card.oracle_text or "").lower()
            if "players can't gain life" in text or "players cannot gain life" in text:
                return True
            if "you can't gain life" in text or "you cannot gain life" in text:
                if card.controller == target_player:
                    return True
            if card.controller == target_player:
                continue
            if "your opponents can't gain life" in text or "your opponents cannot gain life" in text:
                return True
            if "your opponent can't gain life" in text or "your opponent cannot gain life" in text:
                return True
    return False


def player_cant_lose_life(state, target_player: int) -> bool:
    for pid in state.players:
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            text = (card.oracle_text or "").lower()
            if "players can't lose life" in text or "players cannot lose life" in text:
                return True
            if card.controller == target_player and ("you can't lose life" in text or "you cannot lose life" in text):
                return True
            if card.controller != target_player and (
                "your opponents can't lose life" in text
                or "your opponents cannot lose life" in text
                or "your opponent can't lose life" in text
                or "your opponent cannot lose life" in text
            ):
                return True
    return False
