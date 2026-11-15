"""Synthetic API boundaries only; these are not additional gameplay fixtures."""
import pytest

import test_saga_land_entry as entry
from test_resolved_activated_grants import component_grant
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone


@pytest.mark.parametrize('view', ['raw', 'current', 'layer'])
def test_grant_query_result_has_no_mutable_alias_to_authoritative_root(view):
    from rules_engine import activated_grants as grants
    from rules_engine.continuous import effective_activated_grants
    state = entry.position(1)
    cid = entry.add(state, "Urza's Saga", 1, Zone.BATTLEFIELD)
    component_grant(state, cid)
    before = serialize_match_snapshot(state)
    values = (grants.records(state.cards[cid]) if view == 'raw' else
              grants.records(state.cards[cid], state) if view == 'current' else
              effective_activated_grants(state, cid))
    values[0]['timestamp'] += 1
    assert serialize_match_snapshot(state) == before


def test_index_floor_reserves_effective_intrinsic_rows_too(monkeypatch):
    from rules_engine import activated_grants as grants, mana_abilities
    state = entry.position(1)
    cid = entry.add(state, "Urza's Saga", 1, Zone.BATTLEFIELD)
    # Consumer shape can contain more current intrinsic rows than raw printing.
    rows = tuple((i, '{T}', 'Add {' + c + '}.') for i, c in enumerate('WUBRG'))
    monkeypatch.setattr(mana_abilities, '_printed_mana_ability_specs', lambda card, state=None, **kw: rows)
    assert grants._index_floor(state.cards[cid], state) == 5
