"""Canonical life replacement recipients, ordering and durable continuations."""
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.replacement import replacement_options
from tests.test_ai_search_prefix import bare_state
from tests.test_linked_damage_targets import raw_card
from tests.test_lifelink_gain_events import add_nighthawk, add_pridemate


FIXTURES = Path(__file__).parent / 'fixtures/life_conversion'


def permanent(state, name, controller):
    return raw_card(state, json.loads((FIXTURES / (name + '.json')).read_text()),
                    controller, Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['tainted-remedy', 'plague-drone'])
@pytest.mark.parametrize('own', [False, True])
def test_conversion_applies_to_opponents_not_its_controller(seat, name, own):
    state = bare_state(seat)
    source = permanent(state, name, seat if own else 3-seat)
    options = replacement_options(state, 'life_gain', target_player=seat)
    assert [row['source_id'] for row in options] == ([] if own else [source.id])
    resolve_effect(state, seat, 'gain_life', {'amount': 3})
    assert state.players[seat].life == (23 if own else 17)
    assert state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['conversion', 'double'])
def test_affected_player_chooses_conversion_or_double_before_snapshot_resume(seat, first):
    state = bare_state(seat)
    source = permanent(state, 'tainted-remedy', 3-seat)
    archive = permanent(state, 'alhammarrets-archive', seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    resolve_effect(state, 3-seat, 'gain_life', {'target_player': seat, 'amount': 3})
    assert state.players[seat].life == 20
    assert state.pending_replacement_choice['player_id'] == seat
    assert {o['source_id'] for o in state.pending_replacement_choice['options']} == {source.id, archive.id}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_replacement',
                          'replacement_source_id': source.id if first == 'conversion' else archive.id})
    assert not state.pending_replacement_choice
    assert state.players[seat].life == (17 if first == 'conversion' else 14)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lock', ['cant_gain', 'total_lock'])
def test_gain_and_loss_prohibitions_apply_to_the_event_they_prohibit(seat, lock):
    state = bare_state(seat)
    permanent(state, 'tainted-remedy', 3-seat)
    if lock == 'cant_gain':
        state.turn_cant_gain_life.add(seat)
    else:
        permanent(state, 'platinum-emperion', seat)
    resolve_effect(state, seat, 'gain_life', {'amount': 3})
    assert state.players[seat].life == 20
    assert not state.pending_replacement_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_multiple_converters_do_not_multiply_life_loss(seat):
    state = bare_state(seat)
    permanent(state, 'tainted-remedy', 3-seat)
    permanent(state, 'plague-drone', 3-seat)
    resolve_effect(state, seat, 'gain_life', {'amount': 3})
    assert state.players[seat].life == 17


def test_lifelink_conversion_does_not_emit_life_gain_triggers():
    state = bare_state(1)
    permanent(state, 'tainted-remedy', 2)
    add_pridemate(state)
    source = add_nighthawk(state, 'hawk')
    resolve_effect(state, 1, 'deal_damage', {'target_player': 2, 'amount': 2, '__source_card_id': source})
    assert (state.players[1].life, state.players[2].life) == (18, 18)
    assert not any(item.source_card_id == 'pridemate' for item in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cause', ['life', 'poison', 'draw'])
def test_unconditional_loss_protection_and_checked_failed_draw_history(seat, cause):
    from rules_engine.state_based_actions import apply_state_based_actions
    from game_state.state import draw_card
    state = bare_state(seat)
    angel = permanent(state, 'platinum-angel', seat)
    if cause == 'life':
        state.players[seat].life = 0
    elif cause == 'poison':
        state.players[seat].poison = 10
    else:
        state.players[seat].library.clear()
        draw_card(state, seat)
        assert seat in state.failed_draw_players
    apply_state_based_actions(state)
    assert state.winner is None
    assert seat not in state.failed_draw_players
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_effect(state, 3-seat, 'exile', {'target_card_id': angel.id})
    apply_state_based_actions(state)
    assert state.winner == (None if cause == 'draw' else 3-seat)
    if cause == 'draw':
        draw_card(state, seat)
        apply_state_based_actions(state)
        assert state.winner == 3-seat


@pytest.mark.parametrize('name', ['plague-drone', 'platinum-angel'])
def test_losing_printed_abilities_disables_static_conversion_or_loss_protection(name):
    from rules_engine.keyword_effects import add_keyword_effect
    from rules_engine.state_based_actions import apply_state_based_actions
    state = bare_state(1)
    source = permanent(state, name, 2 if name == 'plague-drone' else 1)
    add_keyword_effect(state, source.id, ['all abilities'], operation='remove', until_end_of_turn=True)
    if name == 'plague-drone':
        resolve_effect(state, 1, 'gain_life', {'amount': 3})
        assert state.players[1].life == 23
    else:
        state.players[1].life = 0
        apply_state_based_actions(state)
        assert state.winner == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [3, 20])
def test_lethal_damage_does_not_remove_converter_between_spell_instructions(seat, life):
    from tests.test_ai_beneficial_alternatives import damage_gain_position
    from rules_engine.stack_engine import resolve_top_of_stack
    state, spell = damage_gain_position(seat, 'lightning-helix')
    drone = permanent(state, 'plague-drone', 3-seat)
    assert drone.toughness == 3
    state.players[seat].life = life
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
                           'card_id': spell.id, 'targets': {'target_card_id': drone.id}})
    assert resolve_top_of_stack(state)
    # The converter remains active until the complete damage/gain spell finishes.
    assert state.players[seat].life == life-3
    assert state.cards[drone.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['conversion', 'double'])
def test_lethal_converter_and_pending_gain_order_survive_resolution_snapshot(seat, first):
    from tests.test_ai_beneficial_alternatives import damage_gain_position
    from rules_engine.stack_engine import resolve_top_of_stack
    state, spell = damage_gain_position(seat, 'lightning-helix')
    drone = permanent(state, 'plague-drone', 3-seat)
    archive = permanent(state, 'alhammarrets-archive', seat)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
                           'card_id': spell.id, 'targets': {'target_card_id': drone.id}})
    assert not resolve_top_of_stack(state)  # Replacement choice pauses resolution.
    assert state.pending_replacement_choice['resume_kind'] == 'gain_event'
    assert state.cards[drone.id].zone == Zone.BATTLEFIELD
    assert state.cards[drone.id].counters['__damage_marked'] == 3
    assert state.trigger_staging
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_replacement',
                           'replacement_source_id': drone.id if first == 'conversion' else archive.id})
    assert state.players[seat].life == (17 if first == 'conversion' else 14)
    assert state.cards[drone.id].zone == Zone.GRAVEYARD
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert not state.pending_replacement_choice
