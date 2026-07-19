from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
from effects.registry import resolve_effect


def test_top_three_hand_exile_bottom_choice_has_temporary_play_permission() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=21,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    player = state.players[1]
    ids = player.library[-3:]
    values = ["{1}", "{3}", "{2}"]
    for cid, cost in zip(ids, values):
        state.cards[cid].mana_cost = cost
        state.cards[cid].types = ["Sorcery"]
        state.cards[cid].oracle_text = "Draw a card."
    spell = CardInstance(
        id="iteration",
        name="Expressive Iteration",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Look at the top three cards of your library. Put one of them into your hand, one on the bottom of your library, and one into exile. You may play the card exiled this way this turn.",
    )
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)
    assert spec.effect.key == "look_top_choose"
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)

    assert ids[1] in player.hand
    assert ids[2] in player.exile
    assert player.exile_play_until[ids[2]] == state.turn
    assert ids[0] in player.library


def test_top_three_choice_accepts_explicit_human_order() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=22,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    player = state.players[1]
    ids = player.library[-3:]
    spell = CardInstance(
        id="iteration-explicit",
        name="Expressive Iteration",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Look at the top three cards of your library. Put one of them into your hand, one on the bottom of your library, and one into exile. You may play the card exiled this way this turn.",
    )
    state.cards[spell.id] = spell
    spec = build_ability_spec(
        state,
        spell,
        1,
        action_targets={
            "top_choice_hand_id": ids[0],
            "top_choice_exile_id": ids[2],
            "top_choice_bottom_ids": [ids[1]],
        },
    )
    assert spec.effect.payload["top_choice_hand_id"] == ids[0]
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert ids[0] in player.hand
    assert ids[2] in player.exile
    assert player.library[-1] != ids[1]
    assert player.library[0] == ids[1]


def test_top_three_choice_rejects_duplicate_or_missing_cards() -> None:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=23,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    spell = CardInstance(
        id="iteration-invalid",
        name="Expressive Iteration",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        oracle_text="Look at the top three cards of your library. Put one of them into your hand, one on the bottom of your library, and one into exile. You may play the card exiled this way this turn.",
    )
    state.cards[spell.id] = spell
    hints = build_cast_hints(state, spell, 1)
    ids = [item["id"] for item in hints["top_choice"]["candidates"]]
    ok, error = validate_cast_choice(
        hints,
        {
            "top_choice_hand_id": ids[0],
            "top_choice_exile_id": ids[0],
            "top_choice_bottom_ids": [ids[1]],
        },
    )
    assert ok is False
    assert "exactly once" in error.lower()
