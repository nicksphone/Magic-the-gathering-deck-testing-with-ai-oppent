"""Canonical compleated cards and counter bans; entry records are core packets."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.counter_placement import put_counters
from rules_engine.engine import RulesEngine
from rules_engine.move_generator import legal_moves
from tests.test_ai_recurring_engines import add as add_card
from tests.test_counter_prohibitions import source as permanent
from tests.test_counter_replacements import source as modifier, choose
from tests.test_restricted_mana import clean
from tests.test_spell_entry_counters import spell

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/compleated_entry.json').read_text())}


def walker(state, name, player=1):
    card = add_card(state, name, player, cards=ROWS)
    card.loyalty = int(ROWS[name]['loyalty'])
    return card


@pytest.mark.parametrize('name,paid,reduced_first,doubled_first', [
    ('Tamiyo, Compleated Sage', 1, 6, 8),
    ('Nissa, Ascended Animist', 1, 10, 12),
    ('Nissa, Ascended Animist', 2, 6, 10),
])
@pytest.mark.parametrize('first', ['subtract', 'double'])
def test_affected_controller_orders_compleated_against_doubling_across_snapshot(
        name, paid, reduced_first, doubled_first, first):
    state = clean(2)
    card = walker(state, name, 2)
    modifier(state, 'Doubling Season', 2)
    spell(state, card, __phyrexian_life_symbols=paid)
    assert card.zone == Zone.STACK and card.id not in state.players[2].battlefield
    assert state.pending_replacement_choice['player_id'] == 2
    assert sorted(o['operation'] for o in state.pending_replacement_choice['options']) == ['double', 'subtract']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choose(state, first, 1)
    assert serialize_match_snapshot(state) == before
    state = deserialize_match_snapshot(before)
    state = choose(state, first, 2)
    assert state.cards[card.id].loyalty == (reduced_first if first == 'subtract' else doubled_first)
    assert state.players[2].battlefield.count(card.id) == 1
    assert sum(line == f'{name} resolves.' for line in state.log) == 1
    assert sum(line.startswith(f'{name} replaces') for line in state.log) == 1


@pytest.mark.parametrize('name', list(ROWS))
def test_colored_payment_does_not_offer_compleated_reduction(name):
    state = clean()
    card = walker(state, name)
    modifier(state, 'Doubling Season')
    spell(state, card, __phyrexian_life_symbols=0)
    assert not state.pending_replacement_choice
    assert card.loyalty == 2*int(ROWS[name]['loyalty'])


@pytest.mark.parametrize('name,paid,expected', [
    ('Tamiyo, Compleated Sage', 1, 8), ('Nissa, Ascended Animist', 2, 10),
])
def test_ai_chooses_higher_loyalty_without_card_name_policy(name, paid, expected):
    state = clean(2)
    card = walker(state, name, 2)
    modifier(state, 'Doubling Season', 2)
    spell(state, card, __phyrexian_life_symbols=paid)
    action = AIAgent('master').choose_action(state, legal_moves(state, 2), 2).action
    selected = next(o for o in state.pending_replacement_choice['options']
                    if o['source_id'] == action['replacement_source_id'])
    assert selected['operation'] == 'double'
    state = checked_action(state, RulesEngine(), 2, action)
    assert state.cards[card.id].loyalty == expected


def test_multiple_doublers_and_reduction_resume_and_apply_each_once():
    state = clean(2)
    card = walker(state, 'Nissa, Ascended Animist', 2)
    modifier(state, 'Doubling Season', 2)
    modifier(state, 'Vorinclex, Monstrous Raider', 2)
    spell(state, card, __phyrexian_life_symbols=2)
    while state.pending_replacement_choice:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        action = AIAgent('master').choose_action(state, legal_moves(state, 2), 2).action
        state = checked_action(state, RulesEngine(), 2, action)
    assert state.cards[card.id].loyalty == 24
    assert sum('replaces' in line for line in state.log) == 3


@pytest.mark.parametrize('incoming', [True, False])
def test_incoming_global_counter_ban_is_not_retroactive_to_prepared_entry(incoming):
    state = clean()
    if incoming:
        card = permanent(state, 'Melira, Sylvok Outcast')
    else:
        from tests.test_ward_resolution import add
        card = add(state, 'Grizzly Bears')
        permanent(state, 'Melira, Sylvok Outcast')
    state.pending_entry_counters = [{'controller': 1, 'counter': '-1/-1', 'amount': 1,
                                    'expires_turn': state.turn}]
    spell(state, card)
    assert card.zone == Zone.BATTLEFIELD
    assert card.counters.get('-1/-1', 0) == (1 if incoming else 0)
    assert not state.pending_entry_counters
    before = card.counters.copy()
    assert put_counters(state, '-1/-1', 1, target_card_id=card.id) == 0
    assert card.counters == before


def test_entry_reduction_does_not_leak_into_ordinary_loyalty_effects():
    from effects.handlers import add_counters
    state = clean()
    card = walker(state, 'Tamiyo, Compleated Sage')
    spell(state, card, __phyrexian_life_symbols=1)
    assert card.loyalty == 3
    add_counters(state, 1, {'target_card_id': card.id, 'counter': 'loyalty', 'amount': 2})
    assert card.loyalty == 5
