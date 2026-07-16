from __future__ import annotations

import json
from types import SimpleNamespace

from decks.selection import select_representative_decks
from game_state.state import MatchFactory, Zone
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
