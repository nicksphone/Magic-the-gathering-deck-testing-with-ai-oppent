"""Query-local reuse must not become stale across authoritative mutations."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
from threading import Barrier
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from ai.pending_effects import planning_copy
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine import land_types
from rules_engine import query_context
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_source_outputs
from rules_engine.continuous import effective_combat_stats, effective_keyword_counts
from tests.test_land_type_layers import add
from tests.test_variable_mana import clean
from tests.test_ai_projection_scope import dense_removal_state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('source', [None, 'Blood Moon', 'Yavimaya, Cradle of Growth'])
def test_reuses_one_view_during_a_query_including_no_effects(seat, source):
    state = clean()
    land = add(state, 'Hallowed Fountain', seat)
    if source:
        add(state, source, seat)
    before = serialize_match_snapshot(state)
    with patch.object(land_types, '_uncached_view', wraps=land_types._uncached_view) as build:
        with query_context.rule_query_scope(state):
            first = mana_source_outputs(state, seat, land.id)
            for _ in range(4):
                with query_context.rule_query_scope(state):
                    assert mana_source_outputs(state, seat, land.id) == first
            assert build.call_count == 1
        assert mana_source_outputs(state, seat, land.id) == first
        assert build.call_count > 1
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_source_departure_and_controller_change_are_fresh_next_query(seat):
    state = clean()
    land = add(state, 'Hallowed Fountain', seat)
    source = add(state, 'Prismatic Omen', seat)
    with query_context.rule_query_scope(state):
        assert mana_source_outputs(state, seat, land.id) == dict.fromkeys('WUBRG', 1)
    state.players[seat].battlefield.remove(source.id)
    state.players[3-seat].battlefield.append(source.id)
    source.controller = 3-seat
    with query_context.rule_query_scope(state):
        assert mana_source_outputs(state, seat, land.id) == {'W': 1, 'U': 1}
    state.players[3-seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    state.players[source.owner].graveyard.append(source.id)
    with query_context.rule_query_scope(state):
        assert mana_source_outputs(state, seat, land.id) == {'W': 1, 'U': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_nested_branch_scope_and_entry_view_do_not_pollute_parent(seat):
    state = clean()
    land = add(state, 'Hallowed Fountain', seat)
    source = add(state, 'Magus of the Moon', seat)
    state.players[seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source.id)
    with query_context.rule_query_scope(state):
        assert mana_source_outputs(state, seat, land.id) == {'W': 1, 'U': 1}
        assert 'Mountain' in land_types._view(state, source)[0][land.id]
        branch = planning_copy(state)
        branch.players[seat].hand.remove(source.id)
        branch.players[seat].battlefield.append(source.id)
        branch.cards[source.id].move_to_zone(Zone.BATTLEFIELD)
        with query_context.rule_query_scope(branch):
            assert mana_source_outputs(branch, seat, land.id) == {'R': 1}
        assert mana_source_outputs(state, seat, land.id) == {'W': 1, 'U': 1}
    assert source.id in state.players[seat].hand


def test_exception_and_simultaneous_queries_restore_context():
    state = clean()
    land = add(state, 'Hallowed Fountain')
    with pytest.raises(RuntimeError):
        with query_context.rule_query_scope(state):
            mana_source_outputs(state, 1, land.id)
            raise RuntimeError('query aborted')
    assert query_context._query.get() is None


    barrier = Barrier(2)
    def query(name):
        branch = deepcopy(state)
        add(branch, name)
        with query_context.rule_query_scope(branch):
            barrier.wait(timeout=10)
            return [mana_source_outputs(branch, 1, land.id) for _ in range(5)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        moon = pool.submit(query, 'Blood Moon')
        grove = pool.submit(query, 'Yavimaya, Cradle of Growth')
        assert moon.result() == [{'R': 1}] * 5
        assert grove.result() == [{'W': 1, 'U': 1, 'G': 1}] * 5
    assert query_context._query.get() is None


@pytest.mark.parametrize('seat', [1, 2])
def test_stat_flags_counters_and_keyword_results_are_not_stale_or_shared(seat):
    state = clean()
    creature = add(state, 'River Boa', seat)
    before = serialize_match_snapshot(state)
    with query_context.rule_query_scope(state):
        assert effective_combat_stats(state, creature.id) == (2, 1)
        first = effective_keyword_counts(state, creature.id)
        expected = dict(first)
        first['flying'] = 99
        assert effective_keyword_counts(state, creature.id) == expected
    assert serialize_match_snapshot(state) == before
    creature.counters['+1/+1'] = 2
    with query_context.rule_query_scope(state):
        assert effective_combat_stats(state, creature.id) == (4, 3)
    creature.counters.clear()
    creature.power = None
    with query_context.rule_query_scope(state):
        assert effective_combat_stats(state, creature.id)[0] is None
        assert effective_combat_stats(state, creature.id, unknown_as_zero=True)[0] == 0
        assert effective_combat_stats(state, creature.id)[0] is None


@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Midrange', 'Control', 'Tempo', 'Ramp',
    'Drain', 'Aristocrats', 'Reanimator', 'Tokens', 'Tribal', 'Combo-lite',
    'Counter-heavy', 'Removal-heavy'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_cross_style_decisions_and_pure_query_outputs_match_uncached(style, difficulty):
    state, _ = dense_removal_state()
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, 1)
    value = evaluate_board(state, 1)
    optimized = AIAgent(archetype=style, difficulty=difficulty).choose_action(state, moves, 1)
    with patch.object(query_context, 'rule_query_scope', lambda *_: nullcontext()):
        assert RulesEngine().legal_moves(state, 1) == moves
        assert evaluate_board(state, 1) == value
        reference = AIAgent(archetype=style, difficulty=difficulty).choose_action(state, moves, 1)
    assert optimized == reference
    assert serialize_match_snapshot(state) == before
