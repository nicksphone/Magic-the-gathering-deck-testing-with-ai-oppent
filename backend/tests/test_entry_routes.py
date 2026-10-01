"""Canonical cards plus explicitly labeled core entry/effect-sequence packets."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import StackItem, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_ai_recurring_engines import add as add_card
from tests.test_counter_prohibitions import source as permanent, ROWS as PERMANENTS
from tests.test_counter_replacements import source as modifier, choose
from tests.test_entry_replacement_order import ROWS as WALKERS
from tests.test_restricted_mana import clean
from tests.test_saga_counter_events import saga
from tests.test_spell_entry_counters import ROWS as SPELLS

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/entry_routes.json').read_text())}


def grave(state, card):
    state.players[card.controller].battlefield.remove(card.id)
    state.players[card.owner].graveyard.append(card.id)
    card.move_to_zone(Zone.GRAVEYARD)
    return card


def core_stack(state, key, payload, controller=1):
    # An explicit operation packet, not Oracle text assigned to an invented card.
    state.stack.append(StackItem(id=state.allocate_object_id(), source_card_id='core-entry-packet',
                                 controller=controller, label='Core entry packet',
                                 effect_key=key, payload=payload))


@pytest.mark.parametrize('first,expected', [('add', 10), ('double', 9)])
def test_returned_planeswalker_prepares_loyalty_off_graveyard_before_commit(first, expected):
    state = clean(2)
    card = grave(state, permanent(state, "Elspeth, Sun's Champion"))
    modifier(state, 'Doubling Season', 2)
    modifier(state, "Lae'zel, Vlaakith's Champion", 2)
    resolve_effect(state, 2, 'return_permanent_from_graveyard_to_battlefield', {'target_card_id': card.id})
    assert card.zone == Zone.GRAVEYARD and card.id in state.players[1].graveyard
    assert state.pending_replacement_choice['player_id'] == 2
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, first, 2)
    assert state.cards[card.id].controller == 2 and state.cards[card.id].owner == 1
    assert state.cards[card.id].loyalty == expected
    assert card.id not in state.players[1].graveyard
    assert state.players[2].battlefield.count(card.id) == 1


def test_returned_saga_gets_new_intrinsic_lore_and_crossed_chapters():
    state = clean()
    card = saga(state)
    card.counters['__lore'] = 4
    grave(state, card)
    modifier(state, 'Doubling Season')
    resolve_effect(state, 1, 'return_permanent_from_graveyard_to_battlefield', {'target_card_id': card.id})
    assert card.counters['__lore'] == 2
    assert sorted(item.payload['__chapter_number'] for item in state.stack) == [1, 2]


def test_returned_read_ahead_choice_belongs_to_new_controller_and_survives_snapshot():
    state = clean(2)
    card = grave(state, add_card(state, 'The Phasing of Zhalfir', cards=SPELLS))
    resolve_effect(state, 2, 'return_permanent_from_graveyard_to_battlefield', {'target_card_id': card.id})
    assert state.pending_mechanic_choice['player_id'] == 2
    assert card.zone == Zone.GRAVEYARD
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 2, {'type': 'choose_mechanic', 'choice_id': '2'})
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].counters['__lore'] == 2
    assert [item.payload['__chapter_number'] for item in state.stack] == [2]


def test_creature_return_emits_own_entry_trigger_and_does_not_consume_cast_record():
    state = clean(2)
    card = grave(state, add_card(state, 'Elvish Visionary', cards=ROWS))
    state.pending_entry_counters = [{'controller': 2, 'amount': 1, 'expires_turn': state.turn}]
    resolve_effect(state, 2, 'return_creature_from_graveyard_to_battlefield', {'target_card_id': card.id})
    assert card.controller == 2 and not card.counters and state.pending_entry_counters
    assert len(state.stack) == 1 and state.stack[0].controller == 2
    before = len(state.players[2].hand)
    resolve_top_of_stack(state)
    assert len(state.players[2].hand) == before+1


def test_incubate_batch_stays_uncreated_until_every_counter_choice_finishes():
    state = clean(2)
    modifier(state, 'Doubling Season', 2)
    modifier(state, 'Winding Constrictor', 2)
    ids_before = set(state.cards)
    resolve_effect(state, 2, 'incubate', {'counters': 3, 'times': 2})
    assert set(state.cards) == ids_before
    choices = 0
    while state.pending_replacement_choice:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        assert set(state.cards) == ids_before
        state = choose(state, 'add', 2)
        choices += 1
    assert choices == 4  # creation doubling and each recipient's independent counter event
    tokens = [state.cards[cid] for cid in state.players[2].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 4 and all(card.counters['+1/+1'] == 8 for card in tokens)
    assert sum('creates 4 Incubator token(s)' in line for line in state.log) == 1


def test_token_counter_ban_and_creation_doubling_are_separate_events():
    state = clean()
    modifier(state, 'Doubling Season')
    permanent(state, 'Solemnity')
    resolve_effect(state, 1, 'incubate', {'counters': 3})
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2 and all(not card.counters for card in tokens)


@pytest.mark.parametrize('name,expected', [("Elspeth, Sun's Champion", 8), ('Tamiyo, Compleated Sage', 10)])
def test_permanent_spell_copy_enters_with_loyalty_but_was_not_cast(name, expected):
    state = clean()
    modifier(state, 'Doubling Season')
    raw = (WALKERS if name in WALKERS else PERMANENTS)[name]
    core_stack(state, 'noop', {'__stack_copy_kind': 'spell', '__phyrexian_life_symbols': 1,
                             '__copied_card': {**raw, 'types': ['Planeswalker'], 'loyalty': int(raw['loyalty'])}})
    assert resolve_top_of_stack(state)
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 1 and tokens[0].loyalty == expected
    assert sum(line == 'Core entry packet resolves.' for line in state.log) == 1


def test_copied_x_permanent_preserves_announced_x_without_doubling_token_creation():
    state = clean()
    modifier(state, 'Doubling Season')
    core_stack(state, 'noop', {'__stack_copy_kind': 'spell', 'x_value': 2,
                             '__copied_card': {**SPELLS['Walking Ballista'], 'types': ['Artifact', 'Creature'],
                                               'power': 0, 'toughness': 0}})
    resolve_top_of_stack(state)
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 1 and effective_combat_stats(state, tokens[0].id) == (4, 4)


def test_gift_token_entry_choices_resume_later_effect_for_original_caster():
    state = clean()
    modifier(state, 'Doubling Season', 2)
    modifier(state, 'Winding Constrictor', 2)
    core_stack(state, 'effect_sequence', {'effects': [
        {'effect_key': 'create_token', 'payload': {'controller': 2, 'name': 'Phyrexian',
                                                'power': 0, 'toughness': 0, 'counters': {'+1/+1': 1}}},
        {'effect_key': 'gain_life', 'payload': {'amount': 5}},
    ]})
    assert not resolve_top_of_stack(state)
    assert state.trigger_staging and state.players[1].life == 20
    while state.pending_replacement_choice:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        state = choose(state, 'add', 2)
    assert state.players[1].life == 25 and state.players[2].life == 20
    assert not state.trigger_staging
    assert sum(line == 'Core entry packet resolves.' for line in state.log) == 1


def test_stack_resolution_finishes_later_buff_before_sba_and_publishes_entry_triggers():
    state = clean()
    add_card(state, 'Soul Warden', cards=ROWS)
    core_stack(state, 'effect_sequence', {'effects': [
        {'effect_key': 'create_token', 'payload': {'name': 'Phyrexian', 'power': 0, 'toughness': 0}},
        {'effect_key': 'temporary_pt_buff_all', 'payload': {'power': 1, 'toughness': 1}},
    ]})
    resolve_top_of_stack(state)
    token = next(state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token)
    assert effective_combat_stats(state, token.id) == (1, 1)
    assert not state.trigger_staging and len(state.stack) == 1
    assert state.stack[0].effect_key == 'gain_life'


@pytest.mark.parametrize('controller', [1, 2])
def test_creation_doublers_are_controller_scoped_and_compound_once(controller):
    state = clean()
    modifier(state, 'Doubling Season', controller)
    modifier(state, 'Primal Vigor', 2)
    resolve_effect(state, 1, 'create_token', {'name': 'Elf', 'power': 1, 'toughness': 1})
    assert sum(state.cards[cid].is_token for cid in state.players[1].battlefield) == (4 if controller == 1 else 2)


@pytest.mark.parametrize('route', ['search_library', 'topdeck_put_permanents_battlefield'])
def test_library_entry_uses_intrinsic_saga_lore_and_preserves_selection(route):
    state = clean()
    card = saga(state)
    state.players[1].battlefield.remove(card.id)
    card.move_to_zone(Zone.LIBRARY)
    state.players[1].library.append(card.id)
    payload = {'selected_card_ids': [card.id], 'contains': 'card', 'count': 1,
               'destination': 'battlefield', 'top_n': 1, 'max_permanents': 1}
    resolve_effect(state, 1, route, payload)
    assert card.zone == Zone.BATTLEFIELD and card.id not in state.players[1].library
    assert card.counters['__lore'] == 1
    assert len(state.stack) == 1 and state.stack[0].payload['__chapter_number'] == 1


@pytest.mark.parametrize('route', ['search_library', 'topdeck_put_creatures_battlefield'])
def test_noncast_library_entry_does_not_inherit_source_spells_x(route):
    state = clean()
    card = add_card(state, 'Walking Ballista', cards=SPELLS)
    state.players[1].battlefield.remove(card.id)
    card.move_to_zone(Zone.LIBRARY)
    state.players[1].library.append(card.id)
    resolve_effect(state, 1, route, {'selected_card_ids': [card.id], 'contains': 'card', 'count': 1,
                                    'destination': 'battlefield', 'top_n': 1, 'x_value': 5})
    assert card.counters.get('+1/+1', 0) == 0
