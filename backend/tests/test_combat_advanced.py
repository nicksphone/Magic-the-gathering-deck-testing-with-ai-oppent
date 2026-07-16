from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine import combat


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
    card = state.cards[cid]
    card.zone = Zone.BATTLEFIELD
    card.name = name
    card.types = [type_name]
    card.oracle_text = oracle_text
    return cid


def test_trample_spills_over_to_player() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Trampler", 5, 5, ["trample"])
    blk = _setup_creature(state, 2, "Blocker", 2, 2, [])
    state.attackers = [atk]
    state.blocks = {atk: [blk]}
    before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[2].life == before - 3


def test_first_strike_kills_before_regular_damage() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "FS", 2, 2, ["first strike"])
    blk = _setup_creature(state, 2, "Vanilla", 2, 2, [])
    state.attackers = [atk]
    state.blocks = {atk: [blk]}
    combat.combat_damage(state)
    assert state.cards[atk].zone == Zone.BATTLEFIELD
    assert state.cards[blk].zone == Zone.GRAVEYARD


def test_multi_block_assignment_kills_multiple_small_blockers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Attacker", 4, 4, [])
    blk1 = _setup_creature(state, 2, "B1", 1, 1, [])
    blk2 = _setup_creature(state, 2, "B2", 1, 1, [])
    state.attackers = [atk]
    state.blocks = {atk: [blk1, blk2]}
    combat.combat_damage(state)
    assert state.cards[blk1].zone == Zone.GRAVEYARD
    assert state.cards[blk2].zone == Zone.GRAVEYARD


def test_lifelink_gains_life_on_combat_damage() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Lifelink Attacker", 3, 3, ["lifelink"])
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}
    a_life_before = state.players[1].life
    b_life_before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[1].life == a_life_before + 3
    assert state.players[2].life == b_life_before - 3


def test_deathtouch_trample_assigns_one_to_blocker_and_spills_rest() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Deadly Trampler", 4, 4, ["deathtouch", "trample"])
    blk = _setup_creature(state, 2, "Big Blocker", 5, 5, [])
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}
    state.blocks = {atk: [blk]}
    b_life_before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[2].life == b_life_before - 3
    assert state.cards[blk].zone == Zone.GRAVEYARD


def test_double_strike_deals_damage_in_both_steps() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Double Striker", 2, 2, ["double strike"])
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}
    b_life_before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[2].life == b_life_before - 4


def test_block_declaration_hands_priority_back_to_active_player() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.DECLARE_BLOCKERS
    engine = RulesEngine()

    atk = _setup_creature(state, 1, "Attacker", 3, 3, [])
    blk = _setup_creature(state, 2, "Blocker", 3, 3, [])
    state.attackers = [atk]
    state.attackers_declared = True

    engine.take_action(state, 2, {"type": "block", "blocks": {atk: blk}})

    assert state.blocks == {atk: [blk]}
    assert state.priority_player == state.active_player == 1


def test_block_window_closes_after_block_assignment() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.DECLARE_BLOCKERS
    engine = RulesEngine()

    atk = _setup_creature(state, 1, "Attacker", 3, 3, [])
    blk = _setup_creature(state, 2, "Blocker", 3, 3, [])
    state.attackers = [atk]
    state.attackers_declared = True

    engine.take_action(state, 2, {"type": "block", "blocks": {atk: blk}})

    moves = engine.legal_moves(state, 2)
    assert all(move.get("type") != "block" for move in moves)
    assert state.blockers_declared is True


def test_combat_progresses_after_blocker_assignment_and_priority_passes() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 2
    state.step = Step.DECLARE_BLOCKERS
    engine = RulesEngine()

    atk = _setup_creature(state, 1, "Attacker", 3, 3, [])
    blk = _setup_creature(state, 2, "Blocker", 3, 3, [])
    state.attackers = [atk]
    state.attackers_declared = True

    engine.take_action(state, 2, {"type": "block", "blocks": {atk: blk}})
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})

    assert state.step == Step.COMBAT_DAMAGE


def test_combat_damage_marks_clear_on_cleanup() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.COMBAT_DAMAGE
    engine = RulesEngine()

    atk = _setup_creature(state, 1, "Attacker", 2, 2, [])
    blk = _setup_creature(state, 2, "Blocker", 1, 3, [])
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}
    state.blocks = {atk: [blk]}
    combat.combat_damage(state)
    assert state.cards[blk].zone == Zone.BATTLEFIELD
    assert int(state.cards[blk].counters.get("__damage_marked", 0)) > 0

    state.step = Step.END_STEP
    state.priority_player = 1
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert state.step == Step.CLEANUP
    assert int(state.cards[blk].counters.get("__damage_marked", 0)) == 0


def test_combat_damage_triggers_player_hit_trigger() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Sabertooth", 2, 2, [])
    state.cards[atk].oracle_text = "Whenever this creature deals combat damage to a player, draw a card."
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}

    combat.combat_damage(state)

    assert any(item.controller == 1 for item in state.stack)


def test_attack_declared_triggers_attack_payoff() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    atk = _setup_creature(state, 1, "Combat Celebrant", 2, 2, [])
    state.cards[atk].oracle_text = "Whenever this creature attacks, draw a card."

    combat.declare_attackers(state, [atk], {atk: "player:2"})

    assert any(item.controller == 1 for item in state.stack)


def test_attack_declared_can_create_token_payoff() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    atk = _setup_creature(state, 1, "Recruiter", 2, 2, [])
    state.cards[atk].oracle_text = "Whenever this creature attacks, create a 1/1 white Soldier creature token."

    combat.declare_attackers(state, [atk], {atk: "player:2"})

    assert any(item.effect_key == "create_token" for item in state.stack)


def test_block_declared_triggers_block_payoff() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Attacker", 2, 2, [])
    blk = _setup_creature(state, 2, "Guard", 2, 2, [])
    state.cards[blk].oracle_text = "Whenever this creature blocks, draw a card."
    state.attackers = [atk]

    combat.declare_blockers(state, {atk: [blk]})

    assert any(item.controller == 2 for item in state.stack)


def test_flying_attacker_cannot_be_blocked_by_ground_creature() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Sky Drake", 2, 2, ["flying"])
    blk = _setup_creature(state, 2, "Bear", 2, 2, [])
    state.attackers = [atk]
    combat.declare_blockers(state, {atk: [blk]})
    assert state.blocks == {}


def test_reach_creature_can_block_flying_attacker() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Sky Drake", 2, 2, ["flying"])
    blk = _setup_creature(state, 2, "Spider", 1, 3, ["reach"])
    state.attackers = [atk]
    combat.declare_blockers(state, {atk: [blk]})
    assert state.blocks.get(atk) == [blk]


def test_menace_requires_two_blockers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Menace Attacker", 3, 3, ["menace"])
    blk1 = _setup_creature(state, 2, "B1", 2, 2, [])
    blk2 = _setup_creature(state, 2, "B2", 2, 2, [])
    state.attackers = [atk]

    combat.declare_blockers(state, {atk: [blk1]})
    assert state.blocks == {}

    combat.declare_blockers(state, {atk: [blk1, blk2]})
    assert state.blocks.get(atk) == [blk1, blk2]


def test_cannot_be_blocked_except_by_three_or_more_creatures() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Huge Threat", 5, 5, [])
    state.cards[atk].oracle_text = "This creature can't be blocked except by three or more creatures."
    blk1 = _setup_creature(state, 2, "B1", 2, 2, [])
    blk2 = _setup_creature(state, 2, "B2", 2, 2, [])
    blk3 = _setup_creature(state, 2, "B3", 2, 2, [])
    state.attackers = [atk]

    combat.declare_blockers(state, {atk: [blk1, blk2]})
    assert state.blocks == {}

    combat.declare_blockers(state, {atk: [blk1, blk2, blk3]})
    assert state.blocks.get(atk) == [blk1, blk2, blk3]


def test_blocker_with_additional_block_capacity_can_block_two_attackers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk1 = _setup_creature(state, 1, "A1", 2, 2, [])
    atk2 = _setup_creature(state, 1, "A2", 2, 2, [])
    blocker = _setup_creature(state, 2, "Wall Captain", 1, 5, [])
    state.cards[blocker].oracle_text = "Wall Captain can block an additional creature each combat."
    state.attackers = [atk1, atk2]

    combat.declare_blockers(state, {atk1: [blocker], atk2: [blocker]})
    assert state.blocks.get(atk1) == [blocker]
    assert state.blocks.get(atk2) == [blocker]


def test_default_blocker_cannot_block_two_attackers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk1 = _setup_creature(state, 1, "A1", 2, 2, [])
    atk2 = _setup_creature(state, 1, "A2", 2, 2, [])
    blocker = _setup_creature(state, 2, "Bear", 2, 2, [])
    state.attackers = [atk1, atk2]

    combat.declare_blockers(state, {atk1: [blocker], atk2: [blocker]})
    blocked_count = sum(1 for blockers in state.blocks.values() if blocker in blockers)
    assert blocked_count == 1


def test_anthem_effect_increases_combat_damage_output() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Soldier", 2, 2, [])
    anthem = _setup_creature(state, 1, "Anthem Source", 0, 1, [])
    state.cards[anthem].types = ["Enchantment"]
    state.cards[anthem].oracle_text = "Creatures you control get +1/+1."
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}
    before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[2].life == before - 3


def test_anthem_effect_allows_creature_to_survive_marked_damage() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Attacker", 1, 1, [])
    blk = _setup_creature(state, 2, "Defender", 1, 1, [])
    anthem = _setup_creature(state, 2, "Anthem Source", 0, 1, [])
    state.cards[anthem].types = ["Enchantment"]
    state.cards[anthem].oracle_text = "Creatures you control get +1/+1."
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}
    state.blocks = {atk: [blk]}
    combat.combat_damage(state)
    # With +1/+1 anthem, blocker is effectively 2/2 and survives 1 marked damage.
    assert state.cards[blk].zone == Zone.BATTLEFIELD
    # Blocker deals effectively 2 damage back and kills the 1/1 attacker.
    assert state.cards[atk].zone == Zone.GRAVEYARD


def test_vigilance_attacker_does_not_tap() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    atk = _setup_creature(state, 1, "Vigilant Knight", 3, 3, ["vigilance"])
    combat.declare_attackers(state, [atk], {atk: "player:2"})
    assert atk in state.attackers
    assert state.cards[atk].tapped is False


def test_defender_creature_cannot_attack() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    atk = _setup_creature(state, 1, "Wall", 0, 4, ["defender"])
    combat.declare_attackers(state, [atk], {atk: "player:2"})
    assert atk not in state.attackers


def test_islandwalk_attacker_is_unblockable_if_defender_controls_island() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Merfolk", 2, 2, ["islandwalk"])
    blk = _setup_creature(state, 2, "Bear", 2, 2, [])
    land = _setup_creature(state, 2, "Island", 0, 0, [])
    state.cards[land].types = ["Land"]
    state.cards[land].type_line = "Basic Land — Island"
    state.attackers = [atk]
    combat.declare_blockers(state, {atk: [blk]})
    assert state.blocks == {}


def test_islandwalk_attacker_can_be_blocked_without_island() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Merfolk", 2, 2, ["islandwalk"])
    blk = _setup_creature(state, 2, "Bear", 2, 2, [])
    land = _setup_creature(state, 2, "Forest", 0, 0, [])
    state.cards[land].types = ["Land"]
    state.cards[land].type_line = "Basic Land — Forest"
    state.attackers = [atk]
    combat.declare_blockers(state, {atk: [blk]})
    assert state.blocks.get(atk) == [blk]


def test_protection_from_color_prevents_blocking_by_that_color() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Paladin", 2, 2, ["protection from red"])
    blk = _setup_creature(state, 2, "Red Bear", 2, 2, [])
    state.cards[blk].mana_cost = "{1}{R}"
    state.attackers = [atk]
    combat.declare_blockers(state, {atk: [blk]})
    assert state.blocks == {}


def test_cant_be_blocked_except_by_two_or_more_oracle_text() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Sneak", 3, 3, [])
    state.cards[atk].oracle_text = "This creature can't be blocked except by two or more creatures."
    blk1 = _setup_creature(state, 2, "B1", 2, 2, [])
    blk2 = _setup_creature(state, 2, "B2", 2, 2, [])
    state.attackers = [atk]
    combat.declare_blockers(state, {atk: [blk1]})
    assert state.blocks == {}
    combat.declare_blockers(state, {atk: [blk1, blk2]})
    assert state.blocks.get(atk) == [blk1, blk2]


def test_protection_from_creatures_prevents_creature_blocks_and_damage() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Protector", 3, 3, ["protection from creatures"])
    blk = _setup_creature(state, 2, "Bear", 3, 3, [])
    state.attackers = [atk]
    state.attack_targets = {atk: "player:2"}
    combat.declare_blockers(state, {atk: [blk]})
    assert state.blocks == {}

    state.step = Step.COMBAT_DAMAGE
    before = state.players[2].life
    combat.combat_damage(state)
    assert state.players[2].life == before - 3
    assert state.cards[atk].zone == Zone.BATTLEFIELD
    assert state.cards[blk].zone == Zone.BATTLEFIELD


def test_protection_from_multicolored_blocks_multicolored_source_damage() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.COMBAT_DAMAGE

    atk = _setup_creature(state, 1, "Gold Knight", 3, 3, [])
    state.cards[atk].mana_cost = "{R}{W}"
    blk = _setup_creature(state, 2, "Warded", 2, 2, ["protection from multicolored"])
    state.attackers = [atk]
    state.blocks = {atk: [blk]}
    combat.combat_damage(state)
    assert state.cards[blk].zone == Zone.BATTLEFIELD


def test_shadow_creatures_only_block_and_are_blocked_by_shadow() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Shade", 2, 2, ["shadow"])
    blk = _setup_creature(state, 2, "Bear", 2, 2, [])
    shadow_blk = _setup_creature(state, 2, "Shadow Bear", 2, 2, ["shadow"])
    state.attackers = [atk]

    combat.declare_blockers(state, {atk: [blk]})
    assert state.blocks == {}

    combat.declare_blockers(state, {atk: [shadow_blk]})
    assert state.blocks.get(atk) == [shadow_blk]


def test_fear_and_intimidate_blocking_restrictions_work() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    fear_atk = _setup_creature(state, 1, "Nightstalker", 2, 2, ["fear"])
    state.cards[fear_atk].mana_cost = "{B}"
    black_blk = _setup_creature(state, 2, "Dread Knight", 2, 2, [])
    state.cards[black_blk].mana_cost = "{B}"
    white_blk = _setup_creature(state, 2, "Soldier", 2, 2, [])
    state.cards[white_blk].mana_cost = "{W}"
    state.attackers = [fear_atk]

    combat.declare_blockers(state, {fear_atk: [white_blk]})
    assert state.blocks == {}
    combat.declare_blockers(state, {fear_atk: [black_blk]})
    assert state.blocks.get(fear_atk) == [black_blk]

    state.blocks = {}
    intimidate_atk = _setup_creature(state, 1, "Warband", 2, 2, ["intimidate"])
    state.cards[intimidate_atk].mana_cost = "{R}"
    red_blk = _setup_creature(state, 2, "Goblin", 2, 2, [])
    state.cards[red_blk].mana_cost = "{R}"
    green_blk = _setup_creature(state, 2, "Elf", 2, 2, [])
    state.cards[green_blk].mana_cost = "{G}"
    artifact_blk = _setup_creature(state, 2, "Myr", 2, 2, [])
    state.cards[artifact_blk].types = ["Artifact", "Creature"]
    state.cards[artifact_blk].mana_cost = "{2}"
    state.attackers = [intimidate_atk]

    combat.declare_blockers(state, {intimidate_atk: [green_blk]})
    assert state.blocks == {}
    combat.declare_blockers(state, {intimidate_atk: [red_blk]})
    assert state.blocks.get(intimidate_atk) == [red_blk]
    combat.declare_blockers(state, {intimidate_atk: [artifact_blk]})
    assert state.blocks.get(intimidate_atk) == [artifact_blk]
def test_nonbasic_landwalk_prevents_blocking() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=21)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    attacker = _setup_creature(state, 1, "Nonbasic Walker", 2, 2, ["nonbasic landwalk"])
    blocker = _setup_creature(state, 2, "Bear", 2, 2, [])
    land = _setup_permanent(state, 2, "Hallowed Fountain", "Land", "")
    state.cards[land].type_line = "Land — Plains Island"
    state.attackers = [attacker]

    combat.declare_blockers(state, {attacker: [blocker]})

    assert state.blocks == {}


def test_snow_landwalk_prevents_blocking_when_snow_land_is_controlled() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=22)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    attacker = _setup_creature(state, 1, "Snow Walker", 2, 2, ["snow landwalk"])
    blocker = _setup_creature(state, 2, "Bear", 2, 2, [])
    land = _setup_permanent(state, 2, "Snow-Covered Forest", "Land", "")
    state.cards[land].type_line = "Basic Snow Land — Forest"
    state.attackers = [attacker]

    combat.declare_blockers(state, {attacker: [blocker]})

    assert state.blocks == {}
