"""Suppression reuse is limited to immutable queries and explicit argument values."""
from copy import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone
from rules_engine import continuous
from rules_engine.land_types import printed_land_abilities_lost
from rules_engine.query_context import rule_query_scope, query_cache
from tests.test_ability_suppression import add
from tests.test_ai_recurring_engines import fixture


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_repeated_scalar_queries_reuse_and_refresh_after_departure(seat, explicit):
    state = fixture()
    elf = add(state, 'Llanowar Elves', seat)
    source = add(state, 'Humility', 3-seat)
    losses = continuous._printed_ability_loss_sources(state)
    with patch('rules_engine.land_types.printed_land_abilities_lost', wraps=printed_land_abilities_lost) as query:
        with rule_query_scope(state):
            for _ in range(3):
                kwargs = {'losses': list(losses)} if explicit else {}
                assert continuous.printed_abilities_suppressed(state, elf.id, **kwargs)
            assert query.call_count == 1
    assert query_cache(state) is None
    resolve_effect(state, 3-seat, 'destroy_permanent', {'target_card_id': source.id})
    assert not continuous.printed_abilities_suppressed(state, elf.id)


def test_explicit_loss_values_are_not_cached_by_list_identity():
    state = fixture()
    elf = add(state, 'Llanowar Elves')
    add(state, 'Humility', 2)
    losses = []
    with rule_query_scope(state):
        assert not continuous.printed_abilities_suppressed(state, elf.id, losses=losses)
        losses.extend(continuous._printed_ability_loss_sources(state))
        assert continuous.printed_abilities_suppressed(state, elf.id, losses=losses)
        # Only the controller used by the argument changes; state stays immutable.
        source, _, other_only, subject = losses[0]
        proxy = copy(source)
        qualified = [(proxy, 'you control', other_only, subject)]
        assert not continuous.printed_abilities_suppressed(state, elf.id, losses=qualified)
        proxy.controller = elf.controller
        assert continuous.printed_abilities_suppressed(state, elf.id, losses=qualified)


@pytest.mark.parametrize('seat', [1, 2])
def test_land_type_inclusion_is_part_of_the_query_key(seat):
    from tests.test_land_type_layers import add as add_land
    state = fixture()
    land = add_land(state, 'Hallowed Fountain', seat)
    add_land(state, 'Blood Moon', 3-seat)
    with rule_query_scope(state):
        assert not continuous.printed_abilities_suppressed(state, land.id, losses=[], include_land_types=False)
        assert continuous.printed_abilities_suppressed(state, land.id, losses=[], include_land_types=True)
        assert not continuous.printed_abilities_suppressed(state, land.id, losses=[], include_land_types=False)


def test_nonbattlefield_queries_and_other_state_scopes_do_not_reuse():
    state = fixture()
    elf = add(state, 'Llanowar Elves')
    with rule_query_scope(state):
        assert not continuous.printed_abilities_suppressed(state, elf.id)
    state.players[1].battlefield.remove(elf.id)
    state.players[1].graveyard.append(elf.id)
    elf.move_to_zone(Zone.GRAVEYARD)
    with rule_query_scope(state), patch.object(continuous, '_printed_suppression_result',
                                             side_effect=AssertionError('irrelevant query')):
        assert not continuous.printed_abilities_suppressed(state, elf.id)


def test_loss_iterators_keep_original_lazy_consumption():
    state = fixture()
    elf = add(state, 'Llanowar Elves')
    add(state, 'Humility', 2)
    losses = continuous._printed_ability_loss_sources(state)
    iterator = iter(losses + losses)
    with rule_query_scope(state):
        assert continuous.printed_abilities_suppressed(state, elf.id, losses=iterator)
        assert next(iterator) == losses[0]


@pytest.mark.parametrize('subject,expected', [
    ('elves', True), ('creatures', True), ('green creatures', True),
    ('nonblue creatures', True), ('artifacts', False), ('permanents', True),
    ('creature tokens', False),
])
def test_subject_queries_reuse_exact_qualifiers_only(subject, expected):
    state = fixture()
    elf = add(state, 'Llanowar Elves')
    original = continuous._subject_match_result
    with patch.object(continuous, '_subject_match_result', wraps=original) as query:
        with rule_query_scope(state):
            for _ in range(3):
                assert continuous._subject_matches(state, elf.id, subject) is expected
            assert query.call_count == 1
    state.players[1].battlefield.remove(elf.id)
    state.players[1].exile.append(elf.id)
    elf.move_to_zone(Zone.EXILE)
    assert not continuous._subject_matches(state, elf.id, 'permanents')


def test_global_loss_records_do_not_require_unused_source_identity():
    state = fixture()
    elf = add(state, 'Llanowar Elves')
    loss = (SimpleNamespace(controller=2), 'all', False, 'creatures')
    with rule_query_scope(state):
        assert continuous.printed_abilities_suppressed(state, elf.id, losses=[loss])
