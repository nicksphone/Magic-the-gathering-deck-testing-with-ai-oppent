from __future__ import annotations

import copy

from game_state.state import MatchState, Zone, assign_static_order_on_battlefield_entry
from card_data.token_images import resolve_token_image_uri
from rules_engine.continuous import effective_keywords, effective_toughness, has_keyword
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
from rules_engine.replacement import (
    apply_damage_replacements,
    damage_cant_be_prevented,
    player_cant_gain_life,
    player_cant_lose_life,
    replace_draw_cards,
    replace_gain_life,
)

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"


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


def _move_creature_to_graveyard(state: MatchState, card_id: str) -> None:
    card = state.cards[card_id]
    owner = state.players[card.controller]
    if card_id in owner.battlefield:
        owner.battlefield.remove(card_id)
        owner.graveyard.append(card_id)
        card.zone = Zone.GRAVEYARD
        state.log.append(f"{card.name} dies.")
        emit_event(state, "creature_dies", {"card_id": card_id, "controller": card.controller})


def deal_damage(state: MatchState, controller: int, payload: dict) -> None:
    payload = apply_replacement_effects("damage", dict(payload))
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    amount = int(payload.get("amount", 0))
    source_card_id = payload.get("__source_card_id")
    prevention_locked = damage_cant_be_prevented(
        state,
        source_card_id=source_card_id,
        target_player=int(target_player) if target_player is not None else None,
        target_card_id=target_card_id,
    )
    source_colors: set[str] = set()
    if source_card_id in state.cards:
        source_colors = card_color_names(state.cards[source_card_id])
    if target_card_id is not None and target_card_id in state.cards:
        card = state.cards[target_card_id]
        kws = effective_keywords(state, target_card_id)
        for color in source_colors:
            if f"protection from {color}" in kws:
                state.log.append(f"{card.name} prevents damage from {color} source due to protection.")
                return
        if card.toughness is not None and amount > 0:
            post, prevented = (amount, 0) if prevention_locked else consume_card_prevention_shield(card, amount)
            if prevented > 0:
                state.log.append(f"{card.name} prevents {prevented} damage.")
            if post <= 0:
                return
            card.counters[DMG_MARK_KEY] = int(card.counters.get(DMG_MARK_KEY, 0)) + int(post)
            state.log.append(f"{card.name} takes {post} damage.")
            # Check for lethal damage — creatures die state-based, not just at combat cleanup.
            if "Creature" in card.types and _creature_is_lethally_damaged(state, target_card_id):
                _move_creature_to_graveyard(state, target_card_id)
            return
    if target_player is not None:
        replaced_amount = amount if prevention_locked else apply_damage_replacements(state, int(target_player), amount)
        post, prevented = (replaced_amount, 0) if prevention_locked else consume_player_prevention_shield(state, int(target_player), replaced_amount)
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
    replaced = replace_draw_cards(state, target_player, amount)
    if replaced is not None:
        key, repl_payload = replaced
        from effects.registry import resolve_effect
        resolve_effect(state, controller, key, repl_payload)
        return
    draw_card(state, target_player, amount)
    state.log.append(f"{state.players[target_player].name} draws {amount}.")


def gain_life(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", controller))
    amount = int(payload.get("amount", 0))
    if amount <= 0:
        return
    if player_cant_gain_life(state, target_player):
        state.log.append(f"{state.players[target_player].name} can't gain life.")
        return
    replaced = replace_gain_life(state, target_player, amount)
    if replaced is not None:
        key, repl_payload = replaced
        from effects.registry import resolve_effect
        resolve_effect(state, controller, key, repl_payload)
        return
    state.players[target_player].life += amount
    state.log.append(f"{state.players[target_player].name} gains {amount} life.")
    if amount > 0:
        emit_event(state, "life_gain", {"player_id": target_player, "amount": amount})


def lose_life(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", controller))
    amount = int(payload.get("amount", 0))
    if amount <= 0:
        return
    if player_cant_lose_life(state, target_player):
        state.log.append(f"{state.players[target_player].name} can't lose life.")
        return
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


def copy_spell(state: MatchState, controller: int, payload: dict) -> None:
    target_stack_id = payload.get("target_stack_id")
    if not target_stack_id:
        return
    item = next((x for x in state.stack if x.id == target_stack_id), None)
    if item is None:
        return
    copied_payload = copy.deepcopy(item.payload or {})
    copied_payload["__source_card_id"] = item.source_card_id
    from effects.registry import resolve_effect

    resolve_effect(state, controller, item.effect_key, copied_payload)
    state.log.append(f"{state.players[controller].name} copies {item.label}.")


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
    token_controller = int(payload.get("controller", controller))
    sac_next_end = bool(payload.get("sacrifice_next_end_step", False))
    token_image_uri = payload.get("image_uri") or resolve_token_image_uri(name, p, t)
    for _ in range(amount):
        cid = str(uuid.uuid4())
        token = CardInstance(
            id=cid,
            name=name,
            owner=token_controller,
            controller=token_controller,
            zone=Zone.BATTLEFIELD,
            types=types,
            power=p,
            toughness=t,
            summoning_sick="Creature" in types,
            entered_turn=state.turn,
            keywords=keywords,
            image_uri=token_image_uri,
        )
        state.cards[cid] = token
        state.players[token_controller].battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        if sac_next_end:
            token.counters["__sac_next_end_step"] = 1
    state.log.append(f"{state.players[token_controller].name} creates {amount} {p}/{t} token(s).")


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
        # PT delta from counters is computed dynamically by effective_power/toughness


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
    # No-op — continuous PT bonuses are computed dynamically by
    # effective_power() / effective_toughness() which scan all battlefield
    # permanents for anthem-like oracle text via _continuous_pt_delta().
    # Permanently mutating base stats here caused buffs to persist after
    # the source left the battlefield (Bug #7).
    pass


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
        card.entered_turn = state.turn
        player.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
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
