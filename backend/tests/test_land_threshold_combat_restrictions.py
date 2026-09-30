from card_data.fallback_cards import fallback_card_payload
from game_state.state import MatchFactory, Step, Zone
from rules_engine import combat
from rules_engine.engine import RulesEngine
from rules_engine.restrictions import card_cant_attack, card_cant_block


def test_topiary_stomper_attack_and_block_unlock_at_seven_lands():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=61)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    stomper_id = state.players[1].hand.pop()
    stomper = state.cards[stomper_id]
    state.players[1].battlefield.append(stomper_id)
    stomper.move_to_zone(Zone.BATTLEFIELD)
    printed = fallback_card_payload("Topiary Stomper")
    stomper.name = printed["name"]
    stomper.oracle_text = printed["oracle_text"]
    stomper.types = ["Creature"]
    stomper.power = stomper.toughness = 4
    stomper.keywords = ["vigilance"]
    stomper.summoning_sick = False

    def add_forest():
        card_id = state.players[1].library.pop()
        land = state.cards[card_id]
        land.move_to_zone(Zone.BATTLEFIELD)
        land.types = ["Land"]
        state.players[1].battlefield.append(card_id)

    for _ in range(6):
        add_forest()
    for _ in range(7):
        card_id = state.players[2].library.pop()
        land = state.cards[card_id]
        land.move_to_zone(Zone.BATTLEFIELD)
        land.types = ["Land"]
        state.players[2].battlefield.append(card_id)
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    assert card_cant_attack(state, stomper_id)
    assert not any(stomper_id in move.get("attackers", []) for move in RulesEngine().legal_moves(state, 1))
    combat.declare_attackers(state, [stomper_id])
    assert state.attackers == []

    attacker_id = state.players[2].hand.pop()
    attacker = state.cards[attacker_id]
    attacker.move_to_zone(Zone.BATTLEFIELD)
    attacker.types = ["Creature"]
    attacker.power = attacker.toughness = 2
    state.players[2].battlefield.append(attacker_id)
    state.active_player = 2
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = [attacker_id]
    assert card_cant_block(state, stomper_id)
    combat.declare_blockers(state, {attacker_id: [stomper_id]})
    assert state.blocks == {}

    add_forest()
    assert not card_cant_attack(state, stomper_id)
    assert not card_cant_block(state, stomper_id)
    combat.declare_blockers(state, {attacker_id: [stomper_id]})
    assert state.blocks == {attacker_id: [stomper_id]}
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    combat.declare_attackers(state, [stomper_id])
    assert state.attackers == [stomper_id]
