"""Closed Domain-only admission; mutations are diagnostics, never gameplay Oracle."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

import inventory as inv
from card_data.hydration import hydrate_deck_cards
from rules_engine.coverage import known_unsupported_mechanics

DOMAIN = ['Herd Migration', 'Leyline Binding']
STAGE = os.environ.get('GATE2_ADMISSION_STAGE', 'parent')
assert STAGE in {'parent', 'composition'}


@pytest.fixture(scope='module')
def cards():
    metadata = hydrate_deck_cards(None, [{'card_name': name, 'quantity': 1} for name in DOMAIN])
    return {row['card_name']: row for row in metadata}


def warnings(metadata, *, name=None, text=None, faces=None):
    return known_unsupported_mechanics(
        metadata['oracle_text'] if text is None else text, faces,
        card_name=metadata['card_name'] if name is None else name,
        canonical_context=metadata)


@pytest.mark.parametrize('name', DOMAIN)
def test_sourced_complete_body_admission_is_query_pure(cards, name):
    metadata = cards[name]
    before = deepcopy(metadata)
    assert warnings(metadata) == []
    assert known_unsupported_mechanics(metadata['oracle_text'], card_name=name) == ['domain']
    assert metadata == before


@pytest.mark.parametrize('name', DOMAIN)
def test_admission_is_body_driven_not_a_name_exemption(cards, name):
    metadata = deepcopy(cards[name])
    metadata['card_name'] = metadata['name'] = 'Diagnostic generic complete body'
    assert warnings(metadata) == []
    # This is a diagnostic copy, not a new canonical card or paid Oracle fixture.


FAULTS = ['suffix', 'new-line', 'parenthetical-suffix', 'parenthetical-line',
          'unknown-prefix', 'duplicated-body', 'missing-instruction', 'changed-recipient',
          'changed-duration', 'changed-amount', 'changed-cost', 'type-mismatch',
          'mana-mismatch', 'source-unknown', 'sources-mixed', 'source-absent',
          'sources-not-list', 'layout-transform', 'layout-split', 'layout-token',
          'faces-in-context', 'faces-in-call', 'context-text-mismatch', 'name-mismatch',
          'missing-name']


@pytest.mark.parametrize('name', DOMAIN)
@pytest.mark.parametrize('fault', FAULTS)
def test_complete_body_boundaries_keep_domain_warning(cards, name, fault):
    metadata = deepcopy(cards[name])
    original = metadata['oracle_text']
    text = original
    call_name = name
    faces = None
    if fault == 'suffix':
        text += ' Unknown diagnostic instruction.'
    elif fault == 'new-line':
        text += '\nUnknown diagnostic instruction.'
    elif fault == 'parenthetical-suffix':
        text += ' (Unknown diagnostic instruction.)'
    elif fault == 'parenthetical-line':
        text += '\n(Unknown diagnostic instruction.)'
    elif fault == 'unknown-prefix':
        text = 'Unknown diagnostic instruction.\n' + text
    elif fault == 'duplicated-body':
        text += '\n' + text
    elif fault == 'missing-instruction':
        text = '\n'.join(text.splitlines()[:-1])
    elif fault == 'changed-recipient':
        text = text.replace('lands you control', 'lands an opponent controls')
    elif fault == 'changed-duration':
        text = text.replace('then shuffle.', 'then mill a card.').replace(
            'until this enchantment leaves the battlefield.', 'until end of turn.')
    elif fault == 'changed-amount':
        text = text.replace('3 life', '4 life').replace('costs {1}', 'costs {2}')
    elif fault == 'changed-cost':
        text = text.replace('{1}{G}', '{2}{G}').replace('less to cast', 'more to cast')
    elif fault == 'type-mismatch':
        metadata['type_line'] = 'Artifact'
    elif fault == 'mana-mismatch':
        metadata['mana_cost'] = '{100}'
    elif fault == 'source-unknown':
        metadata['card_data_sources'] = ['untrusted']
    elif fault == 'sources-mixed':
        metadata['card_data_sources'] = ['offline_seed', 'untrusted']
    elif fault == 'source-absent':
        metadata.pop('card_data_sources', None)
    elif fault == 'sources-not-list':
        metadata['card_data_sources'] = 'offline_seed'
    elif fault.startswith('layout-'):
        metadata['layout'] = fault.removeprefix('layout-')
    elif fault == 'faces-in-context':
        metadata['card_faces'] = [{'name': name, 'oracle_text': original, 'type_line': 'Sorcery'}]
    elif fault == 'faces-in-call':
        faces = [{'name': name, 'oracle_text': original, 'type_line': 'Sorcery'}]
    elif fault == 'context-text-mismatch':
        metadata['oracle_text'] = 'Unknown diagnostic instruction.'
    elif fault == 'name-mismatch':
        call_name = 'Different query name'
    elif fault == 'missing-name':
        metadata.pop('card_name', None)
        metadata.pop('name', None)
    else:
        raise AssertionError(fault)
    if text != original:
        metadata['oracle_text'] = text
    before = deepcopy(metadata)
    assert 'domain' in warnings(metadata, name=call_name, text=text, faces=faces)
    assert metadata == before


def test_exact_full155_delta_has_only_two_domain_reason_removals():
    before = json.loads((Path(__file__).parent / 'fixtures' / ('domain-' + STAGE + '-baseline.json')).read_text())
    current = inv.report(*inv.load_inputs())
    old = {c['name']: c for c in before['cards']}
    new = {c['name']: c for c in current['cards']}
    assert set(old) == set(new) and len(new) == 155
    changed = []
    for name in sorted(new):
        assert new[name]['runtime_printing_id'] == old[name]['runtime_printing_id']
        assert new[name]['raw_sha256'] == old[name]['raw_sha256']
        reasons = old[name]['hydrated_known_admission_gaps']
        expected = [r for r in reasons if r != 'domain'] if name in DOMAIN else reasons
        assert new[name]['hydrated_known_admission_gaps'] == expected
        if reasons != expected:
            changed.append(name)
    assert changed == sorted(DOMAIN)
    actual = current['actual_offline_preflight']
    assert actual['metadata_ready_cards'] == 155
    assert actual['gap_cards'] == (7 if STAGE == 'composition' else 10)
    assert actual['no_known_gap_not_certified_cards'] == (148 if STAGE == 'composition' else 145)
    assert current['source_data'] == before['source_data']
    assert (actual['runtime_surfaces'], actual['runtime_printed_lines'],
            actual['runtime_positive_contract_lines'], actual['runtime_unsatisfied_positive_contract_lines']) == (171, 332, 11, 321)
    assert current['expert_ai_certified'] is False and current['rules_support_certified'] is False
    assert all(c['complete_card_semantics'] == 'unverified' for c in current['cards'])
