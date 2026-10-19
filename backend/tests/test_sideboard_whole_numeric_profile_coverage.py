"""Whole-body advisory coverage audit; no Rule actions, SQL or policy injection."""
from copy import deepcopy
import json

import pytest

from ai import sideboard_policy as policy
from card_data.hydration import hydrate_deck_cards
from knowledge.profiles import derive_profile, merge_profile_payload
from knowledge.service import estimate_for, tags_for
from tests.test_sideboard_finished_transition import MetadataRows, RAW


DECLINE_TEXTS = (
    'UNKNOWN.\n' + RAW['Abrupt Decay']['oracle_text'],
    RAW['Abrupt Decay']['oracle_text'] + ' UNKNOWN.',
    "This spell can't be countered.\nDestroy target nonland permanent with mana value 3 or less if you control a creature.",
    "This spell can't be countered.\nYou may destroy target nonland permanent with mana value 3 or less.",
    "This spell can't be countered if you control a creature.\nDestroy target nonland permanent with mana value 3 or less.",
    "Target spell can't be countered.\nDestroy target nonland permanent with mana value 3 or less.",
    "This spell can't be countered.\nDestroy target nonland permanent with mana value X or less.",
    RAW['Abrupt Decay']['oracle_text'] + ' (UNKNOWN)',
)


@pytest.fixture(scope='module')
def metadata():
    return MetadataRows()


def ordinary_row(metadata, name):
    row = hydrate_deck_cards(metadata, [{'card_name': name, 'quantity': 1}])[0]
    assert tags_for(policy._view(row)).source == 'persisted'
    assert estimate_for(policy._view(row)) is not None
    return row


def test_full_canonical_two_paragraphs_are_covered_without_erasing_prohibition(metadata):
    row = ordinary_row(metadata, 'Abrupt Decay')
    assert row['oracle_text'] == RAW['Abrupt Decay']['oracle_text']
    before = deepcopy(row)
    profile = policy._profile(row)
    assert row == before
    assert profile is not None
    inputs = row['knowledge_snapshot']['estimates']['root']['printed_inputs']
    original = policy._face(inputs, None, None)
    assert len(profile.ability_specs) == len(original.ability_specs) == 2
    for covered, captured in zip(profile.ability_specs, original.ability_specs):
        assert {key: value for key, value in covered.items() if key != 'effects'} == {
            key: value for key, value in captured.items() if key != 'effects'}
    first, second = profile.ability_specs
    start, end = first['source_span']
    assert row['oracle_text'][start:end] == "This spell can't be countered."
    assert first['effects'] == original.ability_specs[0]['effects']
    assert second['kind'] == 'spell_effect' and not second['condition'] and not second['cost']
    effect = next(effect for effect in second['effects'] if effect['effect_key'] == 'destroy_permanent')
    assert effect['payload']['mana_value_max'] == 3
    assert 'Land' in effect['payload']['exclude_types']


@pytest.mark.parametrize('name', ('Counterspell', 'Negate', 'Go for the Throat'))
def test_existing_complete_counter_and_removal_controls_remain_available(metadata, name):
    row = ordinary_row(metadata, name)
    before = deepcopy(row)
    assert policy._profile(row) is not None
    assert row == before


@pytest.mark.parametrize('text', DECLINE_TEXTS, ids=(
    'unknown-prefix', 'unknown-suffix', 'conditional-removal', 'optional-removal',
    'conditional-prohibition', 'wrong-prohibition-subject', 'variable-bound', 'unknown-parenthetic-tail'))
def test_coherent_protocol_body_does_not_gain_coverage_from_source_eligibility(text, metadata):
    # Mutated full RAW COPY is a grammar protocol negative, NOT official Oracle
    # or an executed spell. Ordinary derive/merge/hydrate must do all admission.
    raw = deepcopy(RAW['Abrupt Decay'])
    raw['oracle_text'] = text
    protocol = MetadataRows.__new__(MetadataRows)
    protocol.rows = dict(metadata.rows)
    descriptor = deepcopy(protocol.rows['abrupt decay'])
    descriptor.profiles_json = json.dumps(merge_profile_payload(
        {'card_data': raw, 'rulings_verified': False}, derive_profile(raw)))
    protocol.rows['abrupt decay'] = descriptor
    row = ordinary_row(protocol, 'Abrupt Decay')
    assert row['oracle_text'] == text
    before = deepcopy(row)
    assert policy._profile(row) is None
    assert row == before
