from __future__ import annotations

from game_state.state import MatchState, Zone
from rules_engine.colors import card_color_names
from rules_engine.hooks import apply_replacement_effects
from rules_engine.events import emit_event
from rules_engine.mana import parse_mana_cost
from rules_engine.prevention import (
    add_card_prevention_shield,
    add_player_prevention_shield,
    consume_card_prevention_shield,
    consume_player_prevention_shield,
)


def deal_damage(state: MatchState, controller: int, payload: dict) -> None:
    payload = apply_replacement_effects("damage", dict(payload))
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    amount = int(payload.get("amount", 0))
    source_card_id = payload.get("__source_card_id")
    source_colors: set[str] = set()
    if source_card_id in state.cards:
        source_colors = card_color_names(state.cards[source_card_id])
    if target_card_id is not None and target_card_id in state.cards:
        card = state.cards[target_card_id]
        kws = [str(k).lower() for k in (getattr(card, "keywords", []) or [])]
        for color in source_colors:
            if f"protection from {color}" in kws:
                state.log.append(f"{card.name} prevents damage from {color} source due to protection.")
                return
        if card.toughness is not None and amount > 0:
            post, prevented = consume_card_prevention_shield(card, amount)
            if prevented > 0:
                state.log.append(f"{card.name} prevents {prevented} damage.")
            if post <= 0:
                return
            card.counters["__damage_marked"] = int(card.counters.get("__damage_marked", 0)) + int(post)
            state.log.append(f"{card.name} takes {post} damage.")
            return
    if target_player is not None:
        post, prevented = consume_player_prevention_shield(state, int(target_player), amount)
        if prevented > 0:
            state.log.append(f"{state.players[target_player].name} prevents {prevented} damage.")
        if post <= 0:
            return
        state.players[target_player].life -= post
        state.log.append(f"{state.players[target_player].name} takes {post} damage.")


def draw_cards(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import draw_card

    target_player = int(payload.get("target_player", controller))
    amount = int(payload.get("amount", 1))
    draw_card(state, target_player, amount)
    state.log.append(f"{state.players[target_player].name} draws {amount}.")


def gain_life(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", controller))
    amount = int(payload.get("amount", 0))
    state.players[target_player].life += amount
    state.log.append(f"{state.players[target_player].name} gains {amount} life.")
    if amount > 0:
        emit_event(state, "life_gain", {"player_id": target_player, "amount": amount})


def lose_life(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", controller))
    amount = int(payload.get("amount", 0))
    state.players[target_player].life -= amount
    state.log.append(f"{state.players[target_player].name} loses {amount} life.")


def destroy_permanent(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    owner_state = state.players[card.controller]
    if target in owner_state.battlefield:
        owner_state.battlefield.remove(target)
        owner_state.graveyard.append(target)
        card.zone = Zone.GRAVEYARD
        state.log.append(f"{card.name} is destroyed.")
        if "Creature" in card.types:
            emit_event(state, "creature_dies", {"card_id": target, "controller": card.controller})


def counter_spell(state: MatchState, controller: int, payload: dict) -> None:
    target_stack_id = payload.get("target_stack_id")
    for i, item in enumerate(state.stack):
        if item.id == target_stack_id:
            popped = state.stack.pop(i)
            card = state.cards.get(popped.source_card_id)
            if card:
                owner_state = state.players[card.controller]
                if card.id not in owner_state.graveyard:
                    owner_state.graveyard.append(card.id)
                card.zone = Zone.GRAVEYARD
            state.log.append(f"{item.label} was countered.")
            return


def exile_permanent(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    owner_state = state.players[card.controller]
    if target in owner_state.battlefield:
        owner_state.battlefield.remove(target)
        owner_state.exile.append(target)
        card.zone = Zone.EXILE
        state.log.append(f"{card.name} is exiled.")


def return_from_graveyard(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    if not player.graveyard:
        return
    card_id = player.graveyard.pop()
    player.hand.append(card_id)
    state.cards[card_id].zone = Zone.HAND
    state.log.append(f"{state.cards[card_id].name} returns from graveyard to hand.")


def search_library(state: MatchState, controller: int, payload: dict) -> None:
    subtype = payload.get("contains")
    player = state.players[controller]
    if not subtype:
        return
    for cid in list(player.library):
        if subtype.lower() in state.cards[cid].name.lower():
            player.library.remove(cid)
            player.hand.append(cid)
            state.cards[cid].zone = Zone.HAND
            state.log.append(f"{state.players[controller].name} searched library and found {state.cards[cid].name}.")
            break


def create_token(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import CardInstance
    import uuid

    name = payload.get("name", "Token")
    p = int(payload.get("power", 1))
    t = int(payload.get("toughness", 1))
    amount = max(1, int(payload.get("amount", 1)))
    types = list(payload.get("types", ["Creature", "Token"]))
    keywords = list(payload.get("keywords", []))
    for _ in range(amount):
        cid = str(uuid.uuid4())
        token = CardInstance(
            id=cid,
            name=name,
            owner=controller,
            controller=controller,
            zone=Zone.BATTLEFIELD,
            types=types,
            power=p,
            toughness=t,
            summoning_sick="Creature" in types,
            keywords=keywords,
        )
        state.cards[cid] = token
        state.players[controller].battlefield.append(cid)
    state.log.append(f"{state.players[controller].name} creates {amount} {p}/{t} token(s).")


def add_mana(state: MatchState, controller: int, payload: dict) -> None:
    color = payload.get("color", "C")
    amount = int(payload.get("amount", 1))
    state.players[controller].mana_pool[color] += amount


def add_counters(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    counter = payload.get("counter", "+1/+1")
    amount = int(payload.get("amount", 1))
    if target in state.cards:
        card = state.cards[target]
        card.counters[counter] = card.counters.get(counter, 0) + amount
        if counter == "+1/+1" and card.power is not None and card.toughness is not None:
            card.power += amount
            card.toughness += amount


def sacrifice(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if target in state.cards and target in state.players[controller].battlefield:
        state.players[controller].battlefield.remove(target)
        state.players[controller].graveyard.append(target)
        state.cards[target].zone = Zone.GRAVEYARD
        if "Creature" in state.cards[target].types:
            emit_event(state, "creature_dies", {"card_id": target, "controller": controller})


def deal_damage_multi(state: MatchState, controller: int, payload: dict) -> None:
    distribution = payload.get("target_distribution", {})
    for target, amount in distribution.items():
        if str(target).isdigit():
            deal_damage(state, controller, {"target_player": int(target), "amount": int(amount)})
        else:
            deal_damage(state, controller, {"target_card_id": target, "amount": int(amount)})


def tap_card(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if target in state.cards:
        state.cards[target].tapped = True


def untap_card(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if target in state.cards:
        state.cards[target].tapped = False


def continuous_buff(state: MatchState, controller: int, payload: dict) -> None:
    buff = int(payload.get("amount", 1))
    for cid in state.players[controller].battlefield:
        c = state.cards[cid]
        if "Creature" in c.types and c.power is not None and c.toughness is not None:
            c.power += buff
            c.toughness += buff


def grant_keyword(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    keyword = payload.get("keyword")
    if target in state.cards and keyword:
        card = state.cards[target]
        if keyword not in card.keywords:
            card.keywords.append(keyword)


def prevent_damage(state: MatchState, controller: int, payload: dict) -> None:
    amount = int(payload.get("amount", 0))
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    if target_player is not None:
        add_player_prevention_shield(state, int(target_player), amount)
        state.log.append(f"{state.players[int(target_player)].name} gains a prevention shield of {amount}.")
        return
    if target_card_id in state.cards:
        card = state.cards[target_card_id]
        add_card_prevention_shield(card, amount)
        state.log.append(f"{card.name} gains a prevention shield of {amount}.")


def discard_cards(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", 1 if controller == 2 else 2))
    amount = int(payload.get("amount", 1))
    player = state.players[target_player]
    discarded = 0
    while player.hand and discarded < max(0, amount):
        cid = player.hand.pop(0)
        player.graveyard.append(cid)
        state.cards[cid].zone = Zone.GRAVEYARD
        discarded += 1
    state.log.append(f"{player.name} discards {discarded}.")


def topdeck_put_creatures_battlefield(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    top_n = max(1, int(payload.get("top_n", 6)))
    max_creatures = max(1, int(payload.get("max_creatures", 2)))
    mv_max = max(0, int(payload.get("mv_max", 3)))
    if not player.library:
        return

    # Library top is the tail (draw pops from end).
    top_slice = player.library[-top_n:]

    def is_eligible(cid: str) -> bool:
        card = state.cards[cid]
        if "Creature" not in card.types:
            return False
        req = parse_mana_cost(getattr(card, "mana_cost", "") or "")
        mv = int(req["generic"] + req["W"] + req["U"] + req["B"] + req["R"] + req["G"])
        return mv <= mv_max

    eligibles = [cid for cid in top_slice if is_eligible(cid)]
    eligibles.sort(
        key=lambda cid: (
            state.cards[cid].power or 0,
            state.cards[cid].toughness or 0,
            -(
                parse_mana_cost(getattr(state.cards[cid], "mana_cost", "") or "")["generic"]
                + parse_mana_cost(getattr(state.cards[cid], "mana_cost", "") or "")["W"]
                + parse_mana_cost(getattr(state.cards[cid], "mana_cost", "") or "")["U"]
                + parse_mana_cost(getattr(state.cards[cid], "mana_cost", "") or "")["B"]
                + parse_mana_cost(getattr(state.cards[cid], "mana_cost", "") or "")["R"]
                + parse_mana_cost(getattr(state.cards[cid], "mana_cost", "") or "")["G"]
            ),
        ),
        reverse=True,
    )
    chosen = eligibles[:max_creatures]

    # Remove inspected cards from library in top-to-bottom order.
    inspected_set = set(top_slice)
    remaining_library = [cid for cid in player.library if cid not in inspected_set]
    player.library = remaining_library

    # Put chosen creatures onto battlefield.
    for cid in chosen:
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.summoning_sick = "Creature" in card.types
        player.battlefield.append(cid)
        emit_event(state, "enters_battlefield", {"card_id": cid, "controller": controller})

    # Put the rest onto the bottom (deterministic order).
    rest = [cid for cid in top_slice if cid not in set(chosen)]
    for cid in rest:
        state.cards[cid].zone = Zone.LIBRARY
        player.library.insert(0, cid)

    if chosen:
        names = ", ".join(state.cards[cid].name for cid in chosen)
        state.log.append(f"{player.name} puts {names} onto the battlefield from top of library.")
    else:
        state.log.append(f"{player.name} finds no eligible creature cards in top {top_n}.")
