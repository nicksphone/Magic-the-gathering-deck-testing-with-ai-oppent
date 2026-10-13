"""Task44 facts are private observations, never public rules permissions."""
from dataclasses import field, make_dataclass
import json
import pickle

import pytest

from ai.information import decision_view
from ai.sideboard_facts import copy_facts
from game_state.serializers import serialize_match
from game_state.state import MatchState
from rules_engine import graveyard_inventory as inventory
from tests.test_numeric_inventory_adapter import positive, pure_inventory


class PrivateValue:
    def __deepcopy__(self, memo):
        raise AssertionError('Private fact content must not enter decision view')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['empty', 'producer-initialized', 'forged', 'opaque'])
def test_private_fact_dictionaries_are_neutral_and_hidden_without_source_mutation(seat, kind):
    state = positive(seat)
    factory_facts = state.sideboard_facts
    if kind == 'producer-initialized':
        assert type(factory_facts) is dict and factory_facts['capture_version'] == 3
    else:
        # Declared trusted empty pose, not the real factory's default.
        state.sideboard_facts = {}
        assert state.sideboard_facts == {}
    assert copy_facts({}, state) == {}
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    if kind == 'forged':
        state.sideboard_facts = {'PRIVATE_OBSERVER_SENTINEL': {
            'permission': 'cast_from_graveyard', 'oracle': 'invented private claim'}}
    elif kind == 'opaque':
        state.sideboard_facts = {'PRIVATE_OBSERVER_SENTINEL': PrivateValue()}
    before = pickle.dumps(state, protocol=5)
    assert pure_inventory(state, seat) == expected
    projected, _ = decision_view(state, seat, [])
    assert projected.sideboard_facts == {}
    assert pure_inventory(projected, seat) == expected
    public = json.dumps(serialize_match(state, look_players=[seat]))
    assert 'sideboard_facts' not in public
    assert 'PRIVATE_OBSERVER_SENTINEL' not in public
    assert pickle.dumps(state, protocol=5) == before
    if kind == 'producer-initialized':
        assert state.sideboard_facts is factory_facts


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [None, [], False, 'private string'])
def test_non_dictionary_fact_carrier_is_unknown_without_mutation(seat, bad):
    state = positive(seat)
    assert pure_inventory(state, seat)['status'] == 'inert'
    state.sideboard_facts = bad
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['runtime', 'declared'])
def test_future_state_permissions_remain_uncovered(seat, kind, monkeypatch):
    state = positive(seat)
    assert pure_inventory(state, seat)['status'] == 'inert'
    if kind == 'runtime':
        state.future_private_permission = {}
    else:
        original = inventory.fields
        extra = make_dataclass('UnreviewedState', [('future_private_permission', dict, field(default_factory=dict))])
        monkeypatch.setattr(inventory, 'fields', lambda cls:
            original(cls) + original(extra) if cls is MatchState else original(cls))
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_private_facts_do_not_cover_actual_rules_permission(seat):
    state = positive(seat)
    state.sideboard_facts = {'PRIVATE_OBSERVER_SENTINEL': {'permission': 'safe'}}
    assert pure_inventory(state, seat)['status'] == 'inert'
    state.cards[state.players[3 - seat].graveyard[0]].granted_flashback = {'turn': state.turn}
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_fact_carrier_is_uncovered(seat):
    state = positive(seat)
    assert pure_inventory(state, seat)['status'] == 'inert'
    del state.sideboard_facts
    assert pure_inventory(state, seat)['status'] == 'unknown'
