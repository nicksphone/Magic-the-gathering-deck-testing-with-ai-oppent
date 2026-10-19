from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from tests.transform_draw_canonical_fixtures import permanent


def _state():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=152)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    corruption = permanent("corruption", "Corruption of Towashi")
    state.cards[corruption.id] = corruption
    state.players[1].battlefield.append(corruption.id)
    return state


def test_declining_transform_draw_allows_later_trigger_but_accepting_stops_it():
    state = _state()
    initial_hand = len(state.players[1].hand)
    emit_event(state, "enters_battlefield", {"card_id": "corruption", "controller": 1})
    assert [item.effect_key for item in state.stack] == ["incubate"]
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == initial_hand
    token = next(state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].name == "Incubator")
    assert token.counters == {"+1/+1": 4}

    land_id = state.players[1].hand.pop()
    state.cards[land_id].zone = Zone.BATTLEFIELD
    state.players[1].battlefield.append(land_id)
    emit_event(state, "enters_battlefield", {"card_id": land_id, "controller": 1})
    assert not state.stack

    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    resolve_effect(state, 1, "transform_card", {"target_card_id": token.id, "face_index": 1})
    assert state.stack[-1].effect_key == "draw_cards"
    resolve_top_of_stack(state)
    assert state.pending_trigger_order["phase"] == "optional"
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules = RulesEngine()
    decline = next(move for move in rules.legal_moves(state, 1) if move["type"] == "choose_optional_effect" and not move["accept"])
    rules.take_action(state, 1, decline, reject_invalid=True)
    assert not state.stack
    assert len(state.players[1].hand) == initial_hand - 1

    resolve_effect(state, 1, "transform_card", {"target_card_id": token.id, "face_index": 0})
    assert state.stack[-1].effect_key == "draw_cards"
    resolve_top_of_stack(state)
    accept = next(move for move in rules.legal_moves(state, 1) if move["type"] == "choose_optional_effect" and move["accept"])
    rules.take_action(state, 1, accept, reject_invalid=True)
    assert len(state.players[1].hand) == initial_hand
    assert not state.stack

    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_effect(state, 1, "transform_card", {"target_card_id": token.id, "face_index": 1})
    assert not state.stack

    state.step = Step.CLEANUP
    rules.next_step(state)
    state.step = Step.CLEANUP
    rules.next_step(state)
    resolve_effect(state, 1, "transform_card", {"target_card_id": token.id, "face_index": 0})
    assert state.stack[-1].effect_key == "draw_cards"


def test_entering_transformed_counts_but_modal_back_face_does_not():
    state = _state()
    transformed = permanent("etching", "Kumano Faces Kakkazan // Etching of Kumano", face_index=1)
    state.cards[transformed.id] = transformed
    state.players[1].battlefield.append(transformed.id)
    emit_event(state, "enters_battlefield", {"card_id": transformed.id, "controller": 1})
    assert [item.effect_key for item in state.stack] == ["draw_cards"]
    initial_hand = len(state.players[1].hand)
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == initial_hand + 1

    second = permanent("second-etching", "Kumano Faces Kakkazan // Etching of Kumano", face_index=1)
    state.cards[second.id] = second
    state.players[1].battlefield.append(second.id)
    emit_event(state, "enters_battlefield", {"card_id": second.id, "controller": 1})
    assert not state.stack

    modal = permanent("modal", "Bala Ged Recovery // Bala Ged Sanctuary", face_index=1)
    state.cards[modal.id] = modal
    state.players[1].battlefield.append(modal.id)
    emit_event(state, "enters_battlefield", {"card_id": modal.id, "controller": 1})
    assert not state.stack
