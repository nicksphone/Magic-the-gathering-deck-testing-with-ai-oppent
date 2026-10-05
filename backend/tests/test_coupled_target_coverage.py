"""Canonical gap warnings are not claims of implemented card semantics."""
import json
from pathlib import Path

import pytest

from rules_engine.coverage import known_unsupported_mechanics, deck_pair_coverage


FIXTURES = Path(__file__).parent / 'fixtures/coupled_targets'


@pytest.mark.parametrize('slug,expected', [
    ('searing-blaze', {'controller-linked damage targets', 'conditional land-entry damage'}),
    ('agony-warp', {'independent target-instance fidelity'}),
])
@pytest.mark.parametrize('face', [False, True])
def test_canonical_target_gaps_are_reported_from_root_or_face(slug, expected, face):
    raw = json.loads((FIXTURES / f'{slug}.json').read_text())
    kwargs = {'card_name': raw['name']}
    if face:
        kwargs['card_faces'] = [raw, raw]
    gaps = known_unsupported_mechanics('' if face else raw['oracle_text'], **kwargs)
    assert expected <= set(gaps)
    assert len(gaps) == len(set(gaps))


@pytest.mark.parametrize('slug', ['searing-blaze', 'agony-warp'])
@pytest.mark.parametrize('seat', [0, 1])
def test_deck_preflight_requires_review_for_each_family_and_seat(slug, seat):
    raw = json.loads((FIXTURES / f'{slug}.json').read_text())
    card = {**raw, 'card_name': raw['name'], 'quantity': 4}
    pair = [[], []]
    pair[seat] = [card]
    report = deck_pair_coverage(*pair)
    assert report['status'] == 'exploratory'
    affected = report['known_unsupported_cards']
    assert len(affected) == 1
    assert affected[0]['deck'] == ('A' if seat == 0 else 'B')
    assert affected[0]['card_name'] == raw['name']


@pytest.mark.parametrize('text', [
    'Lightning Bolt deals 3 damage to any target.',
    'Target creature gets -3/-0 until end of turn. Draw a card.',
    'Landfall - Whenever a land enters the battlefield under your control, draw a card.',
    'Searing Blaze is a card name, not an instruction.',
])
def test_unrelated_text_and_card_names_do_not_create_target_gap_warnings(text):
    gaps = set(known_unsupported_mechanics(text))
    assert not gaps.intersection({'controller-linked damage targets',
                                  'conditional land-entry damage',
                                  'independent target-instance fidelity'})
