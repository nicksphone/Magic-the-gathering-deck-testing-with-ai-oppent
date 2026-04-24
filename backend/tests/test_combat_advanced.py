from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
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
