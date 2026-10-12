"""Real query calls: scope bootstrap is not another multiplier evaluation."""
import sys
from unittest.mock import patch

import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine import continuous
from rules_engine.mana_abilities import multiplied_outputs
from rules_engine.query_context import query_cache, rule_query_scope
from tests.test_mana_abilities import add
from tests.test_mana_multiplier_prefilter import reference
from tests.test_variable_mana import clean


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Mana Reflection', 'Nyxbloom Ancient'])
def test_real_scope_reentry_evaluates_only_matching_source_once(seat, name, monkeypatch):
    state = clean()
    land = add(state, 'Forest', seat)
    irrelevant = [add(state, 'Llanowar Elves', seat) for _ in range(8)]
    matching = add(state, name, seat)
    opposing = add(state, 'Mana Reflection', 3-seat)
    before = serialize_match_snapshot(state)
    expected = reference(state, land, {'G': 1, 'U': 2})
    original = continuous.printed_abilities_suppressed
    visits = []

    def observe(current, cid, **kwargs):
        visits.append((current, cid, sys._getframe(1).f_code, query_cache(current) is None))
        return original(current, cid, **kwargs)

    monkeypatch.setattr(continuous, 'printed_abilities_suppressed', observe)
    assert query_cache(state) is None
    with patch.object(continuous, '_printed_suppression_result',
                      wraps=continuous._printed_suppression_result) as evaluations:
        assert multiplied_outputs(state, land, {'G': 1, 'U': 2}) == expected
        assert len(visits) == 2
        assert visits == [(state, matching.id, multiplied_outputs.__code__, True),
                          (state, matching.id, original.__code__, False)]
        assert evaluations.call_count == 1
        assert evaluations.call_args.args[:3] == (state, matching.id, matching)
        assert query_cache(state) is None
        visits.clear()
        evaluations.reset_mock()
        with rule_query_scope(state):
            assert query_cache(state) is not None
            assert multiplied_outputs(state, land, {'G': 1, 'U': 2}) == expected
            assert visits == [(state, matching.id, multiplied_outputs.__code__, False)]
            assert evaluations.call_count == 1
            assert evaluations.call_args.args[:3] == (state, matching.id, matching)
        assert query_cache(state) is None
    assert all(cid != opposing.id and cid not in {land.id, *(c.id for c in irrelevant)}
               for _, cid, _, _ in visits)
    assert serialize_match_snapshot(state) == before
