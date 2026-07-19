from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def _saga_state(oracle: str):
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=41,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    saga = CardInstance(
        id="saga",
        name="Test Saga",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        type_line="Enchantment — Saga",
        oracle_text=oracle,
    )
    state.cards[saga.id] = saga
    state.players[1].battlefield.append(saga.id)
    state.active_player = 1
    state.priority_player = 1
    return state


def test_saga_adds_lore_and_places_chapter_on_stack() -> None:
    state = _saga_state("I — Draw a card.\nII — Gain 2 life.")
    state.step = Step.DRAW
    before_hand = len(state.players[1].hand)
    RulesEngine().next_step(state)
    assert state.step == Step.PRECOMBAT_MAIN
    assert state.cards["saga"].counters["__lore"] == 1
    assert state.stack and "chapter 1" in state.stack[-1].label
    RulesEngine().next_step(state)
    assert len(state.players[1].hand) == before_hand + 1


def test_saga_is_sacrificed_after_final_chapter_resolves() -> None:
    state = _saga_state("I — Draw a card.")
    state.step = Step.DRAW
    engine = RulesEngine()
    engine.next_step(state)
    assert state.stack
    engine.next_step(state)
    assert "saga" in state.players[1].graveyard
    assert state.cards["saga"].zone == Zone.GRAVEYARD
