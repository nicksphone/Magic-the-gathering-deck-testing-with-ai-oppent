from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.seed_cards import seed_card_payload
from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.events import _trigger_from_oracle, emit_event
from rules_engine.oracle_effects import extract_activated_abilities, infer_effect_from_oracle, inspect_target_hints
from rules_engine.oracle_text import without_reminder_text


def _card(name: str) -> CardInstance:
    payload = seed_card_payload(name)
    sources = {
        'Bloodtithe Harvester': (9, 66, 'a086eb1eeb92eda6ad51aa1c551cc3739ac5207456fdc5b7ccb8e2b1c7e198e8',
                                'ae4aec0d-c853-44e6-9f51-cbecf413ea14', '419a8ab2-cff6-4811-a559-8791c9bb3d8e'),
        "Witch's Oven": (117, 66, '28665f48c3fcea64e1b0e48b30ce69ceee4aa3e4a4d33f2982220248699c0cd2',
                         '04ef8493-d986-45f8-a718-617b028f7ad4', '8fa0fe02-2452-4386-8e0c-165757b0f0a3'),
    }
    if name in sources:
        encoded = (Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
        if hashlib.sha256(encoded).hexdigest() != '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732':
            raise ValueError('Full reminder source changed')
        line, fields, object_sha, identifier, oracle_id = sources[name]
        raw = json.loads(encoded.splitlines()[line - 1])
        if (raw.get('object'), raw.get('name'), raw.get('id'), raw.get('oracle_id'), len(raw)) != (
                'card', name, identifier, oracle_id, fields):
            raise ValueError('Full reminder identity changed')
        if hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest() != object_sha:
            raise ValueError('Full reminder object changed')
        normalized = ScryfallSyncService._normalize_payload(raw, 'unused:task13-reminder-display')
        entry = {**raw, **normalized, 'card_name': raw['name'], 'quantity': 8,
                 'image_uri': None, 'colors': deepcopy(raw.get('colors', [])),
                 'card_faces': deepcopy(raw.get('card_faces', []))}
        sample = MatchFactory.from_decks([entry], [], seed=0)
        template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
        return replace(template, id=name, owner=1, controller=1, zone=Zone.BATTLEFIELD,
                       instance_order=0, summoning_sick=True)
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
