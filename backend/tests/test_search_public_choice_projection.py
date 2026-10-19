"""Public search packets do not expose private choices or engine continuations."""
from copy import deepcopy

import pytest

from rules_engine.optional_reveal import public_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['search_library', 'optional_search'])
def test_search_projection_preserves_only_present_prompt_fields(seat, kind):
    pending = {
        'kind': kind, 'player_id': seat, 'count': 1, 'label': 'Search library',
        'options': ['private-card'], 'library_ids': ['private-card', 'top-card'],
        'effect_payload': {'__search_references': [['private-card', 1, 3]]},
        'resolving_item': {'controller': 3-seat, 'id': 'genuine-stack-id'},
        'continuation_controller': 3-seat,
    }
    before = deepcopy(pending)
    projected = public_choice(pending)
    assert projected == {key: pending[key] for key in
                         ('kind', 'player_id', 'count', 'label')}
    assert pending == before
    projected['count'] = 0
    assert pending == before
    pending['min_count'] = 0
    assert public_choice(pending)['min_count'] == 0


@pytest.mark.parametrize('kind', ['legend_rule', 'trigger_order'])
def test_other_choice_projection_is_unchanged(kind):
    pending = {'kind': kind, 'options': ['public-option']}
    assert public_choice(pending) is pending


def test_no_pending_choice_is_unchanged():
    assert public_choice(None) is None
