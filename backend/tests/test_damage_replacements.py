from effects.handlers import deal_damage
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.continuous import effective_toughness


def test_noncombat_damage_replacement_puts_minus_counters_on_opposing_creature() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=41,
    )
    source = CardInstance(
        id="soul-scar",
        name="Damage Replacement",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text=(
            "If a source you control would deal noncombat damage to a creature "
            "an opponent controls, put that many -1/-1 counters on that creature instead."
        ),
    )
    target = CardInstance(
        id="target-creature",
        name="Target Creature",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        power=3,
        toughness=4,
    )
    state.cards.update({source.id: source, target.id: target})
    state.players[1].battlefield.append(source.id)
    state.players[2].battlefield.append(target.id)

    deal_damage(state, 1, {"__source_card_id": "spell", "target_card_id": target.id, "amount": 2})

    # Without a known source the replacement is not applicable; this protects
    # the rule from rewriting damage whose source identity was not preserved.
    assert target.counters.get("-1/-1", 0) == 0
    target.counters.clear()

    spell = CardInstance(
        id="spell",
        name="Shock",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
        oracle_text="Shock deals 2 damage to any target.",
    )
    state.cards[spell.id] = spell
    deal_damage(state, 1, {"__source_card_id": spell.id, "target_card_id": target.id, "amount": 2})

    assert target.counters["-1/-1"] == 2
    assert effective_toughness(state, target.id) == 2
    assert target.counters.get("__damage_marked", 0) == 0


def test_noncombat_damage_replacement_does_not_apply_to_controller_creature() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=42,
    )
    source = CardInstance(
        id="replacement",
        name="Damage Replacement",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="If a source you control would deal noncombat damage to a creature an opponent controls, put that many -1/-1 counters on that creature instead.",
    )
    target = CardInstance(
        id="own-creature",
        name="Own Creature",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        power=3,
        toughness=4,
    )
    spell = CardInstance(
        id="spell-own",
        name="Shock",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
        oracle_text="Shock deals 2 damage to any target.",
    )
    state.cards.update({source.id: source, target.id: target, spell.id: spell})
    state.players[1].battlefield.extend([source.id, target.id])

    deal_damage(state, 1, {"__source_card_id": spell.id, "target_card_id": target.id, "amount": 2})

    assert target.counters.get("-1/-1", 0) == 0
    assert target.counters["__damage_marked"] == 2
