"""Input-forwarding protocol negatives; altered rows never execute gameplay.

The existing whole NEW12 owns genuine RAW/native birth/record/serde acceptance.
These controls stop at the original cache or constructor boundary, not a game
outcome, and must also work against the unchanged observer-only baseline.
"""
from copy import deepcopy
import json
import sys

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import Zone
from tests import test_ai_recurring_engines as recurring
from tests import test_foretell as foretell
from tests import test_modal_spell_faces as modal
from tests import test_ward_resolution as ward


CASES = ('modal', 'ward', 'foretell')
MUTANTS = ('scalar', 'nested-value', 'nested-type', 'replaced-row', 'copied-table')
NAMES = {'modal': modal.ARCHAIC, 'ward': 'Graveyard Trespasser',
         'foretell': 'Behold the Multiverse'}


class AdmissionObserved(Exception):
    pass


def _forbid_raw_lookup(monkeypatch):
    support = sys.modules.get('tests.remaining_named_birth_fixtures')
    if support is not None:
        def forbidden(name):
            raise AssertionError('Negative row reached pinned RAW lookup')
        monkeypatch.setattr(support, 'raw_card', forbidden)


def _observe_normalization(monkeypatch, name):
    calls = []
    original = ScryfallSyncService._normalize_payload

    def observe(cls, raw, image_uri, rulings=None):
        if raw.get('name') in (name, name.split(' // ')[0]):
            calls.append(deepcopy(raw))
        return original.__func__(cls, raw, image_uri, rulings)

    monkeypatch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe))
    return calls


def _observe_constructor(monkeypatch):
    calls = []

    def observe(**kwargs):
        calls.append(deepcopy(kwargs))
        raise AdmissionObserved

    monkeypatch.setattr(recurring, 'CardInstance', observe)
    return calls


def _assert_direct_input(supplied, row, name, seat):
    assert (supplied['name'], supplied['owner'], supplied['controller'], supplied['zone']) == (
        name, seat, seat, Zone.HAND)
    for key in ('mana_cost', 'oracle_text', 'keywords', 'colors'):
        expected = row[key] or [] if key in ('keywords', 'colors') else row[key]
        assert type(supplied[key]) is type(expected)
        assert supplied[key] == expected
    for key, expected in (('layout', row.get('layout') or ''),
                          ('card_faces', row.get('card_faces') or [])):
        assert type(supplied[key]) is type(expected)
        assert supplied[key] == expected


@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('mutant', MUTANTS)
@pytest.mark.parametrize('seat', (1, 2))
def test_changed_or_replaced_original_rows_retain_legacy_admission(case, mutant, seat, monkeypatch):
    module = {'modal': modal, 'ward': ward, 'foretell': foretell}[case]
    attribute = 'DATA' if case == 'modal' else 'CARDS'
    table, name = getattr(module, attribute), NAMES[case]
    row = table[name]
    if mutant == 'copied-table':
        table = deepcopy(table)
        monkeypatch.setattr(module, attribute, table)
    elif mutant == 'replaced-row':
        monkeypatch.setitem(table, name, deepcopy(row))
    elif mutant == 'scalar':
        monkeypatch.setitem(row, 'mana_cost', False)
    elif mutant == 'nested-value':
        if row.get('card_faces'):
            front = row['card_faces'][0]
            monkeypatch.setitem(front, 'oracle_text', front['oracle_text'] + ' ')
        else:
            monkeypatch.setitem(row, 'colors', deepcopy(row['colors']))
            row['colors'].append('G')
    else:
        key = 'card_faces' if row.get('card_faces') else 'colors'
        monkeypatch.setitem(row, key, tuple(row[key]))
    row = table[name]
    before = deepcopy(row)
    state = None if case == 'modal' else (ward.clean(seat) if case == 'ward' else foretell.clean())
    _forbid_raw_lookup(monkeypatch)
    normalizations = _observe_normalization(monkeypatch, name)
    if case == 'modal':
        admitted = []

        def observe_hydration(repo, rows):
            admitted.append(deepcopy(vars(repo.get_cached_cards_by_names([name])[name.lower()])))
            raise AdmissionObserved

        monkeypatch.setattr(modal, 'hydrate_deck_cards', observe_hydration)
        with pytest.raises(AdmissionObserved):
            modal.fixture(name)
        expected = {key: value for key, value in row.items() if key != 'card_faces'}
        expected.update(card_faces_json=json.dumps(row['card_faces']), image_uri='/card-images/offline.svg')
        assert admitted == [expected]
    else:
        admitted = _observe_constructor(monkeypatch)
        with pytest.raises(AdmissionObserved):
            module.add(state, name, seat, Zone.HAND)
        assert len(admitted) == 1
        _assert_direct_input(admitted[0], row, name, seat)
    assert normalizations == [], 'Negative inputs must bypass RAW lookup/projection, not be healed'
    assert row == before


@pytest.mark.parametrize('case', ('ward', 'foretell'))
@pytest.mark.parametrize('seat', (1, 2))
def test_explicit_custom_target_table_is_forwarded_unchanged(case, seat, monkeypatch):
    module, name = (ward, NAMES['ward']) if case == 'ward' else (foretell, NAMES['foretell'])
    cards = {name: deepcopy(module.CARDS[name])}
    before = deepcopy(cards)
    state = ward.clean(seat) if case == 'ward' else foretell.clean()
    _forbid_raw_lookup(monkeypatch)
    normalizations = _observe_normalization(monkeypatch, name)
    admitted = _observe_constructor(monkeypatch)
    alias = module.add_card if case == 'ward' else module.raw_add
    with pytest.raises(AdmissionObserved):
        alias(state, name, seat, Zone.HAND, cards=cards)
    assert len(admitted) == 1
    _assert_direct_input(admitted[0], cards[name], name, seat)
    assert normalizations == [] and cards == before


@pytest.mark.parametrize('name', ('Damnation', 'Grizzly Bears'))
@pytest.mark.parametrize('seat', (1, 2))
def test_default_recurring_table_remains_the_original_interface(name, seat, monkeypatch):
    state = foretell.clean()
    _forbid_raw_lookup(monkeypatch)
    row = deepcopy(recurring.CARDS[name])
    normalizations = _observe_normalization(monkeypatch, name)
    admitted = _observe_constructor(monkeypatch)
    with pytest.raises(AdmissionObserved):
        foretell.raw_add(state, name, seat, Zone.HAND)
    assert len(admitted) == 1
    _assert_direct_input(admitted[0], row, name, seat)
    assert normalizations == [] and recurring.CARDS[name] == row
