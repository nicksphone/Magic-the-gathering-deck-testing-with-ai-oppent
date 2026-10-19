"""Paid canonical loyalty frames must not manufacture opaque exile identities."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from ai.information import decision_view, is_unknown
from ai.pending_effects import (
    UncertainSimulation, settled_public_position, simulation_frontier,
    simulation_resolve_top, simulation_take_action,
)
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_source_linked_exile import action, position, snap


@pytest.fixture(scope="module", params=[1, 2])
def paid(request):
    state, source = position(request.param)
    state = action(state, request.param, {
        "type": "activate_loyalty", "card_id": source, "ability_index": 0,
        "targets": {},
    })
    assert state.stack[-1].effect_key == "effect_sequence"
    assert any(step["effect_key"] == "loyalty_source_exile"
               and step["payload"]["selection"] == "libraries"
               for step in state.stack[-1].payload["effects"])
    return request.param, state


def private(paid):
    seat, state = paid
    result = decision_view(state, seat, RulesEngine().legal_moves(state, seat))[0]
    assert all(is_unknown(result.cards[player.library[-1]])
               for player in result.players.values())
    return result


def test_first_pass_allowed_imminent_exile_stops_atomically(paid):
    seat, _ = paid
    state = private(paid)
    move = {"type": "pass_priority"}
    assert simulation_frontier(state, seat, move) is None
    simulation_take_action(RulesEngine(), state, seat, move, reject_invalid=True)
    before = snap(state)
    with pytest.raises(UncertainSimulation, match="opaque_source_linked_exile"):
        simulation_take_action(RulesEngine(), state, state.priority_player,
                               move, reject_invalid=True)
    assert snap(state) == before


def test_direct_simulation_resolution_keeps_library_and_permissions(paid):
    state = private(paid)
    before = snap(state)
    with pytest.raises(UncertainSimulation, match="opaque_source_linked_exile"):
        simulation_resolve_top(state)
    assert snap(state) == before


def test_settlement_returns_unknown_without_running_hidden_exile(paid):
    seat, _ = paid
    state = private(paid)
    before = snap(state)
    from rules_engine import source_linked_exile
    with patch.object(source_linked_exile, "execute",
                      wraps=source_linked_exile.execute) as execute:
        assert settled_public_position(state, seat, opaque_draw_counts=True) is None
    assert execute.call_count == 0
    assert snap(state) == before


def test_full_canonical_known_counterpart_matches_actual_engine(paid):
    # Unit knowledge counterpart, not a claim that future library cards are public.
    _, original = paid
    expected, actual = deepcopy(original), deepcopy(original)
    assert simulation_frontier(actual) is None
    assert simulation_resolve_top(actual)
    assert resolve_top_of_stack(expected)
    assert snap(actual) == snap(expected)
    assert len(actual.loyalty_permissions[0]["cards"]) == 2
