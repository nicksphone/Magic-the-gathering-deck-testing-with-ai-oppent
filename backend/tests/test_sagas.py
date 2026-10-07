from card_data.fallback_cards import fallback_card_payload
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
    from rules_engine.targeting import stack_object_kind
    original, binding = state.stack[-2:]
    assert original.source_card_id == creature.id
    assert binding.effect_key == 'bind_creature_spell_entry_counter'
    assert stack_object_kind(state, binding) == 'triggered'
    assert not binding.payload.get('uncounterable')
    assert binding.payload['__native_cast']['stack_id'] == original.id
    assert state.cards[creature.id].zone == Zone.STACK
    assert state.pending_entry_counters == []
    resolve_top_of_stack(state)
    assert state.stack[-1].id == original.id
    assert state.cards[creature.id].zone == Zone.STACK
    resolve_top_of_stack(state)
    assert state.cards[creature.id].zone == Zone.BATTLEFIELD

    assert state.cards[creature.id].counters["+1/+1"] == 1
    assert state.pending_entry_counters == []


def test_saga_transform_chapter_uses_the_source_permanents_back_face() -> None:
    fable = fallback_card_payload("Fable of the Mirror-Breaker")
    assert fable
    state = _saga_state(fable["card_faces"][0]["oracle_text"])
    saga = state.cards["saga"]
    saga.name = fable["card_faces"][0]["name"]
    saga.layout = fable["layout"]
    saga.card_faces = fable["card_faces"]
    saga.counters["__lore"] = 2
    saga.counters["+1/+1"] = 1
    saga.tapped = True
    saga.summoning_sick = False
    state.turn = 4
    observer = CardInstance(
        "corruption", "Corruption of Towashi", 1, 1, Zone.BATTLEFIELD, ["Enchantment"],
        oracle_text=(
            "When Corruption of Towashi enters the battlefield, incubate 4.\n"
            "Whenever a permanent you control transforms or a permanent enters the battlefield under your control transformed, "
            "you may draw a card. Do this only once each turn."
        ), type_line="Enchantment",
    )
    state.cards[observer.id] = observer
    state.players[1].battlefield.append(observer.id)
    engine = RulesEngine()
    engine._advance_sagas(state)
    assert state.stack[-1].effect_key == "exile_return_transformed"
    resolve_top_of_stack(state)

    assert saga.zone == Zone.BATTLEFIELD
    assert saga.id in state.players[1].battlefield and saga.id not in state.players[1].exile
    assert saga.selected_face_index == 1
    assert saga.name == "Reflection of Kiki-Jiki"
    assert "Creature" in saga.types and "Saga" not in saga.type_line
    assert saga.counters == {}
    assert not saga.tapped and saga.summoning_sick and saga.entered_turn == 4
    assert len(state.stack) == 1
    assert state.stack[-1].effect_key == "draw_cards"
    assert state.stack[-1].payload["__trigger_event"] == "enters_battlefield"
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[saga.id].selected_face_index == 1
    assert restored.cards[saga.id].counters == {}


def test_transforming_saga_returns_under_chapter_controller_after_exile() -> None:
    fable = fallback_card_payload("Fable of the Mirror-Breaker")
    assert fable
    state = _saga_state(fable["card_faces"][0]["oracle_text"])
    saga = state.cards["saga"]
    saga.name = fable["card_faces"][0]["name"]
    saga.layout = fable["layout"]
    saga.card_faces = fable["card_faces"]
    saga.counters["__lore"] = 2
    state.players[1].battlefield.remove(saga.id)
    state.players[2].battlefield.append(saga.id)
    saga.controller = 2
    state.active_player = state.priority_player = 2

    RulesEngine()._advance_sagas(state)
    resolve_top_of_stack(state)

    assert saga.owner == 1 and saga.controller == 2
    assert saga.id not in state.players[1].exile
    assert saga.id in state.players[2].battlefield
    assert saga.selected_face_index == 1 and saga.counters == {}


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
