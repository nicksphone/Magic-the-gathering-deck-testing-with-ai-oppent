from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def _state() -> object:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=22,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    return state


def test_day_night_starts_at_upkeep_after_no_spells() -> None:
    state = _state()
    state.turn = 2
    state.step = Step.UPKEEP
    state.spells_cast_last_turn = 0

    RulesEngine()._apply_step_start_actions(state)

    assert state.day_night == "night"
    assert any("becomes night" in line.lower() for line in state.log)


def test_day_night_transitions_only_on_zero_or_two_spells() -> None:
    state = _state()
    state.turn = 3
    state.step = Step.UPKEEP
    engine = RulesEngine()

    state.day_night = "night"
    state.spells_cast_last_turn = 1
    engine._apply_step_start_actions(state)
    assert state.day_night == "night"
    state.spells_cast_last_turn = 2
    engine._apply_step_start_actions(state)
    assert state.day_night == "day"

    state.spells_cast_last_turn = 0
    engine._apply_step_start_actions(state)
    assert state.day_night == "night"


def test_day_night_transforms_matching_double_faced_permanents() -> None:
    state = _state()
    state.turn = 2
    state.step = Step.UPKEEP
    card = CardInstance(
        id="daybound-werewolf",
        name="Daybound Werewolf",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        oracle_text="Daybound",
        card_faces=[
            {"name": "Daybound Werewolf", "oracle_text": "Daybound", "type_line": "Creature — Werewolf", "power": "2", "toughness": "2"},
            {"name": "Nightbound Werewolf", "oracle_text": "Nightbound", "type_line": "Creature — Werewolf", "power": "4", "toughness": "4"},
        ],
    )
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)

    RulesEngine()._apply_step_start_actions(state)

    assert state.day_night == "night"
    assert state.cards[card.id].name == "Nightbound Werewolf"
    assert state.cards[card.id].selected_face_index == 1


def test_spell_cast_count_and_day_night_state_survive_snapshot_restore() -> None:
    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    card = CardInstance(
        id="free-draw",
        name="Free Draw",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Sorcery"],
        mana_cost="{0}",
        oracle_text="Draw a card.",
    )
    state.cards[card.id] = card
    state.players[1].hand.append(card.id)

    RulesEngine().take_action(state, 1, {"type": "cast_spell", "card_id": card.id})

    assert state.spells_cast_this_turn[1] == 1
    state.day_night = "day"
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.spells_cast_this_turn[1] == 1
    assert restored.day_night == "day"
    assert serialize_match(restored)["day_night"] == "day"
