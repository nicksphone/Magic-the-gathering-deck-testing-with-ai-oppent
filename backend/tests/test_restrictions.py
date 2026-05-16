from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine import combat
from rules_engine.engine import RulesEngine


def _setup_creature(state, player_id: int, name: str, power: int, toughness: int, oracle_text: str = "") -> str:
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
    c.oracle_text = oracle_text
    return cid


def test_cant_attack_creature_is_filtered_from_attackers() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    cid = _setup_creature(state, 1, "Pacified", 2, 2, "This creature can't attack.")
    combat.declare_attackers(state, [cid], {cid: "player:2"})
    assert cid not in state.attackers


def test_must_attack_if_able_auto_added_when_omitted() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    cid = _setup_creature(state, 1, "Berserker", 2, 2, "Berserker attacks each combat if able.")
    combat.declare_attackers(state, [], {})
    assert cid in state.attackers


def test_cant_attack_alone_enforced() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    lone = _setup_creature(state, 1, "Lone Wolf", 3, 1, "This creature can't attack alone.")
    combat.declare_attackers(state, [lone], {lone: "player:2"})
    assert lone not in state.attackers


def test_cant_attack_alone_not_treated_as_global_cant_attack() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_ATTACKERS

    lone = _setup_creature(state, 1, "Lone Wolf", 3, 1, "This creature can't attack alone.")
    ally = _setup_creature(state, 1, "Ally", 2, 2, "")
    combat.declare_attackers(state, [lone, ally], {lone: "player:2", ally: "player:2"})
    assert lone in state.attackers
    assert ally in state.attackers


def test_must_block_if_able_auto_assignment() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.step = Step.DECLARE_BLOCKERS

    atk = _setup_creature(state, 1, "Attacker", 2, 2)
    blk = _setup_creature(state, 2, "Guard", 1, 4, "Guard blocks each combat if able.")
    state.attackers = [atk]
    combat.declare_blockers(state, {})
    assert state.blocks.get(atk) == [blk]


def test_cast_only_during_your_turn_restriction_and_move_hint() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 2
    state.priority_player = 1
    state.step = Step.UPKEEP

    engine = RulesEngine()
    cid = state.players[1].hand[0]
    card = state.cards[cid]
    card.name = "Strict Timing"
    card.types = ["Instant"]
    card.type_line = "Instant"
    card.mana_cost = "{U}"
    card.oracle_text = "Cast this spell only during your turn."

    moves = engine.legal_moves(state, 1)
    restricted = [m for m in moves if m.get("type") == "cast_spell_restricted" and m.get("card_id") == cid]
    assert len(restricted) == 1
    assert "your turn" in restricted[0]["reason"].lower()


def test_static_you_cant_cast_spells_during_combat_enforced() -> None:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.BEGIN_COMBAT
    engine = RulesEngine()

    lock_id = state.players[1].hand[0]
    state.players[1].hand.remove(lock_id)
    state.players[1].battlefield.append(lock_id)
    lock = state.cards[lock_id]
    lock.zone = Zone.BATTLEFIELD
    lock.types = ["Enchantment"]
    lock.oracle_text = "You can't cast spells during combat."

    cid = state.players[1].hand[0]
    card = state.cards[cid]
    card.name = "Combat Trick"
    card.types = ["Instant"]
    card.type_line = "Instant"
    card.mana_cost = "{U}"
    card.oracle_text = "Draw a card."

    before_stack = len(state.stack)
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})
    assert len(state.stack) == before_stack
    assert any("can't cast" in line.lower() for line in state.log)
