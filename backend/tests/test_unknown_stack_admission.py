"""Unknown storage frames never become abilities at a direct effect boundary."""
from copy import deepcopy

import pytest

from effects.handlers import copy_ability, counter_ability
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Zone
from rules_engine.targeting import stack_object_kind


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', [Zone.HAND, Zone.STACK, Zone.BATTLEFIELD])
@pytest.mark.parametrize('handler', [copy_ability, counter_ability])
def test_unknown_frame_is_atomic_before_copy_or_counter(seat, zone, handler):
    state = MatchFactory.from_decks([], [], seed=11)
    source = CardInstance('source', 'Unrelated source', seat, seat, zone, ['Creature'])
    state.cards[source.id] = source
    item = StackItem('unknown', source.id, seat, 'Unproven frame', 'gain_life',
                     {'amount': 1, 'target_player': seat})
    state.stack.append(item)
    assert stack_object_kind(state, item) == 'legacy_unknown'
    before = deepcopy(serialize_match_snapshot(state))
    handler(state, 3-seat, {'target_stack_id': item.id})
    assert serialize_match_snapshot(state) == before
    assert state.stack == [item]


@pytest.mark.parametrize('kind', ['spell', 'activated', 'triggered'])
def test_declared_kind_not_later_source_zone_controls_direct_ability_effects(kind):
    for handler in (copy_ability, counter_ability):
        state = MatchFactory.from_decks([], [], seed=11)
        source = CardInstance('source', 'Unrelated source', 1, 1, Zone.HAND, ['Creature'])
        state.cards[source.id] = source
        payload = {'amount': 1, 'target_player': 1}
        if kind == 'triggered':
            payload['__trigger_event'] = 'enters_battlefield'
        else:
            payload['__announced_stack_kind'] = kind
        item = StackItem('declared', source.id, 1, 'Declared frame', 'gain_life', payload)
        state.stack.append(item)
        handler(state, 2, {'target_stack_id': item.id})
        expected = 1 if kind == 'spell' else (2 if handler is copy_ability else 0)
        assert len(state.stack) == expected
        if kind != 'spell' and handler is copy_ability:
            assert state.stack[-1].payload['__stack_copy_kind'] == kind
