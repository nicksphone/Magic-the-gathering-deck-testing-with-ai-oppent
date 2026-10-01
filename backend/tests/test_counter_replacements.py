"""Canonical replacement clauses and explicitly labeled core-effect fixtures."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.handlers import add_counters, add_counters_each_creature, add_player_counters
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.counter_replacements import counter_modifier, counter_options
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.move_generator import legal_moves
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_ai_recurring_engines import add as add_card
from tests.test_counter_prohibitions import source as ban
from tests.test_player_counters import source as experience_source
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add


ROWS = {r['name']: r for r in json.loads((Path(__file__).parent / 'fixtures/counter_replacements.json').read_text())}
for row in ROWS.values():
    for key in ('power', 'toughness', 'colors', 'keywords'):
        row.setdefault(key, None)


def source(state, name, player=1):
    card = add_card(state, name, player, cards=ROWS)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def choose(state, operation, player=None):
    pending = state.pending_replacement_choice
    option = next(o for o in pending['options'] if o['operation'] == operation)
    return checked_action(state, RulesEngine(), player or pending['player_id'],
                          {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})


@pytest.mark.parametrize('player', [1, 2])
def test_vorinclex_depends_on_placer_not_player_recipient(player):
    state = clean()
    source(state, 'Vorinclex, Monstrous Raider', player)
    add_player_counters(state, player, {'target_player': 3-player, 'counter': 'poison', 'amount': 3})
    assert state.players[3-player].poison == 6
    add_player_counters(state, 3-player, {'target_player': player, 'counter': 'energy', 'amount': 3})
    assert state.players[player].counters['energy'] == 1


@pytest.mark.parametrize('name', ['Doubling Season', 'Corpsejack Menace', 'Branching Evolution', 'Primal Vigor'])
def test_printed_permanent_doublers(name):
    state = clean()
    source(state, name)
    bear = add(state, 'Grizzly Bears')
    add_counters(state, 2, {'target_card_id': bear.id, 'amount': 3})
    assert bear.counters['+1/+1'] == 6
    add_player_counters(state, 1, {'counter': 'experience', 'amount': 3})
    assert state.players[1].counters['experience'] == 3


@pytest.mark.parametrize('name', ['Hardened Scales', 'Kami of Whispered Hopes'])
def test_plus_counter_adders_do_not_modify_other_kinds(name):
    state = clean()
    source(state, name)
    bear = add(state, 'Grizzly Bears')
    add_counters(state, 1, {'target_card_id': bear.id, 'amount': 2})
    add_counters(state, 1, {'target_card_id': bear.id, 'counter': '-1/-1', 'amount': 2})
    assert bear.counters == {'+1/+1': 3, '-1/-1': 2}


def test_winding_and_laezel_distinguish_recipient_and_placer():
    state = clean()
    source(state, 'Winding Constrictor')
    add_player_counters(state, 2, {'target_player': 1, 'counter': 'poison', 'amount': 1})
    assert state.players[1].poison == 2
    state = clean()
    source(state, "Lae'zel, Vlaakith's Champion")
    add_player_counters(state, 2, {'target_player': 1, 'counter': 'poison', 'amount': 1})
    assert state.players[1].poison == 1
    add_player_counters(state, 1, {'target_player': 1, 'counter': 'energy', 'amount': 1})
    assert state.players[1].counters['energy'] == 2


@pytest.mark.parametrize('first, expected', [('add', 4), ('double', 3)])
def test_choice_order_changes_result_and_each_ability_applies_once(first, expected):
    state = clean()
    source(state, 'Winding Constrictor')
    source(state, 'Vorinclex, Monstrous Raider')
    add_player_counters(state, 1, {'counter': 'experience', 'amount': 1})
    assert state.players[1].counters == {} and state.pending_replacement_choice
    state = choose(state, first)
    assert state.players[1].counters['experience'] == expected
    assert not state.pending_replacement_choice


@pytest.mark.parametrize('first, expected', [('half', 0), ('add', 1)])
def test_halving_to_zero_stops_remaining_additions(first, expected):
    state = clean()
    source(state, 'Winding Constrictor')
    source(state, 'Vorinclex, Monstrous Raider', 2)
    add_player_counters(state, 1, {'counter': 'energy', 'amount': 1})
    state = choose(state, first)
    assert state.players[1].counters.get('energy', 0) == expected
    assert not state.pending_replacement_choice


def test_cant_override_suppresses_all_replacements_and_choices():
    state = clean()
    source(state, 'Winding Constrictor')
    source(state, 'Vorinclex, Monstrous Raider')
    ban(state, 'Solemnity')
    add_player_counters(state, 1, {'counter': 'energy', 'amount': 2})
    assert not state.pending_replacement_choice and not state.players[1].counters


def test_affected_permanent_controller_chooses_not_placer():
    state = clean()
    source(state, 'Doubling Season', 2)
    source(state, 'Hardened Scales', 2)
    bear = add(state, 'Grizzly Bears', 2)
    add_counters(state, 1, {'target_card_id': bear.id})
    assert state.pending_replacement_choice['player_id'] == 2
    with pytest.raises(ActionRejected):
        choose(state, 'double', 1)
    state = choose(state, 'add', 2)
    assert state.cards[bear.id].counters['+1/+1'] == 4


def test_snapshot_resumes_real_experience_trigger_exactly_once():
    state = clean()
    experience_source(state, 'Minthara, Merciless Soul')
    source(state, 'Winding Constrictor')
    source(state, 'Vorinclex, Monstrous Raider')
    state.players_with_permanent_departure.add(1)
    emit_event(state, 'begin_step', {'step': 'end_step', 'active_player': 1})
    assert len(state.stack) == 1
    assert not resolve_top_of_stack(state)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'add')
    assert state.players[1].counters['experience'] == 4 and not state.stack
    assert not state.pending_replacement_choice


def test_effect_sequence_waits_for_choice_and_continues_once():
    state = clean()
    source(state, 'Winding Constrictor')
    source(state, 'Vorinclex, Monstrous Raider')
    # Core-operation fixture, not an invented card or ability.
    resolve_effect(state, 1, 'effect_sequence', {'effects': [
        {'effect_key': 'add_player_counters', 'payload': {'counter': 'energy', 'amount': 1}},
        {'effect_key': 'gain_life', 'payload': {'amount': 5}},
    ]})
    assert state.players[1].life == 20
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'add')
    assert state.players[1].life == 25 and state.players[1].counters['energy'] == 4


def test_multiple_creature_counter_effects_resume_without_skipping_or_repeating():
    state = clean()
    source(state, 'Doubling Season')
    source(state, 'Hardened Scales')
    bears = [add(state, 'Grizzly Bears') for _ in range(2)]
    add_counters_each_creature(state, 1, {'amount': 1})
    for _ in bears:
        state = choose(state, 'add')
    assert not state.pending_replacement_choice
    assert all(state.cards[card.id].counters['+1/+1'] == 4 for card in bears)


@pytest.mark.parametrize('kind, first, expected', [('poison', 'half', 0), ('energy', 'add', 1)])
def test_shared_ai_optimizes_result_without_mutating_live_state(kind, first, expected):
    state = clean()
    source(state, 'Winding Constrictor')
    source(state, 'Vorinclex, Monstrous Raider', 2)
    add_player_counters(state, 1, {'counter': kind, 'amount': 1})
    before = serialize_match_snapshot(state)
    decision = AIAgent('master').choose_action(state, legal_moves(state, 1), 1)
    assert serialize_match_snapshot(state) == before
    option = next(o for o in state.pending_replacement_choice['options'] if o['source_id'] == decision.action['replacement_source_id'])
    assert option['operation'] == first
    state = checked_action(state, RulesEngine(), 1, decision.action)
    assert state.players[1].poison == expected if kind == 'poison' else state.players[1].counters[kind] == expected


@pytest.mark.parametrize('name', list(ROWS))
def test_canonical_clauses_recognized_but_full_route_warnings_retained(name):
    lines = [line for line in ROWS[name]['oracle_text'].splitlines() if 'counter' in line.lower() and line.lower().startswith('if ')]
    assert lines and all(counter_modifier(line) is not None for line in lines)
    assert 'counter replacement route fidelity' in known_unsupported_mechanics(ROWS[name]['oracle_text'])


def test_unknown_or_quoted_clause_is_not_guessed():
    line = ROWS['Hardened Scales']['oracle_text']
    assert counter_modifier('"'+line+'"') is None
    assert counter_modifier(line+' Until end of turn.') is None
    assert 'unsupported counter replacement clause' in known_unsupported_mechanics('If you would get counters, get seven counters instead.')


def test_three_abilities_resume_order_ledger_across_multiple_choices():
    state = clean()
    source(state, 'Doubling Season')
    source(state, 'Branching Evolution')
    source(state, 'Hardened Scales')
    bear = add(state, 'Grizzly Bears')
    add_counters(state, 1, {'target_card_id': bear.id})
    assert len(state.pending_replacement_choice['options']) == 3
    state = choose(state, 'add')
    assert len(state.pending_replacement_choice['options']) == 2
    assert len(state.pending_replacement_choice['counter_payload']['__counter_used']) == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'double')
    assert state.cards[bear.id].counters['+1/+1'] == 8 and not state.pending_replacement_choice


def test_replacement_event_stops_before_land_animation_and_resumes_both_in_order():
    state = clean()
    source(state, 'Doubling Season')
    source(state, 'Vorinclex, Monstrous Raider')
    land = add(state, 'Forest')
    add_counters(state, 1, {'target_card_id': land.id, 'amount': 3, 'animate_land': True})
    assert 'Creature' not in land.types and not land.counters
    state = choose(state, 'double')
    assert 'Creature' in state.cards[land.id].types and state.cards[land.id].counters['+1/+1'] == 12


@pytest.mark.parametrize('name, kind', [('Hardened Scales', '+1/+1'), ('Winding Constrictor', '-1/-1')])
def test_creature_scoped_modifiers_do_not_see_land_before_animation(name, kind):
    state = clean()
    source(state, name)
    land = add(state, 'Forest')
    add_counters(state, 1, {'target_card_id': land.id, 'counter': kind, 'amount': 3, 'animate_land': True})
    assert land.counters[kind] == 3 and 'Creature' in land.types


@pytest.mark.parametrize('name, expected', [('Doubling Season', 2), ('Corpsejack Menace', 2), ('Branching Evolution', 2), ('Primal Vigor', 4)])
def test_global_and_controlled_doublers_differ_for_opponent_creatures(name, expected):
    state = clean()
    source(state, name)
    bear = add(state, 'Grizzly Bears', 2)
    add_counters(state, 1, {'target_card_id': bear.id, 'amount': 2})
    assert bear.counters['+1/+1'] == expected


@pytest.mark.parametrize('recipient, expected', [(1, 3), (2, 2)])
def test_constrictor_modifies_only_controlled_artifacts(recipient, expected):
    state = clean()
    source(state, 'Winding Constrictor')
    ring = add(state, 'Sol Ring', recipient)
    add_counters(state, 2, {'target_card_id': ring.id, 'counter': 'charge', 'amount': 2})
    assert ring.counters['charge'] == expected


def test_kami_modifies_controlled_land_before_animation():
    state = clean()
    source(state, 'Kami of Whispered Hopes')
    land = add(state, 'Forest')
    add_counters(state, 1, {'target_card_id': land.id, 'amount': 2, 'animate_land': True})
    assert land.counters['+1/+1'] == 3 and 'Creature' in land.types


@pytest.mark.parametrize('placer, recipient, expected', [(1, 1, 3), (2, 1, 2), (1, 2, 2)])
def test_laezel_requires_both_placer_and_permanent_scope(placer, recipient, expected):
    state = clean()
    source(state, "Lae'zel, Vlaakith's Champion")
    bear = add(state, 'Grizzly Bears', recipient)
    add_counters(state, placer, {'target_card_id': bear.id, 'amount': 2})
    assert bear.counters['+1/+1'] == expected
