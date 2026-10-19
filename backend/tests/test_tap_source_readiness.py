"""Shared cost readiness using canonical cards and explicit keyword-layer controls.

These controlled boards do not certify casting or an entire card's effects.
"""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import activated_cost_available
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_ai_recurring_engines import add, fixture


FIXTURES = Path(__file__).parent / "fixtures"
DYNAMO_PATH = FIXTURES / "ability_hint_copy/goblin-dynamo.json"
assert hashlib.sha256(DYNAMO_PATH.read_bytes()).hexdigest() == json.loads(
    DYNAMO_PATH.with_name(DYNAMO_PATH.name + ".provenance.json").read_text()
)["sha256"]
DYNAMO = json.loads(DYNAMO_PATH.read_text())
OFFICER = json.loads((FIXTURES / "cathar_canonical/c226656b-68d5-4df2-b313-a323a728c520.json").read_text())
SOL_RING = next(row for row in map(json.loads, (FIXTURES / "generic_article_mill/canonical.jsonl").read_text().splitlines())
                if row["name"] == "Sol Ring")
assert all(row.get("oracle_id") for row in (DYNAMO, OFFICER, SOL_RING))
ROWS = {row["name"]: {**row, "power": row.get("power"), "toughness": row.get("toughness")}
        for row in (DYNAMO, OFFICER, SOL_RING)}


def position(seat, name="Goblin Dynamo", *, sick=True):
    state = fixture()
    state.active_player = state.priority_player = seat
    source = add(state, name, seat, cards=ROWS)
    source.summoning_sick = sick
    state.players[seat].mana_pool = {"W": 4, "R": 4, "C": 4}
    return state, source


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("sick", [False, True])
@pytest.mark.parametrize("haste", [False, True])
def test_tap_cost_uses_effective_haste_and_preserves_snapshot(seat, sick, haste):
    state, source = position(seat, sick=sick)
    if haste:
        add_keyword_effect(state, source.id, ["haste"], until_end_of_turn=True)
    before = serialize_match_snapshot(state)
    assert activated_cost_available(state, seat, source.id, "{T}", ability_index=0) is (not sick or haste)
    assert serialize_match_snapshot(state) == before
    restored = deserialize_match_snapshot(before)
    assert activated_cost_available(restored, seat, source.id, "{T}", ability_index=0) is (not sick or haste)


@pytest.mark.parametrize("seat", [1, 2])
def test_removing_effective_haste_restores_tap_restriction(seat):
    state, source = position(seat)
    add_keyword_effect(state, source.id, ["haste"])
    assert activated_cost_available(state, seat, source.id, "{T}")
    add_keyword_effect(state, source.id, ["haste"], operation="remove")
    assert not activated_cost_available(state, seat, source.id, "{T}")


@pytest.mark.parametrize("seat", [1, 2])
def test_haste_does_not_allow_an_already_tapped_source(seat):
    state, source = position(seat)
    add_keyword_effect(state, source.id, ["haste"])
    source.tapped = True
    assert not activated_cost_available(state, seat, source.id, "{T}")


@pytest.mark.parametrize("seat", [1, 2])
def test_sickness_does_not_restrict_non_tap_creature_abilities(seat):
    state, source = position(seat, "Recruitment Officer")
    assert activated_cost_available(state, seat, source.id, "{3}{W}", ability_index=0)


@pytest.mark.parametrize("seat", [1, 2])
def test_noncreature_tap_cost_ignores_sickness_flag(seat):
    state, source = position(seat, "Sol Ring")
    assert activated_cost_available(state, seat, source.id, "{T}", ability_kind="mana", ability_index=0)


@pytest.mark.parametrize("seat", [1, 2])
def test_checked_action_rejects_sick_tap_without_mutation(seat):
    state, source = position(seat)
    rules = RulesEngine()
    assert not any(move.get("card_id") == source.id and move["type"] == "activate_ability"
                   for move in rules.legal_moves(state, seat))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, rules, seat, {"type": "activate_ability", "card_id": source.id,
                                          "ability_index": 0, "targets": {"target_player": 3 - seat}})
    assert serialize_match_snapshot(state) == before
