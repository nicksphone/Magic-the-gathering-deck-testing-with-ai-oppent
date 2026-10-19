"""Tests-first constructor observations of one real release-contract caller.

Compose this file under backend/tests before running. No Main/HTTP caller, fake
cache row, unknown-stat protocol vector, or printed metadata is replaced here.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, MatchFactory, Zone
from tests import test_release_card_contracts as release


CASES = {
    'Grizzly Bears': (
        'vraska_full/fixtures/grizzly-bears-scryfall-raw.json',
        '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c',
        '409f9b88-f03e-40b6-9883-68c14c37c0de',
    ),
    'Glorious Anthem': (
        'fixtures/mass_exile_audit/glorious-anthem.json',
        '475da90077f984d1b82160a7b480fae627973edbc13dd07357c6c03106dad2af',
        '17d154d3-7ae5-43ff-9978-d974285e2c89',
    ),
}
COPIABLE = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
            'printed_power', 'printed_toughness', 'loyalty', 'oracle_text',
            'keywords', 'colors')
PHYSICAL = (*COPIABLE, 'card_faces', 'layout', 'selected_face_index', 'image_uri')


def _raw(name):
    relative, expected_sha, printing_id = CASES[name]
    body = (Path(release.__file__).parent / relative).read_bytes()
    assert hashlib.sha256(body).hexdigest() == expected_sha
    raw = json.loads(body)
    assert (raw['object'], raw['name'], raw['id']) == ('card', name, printing_id)
    assert raw['layout'] == 'normal' and raw['keywords'] == []
    return raw


def _expected(raw):
    kinds = {'Artifact', 'Battle', 'Creature', 'Enchantment', 'Instant',
             'Kindred', 'Land', 'Planeswalker', 'Sorcery'}
    return {
        **{key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'layout')},
        'types': [word for word in raw['type_line'].split('\u2014')[0].split() if word in kinds],
        'power': int(raw['power']) if 'power' in raw else None,
        'toughness': int(raw['toughness']) if 'toughness' in raw else None,
        'printed_power': raw.get('power'), 'printed_toughness': raw.get('toughness'),
        'loyalty': None, 'keywords': [], 'colors': raw['colors'],
        'card_faces': raw.get('card_faces', []), 'selected_face_index': None,
        'image_uri': None,  # Preserve this caller's existing display-only pose.
    }


def _strict(actual, expected, field):
    assert type(actual) is type(expected), field
    if type(expected) is dict:
        assert actual.keys() == expected.keys(), field
        for key in expected:
            _strict(actual[key], expected[key], field + '.' + key)
    elif type(expected) is list:
        assert len(actual) == len(expected), field
        for index, (left, right) in enumerate(zip(actual, expected)):
            _strict(left, right, field + '[' + str(index) + ']')
    else:
        assert actual == expected, field


@pytest.mark.parametrize('name', CASES, ids=('grizzly-bears', 'glorious-anthem'))
def test_original_release_positive_supplies_complete_facts_before_native_birth(name, monkeypatch):
    raw, factories, births = _raw(name), [], []
    native_factory = MatchFactory.from_decks
    native_post_init = CardInstance.__post_init__

    def observe_birth(card):
        supplied = {key: deepcopy(getattr(card, key)) for key in PHYSICAL}
        result = native_post_init(card)
        births.append((card, supplied, deepcopy(card.characteristic_record)))
        return result

    def observe_factory(deck_a, deck_b, *args, **kwargs):
        decks = deepcopy((deck_a, deck_b))
        state = native_factory(deck_a, deck_b, *args, **kwargs)
        factories.append((state, decks))
        return state

    monkeypatch.setattr(CardInstance, '__post_init__', observe_birth)
    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
    # Retain every native continuous-effect, marked-damage and reload assertion.
    release.test_public_card_view_matches_combat_and_preserves_base_after_reload()

    assert factories, 'The original caller must execute the genuine Factory'
    state, decks = factories[0]
    assert state.starting_decks == {1: decks[0], 2: decks[1]}
    if name == 'Grizzly Bears':
        for deck in decks:
            assert sum(row['quantity'] for row in deck) == 60
            for row in deck:
                assert row['card_name'] == name
                printed = {'mana_cost', 'oracle_text', 'type_line', 'colors', 'layout', 'power', 'toughness'}
                assert printed <= row.keys(), 'Original Bears Factory input drops printed facts'
                assert raw.keys() <= row.keys(), 'Original Bears input must admit the full pinned RAW'
                for key, value in raw.items():
                    _strict(row[key], value, 'Factory RAW.' + key)
        selected = [birth for birth in births
                    if any(birth[0] is card for card in state.cards.values())]
        assert len(selected) == 120
        assert {card.owner for card, _, _ in selected} == {1, 2}
    else:
        selected = [birth for birth in births if birth[0].id == 'anthem']
        assert len(selected) == 1
        card = selected[0][0]
        assert (card.name, card.owner, card.controller, card.zone) == (name, 1, 1, Zone.BATTLEFIELD)

    expected = _expected(raw)
    for card, supplied, record in selected:
        _strict(supplied, expected, name + ' supplied at birth')
        _strict(record, {'version': 1, 'physical': expected,
                        'values': {key: expected[key] for key in COPIABLE}},
                name + ' native retained birth')
