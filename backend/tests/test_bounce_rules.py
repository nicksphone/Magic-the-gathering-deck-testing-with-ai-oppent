from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
from rules_engine.oracle_effects import infer_effect_from_oracle


def _state_with_target() -> tuple[object, str]:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Island"}],
        [{"quantity": 60, "card_name": "Island"}],
        seed=31,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    target = CardInstance(
        id="stolen-permanent",
        name="Stolen Threat",
        owner=2,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        power=3,
        toughness=3,
    )
    state.cards[target.id] = target
    state.players[1].battlefield.append(target.id)
    return state, target.id


def test_bounce_inference_exposes_nonland_permanent_targets() -> None:
    state, target_id = _state_with_target()
    state.players[1].battlefield.remove(target_id)
    state.players[2].battlefield.append(target_id)
    state.cards[target_id].controller = 2
    spell = CardInstance(
        id="petty-theft",
        name="Petty Theft",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Return target nonland permanent an opponent controls to its owner's hand.",
    )
    state.cards[spell.id] = spell
    hints = build_cast_hints(state, spell, 1)
    assert target_id in {item["id"] for item in hints["permanent_targets"]}
    ok, error = validate_cast_choice(hints, {"target_card_id": target_id})
    assert ok is True, error
    effect, payload = infer_effect_from_oracle(state, spell, 1, {"target_card_id": target_id})
    assert effect == "return_permanent_to_hand"
    assert payload["target_card_id"] == target_id


def test_bounce_returns_stolen_permanent_to_owner_hand_and_clears_control() -> None:
    state, target_id = _state_with_target()
    resolve_effect(state, 1, "return_permanent_to_hand", {"target_card_id": target_id})
    target = state.cards[target_id]
    assert target_id not in state.players[1].battlefield
    assert target_id in state.players[2].hand
    assert target.zone == Zone.HAND
    assert target.controller == 2
    assert any("owner's hand" in line for line in state.log)


def test_bounce_ability_spec_is_not_marked_as_oracle_fallback() -> None:
    state, target_id = _state_with_target()
    spell = CardInstance(
        id="petty-theft-spec",
        name="Petty Theft",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
        oracle_text="Return target nonland permanent an opponent controls to its owner's hand.",
    )
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1, {"target_card_id": target_id})
    assert spec.effect.key == "return_permanent_to_hand"
    assert spec.used_fallback is False
