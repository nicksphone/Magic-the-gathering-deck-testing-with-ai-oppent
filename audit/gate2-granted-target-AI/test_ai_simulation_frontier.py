"""Real paid-frame frontier controls; known/empty counterparts are explicitly unit controls."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from ai.information import decision_view
from ai.pending_effects import (
    simulation_frontier, simulation_take_action, simulation_checked_action, simulation_resolve_top,
    UncertainSimulation, settled_public_position,
)
from effects import registry
from nadu_support import snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from test_ai_granted_equip import prepare


@pytest.fixture(scope='module', params=[1, 2])
def paid(request):
    p, _, _ = prepare(request.param, 'one_slot')
    return p


def frame(p, private=True):
    state = checked_action(deepcopy(p.state), RulesEngine(), p.seat,
                           {'type': 'equip', 'card_id': p.ids['shuko'], 'target_card_id': p.ids['elf']})
    assert [i.effect_key for i in state.stack] == ['equip_attachment', 'reveal_top_conditional']
    return decision_view(state, p.seat, RulesEngine().legal_moves(state, p.seat))[0] if private else state


def test_first_pass_allowed_second_is_atomic_uncertainty(paid):
    state = frame(paid)
    first = {'type': 'pass_priority'}
    assert simulation_frontier(state, paid.seat, first) is None
    simulation_take_action(RulesEngine(), state, paid.seat, first, reject_invalid=True)
    before = snapshot(state)
    assert simulation_frontier(state, state.priority_player, first) == 'opaque_conditional_acquisition'
    with pytest.raises(UncertainSimulation, match='opaque_conditional_acquisition'):
        simulation_take_action(RulesEngine(), state, state.priority_player, first, reject_invalid=True)
    assert snapshot(state) == before


def test_real_offered_mana_response_remains_executed_and_valued(paid):
    state = frame(paid)
    actor = state.priority_player
    response = next(m for m in RulesEngine().legal_moves(state, actor) if m['type'] == 'activate_mana_ability')
    response = {**response, **response['output_options'][0]}
    before = snapshot(state)
    score = evaluate_board(state, actor)
    assert simulation_frontier(state, actor, response) is None
    simulation_take_action(RulesEngine(), state, actor, response, reject_invalid=True)
    assert evaluate_board(state, actor) > score
    assert len(state.stack) == 2 and state.stack[-1].effect_key == 'reveal_top_conditional'
    assert {pid: p.library for pid, p in state.players.items()} == {
        int(pid): p['library'] for pid, p in before['players'].items()}
    original = frame(paid)
    value = AIAgent(difficulty='master_plus')._strategic_line_score(original, response, actor, 1)
    assert value != -9999.0, 'Opaque pending frame must not prune an actual legal response'


def test_known_canonical_handler_matches_unwrapped_real_engine(paid):
    # Full canonical engine knowledge, NOT a fabricated public-observation gameplay claim.
    known = frame(paid, private=False)
    expected = deepcopy(known)
    assert simulation_frontier(known) is None
    for _ in range(2):
        simulation_take_action(RulesEngine(), known, known.priority_player,
                               {'type': 'pass_priority'}, reject_invalid=True)
        RulesEngine().take_action(expected, expected.priority_player,
                                 {'type': 'pass_priority'}, reject_invalid=True)
    assert snapshot(known) == snapshot(expected)
    assert len(known.players[paid.seat].library) == len(paid.state.players[paid.seat].library)-1


def test_only_current_frame_and_nonempty_opaque_acquisition_are_frontiers(paid):
    state = frame(paid)
    before = snapshot(state)
    assert simulation_frontier(state) == 'opaque_conditional_acquisition'
    assert snapshot(state) == before
    # Pure helper counterparts only, not injected gameplay/corpus certification.
    current_other = deepcopy(state)
    current_other.stack.reverse()
    assert simulation_frontier(current_other) is None
    empty = deepcopy(state)
    empty.players[paid.seat].library = []
    assert simulation_frontier(empty) is None


def test_wrong_actor_retains_engine_validation_not_blanket_uncertainty(paid):
    state = frame(paid)
    simulation_take_action(RulesEngine(), state, paid.seat, {'type': 'pass_priority'}, reject_invalid=True)
    before = snapshot(state)
    assert simulation_frontier(state, paid.seat, {'type': 'pass_priority'}) is None
    with pytest.raises(ActionRejected):
        simulation_checked_action(state, RulesEngine(), paid.seat, {'type': 'pass_priority'})
    assert snapshot(state) == before


def test_common_settlement_returns_unknown_without_reveal_execution(paid):
    state = frame(paid)
    before = snapshot(state)
    calls = []
    original = registry.EFFECT_HANDLERS['reveal_top_conditional']
    def forbidden(*args):
        calls.append(True)
        return original(*args)
    with patch.dict(registry.EFFECT_HANDLERS, {'reveal_top_conditional': forbidden}):
        assert settled_public_position(state, paid.seat, opaque_draw_counts=True) is None
    assert not calls and snapshot(state) == before
