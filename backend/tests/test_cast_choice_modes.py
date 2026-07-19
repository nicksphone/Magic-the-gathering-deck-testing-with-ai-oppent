from __future__ import annotations

from rules_engine.cast_choice import build_cast_hints
from rules_engine.cast_choice import validate_cast_choice
from rules_engine.ability_model import build_ability_spec
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.cast_choice import enrich_divide_total
from rules_engine.oracle_effects import infer_effect_from_oracle, inspect_target_hints
from effects.registry import resolve_effect


def _state() -> object:
    deck = [{"quantity": 60, "card_name": "Island"}]
    return MatchFactory.from_decks(deck, deck)


def test_mode_and_x_hints_exposed() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="x",
        name="Modal X",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        mana_cost="{X}{R}",
        oracle_text="Choose one — Modal X deals X damage to any target; Draw X cards.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("modes")
    assert hints.get("requires_x_value") is True


def test_bullet_and_choose_two_modes_are_exposed_as_explicit_choices() -> None:
    state = _state()
    card = state.cards[state.players[1].hand[0]]
    card.name = "Modal Charm"
    card.oracle_text = "Choose two —\n• Draw a card.\n• Gain 3 life.\n• Create a 1/1 white Soldier creature token."
    hints = build_cast_hints(state, card, 1)

    assert hints["modes"] == [
        "Draw a card",
        "Gain 3 life",
        "Create a 1/1 white Soldier creature token",
    ]
    assert hints["choose_two_modes"] is True
    assert hints["choice_schema"]["mode_texts"]["min_items"] == 2


def test_selected_bullet_modes_resolve_as_an_effect_sequence() -> None:
    state = _state()
    card = state.cards[state.players[1].hand[0]]
    card.name = "Modal Charm"
    card.oracle_text = "Choose one —\n• Draw a card.\n• Gain 3 life."
    mode = "Gain 3 life"
    effect_key, payload = infer_effect_from_oracle(state, card, 1, {"mode_text": mode})

    assert effect_key == "gain_life"
    assert payload["amount"] == 3


def test_mode_specific_hints_only_expose_targets_for_selected_mode() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    creature_id = state.players[2].hand[0]
    state.players[2].hand.remove(creature_id)
    state.players[2].battlefield.append(creature_id)
    creature = state.cards[creature_id]
    creature.zone = Zone.BATTLEFIELD
    creature.types = ["Creature"]
    spell = CardInstance(
        id="drown",
        name="Drown in the Loch",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{U}{B}",
        oracle_text=(
            "Choose one —\n"
            "• Counter target spell.\n"
            "• Destroy target creature."
        ),
    )

    counter_hints = build_cast_hints(state, spell, 1, {"mode_text": "Counter target spell"})
    destroy_hints = build_cast_hints(state, spell, 1, {"mode_text": "Destroy target creature"})
    assert not counter_hints.get("stack_targets")
    assert "creature_targets" not in counter_hints
    assert {item["id"] for item in destroy_hints["creature_targets"]} == {creature_id}


def test_choose_two_modes_resolve_as_ordered_effect_sequence() -> None:
    state = _state()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    card = CardInstance(
        id="charm",
        name="Two Mode Charm",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Choose two —\n• Draw a card.\n• Gain 3 life.\n• Create a 1/1 white Soldier creature token.",
    )
    spec = build_ability_spec(
        state,
        card,
        1,
        {"mode_texts": ["Draw a card", "Gain 3 life"]},
    )
    assert spec.effect.key == "effect_sequence"
    assert [item["effect_key"] for item in spec.effect.payload["effects"]] == ["draw_cards", "gain_life"]
    before_hand = len(state.players[1].hand)
    before_life = state.players[1].life
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert len(state.players[1].hand) == before_hand + 1
    assert state.players[1].life == before_life + 3


def test_x_mode_inference_respects_selected_mode_and_x() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="x",
        name="Modal X",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        mana_cost="{X}{R}",
        oracle_text="Choose one — Modal X deals X damage to any target; Draw X cards.",
    )
    effect, payload = infer_effect_from_oracle(state, card, 1, action_targets={"mode_text": "Draw X cards", "x_value": 3})
    assert effect == "draw_cards"
    assert payload["amount"] == 3


def test_planeswalker_cast_does_not_require_x_value_from_loyalty_text() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="ugin",
        name="Ugin, the Spirit Dragon",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Planeswalker"],
        mana_cost="{8}",
        oracle_text="+2: Ugin, the Spirit Dragon deals 3 damage to any target.\n-X: Exile each permanent with mana value X or less that's one or more colors.\n-10: You gain 7 life and draw seven cards.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("requires_x_value") is not True


def test_memory_deluge_does_not_require_x_value_for_cast() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="deluge",
        name="Memory Deluge",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{2}{U}{U}",
        oracle_text="Look at the top X cards of your library, where X is the amount of mana spent to cast this spell.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("requires_x_value") is not True


def test_shark_typhoon_does_not_require_x_value_for_cast() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="shark",
        name="Shark Typhoon",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Enchantment"],
        mana_cost="{5}{U}",
        oracle_text="Cycling {X}{1}{U}. When you cycle Shark Typhoon, create an X/X blue Shark creature token with flying.",
    )
    hints = inspect_target_hints(state, card, 1)
    assert hints.get("requires_x_value") is not True


def test_non_divide_x_spell_does_not_auto_set_divide_total() -> None:
    card = CardInstance(
        id="march",
        name="March of Otherworldly Light",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        mana_cost="{X}{W}",
        oracle_text="Exile target artifact, creature, or enchantment with mana value X or less.",
    )
    targets = enrich_divide_total(card, {"x_value": 3, "target_card_id": "c1"})
    assert "divide_total" not in targets


def test_validate_cast_choice_accepts_zero_x_value_when_required() -> None:
    hints = {
        "requires_x_value": True,
        "creature_targets": [{"id": "c1", "name": "Target"}],
    }
    ok, msg = validate_cast_choice(hints, {"x_value": 0, "target_card_id": "c1"})
    assert ok is True
    assert msg == ""


def test_build_cast_hints_exposes_face_selection_schema() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    card = CardInstance(
        id="modal",
        name="Modal Adept",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Creature"],
        mana_cost="{2}{G}",
        oracle_text="",
        card_faces=[
            {"name": "Adept Form", "oracle_text": "Create a 1/1 token.", "mana_cost": "{2}{G}", "type_line": "Creature - Elf"},
            {"name": "Scholar Form", "oracle_text": "Draw a card and destroy target artifact.", "mana_cost": "{2}{G}", "type_line": "Creature - Elf"},
        ],
    )
    hints = build_cast_hints(state, card, 1)
    schema = hints["choice_schema"]["selected_face_index"]
    assert schema["minimum"] == 0
    assert schema["maximum"] == 1


def test_validate_cast_choice_rejects_out_of_range_face_index() -> None:
    hints = {
        "face_names": ["Adept Form", "Scholar Form"],
        "choice_schema": {
            "selected_face_index": {"type": "integer", "required": False, "minimum": 0, "maximum": 1},
        },
    }
    ok, msg = validate_cast_choice(hints, {"selected_face_index": 2})
    assert ok is False
    assert "out of range" in msg.lower()
