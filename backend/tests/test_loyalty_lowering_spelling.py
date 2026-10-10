"""Declared grammar boundaries, not modified canonical Oracle records."""
import pytest

from rules_engine.closed_loyalty import compile_instruction
from rules_engine.loyalty_instructions import compile_extended


def instruction(stats):
    return (
        "Put three +1/+1 counters on up to one target noncreature land you control. "
        "Untap it. It becomes a " + stats
        + " Elemental creature with vigilance and haste that's still a land."
    )


@pytest.mark.parametrize("stats", ["00/0", "000/0"])
def test_non_native_spelling_retains_complete_extended_program(stats):
    body = instruction(stats)
    expected = compile_extended(body, "")
    assert [step["effect_key"] for step in expected] == ["loyalty_counter", "loyalty_animate"]
    assert compile_instruction(body) == expected


@pytest.mark.parametrize("stats", ["0/0", "0/00"])
def test_native_recognized_zero_spelling_keeps_native_lowering(stats):
    body = instruction(stats)
    assert compile_instruction(body) == [{"effect_key": "add_counters", "instruction": body[:-1]}]
