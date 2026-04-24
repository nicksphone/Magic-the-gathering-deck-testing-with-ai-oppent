from __future__ import annotations

from game_state.state import MatchState, Zone
from rules_engine.hooks import apply_replacement_effects
from rules_engine.events import emit_event


def deal_damage(state: MatchState, controller: int, payload: dict) -> None:
    payload = apply_replacement_effects("damage", dict(payload))
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    amount = int(payload.get("amount", 0))
    if target_card_id is not None and target_card_id in state.cards:
        card = state.cards[target_card_id]
        if card.toughness is not None:
            card.toughness -= amount
            state.log.append(f"{card.name} takes {amount} damage.")
            return
    if target_player is not None:
        state.players[target_player].life -= amount
        state.log.append(f"{state.players[target_player].name} takes {amount} damage.")


def draw_cards(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import draw_card

    amount = int(payload.get("amount", 1))
    draw_card(state, controller, amount)
    state.log.append(f"{state.players[controller].name} draws {amount}.")


def gain_life(state: MatchState, controller: int, payload: dict) -> None:
    amount = int(payload.get("amount", 0))
    state.players[controller].life += amount
    state.log.append(f"{state.players[controller].name} gains {amount} life.")
    if amount > 0:
        emit_event(state, "life_gain", {"player_id": controller, "amount": amount})


def lose_life(state: MatchState, controller: int, payload: dict) -> None:
    amount = int(payload.get("amount", 0))
    state.players[controller].life -= amount
    state.log.append(f"{state.players[controller].name} loses {amount} life.")


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
    cid = str(uuid.uuid4())
    token = CardInstance(
        id=cid,
        name=name,
        owner=controller,
        controller=controller,
        zone=Zone.BATTLEFIELD,
        types=["Creature", "Token"],
        power=p,
        toughness=t,
        summoning_sick=True,
    )
    state.cards[cid] = token
    state.players[controller].battlefield.append(cid)
    state.log.append(f"{state.players[controller].name} creates a {p}/{t} token.")


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
