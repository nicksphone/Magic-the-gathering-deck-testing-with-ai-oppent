"""Direct-card combat controls consume engine legality, not printed keywords."""
import pytest

from game_state.state import Step
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_attack_bands import _state
from tests.test_ai_combat_intents import board


def test_attack_view_exposes_effective_banding_without_mutation():
    state = _state()
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    move = next(move for move in rules.legal_moves(state, 1) if move['type'] == 'attack')
    assert set(move['options']) == {'hero', 'angel', 'elf'}
    assert move['banding_attackers'] == ['hero']
    assert serialize_match_snapshot(state) == before
    state.cards['hero'].keywords = []
    assert next(move for move in rules.legal_moves(state, 1) if move['type'] == 'attack')['banding_attackers'] == []


def test_block_edges_distinguish_direct_flying_restriction_from_band_propagation():
    state = checked_action(_state(), RulesEngine(), 1, {
        'type': 'attack', 'attackers': ['hero', 'angel'], 'bands': [['hero', 'angel']],
    })
    state.step = Step.DECLARE_BLOCKERS
    state.priority_player = 2
    state.passed_priority = set()
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    move = next(move for move in rules.legal_moves(state, 2) if move['type'] == 'block')
    assert move['legal_blocks']['bears'] == ['hero']
    assert move['blocker_capacities']['bears'] == 1
    assert serialize_match_snapshot(state) == before
    paid = checked_action(state, rules, 2, {'type': 'block', 'blocks': {'hero': ['bears']}})
    assert paid.blocks == {'hero': ['bears'], 'angel': ['bears']}


@pytest.mark.parametrize('seat', [1, 2])
def test_unlimited_block_capacity_is_json_safe_for_both_seats(seat):
    state, attackers, bid = board(seat)
    move = next(move for move in RulesEngine().legal_moves(state, 3-seat) if move['type'] == 'block')
    assert move['blocker_capacities'][bid] is None
    assert move['legal_blocks'][bid] == attackers
    paid = checked_action(state, RulesEngine(), 3-seat, {
        'type': 'block', 'blocks': {aid: [bid] for aid in attackers},
    })
    assert paid.blocks == {aid: [bid] for aid in attackers}
