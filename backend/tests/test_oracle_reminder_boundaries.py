from card_data.fallback_cards import fallback_card_payload
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.events import _trigger_from_oracle, emit_event
from rules_engine.oracle_effects import extract_activated_abilities, infer_effect_from_oracle, inspect_target_hints
from rules_engine.oracle_text import without_reminder_text


def _card(name: str) -> CardInstance:
    payload = fallback_card_payload(name)
    return CardInstance(
        id=name, name=name, owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=payload["type_line"].split(" — ")[0].split(),
        oracle_text=payload["oracle_text"],
    )


def _state():
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    return MatchFactory.from_decks(deck, deck, seed=1)


def test_nested_reminder_text_cannot_supply_executable_clauses() -> None:
    text = "Create a Food token. (It has (among other rules) {2}, {T}: You gain 3 life.)\nDraw a card."
    assert without_reminder_text(text) == "Create a Food token. \nDraw a card."


def test_quoted_token_ability_is_not_extracted_from_creator() -> None:
    harvester = _card("Bloodtithe Harvester")
    oven = _card("Witch's Oven")
    harvester_abilities = extract_activated_abilities(harvester)
    oven_abilities = extract_activated_abilities(oven)
    assert len(harvester_abilities) == len(oven_abilities) == 1
    assert "Target creature gets" in harvester_abilities[0]["text"]
    assert "Create a Food token" in oven_abilities[0]["text"]
    assert "Draw a card" not in harvester_abilities[0]["text"]
    assert "gain 3 life" not in oven_abilities[0]["text"]


def test_reminder_text_cannot_create_false_draw_life_or_target_effects() -> None:
    state = _state()
    for name in ("Bloodtithe Harvester", "Witch's Oven"):
        card = _card(name)
        state.cards[card.id] = card
        effect, _ = infer_effect_from_oracle(state, card, 1)
        assert effect not in {"draw_cards", "gain_life", "lose_life"}
        hints = inspect_target_hints(state, card, 1)
        assert "target_stack_id" not in hints
        trigger = _trigger_from_oracle(
            state, card.id, 1, card.oracle_text.lower(), f"{name} trigger",
            "enters_battlefield", {"card_id": card.id, "controller": 1},
        )
        assert trigger["effect_key"] not in {"draw_cards", "gain_life", "lose_life"}


def test_reminder_text_does_not_register_a_trigger() -> None:
    state = _state()
    card = CardInstance(
        id="reminder-only", name="Reminder Only", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Artifact"],
        oracle_text="An artifact. (Whenever you draw a card, gain 3 life.)",
    )
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    emit_event(state, "draw_card", {"player_id": 1})
    assert state.stack == []
