"""Printed policy fit is not permission; source binding and domains remain strict."""
from copy import deepcopy

import pytest

from ai import sideboard_policy as policy
from tests.test_sideboard_finished_transition import MetadataRows
from card_data.hydration import hydrate_deck_cards


@pytest.mark.parametrize('name,types,want', [
    ('Negate', ['Creature'], 0),
    ('Negate', ['Artifact', 'Creature'], 0),
    ('Negate', ['Instant'], 1),
    ('Go for the Throat', ['Artifact', 'Creature'], 0),
    ('Go for the Throat', ['Enchantment'], 0),
    ('Go for the Throat', ['Creature'], 2),
])
def test_whole_printed_answer_fit_retains_actual_native_target_domain(name, types, want):
    row = hydrate_deck_cards(MetadataRows(), [{'card_name': name, 'quantity': 1}])[0]
    profile = policy._profile(row)
    assert profile is not None
    before = deepcopy(row)
    public = {'observed_types': types, 'public_type_groups': [types],
              'observed_creature_count': int('Creature' in types), 'own_creature_count': 0}
    assert policy._fit(profile, public, row['oracle_text']) == want
    assert row == before


@pytest.mark.parametrize('name', ['Negate', 'Go for the Throat'])
@pytest.mark.parametrize('fault', ['forged-carrier', 'changed-live-source'])
def test_cached_advice_cannot_cover_forged_or_stale_printed_source(name, fault):
    row = hydrate_deck_cards(MetadataRows(), [{'card_name': name, 'quantity': 1}])[0]
    assert policy._profile(row) is not None
    if fault == 'forged-carrier':
        row['knowledge_snapshot']['source_sha256'] = '0' * 64
    else:
        row['oracle_text'] += ' You win the game.'
    before = deepcopy(row)
    assert policy._profile(row) is None
    assert row == before
