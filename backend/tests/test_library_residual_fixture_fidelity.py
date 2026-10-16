"""Real first-consumer checks; original scenarios always retain their delegates."""
import importlib

import pytest

from game_state.state import Zone
from tests.library_canonical_fixtures import raw_card, ranking_raw_card, RANKING_NAMES
from tests.test_library_fixture_fidelity import assert_printed
from tests import test_library_search_rules as search


def _facts(state, ids, names, *, zone=None):
    assert len(ids) == len(names) and len(ids) == len(set(ids))
    for cid, name in zip(ids, names):
        card = state.cards[cid]
        raw = ranking_raw_card(name) if name in RANKING_NAMES else raw_card(name)
        assert card.id == cid and card.owner == card.controller == 1
        if zone is not None:
            assert card.zone == zone
        assert_printed(card, raw)


@pytest.mark.parametrize('branch', (0, 1, 2), ids=('graveyard-three', 'RiP-exile', 'optional-ai'))
def test_buried_alive_actual_target_facts_in_every_branch(monkeypatch, branch):
    delegate = search.resolve_effect
    observed = []

    def capture(state, *args, **kwargs):
        index = len(observed)
        ids = list(state.players[1].library[-3:] if index == 0 else state.players[1].library[-1:])
        observed.append(ids)
        if index == branch:
            _facts(state, ids, ['Grizzly Bears'] * len(ids), zone=Zone.LIBRARY)
        return delegate(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(search, 'resolve_effect', capture)
        search.test_buried_alive_searches_three_creatures_into_graveyard_with_replacement()
    assert list(map(len, observed)) == [3, 1, 1]


def test_explicit_topdeck_tutor_actual_six_inputs_and_unchanged_actions(monkeypatch):
    delegate = search.resolve_effect
    observed = []

    def capture(state, *args, **kwargs):
        ids = list(state.players[1].library[-6:])
        names = ('Deathbloom Gardener', 'Forest', 'Brindle Boar', 'Forest',
                 'Wayward Swordtooth', 'Forest')
        _facts(state, ids, names, zone=Zone.LIBRARY)
        cards = [state.cards[ids[index]] for index in (0, 2, 4)]
        assert [card.mana_cost for card in cards] == ['{2}{G}'] * 3
        assert [(card.power, card.toughness) for card in cards] == [(1, 1), (2, 2), (5, 5)]
        observed.append(ids)
        return delegate(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(search, 'resolve_effect', capture)
        search.test_topdeck_battlefield_tutor_chooses_only_at_resolution()
    assert len(observed) == 1


def test_choose_zero_and_overlimit_use_six_real_eligible_elves(monkeypatch):
    delegate = search.resolve_effect
    observed = []

    def capture(state, *args, **kwargs):
        ids = list(state.players[1].library[-6:])
        _facts(state, ids, ['Llanowar Elves'] * 6, zone=Zone.LIBRARY)
        assert [(state.cards[cid].power, state.cards[cid].toughness) for cid in ids] == [(1, 1)] * 6
        assert [state.cards[cid].mana_cost for cid in ids] == ['{G}'] * 6
        observed.append(ids)
        return delegate(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(search, 'resolve_effect', capture)
        search.test_topdeck_put_may_choose_zero_and_rejects_more_than_limit()
    assert len(observed) == 1


def test_negative_explicit_choice_has_a_real_wrong_type_target(monkeypatch):
    hints_delegate, validate_delegate = search.build_cast_hints, search.validate_cast_choice
    states, observed = [], []

    def hints(state, *args, **kwargs):
        states.append(state)
        return hints_delegate(state, *args, **kwargs)

    def validate(hints, choice, *args, **kwargs):
        assert len(states) == 1
        ids = choice['search_card_ids']
        _facts(states[0], ids, ['Llanowar Elves'], zone=Zone.LIBRARY)
        observed.append(list(ids))
        return validate_delegate(hints, choice, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(search, 'build_cast_hints', hints)
        patch.setattr(search, 'validate_cast_choice', validate)
        search.test_library_search_rejects_nonmatching_explicit_selection()
    assert len(observed) == 1


def test_cultivate_split_actual_land_inputs_retain_printed_type_lines(monkeypatch):
    delegate = search.resolve_effect
    observed = []

    def capture(state, *args, **kwargs):
        ids = list(state.players[1].library[-2:])
        _facts(state, ids, ['Plains', 'Island'], zone=Zone.LIBRARY)
        observed.append(ids)
        return delegate(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(search, 'resolve_effect', capture)
        search.test_cultivate_human_choice_orders_battlefield_then_hand()
    assert len(observed) == 1


@pytest.mark.parametrize('test_name,source_id,expected_count', (
    ('test_company_bottom_order_keeps_spell_unresolved_until_second_choice', 'company-stack', 2),
    ('test_topdeck_put_uses_resolution_library_and_resumes_stack_after_snapshot', 'topdeck-spell', 5),
))
def test_actual_stack_resolution_has_complete_elf_facts(monkeypatch, test_name, source_id, expected_count):
    stack = importlib.import_module('rules_engine.stack_engine')
    delegate = stack.resolve_top_of_stack
    observed = []

    def capture(state, *args, **kwargs):
        if state.stack and state.stack[-1].source_card_id == source_id:
            ids = [cid for cid, card in state.cards.items() if card.name == 'Llanowar Elves']
            assert len(ids) == expected_count
            _facts(state, ids, ['Llanowar Elves'] * expected_count, zone=Zone.LIBRARY)
            observed.append(ids)
        return delegate(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(stack, 'resolve_top_of_stack', capture)
        getattr(search, test_name)()
    assert len(observed) == 1


def test_recruitment_real_mana_sources_have_complete_plains_facts(monkeypatch):
    original = importlib.import_module('tests.test_topdeck_reveal_creature')
    delegate = original.RulesEngine.legal_moves
    observed = []

    def capture(engine, state, *args, **kwargs):
        ids = [cid for cid in state.players[1].battlefield if state.cards[cid].name == 'Plains']
        assert len(ids) == 4
        _facts(state, ids, ['Plains'] * 4, zone=Zone.BATTLEFIELD)
        observed.append(ids)
        return delegate(engine, state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(original.RulesEngine, 'legal_moves', capture)
        original.test_human_recruitment_officer_choice_resumes_activated_stack_after_snapshot()
    assert observed
