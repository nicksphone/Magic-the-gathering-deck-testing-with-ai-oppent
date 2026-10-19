"""A retained printed record is genuine data, never an anonymous runtime pose."""
from copy import deepcopy
from dataclasses import fields
import importlib
import random

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, MatchState, PlayerState, Zone
from rules_engine.copiable_values import FIELDS, PHYSICAL
from tests import library_canonical_fixtures as library


HELPERS = (
    ('library_canonical_fixtures', 'Counterspell'),
    ('counterability_canonical_936', 'Stifle'),
    ('prevention_replacement_canonical_fb531', 'Ancestral Recall'),
)
RUNTIME = (
    'id', 'owner', 'controller', 'zone', 'tapped', 'summoning_sick', 'entered_turn',
    'counters', 'counter_timestamps', 'keyword_effects', 'base_stat_effects',
    'type_effects', 'type_effect_base', 'control_effect_base', 'control_effects',
    'attached_to', 'static_order', 'effect_timestamp', 'battlefield_incarnation',
    'instance_order', 'zone_change_sequence', 'chosen_creature_type',
    'bestow_characteristics', 'is_token', 'last_known_battlefield',
    'exile_face_down', 'foretell_record', 'suspend_haste', 'granted_flashback',
    'was_foretold', 'was_kicked', 'kicker_count',
)


def expected_record(raw):
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'quantity': 8, 'card_name': raw['name'],
             'colors': raw['colors']}
    state = MatchFactory.from_decks([entry], [], seed=0)
    card = next(card for card in state.cards.values() if card.zone == Zone.LIBRARY)
    physical = {key: deepcopy(getattr(card, key)) for key in PHYSICAL}
    values = {key: deepcopy(physical[key]) for key in FIELDS}
    values['types'] = [kind for kind in values['types'] if kind != 'Token']
    for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout'):
        assert physical[key] == raw[key]
    assert physical['card_faces'] == raw.get('card_faces', [])
    assert card.characteristic_record == {'version': 1, 'physical': physical, 'values': values}
    return card.characteristic_record


@pytest.mark.parametrize('module,name', HELPERS)
def test_each_helper_has_the_genuine_complete_factory_record(module, name):
    helper = importlib.import_module('tests.' + module)
    actual = helper.canonical_card(name)
    assert actual.characteristic_record == expected_record(helper.raw_card(name))


@pytest.mark.parametrize('module,name', HELPERS)
def test_characteristic_record_cannot_be_forged_as_a_fixture_pose(module, name):
    helper = importlib.import_module('tests.' + module)
    with pytest.raises(ValueError, match='Printed fields'):
        helper.canonical_card(name, characteristic_record={'version': 0, 'physical': {}, 'values': {}})


@pytest.mark.parametrize('module,name', HELPERS)
def test_runtime_pose_keeps_values_while_record_remains_real(module, name):
    helper = importlib.import_module('tests.' + module)
    pose = dict(id='runtime-protocol', owner=2, controller=1, zone=Zone.EXILE,
                tapped=True, summoning_sick=False, entered_turn=7,
                counters={'charge': 2}, counter_timestamps={'charge': 3},
                instance_order=19, zone_change_sequence=4)
    actual = helper.canonical_card(name, **pose)
    assert {key: getattr(actual, key) for key in pose} == pose
    assert actual.characteristic_record == expected_record(helper.raw_card(name))


def test_printed_and_runtime_partition_is_exhaustive_and_physical():
    assert 'characteristic_record' in library.PRINTED
    assert set(RUNTIME) == {field.name for field in fields(CardInstance)} - library.PRINTED
    actual = library.canonical_card('Counterspell')
    assert actual.characteristic_record == expected_record(library.raw_card('Counterspell'))


@pytest.mark.parametrize('operation', ('reprint', 'canonicalize_basics'))
def test_reprint_and_basic_reset_replace_stale_records_without_runtime_or_alias_leaks(operation):
    cards = [library.canonical_card('Forest', id=f'forest-{index}', owner=1,
                                    controller=1, zone=Zone.LIBRARY)
             for index in range(2)]
    state = MatchState(id='uncaptured-fixture-protocol',
                       players={1: PlayerState(1, 'one'), 2: PlayerState(2, 'two')},
                       cards={card.id: card for card in cards}, stack=[], rng=random.Random(71))
    state.players[1].library = [card.id for card in cards]
    assert state.sideboard_facts == {}
    stale = CardInstance('anonymous-protocol', 'Anonymous stale-record control', 1, 1,
                         Zone.LIBRARY, []).characteristic_record
    for card in cards:
        card.characteristic_record = deepcopy(stale)
        card.counters['charge'] = 2
    runtime = [{key: deepcopy(getattr(card, key)) for key in RUNTIME} for card in cards]
    rng = state.rng.getstate()
    if operation == 'reprint':
        for card in cards:
            assert library.reprint(state, card.id, 'Forest') is card
    else:
        library.canonicalize_basics(state)
    expected = expected_record(library.raw_card('Forest'))
    assert all(card.characteristic_record == expected for card in cards)
    assert [{key: getattr(card, key) for key in RUNTIME} for card in cards] == runtime
    assert state.rng.getstate() == rng and state.sideboard_facts == {}
    first, second = cards
    assert first.characteristic_record is not second.characteristic_record
    first.characteristic_record['physical']['types'].append('Anonymous alias control')
    assert second.characteristic_record == expected
    assert first.types == expected['physical']['types']
    assert first.characteristic_record['values'] == expected['values']


@pytest.mark.parametrize('module,name', HELPERS)
def test_constructor_record_mutation_does_not_reach_sibling_or_live_fields(module, name):
    helper = importlib.import_module('tests.' + module)
    first, second = helper.canonical_card(name), helper.canonical_card(name)
    expected = expected_record(helper.raw_card(name))
    first.characteristic_record['values']['types'].append('Anonymous alias control')
    assert second.characteristic_record == expected
    assert first.characteristic_record['physical'] == expected['physical']
    assert first.types == expected['physical']['types']
