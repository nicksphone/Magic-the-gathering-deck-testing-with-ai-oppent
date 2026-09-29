from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from game_state.state import MatchState, Zone
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.replacement import can_pay_life, replace_die_zone
from rules_engine.zone_actions import is_departed_token, put_into_graveyard

ALT_COST_RE = re.compile(r"pay\s+((?:\{[^}]+\})+)\s+rather than pay this spell's mana cost", re.IGNORECASE)
KICKER_RE = re.compile(r"kicker\s+((?:\{[^}]+\})+)", re.IGNORECASE)
PAY_LIFE_RE = re.compile(r"additional cost to cast[^.]*pay\s+(\d+)\s+life", re.IGNORECASE)
PAY_X_LIFE_RE = re.compile(r"additional cost to cast[^.]*pay\s+x\s+life\b", re.IGNORECASE)
ACTIVATED_PAY_LIFE_RE = re.compile(r"pay\s+(\d+)\s+life", re.IGNORECASE)
ACTIVATED_DISCARD_RE = re.compile(r"discard\s+(?:a|one|an|\d+)\s+cards?", re.IGNORECASE)
ACTIVATED_SACRIFICE_RE = re.compile(r"sacrifice\s+(?:a|an|this|one|\d+)\s+", re.IGNORECASE)
RESTRICTED_X_PAYMENT_RE = re.compile(r"\bspend only (white|blue|black|red|green|colorless) mana on x\b", re.IGNORECASE)
RESTRICTED_X_COLORS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G", "colorless": "C"}


def restricted_x_color(ability_text: str) -> str | None:
    match = RESTRICTED_X_PAYMENT_RE.search(ability_text or "")
    return RESTRICTED_X_COLORS[match.group(1).lower()] if match else None


@dataclass
class CostOption:
    id: str
    label: str
    mana_cost: str
    pay_life: int = 0
    pay_life_x: bool = False
    discard_cards: int = 0
    sacrifice_creatures: int = 0
    sacrifice_kind: str = "creature"
    exile_graveyard: int = 0


@dataclass(frozen=True)
class ActivatedCost:
    mana_cost: str = ""
    tap_source: bool = False
    pay_life: int = 0
    discard_cards: int = 0
    sacrifice_creatures: int = 0
    sacrifice_kind: str = "creature"
    sacrifice_source: bool = False
    supported: bool = True


def parse_activated_cost(cost_text: str) -> ActivatedCost:
    """Parse common activated costs without treating them as Oracle effects."""
    mana_symbols: list[str] = []
    tap_source = False
    pay_life = discard_cards = sacrifice_creatures = 0
    sacrifice_kind = "creature"
    sacrifice_source = False
    supported = True
    for part in (segment.strip() for segment in (cost_text or "").split(",")):
        if not part:
            continue
        upper = part.upper()
        symbols = re.findall(r"\{[^}]+\}", part)
        if symbols:
            for symbol in symbols:
                if symbol.upper() == "{T}":
                    tap_source = True
                else:
                    mana_symbols.append(symbol.upper())
            remainder = re.sub(r"\{[^}]+\}", "", part).strip(" ,")
            if not remainder:
                continue
            upper = remainder.upper()
        if upper in {"T", "TAP"}:
            tap_source = True
        elif "SACRIFICE" in upper and any(term in upper for term in ("CREATURE", "ARTIFACT", "ENCHANTMENT", "PERMANENT", "TOKEN")):
            match = ACTIVATED_SACRIFICE_RE.search(upper)
            if not match:
                supported = False
                continue
            number = re.search(r"(\d+)", match.group(0))
            sacrifice_creatures += int(number.group(1)) if number else 1
            sacrifice_source = any(f"THIS {kind}" in upper for kind in ("CREATURE", "ARTIFACT", "ENCHANTMENT", "PERMANENT", "TOKEN"))
            if "THIS TOKEN" in upper:
                sacrifice_kind = "permanent"
            elif "ARTIFACT OR CREATURE" in upper:
                sacrifice_kind = "artifact_or_creature"
            elif "PERMANENT" in upper:
                sacrifice_kind = "permanent"
            elif "ARTIFACT" in upper:
                sacrifice_kind = "artifact"
            elif "ENCHANTMENT" in upper:
                sacrifice_kind = "enchantment"
        elif "DISCARD" in upper and "CARD" in upper:
            match = ACTIVATED_DISCARD_RE.search(upper)
            if not match:
                supported = False
                continue
            number = re.search(r"(\d+)", match.group(0))
            discard_cards += int(number.group(1)) if number else 1
        elif "PAY" in upper and "LIFE" in upper:
            match = ACTIVATED_PAY_LIFE_RE.search(upper)
            if not match:
                supported = False
                continue
            pay_life += int(match.group(1))
        else:
            supported = False
    return ActivatedCost(
        mana_cost="".join(mana_symbols),
        tap_source=tap_source,
        pay_life=pay_life,
        discard_cards=discard_cards,
        sacrifice_creatures=sacrifice_creatures,
        sacrifice_kind=sacrifice_kind,
        sacrifice_source=sacrifice_source,
        supported=supported,
    )


def activated_cost_available(state: MatchState, player_id: int, source_id: str, cost_text: str, hybrid_choices: list[str] | None = None, x_value: int = 0, restricted_x_color: str | None = None) -> bool:
    cost = parse_activated_cost(cost_text)
    if not cost.supported or x_value < 0:
        return False
    source = state.cards[source_id]
    player = state.players[player_id]
    if cost.tap_source and source.tapped:
        return False
    if not can_pay_life(state, player_id, cost.pay_life) or sum(not is_departed_token(state.cards[cid]) for cid in player.hand) < cost.discard_cards:
        return False
    creatures = _eligible_sacrifice_ids(state, player_id, cost.sacrifice_kind)
    if cost.sacrifice_source:
        if source_id not in creatures:
            return False
        creatures.remove(source_id)
    if len(creatures) < max(0, cost.sacrifice_creatures - (1 if cost.sacrifice_source else 0)):
        return False
    return not cost.mana_cost or can_pay_with_pool_and_lands(
        state, player_id, cost.mana_cost, card_name=source.name, reserved_life=cost.pay_life,
        hybrid_choices=hybrid_choices, x_value=x_value, restricted_x_color=restricted_x_color,
    )


def apply_activated_costs(state: MatchState, player_id: int, source_id: str, cost_text: str, *, context: dict | None = None, hybrid_choices: list[str] | None = None, x_value: int = 0, restricted_x_color: str | None = None) -> bool:
    cost = parse_activated_cost(cost_text)
    if not activated_cost_available(state, player_id, source_id, cost_text, hybrid_choices, x_value, restricted_x_color):
        return False
    player = state.players[player_id]
    source = state.cards[source_id]
    if cost.mana_cost and not _pay_activated_mana(state, player_id, cost.mana_cost, source.name, cost.pay_life, hybrid_choices, x_value, restricted_x_color):
        return False
    if cost.tap_source:
        source.tapped = True
    if cost.pay_life:
        from rules_engine.replacement import pay_life
        pay_life(state, player_id, cost.pay_life)
        state.log.append(f"{player.name} pays {cost.pay_life} life for {source.name}.")
    from rules_engine.events import emit_event
    for _ in range(cost.discard_cards):
        discard_id = _first_discardable_card(state, player_id, exclude={source_id})
        if discard_id is None:
            return False
        player.hand.remove(discard_id)
        put_into_graveyard(state, discard_id)
        state.log.append(f"{player.name} discards {state.cards[discard_id].name} for {source.name}.")
        emit_event(state, "discard", {"card_id": discard_id, "controller": player_id})
    sacrifice_ids: list[str] = []
    if cost.sacrifice_source:
        sacrifice_ids.append(source_id)
    sacrifice_ids.extend(cid for cid in _eligible_sacrifice_ids(state, player_id, cost.sacrifice_kind) if cid != source_id)
    needed = cost.sacrifice_creatures
    destinations = {cid: replace_die_zone(state, state.cards[cid].controller, cid) for cid in sacrifice_ids[:needed]}
    for sac_id in sacrifice_ids[:needed]:
        if context is not None and "Creature" in state.cards[sac_id].types:
            from rules_engine.continuous import effective_toughness
            context["__sacrificed_toughness"] = effective_toughness(state, sac_id)
        if sac_id in player.battlefield:
            player.battlefield.remove(sac_id)
        card = state.cards[sac_id]
        owner = state.players[getattr(card, "owner", player_id)]
        if destinations[sac_id] == "exile":
            owner.exile.append(sac_id)
            card.zone = Zone.EXILE
        else:
            put_into_graveyard(state, sac_id)
        state.log.append(f"{player.name} sacrifices {card.name} for {source.name}.")
        emit_event(state, "sacrifice", {"card_id": sac_id, "controller": player_id})
        card.reset_zone_counters(card.zone)
    return True


def _pay_activated_mana(state: MatchState, player_id: int, mana_cost: str, card_name: str, reserved_life: int = 0, hybrid_choices: list[str] | None = None, x_value: int = 0, restricted_x_color: str | None = None) -> bool:
    from rules_engine.mana import auto_pay_cost

    return auto_pay_cost(state, player_id, mana_cost, card_name=card_name, reserved_life=reserved_life, hybrid_choices=hybrid_choices, x_value=x_value, restricted_x_color=restricted_x_color)


def collect_cost_options(state: MatchState, player_id: int, card) -> list[CostOption]:
    from rules_engine.alternative_casts import escape_cost, flashback_cost, prototype_characteristics
    oracle = (card.oracle_text or "").lower()
    base = CostOption(id="base", label="Base Cost", mana_cost=card.mana_cost or "")
    escape = escape_cost(card) if card.zone == Zone.GRAVEYARD else None
    flashback = flashback_cost(card) if card.zone == Zone.GRAVEYARD else None
    if card.zone == Zone.GRAVEYARD:
        options = []
        if escape:
            options.append(CostOption(id="escape", label="Escape", mana_cost=escape[0], exile_graveyard=escape[1]))
        if flashback:
            options.append(CostOption(id="flashback", label="Flashback", mana_cost=flashback))
        if not options:
            return []
    else:
        options = [base]
    prototype = prototype_characteristics(card)
    if prototype and card.zone != Zone.GRAVEYARD:
        options.append(CostOption(id="prototype", label="Prototype", mana_cost=prototype["mana_cost"]))

    alt = ALT_COST_RE.search(card.oracle_text or "")
    if alt and card.zone != Zone.GRAVEYARD:
        options.append(CostOption(id="alternate", label=f"Alternate {alt.group(1)}", mana_cost=alt.group(1)))

    kicker = KICKER_RE.search(card.oracle_text or "")
    if kicker and card.zone != Zone.GRAVEYARD:
        options.append(CostOption(id="kicker", label=f"Kicker {kicker.group(1)}", mana_cost=_join_costs(base.mana_cost, kicker.group(1))))

    life_match = PAY_LIFE_RE.search(card.oracle_text or "")
    if life_match:
        life = int(life_match.group(1))
        for opt in options:
            opt.pay_life += life
    if PAY_X_LIFE_RE.search(card.oracle_text or ""):
        for opt in options:
            opt.pay_life_x = True

    if "as an additional cost to cast" in oracle and "discard" in oracle and "card" in oracle:
        for opt in options:
            opt.discard_cards += 1
    if "as an additional cost to cast" in oracle and "sacrifice" in oracle:
        sacrifice_kind = "creature"
        if "artifact or creature" in oracle:
            sacrifice_kind = "artifact_or_creature"
        elif "permanent" in oracle:
            sacrifice_kind = "permanent"
        elif "artifact" in oracle:
            sacrifice_kind = "artifact"
        elif "enchantment" in oracle:
            sacrifice_kind = "enchantment"
        for opt in options:
            opt.sacrifice_creatures += 1
            opt.sacrifice_kind = sacrifice_kind

    return options


def check_cost_option_available(state: MatchState, player_id: int, card, option: CostOption, x_value: int = 0) -> bool:
    player = state.players[player_id]
    if x_value < 0:
        return False
    if option.exile_graveyard and len([cid for cid in player.graveyard if cid != card.id and not is_departed_token(state.cards[cid])]) < option.exile_graveyard:
        return False
    if not can_pay_life(state, player_id, option.pay_life + (x_value if option.pay_life_x else 0)):
        return False
    if sum(cid != card.id and not is_departed_token(state.cards[cid]) for cid in player.hand) < option.discard_cards:
        return False
    if len(_eligible_sacrifice_ids(state, player_id, option.sacrifice_kind)) < option.sacrifice_creatures:
        return False
    return can_pay_with_pool_and_lands(
        state, player_id, option.mana_cost, is_land=("Land" in card.types),
        card_name=card.name, x_value=x_value, spell_types=set(card.types),
        oracle_text=card.oracle_text or "",
        reserved_life=option.pay_life + (x_value if option.pay_life_x else 0),
    )


def normalize_cost_choice(action: dict[str, Any], options: list[CostOption]) -> CostOption:
    choice_id = (action.get("cost_choice") or {}).get("id")
    if choice_id:
        for option in options:
            if option.id == choice_id:
                return option
    return options[0]


def apply_additional_costs(state: MatchState, player_id: int, option: CostOption, spell_card_id: str, x_value: int = 0) -> bool:
    player = state.players[player_id]
    life_amount = option.pay_life + (x_value if option.pay_life_x else 0)
    if x_value < 0 or not can_pay_life(state, player_id, life_amount):
        return False
    if life_amount:
        from rules_engine.replacement import pay_life
        if not pay_life(state, player_id, life_amount):
            return False
        state.log.append(f"{player.name} pays {life_amount} life as an additional cost.")

    for _ in range(option.discard_cards):
        discard_id = _first_discardable_card(state, player_id, exclude={spell_card_id})
        if not discard_id:
            return False
        player.hand.remove(discard_id)
        put_into_graveyard(state, discard_id)
        state.log.append(f"{player.name} discards {state.cards[discard_id].name} for additional cost.")
        from rules_engine.events import emit_event

        emit_event(state, "discard", {"card_id": discard_id, "controller": player_id})

    for _ in range(option.sacrifice_creatures):
        sac_id = _first_sacrificable_creature(state, player_id, option.sacrifice_kind)
        if not sac_id:
            return False
        destination = replace_die_zone(state, player_id, sac_id)
        player.battlefield.remove(sac_id)
        card = state.cards[sac_id]
        zone_owner = state.players[getattr(card, "owner", player_id)]
        if destination == "exile":
            zone_owner.exile.append(sac_id)
            card.zone = Zone.EXILE
            state.log.append(f"{player.name} sacrifices {card.name} for additional cost, but it is exiled instead of dying.")
        else:
            put_into_graveyard(state, sac_id)
            state.log.append(f"{player.name} sacrifices {card.name} for additional cost.")
        from rules_engine.events import emit_event

        emit_event(state, "sacrifice", {"card_id": sac_id, "controller": player_id})
        card.reset_zone_counters(card.zone)

    return True


def _join_costs(a: str, b: str) -> str:
    return (a or "") + (b or "")


def _first_discardable_card(state: MatchState, player_id: int, exclude: set[str]) -> str | None:
    for cid in state.players[player_id].hand:
        if cid not in exclude and not is_departed_token(state.cards[cid]):
            return cid
    return None


def _eligible_sacrifice_ids(state: MatchState, player_id: int, kind: str = "creature") -> list[str]:
    eligible: list[str] = []
    for cid in state.players[player_id].battlefield:
        types = set(state.cards[cid].types or [])
        if (
            kind == "permanent"
            or (kind == "artifact_or_creature" and ("Artifact" in types or "Creature" in types))
            or (kind == "artifact" and "Artifact" in types)
            or (kind == "enchantment" and "Enchantment" in types)
            or (kind == "creature" and "Creature" in types)
        ):
            eligible.append(cid)
    return eligible


def _first_sacrificable_creature(state: MatchState, player_id: int, kind: str = "creature") -> str | None:
    eligible = _eligible_sacrifice_ids(state, player_id, kind)
    return eligible[0] if eligible else None
