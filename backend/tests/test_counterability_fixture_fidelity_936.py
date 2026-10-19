"""Observe original real first consumers, not a replacement test scenario."""
from copy import deepcopy
from dataclasses import fields

import pytest

from game_state.state import CardInstance, Zone
from tests import test_counterability_scope as original
from tests.counterability_canonical_936 import canonical_card, raw_card
from tests.library_canonical_fixtures import PRINTED

CASES = (
    ('Allosaurus Shepherd', 'test_spell_protection_does_not_protect_source_activated_ability', ('Allosaurus Shepherd',)),
    ('Destiny Spinner', 'test_spell_protection_does_not_protect_source_activated_ability', ('Destiny Spinner',)),
    ('Stifle', 'test_stifle_cast_and_resolution_counters_shepherd_ability_not_source', ()),
    ('Counterspell', 'test_removed_static_source_no_longer_protects_spell_at_counter_resolution', ()),
    ('Llanowar Elves', 'test_battlefield_spell_protection_checks_printed_scope', ('Allosaurus Shepherd', 'Llanowar Elves', 2, True, False)),
    ('Cultivate', 'test_battlefield_spell_protection_checks_printed_scope', ('Allosaurus Shepherd', 'Cultivate', 2, True, False)),
    ('Lightning Bolt', 'test_battlefield_spell_protection_checks_printed_scope', ('Allosaurus Shepherd', 'Lightning Bolt', 2, False, False)),
    ('Island', 'test_spell_protection_does_not_protect_source_activated_ability', ('Allosaurus Shepherd',)),
)


class Consumed(BaseException):
    pass


def printed(card):
    return {key: deepcopy(getattr(card, key)) for key in PRINTED}


@pytest.mark.parametrize('name,function,args', CASES, ids=[case[0] for case in CASES])
def test_original_first_consumer_receives_complete_parent(monkeypatch, name, function, args):
    seen = []

    def wrap(real):
        def observe(state, *positional, **keywords):
            cards = [card for card in state.cards.values() if card.name == name]
            if cards:
                expected = printed(canonical_card(name))
                for card in cards:
                    assert printed(card) == expected
                    assert card.oracle_text == raw_card(name)['oracle_text']
                seen.extend(card.id for card in cards)
                raise Consumed
            return real(state, *positional, **keywords)
        return observe

    for symbol in ('counter_ability', 'counter_spell', 'counter_spell_unless_pay',
                   'copy_spell', 'checked_action', 'resolve_top_of_stack'):
        monkeypatch.setattr(original, symbol, wrap(getattr(original, symbol)))
    with pytest.raises(Consumed):
        getattr(original, function)(*args)
    assert seen


def test_full_objects_include_identity_and_untrimmed_parent_data():
    assert len({case[0] for case in CASES}) == 8
    for name, _, _ in CASES:
        raw = raw_card(name)
        assert {'id', 'oracle_id', 'legalities', 'set', 'uri', 'scryfall_uri',
                'image_uris', 'type_line', 'oracle_text', 'layout'} <= raw.keys()
        assert raw['name'] == name


def test_fresh_objects_and_raw_rows_are_independently_mutable():
    first, second = raw_card('Allosaurus Shepherd'), raw_card('Allosaurus Shepherd')
    first['legalities']['noncanonical-control'] = 'inert'
    assert 'noncanonical-control' not in second['legalities']
    first, second = canonical_card('Destiny Spinner'), canonical_card('Destiny Spinner')
    before = printed(second)
    first.colors.append('R')
    first.printed_characteristics['noncanonical-control'] = []
    assert printed(second) == before


def test_template_retains_original_direct_constructor_runtime_defaults():
    baseline = CardInstance('runtime-control', 'Anonymous runtime control', 1, 1, Zone.HAND, [])
    actual = canonical_card('Stifle', id=baseline.id, owner=1, controller=1, zone=Zone.HAND)
    for field in fields(CardInstance):
        if field.name not in PRINTED:
            assert getattr(actual, field.name) == getattr(baseline, field.name), field.name


def test_named_printed_metadata_cannot_be_forged_as_pose():
    with pytest.raises(ValueError, match='Printed fields'):
        canonical_card('Counterspell', oracle_text='Anonymous negative input.')
