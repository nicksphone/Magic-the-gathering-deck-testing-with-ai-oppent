"""Rejection-only summary protocols; no fabricated profile or game certificate."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path

import pytest

from ai import sideboard_policy as policy
from card_data.hydration import hydrate_deck_cards
from knowledge.service import estimate_for, tags_for
from tests.test_sideboard_finished_transition import MetadataRows, RAW


MALFORMED = (
    ('empty-id', 'card_id', ''),
    ('whitespace-id', 'card_id', '  '),
    ('empty-sha', 'source_sha256', ''),
    ('short-sha', 'source_sha256', 'a' * 63),
    ('long-sha', 'source_sha256', 'a' * 65),
    ('nonhex-sha', 'source_sha256', 'g' * 64),
    ('uppercase-sha', 'source_sha256', 'A' * 64),
    ('newline-sha', 'source_sha256', 'a' * 64 + '\n'),
)


@pytest.fixture(scope='module')
def genuine_profile():
    row = hydrate_deck_cards(MetadataRows(), [{'card_name': 'Abrupt Decay', 'quantity': 1}])[0]
    assert tags_for(policy._view(row)).source == 'persisted'
    assert estimate_for(policy._view(row)) is not None
    assert row['oracle_text'] == RAW['Abrupt Decay']['oracle_text']
    profile = policy._profile(row)
    assert profile is not None
    return row, profile


@pytest.fixture(scope='module')
def fit_callable():
    stage = os.environ.get('NUMERIC_RECEIPT_PROJECTION')
    if stage is None:
        return policy._fit
    assert stage in ('OLD', 'FIXED')
    root = Path(__file__).resolve().parents[3]
    path = root / ('PROJECTION_' + stage) / '_fit.POST.py'
    source = path.read_bytes()
    pins = __import__('json').loads((root / 'PROJECTION_PINS.json').read_text())
    assert hashlib.sha256(source).hexdigest() == pins[stage]
    namespace = dict(policy.__dict__)
    exec(compile(source, str(path), 'exec'), namespace)
    return namespace['_fit']


@pytest.mark.parametrize('label,key,value', MALFORMED, ids=[x[0] for x in MALFORMED])
def test_malformed_receipt_cannot_authorize_numeric_fit(label, key, value, genuine_profile, fit_callable):
    row, profile = genuine_profile
    group = {'card_id': 'protocol-only-not-a-physical-card',
             'source_sha256': row['knowledge_snapshot']['source_sha256'],
             'types': ['Creature'], 'mana_cost': '{1}{G}'}
    group[key] = value
    events = {'observed_types': ['Creature'], 'observed_creature_count': 0,
              'own_creature_count': 0, 'public_type_groups': [],
              'public_numeric_groups': [group]}
    before = deepcopy((row, events))
    result = fit_callable(profile, events, row['oracle_text'])
    assert (row, events) == before
    assert result == 0
