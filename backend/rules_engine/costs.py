from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from game_state.state import MatchState, Zone
from rules_engine.mana import can_pay_with_pool_and_lands

ALT_COST_RE = re.compile(r"pay\s+((?:\{[^}]+\})+)\s+rather than pay this spell's mana cost", re.IGNORECASE)
KICKER_RE = re.compile(r"kicker\s+((?:\{[^}]+\})+)", re.IGNORECASE)
PAY_LIFE_RE = re.compile(r"additional cost to cast[^.]*pay\s+(\d+)\s+life", re.IGNORECASE)


@dataclass
class CostOption:
    id: str
    label: str
    mana_cost: str
    pay_life: int = 0
    discard_cards: int = 0
    sacrifice_creatures: int = 0


def collect_cost_options(state: MatchState, player_id: int, card) -> list[CostOption]:
    oracle = (card.oracle_text or "").lower()
    base = CostOption(id="base", label="Base Cost", mana_cost=card.mana_cost or "")
    options = [base]

    alt = ALT_COST_RE.search(card.oracle_text or "")
    if alt:
        options.append(CostOption(id="alternate", label=f"Alternate {alt.group(1)}", mana_cost=alt.group(1)))

    kicker = KICKER_RE.search(card.oracle_text or "")
    if kicker:
        options.append(CostOption(id="kicker", label=f"Kicker {kicker.group(1)}", mana_cost=_join_costs(base.mana_cost, kicker.group(1))))

    life_match = PAY_LIFE_RE.search(card.oracle_text or "")
    if life_match:
        life = int(life_match.group(1))
        for opt in options:
            opt.pay_life += life

    if "as an additional cost to cast" in oracle and "discard" in oracle and "card" in oracle:
        for opt in options:
            opt.discard_cards += 1
    if "as an additional cost to cast" in oracle and "sacrifice" in oracle and "creature" in oracle:
        for opt in options:
            opt.sacrifice_creatures += 1

    return options


def check_cost_option_available(state: MatchState, player_id: int, card, option: CostOption, x_value: int = 0) -> bool:
    player = state.players[player_id]
    if player.life <= option.pay_life:
        return False
    if len(player.hand) <= option.discard_cards:
        return False
    if sum(1 for cid in player.battlefield if "Creature" in state.cards[cid].types) < option.sacrifice_creatures:
        return False
    return can_pay_with_pool_and_lands(state, player_id, option.mana_cost, is_land=("Land" in card.types), card_name=card.name, x_value=x_value)


def normalize_cost_choice(action: dict[str, Any], options: list[CostOption]) -> CostOption:
    choice_id = (action.get("cost_choice") or {}).get("id")
    if choice_id:
        for option in options:
            if option.id == choice_id:
                return option
    return options[0]


def apply_additional_costs(state: MatchState, player_id: int, option: CostOption, spell_card_id: str) -> bool:
    player = state.players[player_id]
    if option.pay_life:
        player.life -= option.pay_life
        state.log.append(f"{player.name} pays {option.pay_life} life as an additional cost.")

    for _ in range(option.discard_cards):
        discard_id = _first_discardable_card(state, player_id, exclude={spell_card_id})
        if not discard_id:
            return False
        player.hand.remove(discard_id)
        player.graveyard.append(discard_id)
        state.cards[discard_id].zone = Zone.GRAVEYARD
        state.log.append(f"{player.name} discards {state.cards[discard_id].name} for additional cost.")

    for _ in range(option.sacrifice_creatures):
        sac_id = _first_sacrificable_creature(state, player_id)
        if not sac_id:
            return False
        player.battlefield.remove(sac_id)
        player.graveyard.append(sac_id)
        state.cards[sac_id].zone = Zone.GRAVEYARD
        state.log.append(f"{player.name} sacrifices {state.cards[sac_id].name} for additional cost.")

    return True


def _join_costs(a: str, b: str) -> str:
    return (a or "") + (b or "")


def _first_discardable_card(state: MatchState, player_id: int, exclude: set[str]) -> str | None:
    for cid in state.players[player_id].hand:
        if cid not in exclude:
            return cid
    return None


def _first_sacrificable_creature(state: MatchState, player_id: int) -> str | None:
    for cid in state.players[player_id].battlefield:
        if "Creature" in state.cards[cid].types:
            return cid
    return None
