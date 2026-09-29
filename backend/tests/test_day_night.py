from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


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


def test_simultaneous_day_night_transforms_share_apnap_trigger_order_window(monkeypatch) -> None:
    from rules_engine import events
    from rules_engine.events import resume_trigger_order

    state = _state()
    state.turn = 3
    state.step = Step.UPKEEP
    state.active_player = state.priority_player = 1
    state.day_night = "day"
    state.spells_cast_last_turn = 0
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    arena = CardInstance(
        "arena", "Phyrexian Arena", 1, 1, Zone.BATTLEFIELD, ["Enchantment"],
        oracle_text="At the beginning of your upkeep, you draw a card and you lose 1 life.",
    )
    state.cards[arena.id] = arena
    state.players[1].battlefield.append(arena.id)
    oracle = (
        "When Corruption of Towashi enters the battlefield, incubate 4.\n"
        "Whenever a permanent you control transforms or a permanent enters the battlefield under your control transformed, "
        "you may draw a card. Do this only once each turn."
    )
    for owner in (1, 2):
        corruption = CardInstance(
            f"corruption-{owner}", "Corruption of Towashi", owner, owner,
            Zone.BATTLEFIELD, ["Enchantment"], oracle_text=oracle,
        )
        state.cards[corruption.id] = corruption
        state.players[owner].battlefield.append(corruption.id)
        for copy_number in (1, 2):
            card = CardInstance(
                f"cathar-{owner}-{copy_number}", "Brutal Cathar", owner, owner,
                Zone.BATTLEFIELD, ["Creature"], oracle_text="Daybound", layout="transform",
                selected_face_index=0,
                card_faces=[
                    {"name": "Brutal Cathar", "oracle_text": "Daybound", "type_line": "Creature - Human Soldier Werewolf", "power": "2", "toughness": "2"},
                    {"name": "Moonrage Brute", "oracle_text": "First strike\nNightbound", "type_line": "Creature - Werewolf", "power": "3", "toughness": "3"},
                ],
            )
            state.cards[card.id] = card
            state.players[owner].battlefield.append(card.id)

    observed_faces = []
    original_collect = events._collect_triggers

    def collect_after_all_faces_change(game, event, payload):
        if event == "transformed":
            observed_faces.append(tuple(
                game.cards[f"cathar-{owner}-{copy_number}"].selected_face_index
                for owner in (1, 2) for copy_number in (1, 2)
            ))
        return original_collect(game, event, payload)

    monkeypatch.setattr(events, "_collect_triggers", collect_after_all_faces_change)
    RulesEngine()._apply_step_start_actions(state)
    assert observed_faces == [(1, 1, 1, 1)] * 4
    assert state.day_night == "night"
    assert all(state.cards[f"cathar-{owner}-{copy_number}"].selected_face_index == 1
               for owner in (1, 2) for copy_number in (1, 2))
    pending = state.pending_trigger_order
    assert pending and pending["current_controller"] == 1
    assert [len(pending["groups"][str(owner)]) for owner in (1, 2)] == [3, 2]
    assert not state.stack

    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    pending = state.pending_trigger_order
    for owner in (1, 2):
        order = [trigger["_choice_id"] for trigger in pending["groups"][str(owner)]]
        assert resume_trigger_order(state, list(reversed(order)))
        pending = state.pending_trigger_order
    assert pending is None
    assert [item.controller for item in state.stack] == [1, 1, 1, 2, 2]
    assert [item.payload["__trigger_event"] for item in state.stack].count("transformed") == 4
    assert [item.payload["__trigger_event"] for item in state.stack].count("begin_step") == 1


def test_day_night_change_triggers_use_the_stack() -> None:
    state = _state()
    state.turn = 3
    state.step = Step.UPKEEP
    state.day_night = "day"
    state.spells_cast_last_turn = 0
    trigger_source = CardInstance(
        id="night-trigger",
        name="Night Watch",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Enchantment"],
        oracle_text="Whenever it becomes night, draw a card.",
        type_line="Enchantment",
    )
    state.cards[trigger_source.id] = trigger_source
    state.players[1].battlefield.append(trigger_source.id)
    before = len(state.players[1].hand)

    RulesEngine()._apply_step_start_actions(state)

    assert state.day_night == "night"
    assert state.stack
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == before + 1


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
