from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine import combat
from rules_engine.continuous import effective_keywords, effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions


def _setup_creature(state, player_id: int, name: str, power: int, toughness: int, keywords: list[str] | None = None) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    c.zone = Zone.BATTLEFIELD
    c.name = name
    c.types = ["Creature"]
    c.power = power
    c.toughness = toughness
    c.summoning_sick = False
    c.keywords = keywords or []
    return cid


def _setup_permanent(state, player_id: int, name: str, type_name: str, oracle_text: str) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    c.zone = Zone.BATTLEFIELD
    c.name = name
    c.types = [type_name]
    c.oracle_text = oracle_text
    return cid


def test_other_creatures_you_control_get_bonus_excludes_source() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    anthem = _setup_creature(state, 1, "Chief", 2, 2, [])
    state.cards[anthem].type_line = "Creature - Elf Warrior"
    state.cards[anthem].oracle_text = "Other creatures you control get +1/+1."
    buddy = _setup_creature(state, 1, "Buddy", 2, 2, [])

    assert effective_power(state, anthem) == 2
    assert effective_toughness(state, anthem) == 2
    assert effective_power(state, buddy) == 3
    assert effective_toughness(state, buddy) == 3


def test_tribal_static_buff_applies_to_subtype() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    _setup_permanent(state, 1, "Elvish Anthem", "Enchantment", "Elves you control get +1/+1.")
    elf = _setup_creature(state, 1, "Llanowar Elves", 1, 1, [])
    state.cards[elf].type_line = "Creature - Elf Druid"
    beast = _setup_creature(state, 1, "Bear", 2, 2, [])
    state.cards[beast].type_line = "Creature - Bear"

    assert effective_power(state, elf) == 2
    assert effective_toughness(state, elf) == 2
    assert effective_power(state, beast) == 2
    assert effective_toughness(state, beast) == 2


def test_become_base_power_toughness_static_sets_are_parsed() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    _setup_permanent(state, 1, "Humility Field", "Enchantment", "Creatures you control become 1/1.")
    creature = _setup_creature(state, 1, "Hill Giant", 4, 4, [])

    assert effective_power(state, creature) == 1
    assert effective_toughness(state, creature) == 1


def test_subject_specific_base_pt_set_only_applies_to_matching_creatures() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    _setup_permanent(state, 1, "Elf Ward", "Enchantment", "Elves you control become 1/1.")
    elf = _setup_creature(state, 1, "Llanowar Elves", 1, 1, [])
    state.cards[elf].type_line = "Creature - Elf Druid"
    human = _setup_creature(state, 1, "Knight", 3, 3, [])
    state.cards[human].type_line = "Creature - Human Knight"

    assert effective_power(state, elf) == 1
    assert effective_toughness(state, elf) == 1
    assert effective_power(state, human) == 3
    assert effective_toughness(state, human) == 3


def test_creatures_you_control_have_reach_allows_blocking_flyers() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    attacker = _setup_creature(state, 1, "Sky Drake", 2, 2, ["flying"])
    blocker = _setup_creature(state, 2, "Ground Bear", 2, 2, [])
    _setup_permanent(state, 2, "Global Reach", "Enchantment", "Creatures you control have reach.")
    state.attackers = [attacker]

    assert "reach" in effective_keywords(state, blocker)
    combat.declare_blockers(state, {attacker: [blocker]})
    assert state.blocks.get(attacker) == [blocker]


def test_cant_have_keyword_override_wins_over_granted_keyword() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    _setup_permanent(state, 1, "Grant", "Enchantment", "Creatures you control have flying.")
    _setup_permanent(state, 1, "Suppression", "Enchantment", "Creatures you control can't have flying.")
    creature = _setup_creature(state, 1, "Ground Bear", 2, 2, [])

    assert "flying" not in effective_keywords(state, creature)


def test_opponent_static_minus_kills_x1_creature() -> None:
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    _setup_permanent(state, 1, "Curse Aura", "Enchantment", "Creatures your opponents control get -1/-1.")
    victim = _setup_creature(state, 2, "Token", 1, 1, [])
    apply_state_based_actions(state)
    assert state.cards[victim].zone == Zone.GRAVEYARD


def test_indestructible_grant_prevents_combat_lethal_death() -> None:
    deck = [{"quantity": 60, "card_name": "Plains"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    attacker = _setup_creature(state, 1, "Attacker", 2, 2, [])
    blocker = _setup_creature(state, 2, "Blocker", 2, 2, [])
    _setup_permanent(state, 2, "Shield", "Artifact", "Creatures you control have indestructible.")
    state.attackers = [attacker]
    state.blocks = {attacker: [blocker]}

    combat.combat_damage(state)
    assert state.cards[blocker].zone == Zone.BATTLEFIELD

    # Run SBA as a second safety check path.
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "pass_priority"})
    assert state.cards[blocker].zone == Zone.BATTLEFIELD


def test_continuous_buff_does_not_mutate_base_stats() -> None:
    """Anthem-like buffs must not permanently modify card.power/toughness."""
    from effects.registry import resolve_effect

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)

    # Create a 2/2 creature
    resolve_effect(
        state, 1, "create_token",
        {"name": "TestCreature", "power": 2, "toughness": 2, "amount": 1, "keywords": []},
    )
    cid = [c for c in state.players[1].battlefield if state.cards[c].name == "TestCreature"][0]
    base_power = state.cards[cid].power
    base_toughness = state.cards[cid].toughness

    # Call continuous_buff — should NOT mutate base stats
    resolve_effect(state, 1, "continuous_buff", {"amount": 1})

    # Base stats unchanged
    assert state.cards[cid].power == base_power
    assert state.cards[cid].toughness == base_toughness


def test_counters_affect_effective_stats_dynamically() -> None:
    """+1/+1 and -1/-1 counters should affect effective_power/toughness without mutating base."""
    from effects.registry import resolve_effect

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)

    # Create a 2/2 creature
    resolve_effect(
        state, 1, "create_token",
        {"name": "TestCreature", "power": 2, "toughness": 2, "amount": 1, "keywords": []},
    )
    cid = [c for c in state.players[1].battlefield if state.cards[c].name == "TestCreature"][0]

    # Base stats
    assert state.cards[cid].power == 2
    assert state.cards[cid].toughness == 2
    assert effective_power(state, cid) == 2
    assert effective_toughness(state, cid) == 2

    # Add a +1/+1 counter
    resolve_effect(state, 1, "add_counters", {"target_card_id": cid, "counter": "+1/+1", "amount": 1})
    assert state.cards[cid].power == 2  # base unchanged
    assert state.cards[cid].toughness == 2  # base unchanged
    assert effective_power(state, cid) == 3  # effective increased
    assert effective_toughness(state, cid) == 3

    # Add a -1/-1 counter
    resolve_effect(state, 1, "add_counters", {"target_card_id": cid, "counter": "-1/-1", "amount": 1})
    assert effective_power(state, cid) == 2  # back to base
    assert effective_toughness(state, cid) == 2


def test_self_scales_from_creatures_in_your_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    scaler = _setup_creature(state, 1, "Grave Scaler", 1, 1, [])
    state.cards[scaler].oracle_text = "This creature gets +1/+1 for each creature card in your graveyard."

    # Put two creature cards in controller graveyard.
    p1 = state.players[1]
    for idx in range(2):
        cid = p1.library.pop()
        p1.graveyard.append(cid)
        c = state.cards[cid]
        c.zone = Zone.GRAVEYARD
        c.types = ["Creature"]
        c.name = f"Dead Creature {idx+1}"
        c.type_line = "Creature - Elf"

    assert effective_power(state, scaler) == 3
    assert effective_toughness(state, scaler) == 3


def test_self_scales_from_other_creatures_you_control() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    scaler = _setup_creature(state, 1, "Pack Leader", 2, 2, [])
    state.cards[scaler].oracle_text = "Pack Leader gets +1/+1 for each other Elf you control."
    state.cards[scaler].type_line = "Creature - Elf Warrior"
    buddy = _setup_creature(state, 1, "Elf Buddy", 1, 1, [])
    state.cards[buddy].type_line = "Creature - Elf Druid"
    non_elf = _setup_creature(state, 1, "Bear", 2, 2, [])
    state.cards[non_elf].type_line = "Creature - Bear"

    assert effective_power(state, scaler) == 3
    assert effective_toughness(state, scaler) == 3


def test_characteristic_defined_pt_counts_distinct_graveyard_card_types() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    scaler = _setup_creature(state, 1, "Tarmogoyf", 0, 1, [])
    state.cards[scaler].power = "*"
    state.cards[scaler].oracle_text = "Tarmogoyf's power is equal to the number of card types among cards in all graveyards and its toughness is equal to that number plus 1."
    p1 = state.players[1]
    for card_type in ("Artifact", "Instant"):
        cid = p1.library.pop()
        p1.graveyard.append(cid)
        state.cards[cid].zone = Zone.GRAVEYARD
        state.cards[cid].types = [card_type]

    assert effective_power(state, scaler) == 2
    assert effective_toughness(state, scaler) == 3
