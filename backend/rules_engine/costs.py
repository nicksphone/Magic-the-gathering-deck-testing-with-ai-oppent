from __future__ import annotations
from rules_engine.type_effects import effective_types

import re
from dataclasses import dataclass, replace
from typing import Any

from game_state.state import MatchState, Zone
from rules_engine.mana import can_pay_with_pool_and_lands
from rules_engine.replacement import can_pay_life, cost_payment_is_prohibited, replace_die_zone
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
    discard_x: bool = False
    discard_all: bool = False
    sacrifice_all: bool = False
    sacrifice_creatures: int = 0
    sacrifice_kind: str = "creature"
    exile_graveyard: int = 0
    additional_cost_group: str | None = None
    kicked: bool = False
    kicker_base_id: str | None = None


def casting_method(cost_id: str) -> str:
    """Additional-cost branch suffixes do not change the casting method."""
    return cost_id.partition('_')[0]


@dataclass(frozen=True)
class ActivatedCost:
    mana_cost: str = ""
    tap_source: bool = False
    pay_life: int = 0
    discard_cards: int = 0
    discard_source: bool = False
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
    discard_source = False
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
            if upper == 'DISCARD THIS CARD':
                discard_source = True
                continue
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
        discard_source=discard_source,
        sacrifice_creatures=sacrifice_creatures,
        sacrifice_kind=sacrifice_kind,
        sacrifice_source=sacrifice_source,
        supported=supported,
    )


def activated_cost_candidates(state, player_id, source_id, cost, unavailable_resources=()):
    fixed_discard = [source_id] if cost.discard_source else []
    fixed_sacrifice = [source_id] if cost.sacrifice_source else []
    return {
        'pay_life': cost.pay_life,
        'discard_cards': cost.discard_cards + len(fixed_discard),
        'sacrifice_creatures': cost.sacrifice_creatures,
        'fixed_discard_card_ids': fixed_discard,
        'fixed_sacrifice_card_ids': fixed_sacrifice,
        'discard_card_ids': [cid for cid in state.players[player_id].hand
                             if cid not in unavailable_resources and (cid != source_id or cost.discard_source) and not is_departed_token(state.cards[cid])]
                            if cost.discard_cards or cost.discard_source else [],
        'sacrifice_card_ids': sorted(
            (cid for cid in _eligible_sacrifice_ids(state, player_id, cost.sacrifice_kind, payment_kind='activation')
             if cid not in unavailable_resources),
            key=lambda cid: cid == source_id,
        ) if cost.sacrifice_creatures else [],
    }


def activated_cost_selection(state, player_id, source_id, cost, choice=None, unavailable_resources=()):
    if choice is not None and (not isinstance(choice, dict)
                              or set(choice) - {'discard_card_ids', 'sacrifice_card_ids'}):
        return None
    candidates = activated_cost_candidates(state, player_id, source_id, cost, unavailable_resources)
    selected = {}
    for key, count_key, fixed_key in (
        ('discard_card_ids', 'discard_cards', 'fixed_discard_card_ids'),
        ('sacrifice_card_ids', 'sacrifice_creatures', 'fixed_sacrifice_card_ids'),
    ):
        count, fixed = candidates[count_key], candidates[fixed_key]
        ids = (choice or {}).get(key)
        if ids is None:
            ids = fixed + [cid for cid in candidates[key] if cid not in fixed][:max(0, count-len(fixed))]
        if (not isinstance(ids, list) or any(not isinstance(cid, str) for cid in ids)
                or len(ids) != count or len(set(ids)) != count
                or any(cid not in candidates[key] for cid in ids)
                or any(cid not in ids for cid in fixed)):
            return None
        selected[key] = list(ids)
    return selected


def _activation_selections(state, player_id, source_id, cost, choice, unavailable_resources):
    from itertools import combinations
    if choice is not None and (not isinstance(choice, dict)
                              or set(choice) - {'discard_card_ids', 'sacrifice_card_ids'}):
        return
    candidates = activated_cost_candidates(state, player_id, source_id, cost, unavailable_resources)
    groups = [('discard_card_ids', 'discard_cards'), ('sacrifice_card_ids', 'sacrifice_creatures')]

    def select(index, selected):
        if index == len(groups):
            validated = activated_cost_selection(state, player_id, source_id, cost, selected, unavailable_resources)
            if validated is not None:
                yield validated
            return
        key, count_key = groups[index]
        explicit = (choice or {}).get(key)
        if explicit is not None:
            yield from select(index + 1, {**selected, key: explicit})
            return
        fixed = candidates['fixed_' + key]
        remaining = candidates[count_key] - len(fixed)
        if remaining < 0 or any(cid not in candidates[key] for cid in fixed):
            return
        options = [cid for cid in candidates[key] if cid not in fixed]
        for ids in combinations(options, remaining):
            yield from select(index + 1, {**selected, key: fixed + list(ids)})

    yield from select(0, {})


def _payable_activation_selection(state, player_id, source_id, cost, hybrid_choices, x_value,
                                 restricted_x_color, ability_kind, ability_index, payment_choices,
                                 unavailable_resources, protected_life=0):
    source = state.cards[source_id]
    for selected in _activation_selections(state, player_id, source_id, cost, payment_choices, unavailable_resources):
        reserved = set(unavailable_resources) | set(selected['discard_card_ids']) | set(selected['sacrifice_card_ids'])
        if can_pay_with_pool_and_lands(
            state, player_id, cost.mana_cost, card_name=source.name, reserved_life=cost.pay_life,
            hybrid_choices=hybrid_choices, x_value=x_value, restricted_x_color=restricted_x_color,
            payment_kind='activation', payment_types=set(effective_types(state, source)),
            ability_kind=ability_kind, source_card_id=source_id, ability_index=ability_index,
            excluded_sources={source_id} if cost.tap_source else None, reserved_card_ids=reserved,
            protected_life=protected_life,
        ):
            return selected
    return None


def activated_cost_available(state: MatchState, player_id: int, source_id: str, cost_text: str, hybrid_choices: list[str] | None = None, x_value: int = 0, restricted_x_color: str | None = None, *, ability_kind='activated', ability_index=None, payment_choices=None, unavailable_resources=(), protected_life=0) -> bool:
    cost = parse_activated_cost(cost_text)
    if not cost.supported or x_value < 0:
        return False
    source = state.cards[source_id]
    player = state.players[player_id]
    if cost.tap_source and (source.zone != Zone.BATTLEFIELD or source.tapped):
        return False
    if cost.discard_source and (source_id not in player.hand or source.zone != Zone.HAND):
        return False
    if not can_pay_life(state, player_id, cost.pay_life + protected_life):
        return False
    return _payable_activation_selection(state, player_id, source_id, cost, hybrid_choices, x_value,
        restricted_x_color, ability_kind, ability_index, payment_choices, unavailable_resources, protected_life) is not None


def apply_activated_costs(state: MatchState, player_id: int, source_id: str, cost_text: str, *, context: dict | None = None, hybrid_choices: list[str] | None = None, x_value: int = 0, restricted_x_color: str | None = None, ability_kind='activated', ability_index=None, payment_choices=None, unavailable_resources=(), protected_life=0) -> bool:
    cost = parse_activated_cost(cost_text)
    if not activated_cost_available(state, player_id, source_id, cost_text, hybrid_choices, x_value, restricted_x_color, ability_kind=ability_kind, ability_index=ability_index, payment_choices=payment_choices, unavailable_resources=unavailable_resources, protected_life=protected_life):
        return False
    player = state.players[player_id]
    source = state.cards[source_id]
    selected = _payable_activation_selection(state, player_id, source_id, cost, hybrid_choices, x_value,
        restricted_x_color, ability_kind, ability_index, payment_choices, unavailable_resources, protected_life)
    if selected is None:
        return False
    reserved = set(unavailable_resources) | set(selected['discard_card_ids']) | set(selected['sacrifice_card_ids'])
    if not _pay_activated_mana(state, player_id, cost.mana_cost, source.name, cost.pay_life, hybrid_choices, x_value, restricted_x_color, set(effective_types(state, source)), source_id, ability_kind, {source_id} if cost.tap_source else None, ability_index, reserved, protected_life):
        return False
    selected = activated_cost_selection(state, player_id, source_id, cost, selected, unavailable_resources)
    if selected is None:
        return False
    if cost.tap_source:
        from rules_engine.resource_events import tap_permanents
        tap_permanents(state, [source_id])
    if cost.pay_life:
        from rules_engine.replacement import pay_life
        if not pay_life(state, player_id, cost.pay_life):
            return False
        state.log.append(f"{player.name} pays {cost.pay_life} life for {source.name}.")
    from rules_engine.events import emit_event, emit_event_batch, flush_staged_triggers, was_creature_on_battlefield
    if cost.discard_source:
        from rules_engine.zone_actions import discard_selected
        if not discard_selected(state, player_id, [source_id]):
            return False
    for discard_id in selected['discard_card_ids']:
        if cost.discard_source and discard_id == source_id:
            continue
        player.hand.remove(discard_id)
        put_into_graveyard(state, discard_id)
        state.log.append(f"{player.name} discards {state.cards[discard_id].name} for {source.name}.")
        emit_event(state, "discard", {"card_id": discard_id, "controller": player_id})
    sacrifice_ids = selected['sacrifice_card_ids']
    destinations = {cid: replace_die_zone(state, state.cards[cid].controller, cid) for cid in sacrifice_ids}
    events = [{"card_id": cid, "controller": player_id} for cid in sacrifice_ids]
    started_staging = bool(events) and not state.trigger_staging
    if started_staging:
        state.trigger_staging = True
        state.trigger_staging_event = "ability_activation"
    for sac_id in sacrifice_ids:
        if context is not None and "Creature" in effective_types(state, state.cards[sac_id]):
            from rules_engine.continuous import effective_toughness
            context["__sacrificed_toughness"] = effective_toughness(state, sac_id)
    emit_event_batch(state, "leaves_battlefield", events)
    for sac_id in sacrifice_ids:
        if sac_id in player.battlefield:
            player.battlefield.remove(sac_id)
        card = state.cards[sac_id]
        owner = state.players[getattr(card, "owner", player_id)]
        zone = Zone.EXILE if destinations[sac_id] == "exile" else Zone.GRAVEYARD
        getattr(owner, zone.value).append(sac_id)
        card.zone = zone
        state.log.append(f"{player.name} sacrifices {card.name} for {source.name}.")
    emit_event_batch(state, "sacrifice", events)
    died = [event for event in events if state.cards[event["card_id"]].zone == Zone.GRAVEYARD]
    emit_event_batch(state, "permanent_dies", died)
    emit_event_batch(state, "creature_dies", [event for event in died if was_creature_on_battlefield(state.cards[event["card_id"]])])
    for event in events:
        card = state.cards[event["card_id"]]
        if card.zone == Zone.EXILE:
            card.reset_zone_counters(Zone.EXILE)
    if started_staging:
        flush_staged_triggers(state)
    return True


def _pay_activated_mana(state: MatchState, player_id: int, mana_cost: str, card_name: str, reserved_life: int = 0, hybrid_choices: list[str] | None = None, x_value: int = 0, restricted_x_color: str | None = None, source_types: set[str] | None = None, source_id=None, ability_kind='activated', excluded_sources=None, ability_index=None, reserved_card_ids=(), protected_life=0) -> bool:
    from rules_engine.mana import auto_pay_cost

    return auto_pay_cost(state, player_id, mana_cost, card_name=card_name, reserved_life=reserved_life, hybrid_choices=hybrid_choices, x_value=x_value, restricted_x_color=restricted_x_color, payment_kind="activation", payment_types=source_types, source_card_id=source_id, ability_kind=ability_kind, excluded_sources=excluded_sources, ability_index=ability_index, reserved_card_ids=reserved_card_ids, protected_life=protected_life)


def collect_cost_options(state: MatchState, player_id: int, card, *, without_mana: bool = False) -> list[CostOption]:
    from rules_engine.graveyard_permissions import ordinary_graveyard_cast, zone_cast_prohibited, graveyard_only_cast
    if zone_cast_prohibited(state, player_id, card.zone) or (card.zone != Zone.GRAVEYARD and graveyard_only_cast(card)):
        return []
    from rules_engine.linked_discard import linked_discard_gaps
    if linked_discard_gaps(card.oracle_text or ''):
        return []
    from rules_engine.alternative_casts import escape_cost, flashback_cost, has_aftermath, prototype_characteristics
    from rules_engine.spell_cost_clauses import spell_additional_costs, resource_x_effect_gaps
    branches = spell_additional_costs(card.oracle_text, card.name)
    if branches is None:
        return []
    if any(branch.get('discard_x') for branch in branches) and resource_x_effect_gaps(card.oracle_text or ''):
        return []
    base = CostOption(id="base", label="Base Cost", mana_cost='' if without_mana else card.mana_cost or "")
    from rules_engine.foretell import cast_costs, record
    from rules_engine.card_faces import ordinary_exile_permission
    foretell_only = (card.zone == Zone.EXILE and bool(record(card))
                     and not ordinary_exile_permission(state, player_id, card.id, card.selected_face_index or 0))
    escape = escape_cost(card) if card.zone == Zone.GRAVEYARD else None
    flashback = flashback_cost(card) if card.zone == Zone.GRAVEYARD else None
    from rules_engine.flashback_grants import granted_cost
    granted_flashback = granted_cost(state, card, player_id)
    if without_mana:
        options = [base]
    elif card.zone == Zone.GRAVEYARD:
        options = [base] if card.mana_cost and ordinary_graveyard_cast(state, player_id, card.id) else []
        if has_aftermath(card):
            options.append(CostOption(id="aftermath", label="Aftermath", mana_cost=card.mana_cost or ""))
        if escape:
            options.append(CostOption(id="escape", label="Escape", mana_cost=escape[0], exile_graveyard=escape[1]))
        if flashback:
            options.append(CostOption(id="flashback", label="Flashback", mana_cost=flashback))
        if granted_flashback and granted_flashback != flashback:
            options.append(CostOption(id='flashback_granted' if flashback else 'flashback',
                                      label='Granted flashback', mana_cost=granted_flashback))
        if not options:
            return []
    elif foretell_only:
        options = []
    else:
        # An absent mana cost is unpayable, unlike an explicit {0} (CR 118.6).
        options = [base] if card.mana_cost else []
        from rules_engine.bestow import bestow_cost
        if bestow_cost(card):
            options.append(CostOption(id='bestow', label='Bestow (Aura)', mana_cost=bestow_cost(card)))
    if card.zone == Zone.EXILE and not without_mana:
        options.extend(CostOption(id=f'foretell_{index}', label='Foretell', mana_cost=cost)
                       for index, cost in enumerate(cast_costs(state, card, player_id)))
    prototype = prototype_characteristics(card)
    if prototype and card.zone != Zone.GRAVEYARD and not without_mana and not foretell_only:
        options.append(CostOption(id="prototype", label="Prototype", mana_cost=prototype["mana_cost"]))

    alt = ALT_COST_RE.search(card.oracle_text or "")
    if alt and card.zone != Zone.GRAVEYARD and not without_mana and not foretell_only:
        options.append(CostOption(id="alternate", label=f"Alternate {alt.group(1)}", mana_cost=alt.group(1)))

    from rules_engine.kicker import kicker_price, kicker_cost
    kicker = kicker_cost(card)
    if kicker:
        options = [variant for option in options for variant in (
            option, replace(option, id='kicker' if option.id == 'base' else option.id + '_kicker',
                            label=option.label + f' + kicker {kicker_price(card)}',
                            mana_cost=_join_costs(option.mana_cost, kicker['mana_cost']), kicked=True,
                            pay_life=option.pay_life + kicker.get('pay_life', 0),
                            discard_cards=option.discard_cards + kicker.get('discard_cards', 0),
                            sacrifice_creatures=option.sacrifice_creatures + kicker.get('sacrifice_creatures', 0),
                            sacrifice_kind=kicker.get('sacrifice_kind', option.sacrifice_kind),
                            kicker_base_id=option.id))]

    compiled = []
    for option in options:
        used_suffixes = set()
        for index, branch in enumerate(branches):
            if (option.sacrifice_creatures and branch.get('sacrifice_creatures')
                    and option.sacrifice_kind != branch.get('sacrifice_kind')):
                # Mixed mandatory types need independent selection groups, not
                # a summed count using whichever type appeared last.
                continue
            suffix = ('discard' if set(branch) == {'discard_cards'} else
                      'sacrifice' if set(branch) == {'sacrifice_creatures', 'sacrifice_kind'} else
                      'life' if set(branch) == {'pay_life'} else f'additional_{index}')
            if suffix in used_suffixes:
                suffix += f'_{index}'
            used_suffixes.add(suffix)
            compiled.append(replace(option,
                id=option.id + '_' + suffix if len(branches) > 1 else option.id,
                label=option.label + ' - ' + suffix.replace('_', ' ') if len(branches) > 1 else option.label,
                additional_cost_group=option.id if len(branches) > 1 else None,
                pay_life=option.pay_life + branch.get('pay_life', 0),
                pay_life_x=bool(branch.get('pay_life_x')),
                discard_cards=option.discard_cards + branch.get('discard_cards', 0),
                discard_x=bool(branch.get('discard_x')),
                discard_all=bool(branch.get('discard_all')),
                sacrifice_all=bool(branch.get('sacrifice_all')),
                sacrifice_creatures=option.sacrifice_creatures + branch.get('sacrifice_creatures', 0),
                sacrifice_kind=branch.get('sacrifice_kind', option.sacrifice_kind)))
    return compiled


def check_cost_option_available(state: MatchState, player_id: int, card, option: CostOption, x_value: int = 0, *, target_card_id: str | None = None) -> bool:
    from rules_engine.attachments import is_aura
    if casting_method(option.id) == 'bestow':
        from rules_engine.bestow import bestow_cast_view
        card = bestow_cast_view(card)
    player = state.players[player_id]
    if x_value < 0:
        return False
    if option.exile_graveyard and len([cid for cid in player.graveyard if cid != card.id and not is_departed_token(state.cards[cid])]) < option.exile_graveyard:
        return False
    if not can_pay_life(state, player_id, option.pay_life + (x_value if option.pay_life_x else 0)):
        return False
    if sum(cid != card.id and not is_departed_token(state.cards[cid]) for cid in player.hand) < option.discard_cards + (x_value if option.discard_x else 0):
        return False
    if len(_eligible_sacrifice_ids(state, player_id, option.sacrifice_kind)) < option.sacrifice_creatures:
        return False
    if option.sacrifice_all and set(_eligible_sacrifice_ids(state, player_id, option.sacrifice_kind, payment_kind='effect')) != set(_eligible_sacrifice_ids(state, player_id, option.sacrifice_kind)):
        return False
    return can_pay_with_pool_and_lands(
        state, player_id, option.mana_cost, is_land=("Land" in effective_types(state, card)),
        card_name=card.name, x_value=x_value, spell_types=set(effective_types(state, card)),
        spell_is_aura=is_aura(card),
        spell_kicked=option.kicked,
        oracle_text=card.oracle_text or "",
        reserved_life=option.pay_life + (x_value if option.pay_life_x else 0),
        source_card_id=card.id, target_card_id=target_card_id,
        cast_resource_card=card,
    )


def normalize_cost_choice(action: dict[str, Any], options: list[CostOption]) -> CostOption:
    choice_id = (action.get("cost_choice") or {}).get("id")
    if choice_id:
        for option in options:
            if option.id == choice_id:
                return option
    return options[0]


def additional_cost_candidates(state, player_id, spell_card_id, option):
    return {
        'discard_card_ids': [cid for cid in state.players[player_id].hand
                             if cid != spell_card_id and not is_departed_token(state.cards[cid])],
        'sacrifice_card_ids': _eligible_sacrifice_ids(state, player_id, option.sacrifice_kind),
    }


def additional_cost_selection(state, player_id, option, spell_card_id, choice=None, *, x_value=0):
    candidates = additional_cost_candidates(state, player_id, spell_card_id, option)
    selected = {}
    if x_value < 0:
        return None
    for key, count in [('discard_card_ids', option.discard_cards + (x_value if option.discard_x else 0)),
                       ('sacrifice_card_ids', option.sacrifice_creatures)]:
        ids = (choice or {}).get(key)
        all_resources = option.discard_all if key == 'discard_card_ids' else option.sacrifice_all
        if all_resources:
            # Exhaustive payments are not a selectable subset; recompute after
            # mana abilities have consumed or produced resources.
            if ids:
                return None
            if key == 'sacrifice_card_ids' and set(_eligible_sacrifice_ids(state, player_id, option.sacrifice_kind, payment_kind='effect')) != set(candidates[key]):
                return None
            selected[key] = list(candidates[key])
            continue
        if ids is None:
            ids = candidates[key][:count]
        if (not isinstance(ids, list) or any(not isinstance(cid, str) for cid in ids)
                or len(ids) != count or len(set(ids)) != count
                or any(cid not in candidates[key] for cid in ids)):
            return None
        selected[key] = list(ids)
    return selected


def apply_additional_costs(state: MatchState, player_id: int, option: CostOption, spell_card_id: str,
                           x_value: int = 0, choice=None, *, context: dict | None = None) -> bool:
    player = state.players[player_id]
    selected = additional_cost_selection(state, player_id, option, spell_card_id, choice, x_value=x_value)
    if selected is None:
        return False
    life_amount = option.pay_life + (x_value if option.pay_life_x else 0)
    if (x_value < 0 or not can_pay_life(state, player_id, life_amount)
            or cost_payment_is_prohibited(state, player_id, 'spell', life=life_amount)):
        return False
    if life_amount:
        from rules_engine.replacement import pay_life
        if not pay_life(state, player_id, life_amount):
            return False
        state.log.append(f"{player.name} pays {life_amount} life as an additional cost.")

    from rules_engine.zone_actions import discard_selected, sacrifice_selected
    if selected['discard_card_ids'] and not discard_selected(state, player_id, selected['discard_card_ids']):
        return False
    sacrifices = selected['sacrifice_card_ids']
    names = {cid: state.cards[cid].name for cid in sacrifices}
    if context is not None:
        from rules_engine.continuous import effective_combat_stats
        # Costs precede resolution; later zone changes must not recompute power.
        context['sacrificed_creatures'] = [
            {'card_id': cid, 'power': effective_combat_stats(state, cid)[0],
             'toughness': effective_combat_stats(state, cid)[1]}
            for cid in sacrifices if 'Creature' in effective_types(state, state.cards[cid])
        ]
    if sacrifices and not sacrifice_selected(state, player_id, sacrifices):
        return False
    for cid in sacrifices:
        suffix = ', but it is exiled instead of dying' if state.cards[cid].zone == Zone.EXILE else ''
        state.log.append(f'{player.name} sacrifices {names[cid]} for additional cost{suffix}.')
    return True


def _join_costs(a: str, b: str) -> str:
    return (a or "") + (b or "")


def _first_discardable_card(state: MatchState, player_id: int, exclude: set[str]) -> str | None:
    for cid in state.players[player_id].hand:
        if cid not in exclude and not is_departed_token(state.cards[cid]):
            return cid
    return None


def _eligible_sacrifice_ids(state: MatchState, player_id: int, kind: str = "creature", *, payment_kind: str = 'spell') -> list[str]:
    from rules_engine.colors import card_color_names
    from rules_engine.library_permissions import creature_types
    eligible: list[str] = []
    for cid in state.players[player_id].battlefield:
        card = state.cards.get(cid)
        if card is None or card.zone != Zone.BATTLEFIELD or card.controller != player_id:
            continue
        types = set(effective_types(state, card) or [])
        if 'Creature' in types and cost_payment_is_prohibited(state, player_id, payment_kind, sacrifice_creature=True):
            continue
        if not types.intersection({'Artifact', 'Battle', 'Creature', 'Enchantment', 'Land', 'Planeswalker'}):
            continue
        if kind.startswith('subtype_'):
            subtype = kind.removeprefix('subtype_')
            if types.intersection({'Creature', 'Kindred'}) and (
                    subtype in creature_types(card)
                    or 'changeling' in {str(k).lower() for k in card.keywords or []}):
                eligible.append(cid)
            continue
        color, separator, typed_kind = kind.partition('_')
        if separator and color in {'white', 'blue', 'black', 'red', 'green'}:
            if color in card_color_names(card) and (typed_kind == 'permanent' or typed_kind.title() in types):
                eligible.append(cid)
            continue
        if (
            kind == "permanent"
            or (any(part.title() in types for part in kind.split('_or_')))
            or (kind == "artifact" and "Artifact" in types)
            or (kind == "enchantment" and "Enchantment" in types)
            or (kind == "creature" and "Creature" in types)
        ):
            eligible.append(cid)
    return eligible
