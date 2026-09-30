from __future__ import annotations

import json
from io import StringIO
from types import SimpleNamespace

from decks.selection import select_representative_decks
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from scripts import overnight_verbose_round_robin
from scripts.overnight_verbose_round_robin import _cluster_labels, battlefield_snapshot


def _row(name: str, archetype_guess: str, mainboard: list[dict] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        archetype_guess=archetype_guess,
        mainboard_json="[]" if mainboard is None else json.dumps(mainboard),
    )


def test_regression_matrix_prefers_archetype_spread_before_fill() -> None:
    rows = [
        _row("Aggro One", "Aggro"),
        _row("Aggro Two", "Aggro"),
        _row("Control One", "Control"),
        _row("Tempo One", "Tempo"),
        _row("Ramp One", "Ramp"),
    ]

    selected = select_representative_decks(rows, 3, guess_archetype_fn=lambda _: "unknown")

    assert [item["name"] for item in selected] == ["Aggro One", "Control One", "Tempo One"]
    assert {item["archetype"] for item in selected} == {"Aggro", "Control", "Tempo"}


def test_regression_matrix_falls_back_to_guess_archetype_for_unknown_rows() -> None:
    calls: list[list[dict]] = []

    def fake_guess(mainboard: list[dict]) -> str:
        calls.append(mainboard)
        return "Tokens"

    rows = [_row("Mystery Deck", "unknown", [{"quantity": 4, "card_name": "Raise the Alarm"}])]

    selected = select_representative_decks(rows, 1, guess_archetype_fn=fake_guess)

    assert calls == [[{"quantity": 4, "card_name": "Raise the Alarm"}]]
    assert selected[0]["archetype"] == "Tokens"


def test_verbose_round_robin_snapshot_contains_tactical_fields() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    first = state.players[1].hand[0]
    state.players[1].hand.remove(first)
    state.players[1].battlefield.append(first)
    state.cards[first].zone = Zone.BATTLEFIELD
    state.cards[first].tapped = True

    snapshot = battlefield_snapshot(state, 1)

    assert snapshot[0]["name"] == "Island"
    assert snapshot[0]["tapped"] is True
    assert {"types", "power", "toughness", "loyalty", "selected_face_index"} <= snapshot[0].keys()


def test_verbose_round_robin_trace_life_snapshot_uses_actor_orientation() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.players[1].life = 17
    state.players[2].life = 6

    assert overnight_verbose_round_robin.life_snapshot(state, 2) == {  # type: ignore[attr-defined]
        "self": 6,
        "opp": 17,
    }


def test_verbose_round_robin_emits_explicit_deck_archetype_metadata() -> None:
    deck_pool = [
        {"id": 2, "name": "Slow Deck", "mainboard": [], "archetype": "Control"},
        {"id": 1, "name": "Fast Deck", "mainboard": [], "archetype": "Aggro"},
    ]

    assert hasattr(overnight_verbose_round_robin, "_deck_artifact")
    assert overnight_verbose_round_robin._deck_artifact(deck_pool) == [  # type: ignore[attr-defined]
        {"id": 1, "name": "Fast Deck", "archetype": "Aggro"},
        {"id": 2, "name": "Slow Deck", "archetype": "Control"},
    ]


def test_verbose_round_robin_game_rows_include_stable_deck_identity() -> None:
    left = {"id": 11, "name": "Mirror", "archetype": "Aggro"}
    right = {"id": 22, "name": "Mirror", "archetype": "Control"}

    assert overnight_verbose_round_robin._game_identity(left, right) == {  # type: ignore[attr-defined]
        "deck_a": "Mirror",
        "deck_a_id": 11,
        "deck_a_archetype": "Aggro",
        "deck_b": "Mirror",
        "deck_b_id": 22,
        "deck_b_archetype": "Control",
    }


def test_verbose_round_robin_decision_quality_uses_stable_ids_for_duplicate_names() -> None:
    left = {"id": 11, "name": "Mirror", "archetype": "Aggro"}
    right = {"id": 22, "name": "Mirror", "archetype": "Control"}
    log = [
        'AI TRACE {"pid":1,"turn":1,"step":"Step.PRECOMBAT_MAIN","legal_non_pass":true,"legal_has_land":true,"mana_pool":{"R":1},"action":{"type":"pass_priority"}}',
        'AI TRACE {"pid":1,"turn":1,"step":"Step.END_STEP","legal_non_pass":false,"legal_has_land":false,"mana_pool":{},"action":{"type":"pass_priority"}}',
        'AI TRACE {"pid":1,"step":"Step.DECLARE_ATTACKERS","legal_non_pass":true,"legal_has_land":false,"mana_pool":{},"lethal_attack_available":true,"action":{"type":"pass_priority"}}',
        'AI TRACE {"pid":2,"step":"Step.UPKEEP","legal_non_pass":false,"legal_has_land":false,"mana_pool":{},"action":{"type":"pass_priority"}}',
    ]

    game = overnight_verbose_round_robin._decision_quality_game_summary(log, left, right)  # type: ignore[attr-defined]
    out = overnight_verbose_round_robin._decision_quality_artifact([game], [left, right])  # type: ignore[attr-defined]

    assert out["per_deck"] == [
        {
            "deck_id": 11,
            "deck_name": "Mirror",
            "deck_key": "source::id:int:11",
            "metrics": {
                "missed_land_drops": 1,
                "unused_mana_passes": 1,
                "lethal_misses": 1,
                "bad_blocks": 0,
                "stall_streaks": None,
                "redundant_removal_casts": None,
            },
            "unavailable_metrics": {
                "stall_streaks": "complete per-player AI decision trace evidence absent",
                "redundant_removal_casts": "complete per-player AI decision trace evidence absent",
            },
        },
        {
            "deck_id": 22,
            "deck_name": "Mirror",
            "deck_key": "source::id:int:22",
            "metrics": {
                "missed_land_drops": 0,
                "unused_mana_passes": 0,
                "lethal_misses": 0,
                "bad_blocks": 0,
                "stall_streaks": None,
                "redundant_removal_casts": None,
            },
            "unavailable_metrics": {
                "stall_streaks": "complete per-player AI decision trace evidence absent",
                "redundant_removal_casts": "complete per-player AI decision trace evidence absent",
            },
        },
    ]
    assert out["overall"] == {
        "missed_land_drops": 1,
        "unused_mana_passes": 1,
        "lethal_misses": 1,
        "bad_blocks": 0,
        "stall_streaks": None,
        "redundant_removal_casts": None,
    }
    assert out["unavailable_metrics"] == {
        "stall_streaks": "complete per-player AI decision trace evidence absent",
        "redundant_removal_casts": "complete per-player AI decision trace evidence absent",
    }


def test_verbose_round_robin_decision_quality_only_validates_participating_decks() -> None:
    decks = [
        {"id": 1, "name": "A", "archetype": "Aggro"},
        {"id": 2, "name": "B", "archetype": "Control"},
        {"id": 3, "name": "C", "archetype": "Tempo"},
    ]
    complete = {
        metric: True
        for metric in (
            "missed_land_drops",
            "unused_mana_passes",
            "lethal_misses",
            "bad_blocks",
            "stall_streaks",
            "redundant_removal_casts",
        )
    }
    games = []
    for left, right in ((decks[0], decks[1]), (decks[0], decks[2]), (decks[1], decks[2])):
        games.append(
            {
                "decks": {
                    overnight_verbose_round_robin._deck_quality_key(left): {  # type: ignore[attr-defined]
                        "counts": {},
                        "availability": complete,
                    },
                    overnight_verbose_round_robin._deck_quality_key(right): {  # type: ignore[attr-defined]
                        "counts": {},
                        "availability": complete,
                    },
                }
            }
        )

    out = overnight_verbose_round_robin._decision_quality_artifact(games, decks)  # type: ignore[attr-defined]

    assert all(value == 0 for row in out["per_deck"] for value in row["metrics"].values())
    assert all(value == 0 for value in out["overall"].values())
    assert out["unavailable_metrics"] == {}


def test_verbose_round_robin_decision_quality_keys_cannot_silently_collide() -> None:
    decks = [
        {"id": 7, "source": "builtin", "name": "Duplicate", "archetype": "Aggro"},
        {"id": 7, "source": "builtin", "name": "Duplicate", "archetype": "Control"},
        {"id": "7", "source": "builtin", "name": "String ID", "archetype": "Tempo"},
        {"id": None, "source": "user", "name": "Nameless", "archetype": "Ramp"},
        {"id": None, "source": "user", "name": "Nameless", "archetype": "Combo"},
    ]

    out = overnight_verbose_round_robin._decision_quality_artifact([], decks)  # type: ignore[attr-defined]

    assert len(out["per_deck"]) == len(decks)
    assert len({row["deck_key"] for row in out["per_deck"]}) == len(decks)
    assert [(row["deck_id"], row["deck_name"]) for row in out["per_deck"]] == [
        (7, "Duplicate"),
        (7, "Duplicate"),
        ("7", "String ID"),
        (None, "Nameless"),
        (None, "Nameless"),
    ]


def test_verbose_round_robin_full_logging_also_writes_anomaly() -> None:
    all_games = StringIO()
    anomalies = StringIO()
    record = {"deck_a": "A", "deck_b": "B", "winner": None}

    overnight_verbose_round_robin._write_game_record(  # type: ignore[attr-defined]
        record,
        all_games=all_games,
        anomalies=anomalies,
        write_full_log=True,
        qualifies_as_anomaly=True,
    )

    assert json.loads(all_games.getvalue()) == record
    assert json.loads(anomalies.getvalue()) == record


def test_verbose_round_robin_summoning_sick_power_is_not_lethal_evidence() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    attacker = state.players[1].hand.pop()
    state.players[1].battlefield.append(attacker)
    card = state.cards[attacker]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.power = 20
    card.summoning_sick = True
    state.players[2].life = 1
    legal = RulesEngine().legal_moves(state, 1)

    assert overnight_verbose_round_robin.lethal_attack_available(state, 1, legal) is False  # type: ignore[attr-defined]


def test_verbose_round_robin_lone_cant_attack_alone_is_not_lethal_evidence() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    attacker = state.players[1].hand.pop()
    state.players[1].battlefield.append(attacker)
    card = state.cards[attacker]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.power = 20
    card.oracle_text = "CARDNAME can't attack alone."
    card.summoning_sick = False
    state.players[2].life = 1
    legal = RulesEngine().legal_moves(state, 1)

    assert overnight_verbose_round_robin.lethal_attack_available(state, 1, legal) is False  # type: ignore[attr-defined]


def test_verbose_round_robin_cant_attack_alone_is_lethal_with_companion() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    attackers = [state.players[1].hand.pop(), state.players[1].hand.pop()]
    state.players[1].battlefield.extend(attackers)
    for attacker in attackers:
        card = state.cards[attacker]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Creature"]
        card.summoning_sick = False
    state.cards[attackers[0]].power = 2
    state.cards[attackers[0]].oracle_text = "CARDNAME can't attack alone."
    state.cards[attackers[1]].power = 1
    state.players[2].life = 3
    legal = RulesEngine().legal_moves(state, 1)

    assert overnight_verbose_round_robin.lethal_attack_available(state, 1, legal) is True  # type: ignore[attr-defined]
    assert state.attackers == []
    assert all(not state.cards[attacker].tapped for attacker in attackers)


def test_verbose_round_robin_detects_legal_open_board_lethal() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    attacker = state.players[1].hand.pop()
    state.players[1].battlefield.append(attacker)
    card = state.cards[attacker]
    card.zone = Zone.BATTLEFIELD
    card.types = ["Creature"]
    card.power = 3
    card.summoning_sick = False
    state.players[2].life = 3
    legal = RulesEngine().legal_moves(state, 1)

    assert overnight_verbose_round_robin.lethal_attack_available(state, 1, legal) is True  # type: ignore[attr-defined]


def test_verbose_round_robin_blocker_present_is_explicitly_not_open_board_lethal() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    attacker = state.players[1].hand.pop()
    blocker = state.players[2].hand.pop()
    state.players[1].battlefield.append(attacker)
    state.players[2].battlefield.append(blocker)
    for card_id in (attacker, blocker):
        card = state.cards[card_id]
        card.zone = Zone.BATTLEFIELD
        card.types = ["Creature"]
    state.cards[attacker].power = 20
    state.cards[attacker].summoning_sick = False
    state.players[2].life = 1
    legal = RulesEngine().legal_moves(state, 1)

    assert overnight_verbose_round_robin.lethal_attack_available(state, 1, legal) is False  # type: ignore[attr-defined]


def test_round_robin_cluster_ignores_ordinary_priority_passes() -> None:
    row = {
        "log": ["Player passes priority.", "AI TRACE {\"action\": {\"type\": \"pass_priority\"}}"],
        "passed_with_options": 0,
        "stall_streaks": 0,
        "termination_status": "resolved",
    }

    assert _cluster_labels(row) == ["other"]
    assert _cluster_labels({**row, "passed_with_options": 1}) == ["pass_with_legal_action"]
    assert _cluster_labels(
        {**row, "passed_with_options": 1, "pass_reason_codes": {"hold_up_interaction": 1}}
    ) == ["pass_hold_up_interaction"]
    assert _cluster_labels({**row, "termination_status": "timeout_long_game"}) == ["long_game"]
