import json

import pytest

from ai.agent import AIAgent
from analytics.decision_quality import build_decision_quality_artifact, build_trace_payload, summarize_trace_rows
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from tests.test_copy_stack_characteristics import surviving_copy
from tests.test_pending_removal import add_card, fixture


def test_trace_counts_redundant_cast_and_records_announced_stack():
    state, victim, held = fixture()
    before = serialize_match_snapshot(state)
    payload = build_trace_payload(state, 1, RulesEngine().legal_moves(state, 1), {
        "type": "cast_spell", "card_id": held, "targets": {"target_card_id": victim},
    })
    assert payload["redundant_removal_casts"] == 1
    assert payload["stack"][0]["announced_targets"]["target_card_id"] == victim
    assert payload["stack"][0]["source_name"] == "Go for the Throat"
    assert payload["stack"][0]["kind"] == "spell"
    other = build_trace_payload(state, 2, RulesEngine().legal_moves(state, 2), {"type": "pass_priority"})
    result = summarize_trace_rows([{"log": ["AI TRACE " + json.dumps(row) for row in [payload, other]]}])
    assert result["counts"]["1"]["redundant_removal_casts"] == 1
    assert result["counts"]["2"]["redundant_removal_casts"] == 0
    assert serialize_match_snapshot(state) == before


def test_legacy_trace_does_not_claim_zero_redundant_casts():
    state, _, _ = fixture()
    rows = []
    for pid in [1, 2]:
        payload = build_trace_payload(state, pid, [], {"type": "pass_priority"})
        payload.pop("redundant_removal_casts")
        rows.append("AI TRACE " + json.dumps(payload))
    result = summarize_trace_rows([{"log": rows}])
    assert not result["availability"]["1"]["redundant_removal_casts"]
    artifact = build_decision_quality_artifact([{"id": 1, "name": "Deck A"}], [{"decks": [{
        "deck_key": "source::id:int:1", "counts": result["counts"]["1"],
        "availability": result["availability"]["1"],
    }]}])
    assert artifact["per_deck"][0]["metrics"]["redundant_removal_casts"] is None


def test_unknown_pending_choice_does_not_claim_zero_redundant_casts():
    state, victim, held = fixture()
    state.pending_mechanic_choice = {"player_id": 1, "kind": "unresolved"}
    payload = build_trace_payload(state, 1, [], {
        "type": "cast_spell", "card_id": held, "targets": {"target_card_id": victim},
    })
    assert payload["redundant_removal_casts"] is None
    result = summarize_trace_rows([{"log": ["AI TRACE " + json.dumps(payload)]}])
    assert not result["availability"]["1"]["redundant_removal_casts"]


@pytest.mark.parametrize("value", [True, -1, 0.5, None])
def test_invalid_redundancy_evidence_is_unavailable(value):
    state, _, _ = fixture()
    payload = build_trace_payload(state, 1, [], {"type": "pass_priority"})
    payload["redundant_removal_casts"] = value
    result = summarize_trace_rows([{"log": ["AI TRACE " + json.dumps(payload)]}])
    assert not result["availability"]["1"]["redundant_removal_casts"]


def test_copy_trace_uses_saved_spell_surface_not_departed_physical_card():
    state, source_id, _ = surviving_copy()
    payload = build_trace_payload(state, 1, [], {"type": "pass_priority"})
    assert state.cards[source_id].zone == Zone.GRAVEYARD
    copied = payload["stack"][0]
    assert copied["source_name"] == "Stomp"
    assert copied["types"] == ["Instant"]
    assert copied["mana_value"] == 2


def test_positive_pump_materializes_on_friendly_creature_not_opposing_threat():
    state, _, _ = fixture()
    friendly = add_card(state, "Sprite Dragon", Zone.BATTLEFIELD, 1)
    growth = add_card(state, "Giant Growth", Zone.HAND)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == growth.id)
    action = AIAgent()._materialize_action(state, move, 1)
    assert action["targets"]["target_card_id"] == friendly.id
