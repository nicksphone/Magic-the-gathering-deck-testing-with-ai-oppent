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


def apply_damage_replacements(state, target_player: int | None, amount: int) -> int:
    out = int(amount)
    if target_player is None:
        return out
    for card, text in _battlefield_oracle_texts(state, controller=target_player):
        if _PLAYER_DAMAGE_PREVENTION_RE.search(text):
            out = max(0, out - 1)
    return out


def apply_permanent_damage_replacements(state, target_card_id: str, amount: int) -> int:
    out = int(amount)
    if target_card_id not in state.cards:
        return out
    target = state.cards[target_card_id]
    for card, text in _battlefield_oracle_texts(state, controller=target.controller):
        if _PERMANENT_DAMAGE_PREVENTION_RE.search(text):
            out = max(0, out - 1)
    return out


def damage_cant_be_prevented(
    state,
    source_card_id: str | None = None,
    target_player: int | None = None,
    target_card_id: str | None = None,
    combat: bool = False,
) -> bool:
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


def replace_gain_life(state, target_player: int, amount: int) -> tuple[str, dict] | None:
    for card, text in _battlefield_oracle_texts(state, controller=target_player):
        if "if you would gain life, draw that many cards instead" in text:
            return (
                "draw_cards",
                {"target_player": target_player, "amount": int(amount), "__replacement_source": card.name},
            )
    return None


def replace_draw_cards(state, target_player: int, amount: int) -> tuple[str, dict] | None:
    for card, text in _battlefield_oracle_texts(state, controller=target_player):
        if "if you would draw a card, gain 1 life instead" in text:
            return (
                "gain_life",
                {"target_player": target_player, "amount": int(amount), "__replacement_source": card.name},
            )
    return None


def replace_die_zone(state, controller: int, card_id: str) -> str:
    """Return destination zone for a dying permanent: 'graveyard' or 'exile'."""
    for card, text in _battlefield_oracle_texts(state, controller=controller):
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
