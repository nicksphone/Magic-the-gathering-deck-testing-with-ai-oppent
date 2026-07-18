from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.attachments import attach_if_legal, is_aura, is_equipment
from rules_engine.ability_model import build_ability_spec
from rules_engine.cast_choice import build_cast_hints
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.targeting import validate_cast_targets


def _state() -> object:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=33,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    return state


def test_aura_and_equipment_detection_is_case_insensitive() -> None:
    aura = CardInstance("aura", "Growth Aura", 1, 1, Zone.BATTLEFIELD, ["Enchantment"], type_line="Enchantment — Aura")
    equipment = CardInstance("equipment", "Sword", 1, 1, Zone.BATTLEFIELD, ["Artifact"], type_line="Artifact — Equipment")
    assert is_aura(aura)
    assert is_equipment(equipment)


def test_aura_target_restrictions_are_exposed_and_carried_to_stack_payload() -> None:
    state = _state()
    creature = CardInstance("creature", "Bear", 1, 1, Zone.BATTLEFIELD, ["Creature"], type_line="Creature — Bear")
    land = CardInstance("land", "Forest", 1, 1, Zone.BATTLEFIELD, ["Land"], type_line="Basic Land — Forest")
    aura = CardInstance(
        "aura",
        "Growth Aura",
        1,
        1,
        Zone.HAND,
        ["Enchantment"],
        mana_cost="{G}",
        type_line="Enchantment — Aura",
        oracle_text="Enchant creature.",
    )
    for card in (creature, land, aura):
        state.cards[card.id] = card
    state.players[1].battlefield.extend([creature.id, land.id])
    state.players[1].hand.append(aura.id)

    hints = build_cast_hints(state, aura, 1)
    assert [item["id"] for item in hints["aura_targets"]] == [creature.id]
    ok, error = validate_cast_targets(hints, {"target_card_id": creature.id})
    assert ok is True, error
    bad, error = validate_cast_targets(hints, {"target_card_id": land.id})
    assert bad is False
    spec = build_ability_spec(state, aura, 1, {"target_card_id": creature.id})
    assert spec.effect.payload["target_card_id"] == creature.id


def test_invalid_aura_attachment_is_put_into_graveyard_by_state_based_actions() -> None:
    state = _state()
    creature = CardInstance("creature", "Bear", 1, 1, Zone.BATTLEFIELD, ["Creature"], type_line="Creature — Bear")
    aura = CardInstance(
        "aura",
        "Growth Aura",
        1,
        1,
        Zone.BATTLEFIELD,
        ["Enchantment"],
        type_line="Enchantment — Aura",
        oracle_text="Enchant creature.",
        attached_to=creature.id,
    )
    state.cards[creature.id] = creature
    state.cards[aura.id] = aura
    state.players[1].battlefield.extend([creature.id, aura.id])
    assert attach_if_legal(state, aura.id, creature.id)

    state.players[1].battlefield.remove(creature.id)
    creature.zone = Zone.GRAVEYARD
    state.players[1].graveyard.append(creature.id)
    apply_state_based_actions(state)

    assert aura.zone == Zone.GRAVEYARD
    assert aura.id in state.players[1].graveyard
