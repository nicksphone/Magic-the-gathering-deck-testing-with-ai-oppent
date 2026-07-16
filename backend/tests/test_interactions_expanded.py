from __future__ import annotations

from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine import combat


def test_effect_sequence_resolves_all_clauses() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1_before = state.players[1].life
    p2_before = state.players[2].life
    hand_before = len(state.players[1].hand)

    resolve_effect(
        state,
        1,
        "effect_sequence",
        {
            "effects": [
                {"effect_key": "lose_life", "payload": {"target_player": 2, "amount": 3}},
                {"effect_key": "gain_life", "payload": {"amount": 3}},
                {"effect_key": "draw_cards", "payload": {"amount": 1}},
            ]
        },
    )

    assert state.players[2].life == p2_before - 3
    assert state.players[1].life == p1_before + 3
    assert len(state.players[1].hand) == hand_before + 1


def test_discard_effect_targets_specified_player() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2_hand_before = len(state.players[2].hand)

    resolve_effect(state, 1, "discard_cards", {"target_player": 2, "amount": 2})

    assert len(state.players[2].hand) == p2_hand_before - 2
    assert len(state.players[2].graveyard) >= 2


def test_search_library_returns_all_matching_cards() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    player = state.players[1]
    player.library = []
    for name in ["Goblin Guide", "Goblin Piledriver", "Goblin War Marshal", "Lightning Bolt"]:
        cid = f"card-{name.lower().replace(' ', '-')}"
        state.cards[cid] = CardInstance(
            id=cid,
            name=name,
            owner=1,
            controller=1,
            zone=Zone.LIBRARY,
            types=["Creature"],
        )
        player.library.append(cid)

    hand_before = len(player.hand)
    library_before = len(player.library)
    resolve_effect(state, 1, "search_library", {"contains": "Goblin"})

    assert len(player.hand) == hand_before + 3
    assert len(player.library) == library_before - 3
    assert any("searched library and found 3 card(s)" in line.lower() for line in state.log)


def test_create_token_respects_amount_and_keywords() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    battlefield_before = len(state.players[1].battlefield)
    resolve_effect(
        state,
        1,
        "create_token",
        {"name": "Soldier", "power": 1, "toughness": 1, "amount": 2, "keywords": ["vigilance"]},
    )
    created = state.players[1].battlefield[battlefield_before:]
    assert len(created) == 2
    assert all(state.cards[cid].name == "Soldier" for cid in created)
    assert all("vigilance" in state.cards[cid].keywords for cid in created)


def test_deal_damage_destroys_creature_with_lethal_damage() -> None:
    """Spell damage should kill creatures — state-based lethal check after damage."""
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    battlefield_before = len(state.players[2].battlefield)
    resolve_effect(
        state,
        1,
        "create_token",
        {"name": "Creature", "power": 2, "toughness": 2, "amount": 1, "keywords": [], "controller": 2},
    )
    creature_ids = state.players[2].battlefield[battlefield_before:]
    assert len(creature_ids) == 1
    cid = creature_ids[0]
    assert state.cards[cid].zone == state.cards[cid].zone  # smoke test
    from game_state.state import Zone
    assert state.cards[cid].zone == Zone.BATTLEFIELD

    # Deal 3 damage (lethal for a 2/2)
    resolve_effect(state, 1, "deal_damage", {"target_card_id": cid, "amount": 3})

    # Creature should be dead
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert cid not in state.players[2].battlefield
    assert cid in state.players[2].graveyard


def test_deal_damage_respects_indestructible() -> None:
    """Indestructible creatures should survive lethal spell damage."""
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    battlefield_before = len(state.players[2].battlefield)
    resolve_effect(
        state,
        1,
        "create_token",
        {"name": "Indestructible Creature", "power": 2, "toughness": 2, "amount": 1, "keywords": ["indestructible"], "controller": 2},
    )
    creature_ids = state.players[2].battlefield[battlefield_before:]
    assert len(creature_ids) == 1
    cid = creature_ids[0]

    # Deal 3 damage (would be lethal without indestructible)
    resolve_effect(state, 1, "deal_damage", {"target_card_id": cid, "amount": 3})

    # Should still be alive
    from game_state.state import Zone
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert cid in state.players[2].battlefield


def test_deal_damage_non_lethal_doesnt_kill() -> None:
    """Sub-lethal damage should not kill the creature."""
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    battlefield_before = len(state.players[2].battlefield)
    resolve_effect(
        state,
        1,
        "create_token",
        {"name": "Creature", "power": 2, "toughness": 2, "amount": 1, "keywords": [], "controller": 2},
    )
    creature_ids = state.players[2].battlefield[battlefield_before:]
    cid = creature_ids[0]

    # Deal 1 damage (not lethal for a 2/2)
    resolve_effect(state, 1, "deal_damage", {"target_card_id": cid, "amount": 1})

    from game_state.state import Zone
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert cid in state.players[2].battlefield
    assert state.cards[cid].counters.get("__damage_marked", 0) == 1


def test_deal_damage_cumulative_lethal() -> None:
    """Multiple damage instances should accumulate and kill."""
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    battlefield_before = len(state.players[2].battlefield)
    resolve_effect(
        state,
        1,
        "create_token",
        {"name": "Creature", "power": 2, "toughness": 3, "amount": 1, "keywords": [], "controller": 2},
    )
    creature_ids = state.players[2].battlefield[battlefield_before:]
    cid = creature_ids[0]

    # Deal 2 damage — not lethal for 3 toughness
    resolve_effect(state, 1, "deal_damage", {"target_card_id": cid, "amount": 2})
    from game_state.state import Zone
    assert state.cards[cid].zone == Zone.BATTLEFIELD

    # Deal 1 more — now lethal (2+1 >= 3)
    resolve_effect(state, 1, "deal_damage", {"target_card_id": cid, "amount": 1})
    assert state.cards[cid].zone == Zone.GRAVEYARD
    assert cid not in state.players[2].battlefield


def test_combat_death_replacement_exiles_creature_instead_of_graveyard() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=19)
    replacement = CardInstance(
        id="rep",
        name="Rest in Peace",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="If a creature you control would die, exile it instead.",
    )
    state.cards[replacement.id] = replacement
    state.players[2].battlefield.append(replacement.id)
    attacker = state.players[1].hand[0]
    state.players[1].battlefield.append(attacker)
    state.cards[attacker].zone = Zone.BATTLEFIELD
    state.cards[attacker].types = ["Creature"]
    state.cards[attacker].power = 3
    state.cards[attacker].toughness = 3
    state.cards[attacker].summoning_sick = False
    blocker = CardInstance(
        id="blk",
        name="Bear",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        power=2,
        toughness=2,
    )
    state.cards[blocker.id] = blocker
    state.players[2].battlefield.append(blocker.id)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = state.step.COMBAT_DAMAGE
    state.attackers = [attacker]
    state.attack_targets = {attacker: "player:2"}
    state.blocks = {attacker: [blocker.id]}

    combat.combat_damage(state)

    assert blocker.zone == Zone.EXILE
    assert blocker.id in state.players[2].exile
    assert blocker.id not in state.players[2].graveyard


def test_state_based_action_lethal_creature_emits_permanent_and_creature_death_triggers() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=21)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    creature_id = state.players[1].hand[0]
    state.players[1].hand.remove(creature_id)
    state.players[1].battlefield.append(creature_id)
    state.cards[creature_id].zone = Zone.BATTLEFIELD
    state.cards[creature_id].types = ["Creature"]
    state.cards[creature_id].power = 2
    state.cards[creature_id].toughness = 2
    state.cards[creature_id].counters["__damage_marked"] = 2
    state.cards["trigger"] = CardInstance(
        id="trigger",
        name="Blood Artist",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Whenever a creature dies, draw a card.",
    )
    state.players[1].battlefield.append("trigger")

    from rules_engine.state_based_actions import apply_state_based_actions

    apply_state_based_actions(state)

    assert any(item.controller == 1 for item in state.stack)


def test_state_based_action_zero_loyalty_planeswalker_emits_permanent_death_trigger() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=22)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    pw_id = state.players[1].hand[0]
    state.players[1].hand.remove(pw_id)
    state.players[1].battlefield.append(pw_id)
    state.cards[pw_id].zone = Zone.BATTLEFIELD
    state.cards[pw_id].types = ["Planeswalker"]
    state.cards[pw_id].loyalty = 0
    state.cards[pw_id].name = "The Wandering Emperor"
    state.cards["trigger"] = CardInstance(
        id="trigger",
        name="Afterlife Archive",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever a permanent you control dies, draw a card.",
    )
    state.players[1].battlefield.append("trigger")

    from rules_engine.state_based_actions import apply_state_based_actions

    apply_state_based_actions(state)

    assert any(item.controller == 1 for item in state.stack)
