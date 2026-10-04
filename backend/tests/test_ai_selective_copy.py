from copy import deepcopy

import pytest

from ai.information import decision_view
from ai.pending_effects import planning_copy
from game_state.serializers import serialize_match_snapshot
from tests.test_ai_information_boundary import counter_position


class ForbiddenCopy:
    def __deepcopy__(self, memo):
        raise AssertionError('Hidden metadata must not be traversed')


@pytest.mark.parametrize('seat', [1, 2])
def test_private_card_and_other_deck_metadata_are_not_copied(seat):
    state, _, hidden = counter_position(seat)
    hidden.private_note = ForbiddenCopy()
    state.starting_decks[3-seat] = [{'card_name': 'Counterspell', 'quantity': 4,
                                    'private_note': ForbiddenCopy()}]
    state.hidden_alias = hidden
    state.hidden_dict_alias = hidden.__dict__
    view, _ = decision_view(state, seat, [])
    assert view.hidden_alias is view.cards[hidden.id]
    assert view.hidden_dict_alias is view.cards[hidden.id].__dict__
    assert not hasattr(view.cards[hidden.id], 'private_note')
    assert list(view.starting_decks) == [seat]
    assert hasattr(hidden, 'private_note')


@pytest.mark.parametrize('seat', [1, 2])
def test_caller_memo_is_not_mutated_and_known_mutable_fields_are_independent(seat):
    state, own, _ = counter_position(seat)
    own.counters['charge'] = 1
    before = serialize_match_snapshot(state)
    memo = {id(state.log): ['public observation']}
    expected = dict(memo)
    copied = planning_copy(state, memo=memo)
    assert memo == expected
    assert copied.log == ['public observation']
    copied.cards[own.id].counters['charge'] = 10
    assert serialize_match_snapshot(state) == before
    view, moves = decision_view(state, seat, [{'type': 'pass_priority', 'choices': []}])
    view.cards[own.id].counters['charge'] = 5
    moves[0]['choices'].append('changed')
    assert serialize_match_snapshot(state) == before


def test_plain_planning_copy_still_matches_deepcopy_except_discarded_log():
    state, _, _ = counter_position(1)
    expected = deepcopy(state)
    expected.log = []
    assert serialize_match_snapshot(planning_copy(state)) == serialize_match_snapshot(expected)
