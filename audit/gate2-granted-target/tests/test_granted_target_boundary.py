"""Compiler/layer synthetic boundary controls, NOT canonical paid path certification."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.continuous import effective_granted_target_abilities as query
from rules_engine.granted_target_triggers import compile_granted_target_clauses as compile_raw
from rules_engine.keyword_effects import add_keyword_effect as grant_keywords
from tests.test_ai_recurring_engines import fixture, add

FACTS = json.loads((Path(__file__).resolve().parents[1] / 'nadu-facts.json').read_text())
RAW = FACTS['Nadu, Winged Wisdom']['oracle_text']


@pytest.mark.parametrize('limit', ['once', 'twice', 'three times', '7 times'])
def test_complete_generic_limit_compilation(limit):
    clauses, gaps = compile_raw(RAW.replace('twice', limit), 'Renamed Source')
    assert not gaps and len(clauses) == 1
    assert clauses[0][-1] == ('Land', 'battlefield', 'hand')
    assert clauses[0][-2] == {'once': 1, 'twice': 2, 'three times': 3, '7 times': 7}[limit]


@pytest.mark.parametrize('body', [
    RAW + '\nUnknown tail.', RAW + ' Unknown tail.',
    RAW.replace('twice each turn.', 'twice each turn. Unknown tail.'),
    RAW.replace('reveal the top card', 'invent the top card'),
    RAW.replace('twice each turn.', 'zero times each turn.'),
    RAW.replace('twice each turn.', '0 times each turn.'),
    RAW.replace('spell or ability', 'unknown event'),
    RAW.replace('your hand.', 'your hand. (Unknown reminder.)'),
    RAW[:-1], RAW.replace('land card', 'unknown card'),
])
def test_unknown_complete_body_is_diagnostic_not_partial_grant(body):
    clauses, gaps = compile_raw(body)
    assert not clauses and gaps


@pytest.mark.parametrize('condition', ['land', 'creature', 'artifact', 'enchantment', 'planeswalker'])
def test_instruction_has_typed_condition_not_selected_effect_recipe(condition):
    clauses, gaps = compile_raw(RAW.replace('a land card', ('an ' if condition in ('artifact', 'enchantment') else 'a ') + condition + ' card'))
    assert not gaps and clauses[0][-1][0] == condition.title()


def add_raw(state, body, seat, *, creature=False, name='Synthetic Grant Boundary'):
    data = deepcopy(FACTS['Nadu, Winged Wisdom'])
    data.update(name=name, oracle_text=body, type_line='Creature' if creature else 'Enchantment')
    card = add(state, name, seat, cards={name: data})
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['recipient_loss_then_later_grant', 'grant_then_recipient_loss',
                                'source_dependency', 'independent_instances', 'scope_and_snapshot',
                                'cant_override', 'source_departure'])
def test_layer_boundary_receipts_are_pure_and_independently_identified(seat, case):
    state = fixture()
    target = add_raw(state, '', seat, creature=True, name='Synthetic Recipient')
    if case == 'recipient_loss_then_later_grant':
        grant_keywords(state, target.id, ['all abilities'], operation='remove')
        add_raw(state, RAW, seat)
        expected = 1
    elif case == 'grant_then_recipient_loss':
        add_raw(state, RAW, seat)
        grant_keywords(state, target.id, ['all abilities'], operation='remove')
        expected = 0
    elif case == 'source_dependency':
        add_raw(state, 'All creatures lose all abilities.', 3-seat)
        add_raw(state, RAW, seat, creature=True)
        expected = 0
    elif case == 'independent_instances':
        add_raw(state, RAW, seat, name='Synthetic Grant A')
        add_raw(state, RAW, seat, name='Synthetic Grant B')
        expected = 2
    elif case == 'scope_and_snapshot':
        add_raw(state, RAW, 3-seat)
        add_raw(state, RAW.replace('you control', 'your opponents control'), 3-seat)
        expected = 1
    elif case == 'cant_override':
        add_raw(state, 'Creatures you control cannot have all abilities.', seat)
        add_raw(state, RAW, seat)
        expected = 0
    else:
        source = add_raw(state, RAW, seat)
        assert len(query(state, target.id)) == 1
        state.players[seat].battlefield.remove(source.id)
        source.move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(source.id)
        expected = 0
    before = serialize_match_snapshot(state)
    receipts = query(state, target.id)
    assert len(receipts) == expected and serialize_match_snapshot(state) == before
    assert not state.trigger_once_seen_this_turn
    assert all(r['recipient_id'] == target.id and r['controller'] == seat for r in receipts)
    assert len({(r['grant_source_id'], r['grant_source_incarnation'], r['clause_index']) for r in receipts}) == expected
    restored = deserialize_match_snapshot(before)
    assert query(restored, target.id) == receipts
