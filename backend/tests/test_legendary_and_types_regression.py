from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions


def test_legend_rule_applies_for_offline_named_legendary_permanents() -> None:
    # Simulates cache-miss entries without explicit "Legendary" type line.
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    first = state.players[1].hand.pop()
    second = state.players[1].hand.pop()
    for cid in (first, second):
        state.players[1].battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.cards[cid].name = "Sheoldred, the Apocalypse"
        state.cards[cid].types = ["Creature"]
        state.cards[cid].type_line = ""

    apply_state_based_actions(state)

    on_field = [cid for cid in state.players[1].battlefield if state.cards[cid].name == "Sheoldred, the Apocalypse"]
    in_grave = [cid for cid in state.players[1].graveyard if state.cards[cid].name == "Sheoldred, the Apocalypse"]
    assert len(on_field) == 1
    assert len(in_grave) == 1


def test_ossification_is_inferred_as_enchantment_not_sorcery() -> None:
    deck = [{"quantity": 60, "card_name": "Ossification"}]
    state = MatchFactory.from_decks(deck, deck)
    any_card = state.cards[state.players[1].library[0]]
    assert "Enchantment" in any_card.types
    assert "Sorcery" not in any_card.types


def test_ai_prefers_attack_on_open_board() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS

    attacker = state.players[1].hand.pop()
    state.players[1].battlefield.append(attacker)
    state.cards[attacker].zone = Zone.BATTLEFIELD
    state.cards[attacker].types = ["Creature"]
    state.cards[attacker].power = 4
    state.cards[attacker].toughness = 4
    state.cards[attacker].summoning_sick = False

    engine = RulesEngine()
    legal = engine.legal_moves(state, 1)
    agent = AIAgent(difficulty="master", archetype="Control")
    decision = agent.choose_action(state, legal, 1)
    assert decision.action.get("type") == "attack"
