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
