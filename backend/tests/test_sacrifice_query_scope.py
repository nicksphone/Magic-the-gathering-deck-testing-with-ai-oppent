"""Immutable eligibility batches; canonical facts and explicit transition seams."""
import hashlib
import json
from pathlib import Path
import pickle
import random
from unittest.mock import patch

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine import basic_land_layer, costs
from rules_engine.keyword_effects import add_keyword_effect
from rules_engine.query_context import query_cache, rule_query_scope
from rules_engine.type_effects import add_type_effect, clear_type_effects
from tests.test_attachment_check_preflight import add, board
from tests.test_linked_damage_targets import raw_card


def facts(state):
    return pickle.dumps(state, protocol=5), random.getstate()


def eligibility(state, seat, kind='creature', **kwargs):
    before = facts(state)
    result = costs._eligible_sacrifice_ids(state, seat, kind, **kwargs)
    assert facts(state) == before
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 16, 31])
@pytest.mark.parametrize('kind', ['creature', 'permanent'])
def test_eligibility_classifies_one_immutable_battlefield_batch(seat, count, kind):
    state = board(seat, count)
    expected = [cid for cid in state.players[seat].battlefield
                if kind == 'permanent' or state.cards[cid].name == 'Grizzly Bears']
    function = basic_land_layer._printed_layer_four_effect
    with patch.object(basic_land_layer, '_printed_layer_four_effect', wraps=function) as calls:
        assert eligibility(state, seat, kind) == expected
    assert calls.call_count <= count, 'Eligibility repeated a full battlefield scan per permanent'
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_later_zone_and_controller_transitions_change_eligibility(seat):
    state = board(seat)
    first = add(state, 'Grizzly Bears', seat)
    second = add(state, 'Grizzly Bears', seat)
    assert eligibility(state, seat) == [first.id, second.id]
    # Explicit transition seams, not paid sacrifice/control-change episodes.
    state.players[seat].battlefield.remove(first.id)
    first.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(first.id)
    assert eligibility(state, seat) == [second.id]
    second.controller = 3-seat
    assert eligibility(state, seat) == []
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_native_type_effects_are_visible_on_the_next_call(seat):
    state = board(seat)
    land = add(state, 'Forest', seat)
    assert eligibility(state, seat) == []
    # Native layer-four bookkeeping seam; no invented Oracle instruction.
    add_type_effect(state, land.id, ['Creature'], until_end_of_turn=True)
    assert eligibility(state, seat) == [land.id]
    clear_type_effects(land)
    assert eligibility(state, seat) == []
    assert query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['subtype_bear', 'green_creature'])
def test_full_canonical_subtype_and_color_filters_preserve_order(seat, kind):
    state = board(seat)
    first = add(state, 'Grizzly Bears', seat)
    add(state, 'Forest', seat)
    second = add(state, 'Grizzly Bears', seat)
    add(state, 'Grizzly Bears', 3-seat)
    assert eligibility(state, seat, kind) == [first.id, second.id]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('payment_kind', ['spell', 'activation', 'mana'])
def test_canonical_prohibition_keeps_payment_context_and_refreshes(seat, payment_kind):
    state = board(seat)
    bear = add(state, 'Grizzly Bears', seat)
    path = Path(__file__).parent / 'fixtures/contextual_cost_prohibitions/angel-of-jubilation.json'
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == '9b026a3075748b636d564af1add54d02ee4a1db217b339202d1ac28e2566f043'
    raw = json.loads(content)
    assert raw['name'] == 'Angel of Jubilation' and raw['id'] and raw['oracle_id']
    angel = raw_card(state, raw, 3-seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, angel.id)
    expected = [bear.id] if payment_kind == 'mana' else []
    assert eligibility(state, seat, payment_kind=payment_kind) == expected
    # Actual native ability-loss bookkeeping; printed Oracle data is untouched.
    printed = angel.oracle_text
    add_keyword_effect(state, angel.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    assert eligibility(state, seat, payment_kind=payment_kind) == [bear.id]
    assert angel.oracle_text == printed and query_cache(state) is None


def test_returned_list_does_not_become_a_shared_cache_result():
    state = board(1)
    bear = add(state, 'Grizzly Bears', 1)
    result = eligibility(state, 1)
    result.clear()
    assert eligibility(state, 1) == [bear.id]


def test_matching_outer_query_scope_is_retained():
    state = board(1)
    bear = add(state, 'Grizzly Bears', 1)
    with rule_query_scope(state):
        outer = query_cache(state)
        marker = object()
        outer[marker] = True
        assert eligibility(state, 1) == [bear.id]
        assert query_cache(state) is outer and outer[marker] is True
    assert query_cache(state) is None


def test_query_error_restores_the_callers_context_without_mutation():
    state = board(1)
    add(state, 'Grizzly Bears', 1)
    before = facts(state)
    with patch.object(costs, 'effective_types', side_effect=ValueError('Injected classification failure')):
        with pytest.raises(ValueError, match='Injected classification failure'):
            costs._eligible_sacrifice_ids(state, 1)
    assert facts(state) == before and query_cache(state) is None
