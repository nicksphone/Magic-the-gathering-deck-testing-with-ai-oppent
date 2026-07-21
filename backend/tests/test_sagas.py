from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.engine import RulesEngine
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot


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


def test_saga_next_creature_chapter_applies_one_shot_entry_counter() -> None:
    state = _saga_state(
        "I — Draw a card.\n"
        "II — When you next cast a creature spell this turn, that creature enters with an additional +1/+1 counter on it."
    )
    state.cards["saga"].counters["__lore"] = 1
    engine = RulesEngine()
    engine._advance_sagas(state)
    assert state.stack[-1].effect_key == "set_next_creature_entry_counter"
    resolve_top_of_stack(state)
    assert state.pending_entry_counters
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.pending_entry_counters == state.pending_entry_counters
    state = restored

    creature = CardInstance(
        id="bear",
        name="Bear",
        owner=1,
        controller=1,
        zone=Zone.STACK,
        types=["Creature"],
        power=2,
        toughness=2,
    )
    state.cards[creature.id] = creature
    add_to_stack(state, creature.id, 1, creature.name, "noop", {})
    resolve_top_of_stack(state)

    assert state.cards[creature.id].counters["+1/+1"] == 1
    assert state.pending_entry_counters == []


def test_saga_transform_chapter_uses_the_source_permanents_back_face() -> None:
    state = _saga_state(
        "I — Draw a card.\n"
        "II — Draw a card.\n"
        "III — Exile this Saga, then return it to the battlefield transformed under your control."
    )
    state.cards["saga"].card_faces = [
        {"name": "Front Saga", "type_line": "Enchantment — Saga"},
        {"name": "Back Creature", "type_line": "Creature — Human", "power": "3", "toughness": "3"},
    ]
    state.cards["saga"].counters["__lore"] = 2
    engine = RulesEngine()
    engine._advance_sagas(state)
    resolve_top_of_stack(state)

    assert state.cards["saga"].selected_face_index == 1
    assert state.cards["saga"].name == "Back Creature"
    assert "Creature" in state.cards["saga"].types


def test_double_faced_type_line_uses_front_face_before_transformation() -> None:
    deck = [{
        "quantity": 1,
        "card_name": "Kumano Faces Kakkazan",
        "type_line": "Enchantment — Saga // Enchantment Creature — Human Shaman",
        "oracle_text": "I — Draw a card.",
    }]
    state = MatchFactory.from_decks(deck, deck, seed=77)
    card = next(item for item in state.cards.values() if item.name == "Kumano Faces Kakkazan")

    assert card.types == ["Enchantment"]
