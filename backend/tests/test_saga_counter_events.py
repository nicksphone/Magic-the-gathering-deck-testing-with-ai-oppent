"""Canonical Saga clauses; direct counter resets below are core-event setups."""
import json
from pathlib import Path

import pytest

from effects.handlers import add_counters
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.counter_placement import put_counters
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_saga_chapters
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.state_based_actions import apply_state_based_actions
from tests.test_ai_recurring_engines import add as add_card
from tests.test_counter_prohibitions import source as permanent
from tests.test_counter_replacements import source as modifier, choose
from tests.test_restricted_mana import clean
from tests.test_ward_resolution import add


ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/saga_chapters.json').read_text())}


def saga(state, name='History of Benalia', player=1):
    card = add_card(state, name, player, cards=ROWS)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def order(state, player=1):
    pending = state.pending_trigger_order
    ids = [item['_choice_id'] for item in pending['groups'][str(player)]]
    return checked_action(state, RulesEngine(), player, {
        'type': 'choose_trigger_order', 'trigger_order': ids,
    })


def test_grouped_printed_chapters_expand_to_independent_thresholds():
    chapters = extract_saga_chapters(ROWS['History of Benalia']['oracle_text'])
    assert [chapter['number'] for chapter in chapters] == [1, 2, 3]
    assert chapters[0]['text'] == chapters[1]['text']


@pytest.mark.parametrize('player', [1, 2])
@pytest.mark.parametrize('name,controller,expected', [
    ('Doubling Season', 1, 1), ('Vorinclex, Monstrous Raider', 1, 2),
    ('Vorinclex, Monstrous Raider', 2, 0),
])
def test_turn_based_lore_has_correct_placer_and_effect_provenance(player, name, controller, expected):
    state = clean(player)
    card = saga(state, player=player)
    modifier(state, name, player if controller == 1 else 3-player)
    RulesEngine()._advance_sagas(state)
    assert card.counters.get('__lore', 0) == expected
    assert [item.payload['__chapter_number'] for item in state.stack] == list(range(1, expected+1))
    assert all(item.controller == player for item in state.stack)


def test_another_replacement_enables_effect_only_lore_doubling_and_all_crossed_chapters():
    state = clean()
    card = saga(state)
    modifier(state, 'Doubling Season')
    modifier(state, 'Vorinclex, Monstrous Raider')
    RulesEngine()._advance_sagas(state)
    assert card.counters['__lore'] == 4
    assert sorted(item.payload['__chapter_number'] for item in state.stack) == [1, 2, 3]
    apply_state_based_actions(state)
    assert card.zone == Zone.BATTLEFIELD


def test_registered_lore_effect_triggers_all_crossed_chapters_with_human_order():
    state = clean()
    card = saga(state)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    modifier(state, 'Doubling Season')
    add_counters(state, 1, {'target_card_id': card.id, 'counter': 'lore', 'amount': 2})
    assert card.counters['__lore'] == 4 and state.pending_trigger_order
    apply_state_based_actions(state)
    assert card.zone == Zone.BATTLEFIELD and not state.stack
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = order(state)
    assert len(state.stack) == 3 and state.cards[card.id].zone == Zone.BATTLEFIELD
    while state.stack:
        resolve_top_of_stack(state)
        apply_state_based_actions(state)
        if state.stack:
            assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].zone == Zone.GRAVEYARD


def test_lore_removal_then_regain_can_retrigger_a_threshold():
    state = clean()
    card = saga(state)
    card.counters['__lore'] = 1
    put_counters(state, 'lore', 1, target_card_id=card.id)
    assert [item.payload['__chapter_number'] for item in state.stack] == [2]
    state.stack.clear()
    card.counters['__lore'] = 1  # Core setup: remove the second lore counter.
    put_counters(state, 'lore', 1, target_card_id=card.id)
    assert [item.payload['__chapter_number'] for item in state.stack] == [2]


def test_chapter_target_choice_uses_creature_not_saga_and_survives_snapshot():
    state = clean()
    card = permanent(state, 'The First Iroan Games')
    bear = add(state, 'Grizzly Bears')
    card.counters['__lore'] = 1
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    RulesEngine()._advance_sagas(state)
    assert state.pending_trigger_order['phase'] == 'targets'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    item = state.stack[-1]
    state = checked_action(state, RulesEngine(), 1, {
        'type': 'choose_trigger_target', 'stack_id': item.id, 'target_card_id': bear.id,
    })
    resolve_top_of_stack(state)
    assert state.cards[bear.id].counters['+1/+1'] == 3
    assert '+1/+1' not in state.cards[card.id].counters


def test_targeted_chapter_generates_ward_above_it_after_human_selection():
    state = clean(2)
    card = saga(state, 'Binding the Old Gods', 2)
    target = add(state, 'Tolarian Terror', 1)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {2}
    RulesEngine()._advance_sagas(state)
    item = state.stack[-1]
    state = checked_action(state, RulesEngine(), 2, {
        'type': 'choose_trigger_target', 'stack_id': item.id, 'target_card_id': target.id,
    })
    assert len(state.stack) == 2 and state.stack[-1].effect_key == 'ward_payment'
    assert state.stack[0].source_card_id == card.id


def test_turn_batch_preserves_other_sagas_and_staged_chapters_across_choices():
    state = clean()
    cards = [saga(state), saga(state)]
    for card in cards:
        card.counters['__lore'] = 1
    modifier(state, 'Doubling Season')
    modifier(state, 'Vorinclex, Monstrous Raider')
    modifier(state, 'Vorinclex, Monstrous Raider', 2)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    RulesEngine()._advance_sagas(state)
    assert state.pending_replacement_choice and not state.stack
    assert len(state.pending_replacement_choice['continuation_effects']) == 1
    choices = 0
    while state.pending_replacement_choice:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
        operations = {item['operation'] for item in state.pending_replacement_choice['options']}
        state = choose(state, 'double' if 'double' in operations else 'half')
        apply_state_based_actions(state)
        assert all(state.cards[card.id].zone == Zone.BATTLEFIELD for card in cards)
        choices += 1
        assert choices < 8
    assert all(state.cards[card.id].counters['__lore'] == 3 for card in cards)
    assert state.pending_trigger_order and not state.stack
    state = order(state)
    assert len(state.stack) == 4


def test_unrelated_stack_ability_does_not_delay_final_saga_sacrifice():
    state = clean()
    card = saga(state)
    card.counters['__lore'] = 3  # Core setup: no chapter trigger remains pending.
    add_to_stack(state, card.id, 1, 'Unrelated core ability', 'noop', {}, is_spell=False)
    apply_state_based_actions(state)
    assert card.zone == Zone.GRAVEYARD and len(state.stack) == 1


def test_old_chapter_does_not_hold_a_new_battlefield_incarnation():
    state = clean()
    card = saga(state)
    put_counters(state, 'lore', 3, target_card_id=card.id)
    # Core setup: the same card left and re-entered with a distinct incarnation.
    assign_static_order_on_battlefield_entry(state, card.id)
    card.counters['__lore'] = 3
    apply_state_based_actions(state)
    assert card.zone == Zone.GRAVEYARD


def test_legacy_snapshot_chapter_label_remains_recognized():
    state = clean()
    card = saga(state)
    card.counters['__lore'] = 3
    add_to_stack(state, card.id, 1, f'{card.name} chapter 3', 'noop', {}, is_spell=False)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    apply_state_based_actions(state)
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    resolve_top_of_stack(state)
    apply_state_based_actions(state)
    assert state.cards[card.id].zone == Zone.GRAVEYARD


def test_copied_chapter_does_not_delay_sacrifice_after_original_is_countered():
    from effects.handlers import copy_ability, counter_ability
    state = clean()
    card = saga(state)
    card.counters['__lore'] = 2
    put_counters(state, 'lore', 1, target_card_id=card.id)
    original = state.stack[-1]
    copy_ability(state, 1, {'target_stack_id': original.id})
    assert len(state.stack) == 2
    counter_ability(state, 2, {'target_stack_id': original.id})
    apply_state_based_actions(state)
    assert len(state.stack) == 1 and state.stack[0].payload['__stack_copy_kind'] == 'triggered'
    assert card.zone == Zone.GRAVEYARD


def test_public_card_view_exposes_lore_without_changing_snapshot_storage():
    from game_state.serializers import serialize_card_view
    state = clean()
    card = saga(state)
    put_counters(state, 'lore', 2, target_card_id=card.id)
    view = serialize_card_view(state, card.id)
    assert view['counters']['lore'] == 2 and '__lore' not in view['counters']
    assert card.counters['__lore'] == 2 and 'lore' not in card.counters
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[card.id].counters['__lore'] == 2


@pytest.mark.parametrize('explicit_choice', [False, True])
def test_ai_creates_creatures_before_snapshot_team_buff_without_card_names(explicit_choice):
    from ai.agent import AIAgent
    from rules_engine.continuous import effective_combat_stats
    from rules_engine.move_generator import legal_moves
    state = clean(2)
    card = saga(state, player=2)
    card.counters['__lore'] = 1
    modifier(state, 'Vorinclex, Monstrous Raider', 2)
    state.trigger_order_choice_required = explicit_choice
    state.trigger_order_choice_players = {2} if explicit_choice else set()
    RulesEngine()._advance_sagas(state)
    if explicit_choice:
        decision = AIAgent('master').choose_action(state, legal_moves(state, 2), 2)
        state = checked_action(state, RulesEngine(), 2, decision.action)
    assert [item.payload['__chapter_number'] for item in state.stack] == [3, 2]
    resolve_top_of_stack(state)
    resolve_top_of_stack(state)
    token = next(cid for cid in state.players[2].battlefield if state.cards[cid].is_token)
    assert effective_combat_stats(state, token) == (4, 3)
    apply_state_based_actions(state)
    assert state.cards[card.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('boundary', ['mixed', 'negative', 'different_subtype', 'opponent_tokens'])
def test_trigger_dependency_policy_leaves_unverified_groups_unchanged(boundary):
    from copy import deepcopy
    from ai.trigger_policy import preferred_trigger_order
    # Core effect packets, not fabricated cards or modified Oracle text.
    creator = {'effect_key': 'create_token', 'payload': {
        'controller': 1, 'power': 2, 'toughness': 2, 'type_line': 'Token Creature - Knight',
    }}
    buff = {'effect_key': 'temporary_pt_buff_all', 'payload': {
        'controller_only': True, 'power': 2, 'toughness': 1, 'creature_subtypes': ['Knight'],
    }}
    group = [creator, buff]
    if boundary == 'mixed':
        group.append({'effect_key': 'draw_cards', 'payload': {'amount': 1}})
    elif boundary == 'negative':
        buff['payload']['power'] = -2
    elif boundary == 'different_subtype':
        buff['payload']['creature_subtypes'] = ['Elf']
    else:
        creator['payload']['controller'] = 2
    before = deepcopy(group)
    assert preferred_trigger_order(group, 1) == before
    assert group == before
