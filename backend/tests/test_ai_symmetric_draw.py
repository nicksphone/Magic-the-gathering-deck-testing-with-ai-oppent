"""Symmetric draw is not automatically one-sided card advantage."""

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step
import pytest

from tests.ai_information76_canonical import deck_entry, symmetric_deck


DECK = [deck_entry('Island', 60)]


def _position(card_name='Vision Skeins'):
    state = MatchFactory.from_decks(symmetric_deck(card_name, 318), DECK, seed=318)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 2
    state.priority_player = 1
    state.step = Step.END_STEP
    cid = state.players[1].hand[0]
    moves = [{"type": "cast_spell", "card_id": cid}, {"type": "pass_priority"}]
    return state, moves


@pytest.mark.parametrize("archetype", ["Control", "Tempo", "Aggro", "Ramp", "Tokens"])
def test_ai_holds_symmetric_draw_when_it_refills_only_opponent(archetype):
    state, moves = _position()
    state.players[2].hand.clear()
    decision = AIAgent(difficulty="master", archetype=archetype).choose_action(state, moves, 1)
    assert decision.action["type"] == "pass_priority"


def test_ai_uses_symmetric_draw_when_it_decks_opponent_safely():
    state, moves = _position()
    state.players[2].hand.clear()
    state.players[2].library.clear()
    decision = AIAgent(difficulty="master", archetype="Control").choose_action(state, moves, 1)
    assert decision.action["type"] == "cast_spell"


def test_ai_avoids_symmetric_draw_that_only_decks_itself():
    state, moves = _position()
    state.players[1].library.clear()
    decision = AIAgent(difficulty="master", archetype="Control").choose_action(state, moves, 1)
    assert decision.action["type"] == "pass_priority"


def test_ai_checks_x_draw_against_both_library_sizes():
    state, moves = _position('Prosperity')
    cid = moves[0]["card_id"]
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].mana_pool = {"C": 5, "U": 1}
    state.players[1].library = state.players[1].library[:1]
    ai = AIAgent(difficulty="master", archetype="Ramp")
    assert ai._bad_shared_draw_cast(state, moves[0], 1)
    state.players[2].library.clear()
    assert not ai._bad_shared_draw_cast(state, moves[0], 1)
