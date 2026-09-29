from __future__ import annotations

from game_state.state import Zone
from game_state.state import CardInstance, MatchFactory, Step
from rules_engine.engine import RulesEngine
from rules_engine.mana import add_generic_to_cost, auto_pay_cost, can_pay_with_pool_and_lands, land_mana_amount, mana_value


def test_spectral_procession_hybrid_cost_uses_white_or_generic_mana() -> None:
    cost = "{2/W}{2/W}{2/W}"
    assert mana_value(cost) == 6
    for land_name, count in (("Plains", 3), ("Island", 6)):
        deck = [{"quantity": 60, "card_name": land_name}]
        state = MatchFactory.from_decks(deck, deck, seed=101)
        for _ in range(count):
            cid = state.players[1].library.pop()
            state.cards[cid].zone = Zone.BATTLEFIELD
            state.players[1].battlefield.append(cid)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.step = Step.PRECOMBAT_MAIN
        state.priority_player = 1
        spell_id = state.players[1].hand[0]
        spell = state.cards[spell_id]
        spell.name = "Spectral Procession"
        spell.types = ["Sorcery"]
        spell.mana_cost = cost
        assert any(move["type"] == "cast_spell" and move.get("card_id") == spell_id
                   for move in RulesEngine().legal_moves(state, 1))
        assert can_pay_with_pool_and_lands(state, 1, cost)
        assert auto_pay_cost(state, 1, cost)
        assert sum(state.cards[cid].tapped for cid in state.players[1].battlefield) == count
        assert all(value == 0 for value in state.players[1].mana_pool.values())


def test_two_color_hybrid_uses_either_color_without_changing_mana_value() -> None:
    assert mana_value("{W/U}{W/U}") == 2
    for land_name in ("Plains", "Island"):
        deck = [{"quantity": 60, "card_name": land_name}]
        state = MatchFactory.from_decks(deck, deck, seed=102)
        for _ in range(2):
            cid = state.players[1].library.pop()
            state.cards[cid].zone = Zone.BATTLEFIELD
            state.players[1].battlefield.append(cid)
        assert can_pay_with_pool_and_lands(state, 1, "{W/U}{W/U}")
        assert auto_pay_cost(state, 1, "{W/U}{W/U}")


def test_generic_reduction_applies_after_monocolored_hybrid_choice(monkeypatch) -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=103)
    cid = state.players[1].library.pop()
    state.cards[cid].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(cid)
    assert not can_pay_with_pool_and_lands(state, 1, "{2/W}")

    def reduce_one(context):
        context.generic_reduction = 1
        return context

    monkeypatch.setattr("rules_engine.mana.apply_cost_modifiers", reduce_one)
    assert can_pay_with_pool_and_lands(state, 1, "{2/W}")
    assert auto_pay_cost(state, 1, "{2/W}")
    assert state.cards[cid].tapped
    assert add_generic_to_cost("{2/W}{W/U}", 1) == "{1}{2/W}{W/U}"


def test_nonland_single_color_source_is_used_before_flexible_land() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=96)
    fountain = CardInstance(
        id="fountain", name="Hallowed Fountain", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Land"], type_line="Land - Plains Island",
        oracle_text="{T}: Add {W} or {U}.",
    )
    diamond = CardInstance(
        id="diamond", name="Marble Diamond", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"], type_line="Artifact",
        oracle_text="{T}: Add {W}.",
    )
    for card in (fountain, diamond):
        state.cards[card.id] = card
        state.players[1].battlefield.append(card.id)

    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    spell_id = state.players[1].hand[0]
    spell = state.cards[spell_id]
    spell.name = "Lavinia, Azorius Renegade"
    spell.types = ["Creature", "Legendary"]
    spell.mana_cost = "{W}{U}"
    assert any(move["type"] == "cast_spell" and move.get("card_id") == spell_id
               for move in RulesEngine().legal_moves(state, 1))
    assert can_pay_with_pool_and_lands(state, 1, "{W}{U}")
    assert auto_pay_cost(state, 1, "{W}{U}")
    assert fountain.tapped and diamond.tapped
    assert all(value == 0 for value in state.players[1].mana_pool.values())


def test_multi_mana_source_surplus_pays_generic_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=97)
    lotus = CardInstance(
        id="lotus", name="Gilded Lotus", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"], type_line="Artifact",
        oracle_text="{T}: Add three mana of any one color.",
    )
    state.cards[lotus.id] = lotus
    state.players[1].battlefield.append(lotus.id)
    assert can_pay_with_pool_and_lands(state, 1, "{W}{2}")
    assert auto_pay_cost(state, 1, "{W}{2}")
    assert lotus.tapped
    assert all(value == 0 for value in state.players[1].mana_pool.values())


def test_can_pay_known_mana_cost_with_untapped_lands() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    # Put a UU spell in hand with known mana cost.
    cid = state.players[1].hand[0]
    state.cards[cid].name = "Counterspell"
    state.cards[cid].types = ["Instant"]
    state.cards[cid].mana_cost = "{U}{U}"

    # Ensure player has at least two islands on battlefield.
    p1 = state.players[1]
    for _ in range(2):
        lid = p1.library.pop()
        p1.battlefield.append(lid)
        state.cards[lid].zone = Zone.BATTLEFIELD
        state.cards[lid].types = ["Land"]
        state.cards[lid].name = "Island"

    assert can_pay_with_pool_and_lands(state, 1, "{U}{U}") is True


def test_cast_spell_rejects_if_cost_unpaid() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1

    cid = state.players[1].hand[0]
    state.cards[cid].name = "Big Spell"
    state.cards[cid].types = ["Sorcery"]
    state.cards[cid].mana_cost = "{5}{U}{U}"

    before_hand = len(state.players[1].hand)
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})
    assert len(state.players[1].hand) == before_hand


def test_mana_pool_empties_on_step_transition() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    state.players[1].mana_pool["U"] = 2
    state.players[2].mana_pool["R"] = 1

    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})

    assert state.step == Step.BEGIN_COMBAT
    assert sum(state.players[1].mana_pool.values()) == 0
    assert sum(state.players[2].mana_pool.values()) == 0


def test_generic_cost_can_use_colored_mana_pool() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.mana_pool["U"] = 3

    assert can_pay_with_pool_and_lands(state, 1, "{3}") is True
    assert auto_pay_cost(state, 1, "{3}") is True
    assert sum(p1.mana_pool.values()) == 0


def test_colored_and_generic_cost_cannot_double_spend_same_pool_mana() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.mana_pool["U"] = 1

    assert can_pay_with_pool_and_lands(state, 1, "{U}{1}") is False


def test_explicit_colorless_symbols_require_colorless_mana() -> None:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.mana_pool["R"] = 2

    assert can_pay_with_pool_and_lands(state, 1, "{C}{C}") is False

    p1.mana_pool["R"] = 0
    p1.mana_pool["C"] = 2
    assert can_pay_with_pool_and_lands(state, 1, "{C}{C}") is True
    assert auto_pay_cost(state, 1, "{C}{C}") is True
    assert sum(p1.mana_pool.values()) == 0


def test_dual_land_type_line_counts_as_blue_source_for_double_blue_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    # Two Hallowed Fountains should satisfy {U}{U}.
    for _ in range(2):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Land"]
        card.name = "Hallowed Fountain"
        card.type_line = "Land — Plains Island"
        card.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{U}{U}") is True
    assert auto_pay_cost(state, 1, "{U}{U}") is True
    tapped = sum(1 for cid in p1.battlefield if state.cards[cid].tapped)
    assert tapped == 2


def test_dual_land_type_line_supports_multiple_other_colors() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    # Two Stomping Ground should satisfy {R}{G}.
    for _ in range(2):
        cid = p1.library.pop()
        p1.battlefield.append(cid)
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Land"]
        card.name = "Stomping Ground"
        card.type_line = "Land — Mountain Forest"
        card.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{R}{G}") is True
    assert auto_pay_cost(state, 1, "{R}{G}") is True


def test_oracle_text_dual_land_without_basic_subtypes_is_supported() -> None:
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    cid = p1.library.pop()
    p1.battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Land"]
    card.name = "Battlefield Forge"
    card.type_line = "Land"
    card.oracle_text = "{T}: Add {R} or {W}."
    card.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{W}") is True


def test_tap_land_for_mana_honors_requested_color_when_available() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.battlefield = []
    p1.mana_pool = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}

    cid = p1.library.pop()
    p1.battlefield.append(cid)
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Land"]
    card.name = "Hallowed Fountain"
    card.type_line = "Land — Plains Island"
    card.oracle_text = "{T}: Add {W} or {U}."
    card.tapped = False

    engine.take_action(state, 1, {"type": "tap_land_for_mana", "card_id": cid, "color": "W"})
    assert state.players[1].mana_pool["W"] == 1
    assert state.players[1].mana_pool["U"] == 0


def test_mana_creature_can_help_pay_cost_when_not_summoning_sick() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []

    # One Forest land.
    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Forest"
    land.type_line = "Basic Land — Forest"
    land.tapped = False

    # One Llanowar Elves mana creature that can tap for G.
    elf_id = p1.library.pop()
    p1.battlefield.append(elf_id)
    elf = state.cards[elf_id]
    elf.zone = Zone.BATTLEFIELD
    elf.types = ["Creature"]
    elf.name = "Llanowar Elves"
    elf.oracle_text = "{T}: Add {G}."
    elf.tapped = False
    elf.summoning_sick = False

    assert can_pay_with_pool_and_lands(state, 1, "{1}{G}") is True
    assert auto_pay_cost(state, 1, "{1}{G}") is True
    assert land.tapped is True
    assert elf.tapped is True


def test_summoning_sick_mana_creature_cannot_pay_tap_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []

    # One Forest land.
    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Forest"
    land.type_line = "Basic Land — Forest"
    land.tapped = False

    # Llanowar Elves exists but is summoning sick, so can't tap for mana yet.
    elf_id = p1.library.pop()
    p1.battlefield.append(elf_id)
    elf = state.cards[elf_id]
    elf.zone = Zone.BATTLEFIELD
    elf.types = ["Creature"]
    elf.name = "Llanowar Elves"
    elf.oracle_text = "{T}: Add {G}."
    elf.tapped = False
    elf.summoning_sick = True

    assert can_pay_with_pool_and_lands(state, 1, "{1}{G}") is False


def test_noncreature_mana_source_can_pay_cost() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []

    # One Island land.
    land_id = p1.library.pop()
    p1.battlefield.append(land_id)
    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Island"
    land.type_line = "Basic Land — Island"
    land.tapped = False

    # One mana rock artifact.
    rock_id = p1.library.pop()
    p1.battlefield.append(rock_id)
    rock = state.cards[rock_id]
    rock.zone = Zone.BATTLEFIELD
    rock.types = ["Artifact"]
    rock.name = "Mind Stone"
    rock.oracle_text = "{T}: Add {C}."
    rock.tapped = False

    assert can_pay_with_pool_and_lands(state, 1, "{1}{U}") is True
    assert auto_pay_cost(state, 1, "{1}{U}") is True
    assert land.tapped is True
    assert rock.tapped is True


def test_nissa_style_static_ability_doubles_land_production_and_payment() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    p1 = state.players[1]
    p1.battlefield = []
    land_id = p1.library.pop()
    planeswalker_id = p1.library.pop()
    p1.battlefield.extend([land_id, planeswalker_id])

    land = state.cards[land_id]
    land.zone = Zone.BATTLEFIELD
    land.types = ["Land"]
    land.name = "Forest"
    land.type_line = "Basic Land - Forest"
    land.tapped = False
    nissa = state.cards[planeswalker_id]
    nissa.zone = Zone.BATTLEFIELD
    nissa.types = ["Planeswalker"]
    nissa.name = "Nissa, Who Shakes the World"
    nissa.oracle_text = "Lands you control have '{T}: Add two mana of any one color.'"
    nissa.tapped = False

    assert land_mana_amount(state, 1, land_id) == 2
    assert can_pay_with_pool_and_lands(state, 1, "{G}{G}")
    assert auto_pay_cost(state, 1, "{G}{G}")
    assert land.tapped
