"""Read-only reuse must end before rules mutations or later decisions."""
from contextlib import nullcontext
from copy import deepcopy
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine import state_based_actions as sba
from rules_engine.query_context import query_cache
from tests.test_ability_suppression import add
from tests.test_ai_recurring_engines import fixture


@pytest.mark.parametrize('seat', [1, 2])
def test_scoring_reuses_only_the_current_read_only_position(seat):
    state = fixture()
    add(state, 'Llanowar Elves', seat)
    ai = AIAgent(difficulty='master', archetype='Tribal')
    original = ai._strategic_features
    before = serialize_match_snapshot(state)

    def features(position, actor):
        assert query_cache(position) is not None
        return original(position, actor)

    with patch.object(ai, '_strategic_features', side_effect=features):
        first = ai._strategic_position_score(state, seat)
    assert query_cache(state) is None
    assert serialize_match_snapshot(state) == before
    state.players[seat].life -= 5
    assert ai._strategic_position_score(state, seat) != first
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_lethal_scan_reuse_does_not_survive_departures(seat):
    state = fixture()
    dead = add(state, 'Llanowar Elves', seat)
    add(state, 'Royal Assassin', 3-seat)
    dead.counters['__damage_marked'] = 1
    reference = deepcopy(state)
    with patch.object(sba, 'rule_query_scope', side_effect=lambda _: nullcontext()):
        sba.apply_state_based_actions(reference)
    original_scan = sba.creature_has_lethal_state
    original_departure = sba._resolve_lethal_creature_batch

    def scan(position, card_id):
        assert query_cache(position) is not None
        return original_scan(position, card_id)

    def departure(position, card_ids, *, zero_defense=()):
        assert query_cache(position) is None
        return original_departure(position, card_ids, zero_defense=zero_defense)

    with patch.object(sba, 'creature_has_lethal_state', side_effect=scan), \
            patch.object(sba, '_resolve_lethal_creature_batch', side_effect=departure):
        sba.apply_state_based_actions(state)
    assert dead.zone == Zone.GRAVEYARD
    assert query_cache(state) is None
    assert serialize_match_snapshot(state) == serialize_match_snapshot(reference)


def test_nonbattlefield_creature_does_not_require_continuous_queries():
    state = fixture()
    card = add(state, 'Llanowar Elves')
    state.players[card.controller].battlefield.remove(card.id)
    state.players[card.owner].graveyard.append(card.id)
    card.move_to_zone(Zone.GRAVEYARD)
    with patch.object(sba, 'effective_types', side_effect=AssertionError('irrelevant layer query')):
        assert not sba.creature_has_lethal_state(state, card.id)


def test_ordered_legal_offers_reuse_only_the_current_query_scope(monkeypatch):
    from rules_engine import engine
    from rules_engine.query_context import rule_query_scope
    from tests.test_ai_recurring_engines import fixture

    state = fixture()
    rules = engine.RulesEngine()
    original = engine.legal_moves
    calls = []

    def counted(position, seat):
        calls.append(seat)
        return original(position, seat)

    monkeypatch.setattr(engine, 'legal_moves', counted)
    with rule_query_scope(state):
        expected = rules.legal_moves(state, state.priority_player)
        modified = rules.legal_moves(state, state.priority_player)
        assert modified == expected and modified is not expected
        modified[0]['type'] = 'changed'
        assert rules.legal_moves(state, state.priority_player) == expected
        assert len(calls) == 1
    state.winner = 1
    assert rules.legal_moves(state, state.priority_player) == []
    assert len(calls) == 2
