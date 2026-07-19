from __future__ import annotations

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions
from game_state.state import CardInstance


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


def test_legend_rule_emits_leave_and_death_triggers() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine = CardInstance(
        "legend-engine", "Death Engine", 1, 1, Zone.BATTLEFIELD, ["Enchantment"],
        oracle_text="Whenever another permanent you control leaves the battlefield, draw a card.",
        type_line="Enchantment",
    )
    state.cards[engine.id] = engine
    state.players[1].battlefield.append(engine.id)
    first = state.players[1].hand.pop()
    second = state.players[1].hand.pop()
    for cid in (first, second):
        state.players[1].battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
        state.cards[cid].name = "Legendary Bear"
        state.cards[cid].types = ["Creature", "Legendary"]
        state.cards[cid].type_line = "Legendary Creature — Bear"

    before_hand = len(state.players[1].hand)
    apply_state_based_actions(state)

    assert len(state.stack) == 1
    from rules_engine.stack_engine import resolve_top_of_stack
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == before_hand + 1


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
