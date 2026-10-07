"""Closed admission diagnostics; mutated bodies are never gameplay fixtures."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

import inventory as inv
from card_data.hydration import hydrate_deck_cards
from rules_engine.coverage import known_unsupported_mechanics, _paid_body_admission

NAMES = ['Searing Blaze', 'Sunfall', 'Chrome Host Seedshark']
REASONS = {'Searing Blaze': ['controller-linked damage targets', 'conditional land-entry damage'],
           'Sunfall': ['incubate'], 'Chrome Host Seedshark': ['incubate']}


@pytest.fixture(scope='module')
def cards():
    return {row['card_name']: row for row in hydrate_deck_cards(
        None, [{'card_name': name, 'quantity': 1} for name in NAMES])}


def warnings(metadata, *, name=None, faces=None):
    return known_unsupported_mechanics(metadata['oracle_text'], faces,
        card_name=metadata['card_name'] if name is None else name, canonical_context=metadata)


@pytest.mark.parametrize('name', NAMES)
def test_complete_canonical_body_and_unsourced_negative(cards, name):
    metadata = cards[name]
    before = deepcopy(metadata)
    assert warnings(metadata) == []
    assert known_unsupported_mechanics(metadata['oracle_text'], card_name=name) == REASONS[name]
    assert metadata == before


@pytest.mark.parametrize('name', NAMES)
def test_body_driven_admission_not_name_allowlist(cards, name):
    metadata = deepcopy(cards[name])
    replacement = 'Diagnostic generic complete body'
    metadata['oracle_text'] = metadata['oracle_text'].replace(name, replacement)
    metadata['card_name'] = metadata['name'] = replacement
    assert warnings(metadata) == []


FAULTS = ['suffix', 'newline', 'unknown-parenthetical', 'unknown-parenthetical-line',
          'prefix', 'duplicate', 'amount', 'predicate', 'recipient',
          'type', 'mana', 'layout-transform', 'layout-split', 'layout-token',
          'faces-context', 'faces-call', 'source-unknown', 'source-mixed',
          'source-absent', 'source-not-list', 'text-mismatch', 'name-mismatch', 'missing-name']


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('fault', FAULTS)
def test_unknown_fullbody_and_untrusted_context_keep_all_warnings(cards, name, fault):
    metadata = deepcopy(cards[name])
    faces = None
    call_name = name
    text = metadata['oracle_text']
    if fault == 'suffix':
        text += ' Unknown diagnostic instruction.'
    elif fault == 'newline':
        text += '\nUnknown diagnostic instruction.'
    elif fault == 'unknown-parenthetical':
        text += ' (Unknown diagnostic instruction.)'
    elif fault == 'unknown-parenthetical-line':
        text += '\n(Unknown diagnostic instruction.)'
    elif fault == 'prefix':
        text = 'Unknown diagnostic instruction.\n' + text
    elif fault == 'duplicate':
        text += '\n' + text
    elif fault == 'amount':
        text = text.replace('deals 3 damage', 'deals 4 damage').replace('incubate X', 'incubate 4').replace('Incubate X', 'Incubate 4')
    elif fault == 'predicate':
        text = text.replace('under your control this turn', 'under an opponent\'s control this turn').replace('creatures exiled this way', 'creatures on the battlefield').replace('noncreature spell', 'creature spell')
    elif fault == 'recipient':
        text = text.replace('that player or that planeswalker\'s controller controls', 'you control').replace('Exile all creatures.', 'Exile all artifacts.').replace('Whenever you cast', 'Whenever an opponent casts')
    elif fault == 'type':
        metadata['type_line'] = 'Artifact'
    elif fault == 'mana':
        metadata['mana_cost'] = '{100}'
    elif fault.startswith('layout-'):
        metadata['layout'] = fault.removeprefix('layout-')
    elif fault == 'faces-context':
        metadata['card_faces'] = [{'name': name, 'oracle_text': text}]
    elif fault == 'faces-call':
        faces = [{'name': name, 'oracle_text': text}]
    elif fault == 'source-unknown':
        metadata['card_data_sources'] = ['untrusted']
    elif fault == 'source-mixed':
        metadata['card_data_sources'] = ['offline_seed', 'untrusted']
    elif fault == 'source-absent':
        metadata.pop('card_data_sources', None)
    elif fault == 'source-not-list':
        metadata['card_data_sources'] = 'offline_seed'
    elif fault == 'text-mismatch':
        metadata['oracle_text'] = 'Unknown diagnostic instruction.'
        assert known_unsupported_mechanics(text, card_name=name, canonical_context=metadata) == REASONS[name]
        return
    elif fault == 'name-mismatch':
        call_name = 'Different query name'
    elif fault == 'missing-name':
        metadata.pop('card_name', None)
        metadata.pop('name', None)
    else:
        raise AssertionError(fault)
    metadata['oracle_text'] = text
    before = deepcopy(metadata)
    assert _paid_body_admission(text, metadata, call_name, faces) == set()
    assert warnings(metadata, name=call_name, faces=faces) == known_unsupported_mechanics(
        text, faces, card_name=call_name)
    assert metadata == before


@pytest.mark.parametrize('name', ['Sunfall', 'Chrome Host Seedshark'])
@pytest.mark.parametrize('fault', ['reminder-cost', 'reminder-body', 'reminder-suffix', 'missing-reminder'])
def test_complete_incubator_reminder_is_not_arbitrary_parenthesis_stripping(cards, name, fault):
    metadata = deepcopy(cards[name])
    text = metadata['oracle_text']
    if fault == 'reminder-cost':
        text = text.replace('{2}: Transform', '{1}: Transform')
    elif fault == 'reminder-body':
        text = text.replace('0/0 Phyrexian', '1/1 Phyrexian')
    elif fault == 'reminder-suffix':
        text = text[:-1] + ' Draw a card.)'
    else:
        text = text.split(' (Create an Incubator')[0]
    metadata['oracle_text'] = text
    assert 'incubate' in warnings(metadata)


def test_full155_only_three_hydrated_reason_changes():
    before = json.loads((Path(__file__).parent / 'fixtures/three-parent-baseline.json').read_text())
    # Contracts may contain tuples; compare the same lossless JSON representation.
    after = json.loads(json.dumps(inv.report(*inv.load_inputs())))
    projected = deepcopy(after)
    changed = []
    for old, new in zip(before['cards'], projected['cards']):
        assert old['name'] == new['name']
        expected = [r for r in old['hydrated_known_admission_gaps']
                    if r not in REASONS.get(old['name'], [])]
        assert new['hydrated_known_admission_gaps'] == expected
        if old['hydrated_known_admission_gaps'] != expected:
            changed.append(old['name'])
        new['hydrated_known_admission_gaps'] = old['hydrated_known_admission_gaps']
    assert sorted(changed) == sorted(NAMES)
    actual = after['actual_offline_preflight']
    assert (actual['metadata_ready_cards'], actual['gap_cards'], actual['no_known_gap_not_certified_cards']) == (155, 7, 148)
    # Only these admission counters and the three reason fields may change.
    projected['actual_offline_preflight'] = before['actual_offline_preflight']
    differences = [(old['name'], key) for old, new in zip(before['cards'], projected['cards'])
                   for key in old if old[key] != new[key]]
    assert projected == before, differences
