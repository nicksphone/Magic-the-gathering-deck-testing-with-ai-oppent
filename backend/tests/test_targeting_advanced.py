from __future__ import annotations

from game_state.state import CardInstance, MatchState, PlayerState, Zone
from rules_engine.targeting import (
    validate_cast_targets,
    validate_hexproof_shroud_targets,
    validate_protection_targets,
)


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


def test_validate_protection_targets_blocks_protection_from_creatures() -> None:
    target = CardInstance(
        id="t",
        name="Protected",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        keywords=["protection from creatures"],
    )
    source = CardInstance(
        id="s",
        name="Fight Spell Source",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Creature"],
    )
    state = MatchState(
        id="m",
        players={1: PlayerState(id=1, name="A"), 2: PlayerState(id=2, name="B")},
        cards={"t": target, "s": source},
        stack=[],
    )
    state.players[2].battlefield.append("t")

    ok, err = validate_protection_targets(state, source, {"target_card_id": "t"})
    assert ok is False
    assert "protection" in err.lower()


def test_validate_protection_targets_blocks_noncreature_sources() -> None:
    target = CardInstance(
        id="t2",
        name="Ward",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        keywords=["protection from noncreature"],
    )
    source = CardInstance(
        id="s2",
        name="Removal",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
    )
    state = MatchState(
        id="m2",
        players={1: PlayerState(id=1, name="A"), 2: PlayerState(id=2, name="B")},
        cards={"t2": target, "s2": source},
        stack=[],
    )
    state.players[2].battlefield.append("t2")

    ok, err = validate_protection_targets(state, source, {"target_card_id": "t2"})
    assert ok is False
    assert "protection" in err.lower()


def test_validate_hexproof_targets_block_opponent_targeting() -> None:
    target = CardInstance(
        id="t",
        name="Hex Target",
        owner=2,
        controller=2,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        keywords=["hexproof"],
    )
    source = CardInstance(
        id="s",
        name="Bolt",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
    )
    state = MatchState(
        id="m",
        players={1: PlayerState(id=1, name="A"), 2: PlayerState(id=2, name="B")},
        cards={"t": target, "s": source},
        stack=[],
    )
    state.players[2].battlefield.append("t")

    ok, err = validate_hexproof_shroud_targets(state, 1, {"target_card_id": "t"})
    assert ok is False
    assert "hexproof" in err.lower()


def test_validate_shroud_targets_block_all_targeting() -> None:
    target = CardInstance(
        id="t",
        name="Shroud Target",
        owner=1,
        controller=1,
        zone=Zone.BATTLEFIELD,
        types=["Creature"],
        keywords=["shroud"],
    )
    source = CardInstance(
        id="s",
        name="Buff",
        owner=1,
        controller=1,
        zone=Zone.HAND,
        types=["Instant"],
    )
    state = MatchState(
        id="m",
        players={1: PlayerState(id=1, name="A"), 2: PlayerState(id=2, name="B")},
        cards={"t": target, "s": source},
        stack=[],
    )
    state.players[1].battlefield.append("t")

    ok, err = validate_hexproof_shroud_targets(state, 1, {"target_card_id": "t"})
    assert ok is False
    assert "shroud" in err.lower()
