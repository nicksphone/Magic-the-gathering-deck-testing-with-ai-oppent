"""Observe the original consumers, stopping before effects/HTTP rather than pruning the mixed suite."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from tests import test_prevention_replacement_edges as original
from tests.library_canonical_fixtures import PRINTED
from tests.prevention_replacement_canonical_fb531 import canonical_card, raw_card


CASES = (
    ('test_unconditional_draw_doubling_applies_once_per_source_and_original_draw', 'Thought Reflection'),
    ('test_conditional_draw_doubling_exempts_only_first_actual_draw_in_own_step', "Teferi's Ageless Insight"),
    ('test_archive_life_and_draw_replacements_remain_independent', "Alhammarret's Archive"),
    ('test_archive_life_and_draw_replacements_remain_independent', 'Lich'),
    ('test_replaced_first_draw_does_not_use_draw_step_exception', 'Stinkweed Imp'),
    ('test_dredge_choices_preserve_draw_replacement_context_across_pause', 'Stinkweed Imp'),
    ('test_human_draw_replacement_choice_can_select_dredge_or_doubling', 'Stinkweed Imp'),
    ('test_human_stack_choice_between_draw_doublers_is_resumable', 'Ancestral Recall'),
    ('test_skullcrack_style_turn_restrictions_apply_and_expire_at_cleanup', 'Skullcrack'),
    ('test_destroy_permanent_respects_die_to_exile_replacement', 'Rest in Peace'),
    ('test_destroy_permanent_respects_rest_in_peace_for_artifact', 'Rest in Peace'),
    ('test_http_draw_step_replacement_choice_resumes', 'Thought Reflection'),
)
NAMES = frozenset(name for _, name in CASES)


class Consumed(BaseException):
    pass


def printed(card):
    return {field: deepcopy(getattr(card, field)) for field in PRINTED}


@pytest.mark.parametrize('function,name', CASES, ids=[function + ':' + name for function, name in CASES])
def test_original_first_consumer_has_complete_pinned_printed_facts(monkeypatch, function, name):
    seen = []

    def inspect(state):
        matches = [card for card in state.cards.values() if card.name == name]
        if not matches:
            return
        for card in matches:
            expected = canonical_card(name, id=card.id, owner=card.owner,
                                      controller=card.controller, zone=card.zone)
            assert printed(card) == printed(expected)
            assert card.oracle_text == raw_card(name)['oracle_text']
        seen.extend(card.id for card in matches)
        raise Consumed

    def wrap(real):
        def boundary(state, *args, **kwargs):
            inspect(state)
            return real(state, *args, **kwargs)
        return boundary

    for symbol in ('resolve_effect', 'gain_life', 'replacement_options', 'replace_draw_cards',
                   'resolve_top_of_stack', 'add_to_stack', 'build_ability_spec', 'replace_die_zone'):
        monkeypatch.setattr(original, symbol, wrap(getattr(original, symbol)))
    real_next_step = original.RulesEngine.next_step

    def next_step(engine, state, *args, **kwargs):
        inspect(state)
        return real_next_step(engine, state, *args, **kwargs)

    monkeypatch.setattr(original.RulesEngine, 'next_step', next_step)
    with pytest.raises(Consumed):
        getattr(original, function)()
    assert seen


def test_original_factory_basic_land_birth_is_complete_not_a_retagged_card():
    state = original._state()
    expected = printed(canonical_card('Island', id='expected', owner=1, controller=1, zone=Zone.HAND))
    assert len(state.cards) == 120
    assert all(printed(card) == expected for card in state.cards.values())


def test_full_raw_identity_provenance_and_bodies_are_not_reduced_fixtures():
    assert len(NAMES) == 8
    for name in NAMES | {'Island'}:
        raw = raw_card(name)
        assert {'id', 'oracle_id', 'legalities', 'uri', 'scryfall_uri', 'set',
                'collector_number', 'rarity', 'layout', 'color_identity'} <= raw.keys()
        assert raw['name'] == name and raw['object'] == 'card'
        assert canonical_card(name, id='raw-check', owner=1, controller=1,
                              zone=Zone.HAND).oracle_text == raw['oracle_text']


def test_materialized_objects_do_not_share_mutable_printed_fields():
    first = canonical_card('Thought Reflection', id='one', owner=1, controller=1, zone=Zone.BATTLEFIELD)
    second = canonical_card('Thought Reflection', id='two', owner=1, controller=1, zone=Zone.BATTLEFIELD)
    before = printed(second)
    first.colors.append('R')
    first.printed_characteristics['noncanonical-test-key'] = []
    assert printed(second) == before
    assert 'noncanonical-test-key' not in raw_card('Thought Reflection')


def test_printed_facts_cannot_be_overridden_as_a_fixture_pose():
    with pytest.raises(ValueError, match='Printed fields'):
        canonical_card('Thought Reflection', id='forged', oracle_text='Draw a card.')
