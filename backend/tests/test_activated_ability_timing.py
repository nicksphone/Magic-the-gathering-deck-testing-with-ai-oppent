import pytest

from game_state.state import MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from game_state.serializers import serialize_match_snapshot


def _state(oracle_text: str):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=7)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    source_id = state.players[1].library.pop()
    source = state.cards[source_id]
    source.zone = Zone.BATTLEFIELD
    source.types = ["Artifact"]
    source.oracle_text = oracle_text
    state.players[1].battlefield.append(source_id)
    return state, source_id


@pytest.mark.parametrize("active,step,stacked", [
    (1, Step.UPKEEP, False),
    (2, Step.PRECOMBAT_MAIN, False),
    (1, Step.POSTCOMBAT_MAIN, True),
])
def test_sorcery_only_activation_is_unavailable_and_direct_action_is_rejected(active, step, stacked) -> None:
    state, source_id = _state("{T}: Draw a card. Activate only as a sorcery.")
    state.active_player = active
    state.step = step
    if stacked:
        state.stack.append(StackItem("pending", source_id, 1, "Pending", "noop", {}))
    before_stack = list(state.stack)
    assert not any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected, match="sorcery speed"):
        RulesEngine().take_action(
            state, 1, {"type": "activate_ability", "card_id": source_id, "ability_index": 0},
            reject_invalid=True,
        )
    assert state.stack == before_stack
    assert not state.cards[source_id].tapped


def test_sorcery_only_activation_is_available_in_own_empty_main_phase() -> None:
    state, source_id = _state("{T}: Draw a card. Activate only as a sorcery.")
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "activate_ability")
    RulesEngine().take_action(state, 1, move, reject_invalid=True)
    assert state.cards[source_id].tapped
    assert state.stack[-1].effect_key == "draw_cards"


def test_unrestricted_activated_ability_remains_available_with_stack() -> None:
    state, source_id = _state("{T}: Draw a card.")
    state.stack.append(StackItem("pending", source_id, 1, "Pending", "noop", {}))
    assert any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))


def test_restricted_x_payment_is_not_offered_or_charged_without_color_enforcement() -> None:
    state, source_id = _state("{X}: This creature deals X damage to each creature and each player. Spend only black mana on X.")
    state.cards[source_id].name = "Crypt Rats"
    state.cards[source_id].types = ["Creature"]
    state.players[1].mana_pool["B"] = 3
    before = serialize_match_snapshot(state)
    assert not any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        RulesEngine().take_action(state, 1, {
            "type": "activate_ability", "card_id": source_id,
            "ability_index": 0, "targets": {"x_value": 2},
        }, reject_invalid=True)
    assert serialize_match_snapshot(state) == before
