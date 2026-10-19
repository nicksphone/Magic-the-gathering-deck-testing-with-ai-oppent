"""NEW pure actual paid continuation and generic projection compatibility."""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.optional_reveal import public_choice
import test_brainstorm_desired as brain


FIELDS = ('kind', 'player_id', 'options', 'count', 'min_count', 'label',
          'option_labels', 'option_type_lines')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_actual_paid_public_projection_preserves_internal_resume_and_order(seat, restore):
    state = brain.position(seat)
    brain.add(state, 'Counterspell', seat, Zone.HAND)
    state, source = brain.brainstorm(state, seat)
    if restore:
        state = brain.cold(state)
    before = deepcopy(serialize_match_snapshot(state))
    pending = deepcopy(state.pending_mechanic_choice)
    assert {'effect_payload', 'resolving_item', 'continuation_controller', 'continuation_effects'} <= set(pending)
    expected = {key: pending[key] for key in FIELDS if key in pending}
    assert public_choice(state.pending_mechanic_choice) == expected
    assert serialize_match(state)['pending_mechanic_choice'] == expected
    assert serialize_match_snapshot(state) == before
    assert state.pending_mechanic_choice == pending
    assert state.cards[source].zone == Zone.STACK
    selected = list(reversed(state.players[seat].hand[:2]))
    library = list(state.players[seat].library)
    result = brain.act(state, seat, {'type': 'choose_mechanic', 'card_ids': selected})
    assert result.players[seat].library == library + list(reversed(selected))
    assert not result.pending_mechanic_choice and result.cards[source].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before
    brain.cold(result)


@pytest.mark.parametrize('pending,expected', [
    (None, None),
    ({'kind': 'search_library', 'player_id': 1, 'label': 'Search', 'count': 1,
      'min_count': 0, 'options': ['private'], 'effect_payload': {'amount': 1}},
     {'kind': 'search_library', 'player_id': 1, 'label': 'Search', 'count': 1, 'min_count': 0}),
    ({'kind': 'optional_search', 'player_id': 2, 'label': 'Search', 'count': 1,
      'options': ['private']}, {'kind': 'optional_search', 'player_id': 2, 'label': 'Search', 'count': 1}),
    ({'kind': 'land_from_hand', 'player_id': 1, 'label': 'Land', 'count': 1,
      'min_count': 0, 'options': ['private']},
     {'kind': 'land_from_hand', 'player_id': 1, 'label': 'Land', 'count': 1, 'min_count': 0}),
    ({'kind': 'optional_reveal', 'player_id': 2, 'label': 'Reveal', 'count': 1,
      'options': ['private']}, {'kind': 'optional_reveal', 'player_id': 2, 'label': 'Reveal', 'count': 1}),
    ({'kind': 'legacy_unknown', 'options': ['legacy'], 'context': 'legacy'},
     {'kind': 'legacy_unknown', 'options': ['legacy'], 'context': 'legacy'}),
])
def test_legacy_projection_branches_exact_protocol_only(pending, expected):
    # Explicit projection-only descriptors, not fabricated gameplay/private events.
    before = deepcopy(pending)
    assert public_choice(pending) == expected
    assert pending == before


def test_optional_display_fields_kept_projection_only():
    pending = {'kind': 'hand_top_order', 'player_id': 2, 'count': 2, 'min_count': 2,
               'options': ['a', 'b'], 'label': 'Topmost first',
               'option_labels': {'a': 'A'}, 'option_type_lines': {'a': 'Land'},
               'effect_payload': {'amount': 2}, 'continuation_controller': 2}
    before = deepcopy(pending)
    assert public_choice(pending) == {key: pending[key] for key in FIELDS}
    assert pending == before
