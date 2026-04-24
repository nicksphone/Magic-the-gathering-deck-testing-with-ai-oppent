from __future__ import annotations

from rules_engine.targeting import validate_cast_targets


def test_choose_two_validator() -> None:
    hints = {"modes": ["A", "B", "C"], "choose_two_modes": True}
    ok, err = validate_cast_targets(hints, {"mode_texts": ["A", "B"]})
    assert ok is True
    ok2, _ = validate_cast_targets(hints, {"mode_texts": ["A"]})
    assert ok2 is False


def test_divide_validator() -> None:
    hints = {"supports_divide": True}
    ok, _ = validate_cast_targets(hints, {"target_distribution": {"1": 2, "2": 1}, "divide_total": 3})
    assert ok is True
    ok2, _ = validate_cast_targets(hints, {"target_distribution": {"1": 2}, "divide_total": 3})
    assert ok2 is False
