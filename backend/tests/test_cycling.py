from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def _state_with_cycler() -> tuple[object, str]:
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}])
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    state.players[1].battlefield.append("land-1")
    state.cards["land-1"] = CardInstance(
        id="land-1", name="Island", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Land"]
    )
    cid = "cycler"
    state.cards[cid] = CardInstance(
        id=cid,
        name="Lonely Sandbar",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Land"],
        oracle_text="Cycling {1}",
    )
    state.players[1].hand.append(cid)
    return state, cid


def test_fixed_cycling_is_a_legal_hand_action() -> None:
    state, cid = _state_with_cycler()
    moves = RulesEngine().legal_moves(state, 1)
    assert any(m["type"] == "cycle_card" and m["card_id"] == cid for m in moves)


def test_cycling_pays_cost_discards_then_draws_on_resolution() -> None:
    state, cid = _state_with_cycler()
    engine = RulesEngine()
    before_hand = len(state.players[1].hand)
    engine.take_action(state, 1, {"type": "cycle_card", "card_id": cid})
    assert cid in state.players[1].graveyard
    assert cid not in state.players[1].hand
    assert len(state.players[1].hand) == before_hand - 1
    assert state.stack
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert not state.stack
    assert len(state.players[1].hand) == before_hand
