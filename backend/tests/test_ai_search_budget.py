from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Zone


def test_master_skips_deep_copy_search_on_dense_token_boards(monkeypatch) -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=71,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    for index in range(11):
        cid = f"token-{index}"
        state.cards[cid] = CardInstance(
            id=cid,
            name="Soldier Token",
            owner=1,
            controller=1,
            zone=Zone.BATTLEFIELD,
            types=["Creature"],
            power=1,
            toughness=1,
        )
        state.players[1].battlefield.append(cid)
    agent = AIAgent(difficulty="master", archetype="Tokens")
    called = 0

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called += 1
        return 0.0

    monkeypatch.setattr(agent, "_simulate_delta", fail_if_called)
    agent._rank_moves(state, [{"type": "pass_priority"}], 1)

    assert called == 0
