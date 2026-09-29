from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack


INQUISITOR_ORACLE = (
    "When Norn's Inquisitor enters the battlefield, incubate 2.\n"
    "Whenever a permanent you control transforms into a Phyrexian, put a +1/+1 counter on it."
)


def _state():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=151)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    inquisitor = CardInstance(
        "inquisitor", "Norn's Inquisitor", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        oracle_text=INQUISITOR_ORACLE, type_line="Creature - Phyrexian Knight", power=1, toughness=1,
    )
    state.cards[inquisitor.id] = inquisitor
    state.players[1].battlefield.append(inquisitor.id)
    return state


def _incubator(state, controller=1):
    return next(state.cards[cid] for cid in state.players[controller].battlefield if state.cards[cid].name == "Incubator")


def test_norns_inquisitor_transform_trigger_uses_stack_and_survives_snapshot():
    state = _state()
    emit_event(state, "enters_battlefield", {"card_id": "inquisitor", "controller": 1})
    assert state.stack[-1].effect_key == "incubate"
    resolve_top_of_stack(state)
    token = _incubator(state)
    state.players[1].mana_pool["G"] = 2
    move = next(m for m in RulesEngine().legal_moves(state, 1) if m["type"] == "activate_ability" and m["card_id"] == token.id)
    RulesEngine().take_action(state, 1, move, reject_invalid=True)
    assert state.stack[-1].effect_key == "transform_card"
    resolve_top_of_stack(state)
    assert token.counters == {"+1/+1": 2}
    assert state.stack[-1].effect_key == "add_counters"
    assert state.stack[-1].payload["target_card_id"] == token.id

    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_top_of_stack(restored)
    token = restored.cards[token.id]
    assert token.counters == {"+1/+1": 3}
    assert (effective_power(restored, token.id), effective_toughness(restored, token.id)) == (3, 3)


def test_transform_trigger_requires_control_and_resulting_subtype():
    state = _state()
    resolve_effect(state, 2, "incubate", {"counters": 2})
    opponent_token = _incubator(state, 2)
    resolve_effect(state, 2, "transform_card", {"target_card_id": opponent_token.id, "face_index": 1})
    assert not state.stack

    delver = CardInstance(
        "delver", "Delver of Secrets", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        type_line="Creature - Human Wizard", layout="transform", selected_face_index=0,
        card_faces=[
            {"name": "Delver of Secrets", "type_line": "Creature - Human Wizard", "power": "1", "toughness": "1"},
            {"name": "Insectile Aberration", "type_line": "Creature - Human Insect", "power": "3", "toughness": "2"},
        ],
    )
    state.cards[delver.id] = delver
    state.players[1].battlefield.append(delver.id)
    resolve_effect(state, 1, "transform_card", {"target_card_id": delver.id, "face_index": 1})
    assert not state.stack
    resolve_effect(state, 1, "transform_card", {"target_card_id": delver.id, "face_index": 1})
    assert not state.stack


def test_transform_counter_trigger_does_not_follow_departed_token():
    state = _state()
    resolve_effect(state, 1, "incubate", {"counters": 2})
    token = _incubator(state)
    resolve_effect(state, 1, "transform_card", {"target_card_id": token.id, "face_index": 1})
    assert state.stack[-1].effect_key == "add_counters"
    before = dict(token.counters)
    state.players[1].battlefield.remove(token.id)
    token.zone = Zone.CEASED
    resolve_top_of_stack(state)
    assert token.counters == before
