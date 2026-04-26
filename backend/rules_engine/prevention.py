from __future__ import annotations


PLAYER_SHIELD_KEY = "prevent_damage_shield"
CARD_SHIELD_KEY = "__prevent_damage_shield"


def add_player_prevention_shield(state, player_id: int, amount: int) -> None:
    if amount <= 0:
        return
    player = state.players[player_id]
    current = int(getattr(player, PLAYER_SHIELD_KEY, 0))
    setattr(player, PLAYER_SHIELD_KEY, current + int(amount))


def add_card_prevention_shield(card, amount: int) -> None:
    if amount <= 0:
        return
    card.counters[CARD_SHIELD_KEY] = int(card.counters.get(CARD_SHIELD_KEY, 0)) + int(amount)


def consume_player_prevention_shield(state, player_id: int, amount: int) -> tuple[int, int]:
    if amount <= 0:
        return 0, 0
    player = state.players[player_id]
    shield = int(getattr(player, PLAYER_SHIELD_KEY, 0))
    prevented = min(shield, int(amount))
    setattr(player, PLAYER_SHIELD_KEY, max(0, shield - prevented))
    return int(amount) - prevented, prevented


def consume_card_prevention_shield(card, amount: int) -> tuple[int, int]:
    if amount <= 0:
        return 0, 0
    shield = int(card.counters.get(CARD_SHIELD_KEY, 0))
    prevented = min(shield, int(amount))
    card.counters[CARD_SHIELD_KEY] = max(0, shield - prevented)
    if int(card.counters.get(CARD_SHIELD_KEY, 0)) == 0:
        card.counters.pop(CARD_SHIELD_KEY, None)
    return int(amount) - prevented, prevented
