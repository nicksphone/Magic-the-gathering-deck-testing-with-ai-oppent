"""Native Battle counter/trigger/SBA acceptance, with declared core-policy inputs.

The paid Woodland and Stifle cases use real announcements and original complete
printing readers. Other positions, type/stat inputs and direct effect packets
are explicitly scoped policy controls; they do not invent card printings or
claim an unplayed paid producer history. Tests inspect only their own game data.
"""
from copy import deepcopy

import pytest

from game_state.state import Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.events import emit_event, emit_event_batch, flush_staged_triggers
from rules_engine.state_based_actions import apply_state_based_actions
from rules_engine.type_effects import add_type_effect
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from effects.registry import resolve_effect
from tests.test_battle_entry import position, battle_ready, move, place, act, row, BATTLE
from tests.test_battle_characteristics import mark
from tests.battle_copy_native_support import paid_copy_without_entry_defense as _paid_copy


def ready(seat, count=3, extra=()):
    state, cid = position(seat, extra)
    battle_ready(state, cid, 3-seat, count=count)
    return state, cid


def remove(state, cid, count, *, emit_events=True, kind='defense'):
    from rules_engine.counter_removal import remove_counters
    return remove_counters(state, cid, kind, count, emit_events=emit_events)


def ref(card):
    return {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}


def defeat_items(state, cid):
    return [x for x in state.stack if x.source_card_id == cid and x.effect_key == 'battle_defeat']


def etb(state, cid):
    emit_event(state, 'enters_battlefield', {'card_id': cid, 'controller': state.cards[cid].controller})


def cold(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_woodland_copy_without_entry_uses_zero_defense_sba(seat):
    _paid_copy(seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_last_defense_removal_emits_one_native_bound_defeat_trigger(seat):
    state, cid = ready(seat)
    current = ref(state.cards[cid]); state.cards[cid].counter_timestamps['defense'] = 7
    assert remove(state, cid, 99) == 3
    assert state.cards[cid].counters.get('defense', 0) == 0
    assert 'defense' not in state.cards[cid].counter_timestamps
    items = defeat_items(state, cid)
    assert len(items) == 1 and items[0].controller == seat
    assert items[0].payload['target_card_id'] == cid
    assert items[0].payload['__trigger_source_reference'] == current
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    mark('last-defense-native-trigger-reference-and-SBA-hold-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_partial_and_zero_to_zero_removal_do_not_retrigger(seat):
    state, cid = ready(seat)
    state.cards[cid].counter_timestamps['defense'] = 7
    assert remove(state, cid, 1) == 1 and not defeat_items(state, cid)
    assert state.cards[cid].counters['defense'] == 2 and state.cards[cid].counter_timestamps['defense'] == 7
    assert remove(state, cid, 2) == 2 and len(defeat_items(state, cid)) == 1
    assert remove(state, cid, 1) == 0 and remove(state, cid, 0) == 0
    assert len(defeat_items(state, cid)) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_defense_position_does_not_fabricate_a_defeat_trigger(seat):
    state, cid = ready(seat, count=0)
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_zone_counter_reset_is_not_a_gameplay_removal(seat):
    state, cid = ready(seat)
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': cid})
    assert state.cards[cid].zone == Zone.HAND and not state.cards[cid].counters
    assert not defeat_items(state, cid)


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_non_event_removal_does_not_publish_defeat(seat):
    state, cid = ready(seat)
    assert remove(state, cid, 3, emit_events=False) == 3 and not state.stack
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_defense_counters_on_an_ordinary_permanent_have_no_siege_intrinsic(seat):
    state, _ = ready(seat)
    cid = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    state.cards[cid].counters['defense'] = 1
    assert remove(state, cid, 1) == 1 and not defeat_items(state, cid)
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_non_siege_zero_battle_is_unconditional_even_with_own_trigger(seat):
    state, cid = ready(seat, count=0)
    etb(state, cid)
    (mark('non-Siege-own-ETB-is-staged') if state.staged_triggers else
     mark('non-Siege-own-ETB-is-cleanup-deferred') if state.cleanup_deferred_triggers else
     mark('non-Siege-own-ETB-is-pending-order') if state.pending_trigger_order else
     mark('non-Siege-own-ETB-not-collected'))
    assert any(x.source_card_id == cid for x in state.stack)
    state.cards[cid].type_line = 'Battle'  # Declared noncopy subtype-loss policy input.
    apply_state_based_actions(state)
    mark('non-Siege-native-graveyard-SBA-assertion-reached')
    assert state.cards[cid].zone == Zone.GRAVEYARD
    mark('non-Siege-native-retained-trigger-assertion-reached')
    assert any(x.source_card_id == cid for x in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
def test_all_ability_loss_suppresses_defeat_transition(seat):
    state, cid = ready(seat, extra=('Humility',))
    place(state, 3-seat, 'Humility', Zone.BATTLEFIELD)
    add_type_effect(state, cid, ['Creature'])
    assert remove(state, cid, 3) == 3 and not defeat_items(state, cid)
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_basic_land_type_loss_does_not_suppress_battle_intrinsic_transition(seat):
    state, cid = ready(seat, extra=('Blood Moon',))
    place(state, 3-seat, 'Blood Moon', Zone.BATTLEFIELD)
    add_type_effect(state, cid, ['Land'])
    assert remove(state, cid, 3) == 3 and len(defeat_items(state, cid)) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_defeat_is_captured_before_a_later_ability_loss_instruction(seat):
    state, cid = ready(seat)
    resolve_effect(state, seat, 'effect_sequence', {'effects': [
        {'effect_key': 'remove_counters', 'payload': {'target_card_id': cid, 'counter': 'defense', 'amount': 3}},
        {'effect_key': 'temporary_ability_loss', 'payload': {'target_card_id': cid}},
    ]})
    assert len(defeat_items(state, cid)) == 1
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_foreign_battle_trigger_does_not_hold_a_zero_siege(seat):
    state, cid = ready(seat, count=0)
    other = place(state, 3-seat, BATTLE, Zone.BATTLEFIELD)
    state.cards[other].counters['defense'] = 3
    etb(state, other)
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD and state.cards[other].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_old_incarnation_trigger_does_not_hold_a_returned_zero_siege(seat):
    state, cid = ready(seat)
    etb(state, cid); previous = ref(state.cards[cid])
    move(state, cid, Zone.HAND); battle_ready(state, cid, 3-seat, count=0)
    assert ref(state.cards[cid]) != previous and state.stack[0].source_card_id == cid
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_announced_activated_item_from_same_object_does_not_hold_zero_siege(seat):
    state, cid = ready(seat, count=0)
    add_to_stack(state, cid, seat, 'Declared activated policy input', 'draw_cards',
                 {'amount': 1, '__activation_source_reference': ref(state.cards[cid])}, is_spell=False)
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD and state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_or_malformed_trigger_reference_never_guesses_a_current_object(seat):
    for malformed in (None, {}, {'incarnation': True, 'zone_change_sequence': 0}):
        state, cid = ready(seat, count=0)
        etb(state, cid)
        if malformed is None: state.stack[0].payload.pop('__trigger_source_reference', None)
        else: state.stack[0].payload['__trigger_source_reference'] = malformed
        apply_state_based_actions(state)
        assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_own_staged_etb_trigger_holds_zero_siege_across_snapshot(seat):
    state, cid = ready(seat, count=0)
    state.trigger_staging = True; state.trigger_staging_event = 'declared entry event'
    etb(state, cid)
    assert state.staged_triggers[0]['payload']['__trigger_source_reference'] == ref(state.cards[cid])
    state = cold(state); apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD and state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_own_cleanup_deferred_trigger_holds_zero_siege(seat):
    state, cid = ready(seat, count=0)
    state.cleanup_pending = True
    etb(state, cid)
    assert state.cleanup_deferred_triggers[0]['payload']['__trigger_source_reference'] == ref(state.cards[cid])
    state = cold(state); apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_native_human_order_retains_references_before_publication(seat):
    state, cid = ready(seat, count=0, extra=(BATTLE,))
    other = place(state, seat, BATTLE, Zone.BATTLEFIELD); state.cards[other].counters['defense'] = 3
    state.trigger_order_choice_required = True; state.trigger_order_choice_players = {seat}
    emit_event_batch(state, 'enters_battlefield', [
        {'card_id': cid, 'controller': seat}, {'card_id': other, 'controller': seat}])
    assert state.pending_trigger_order and not state.stack
    state = cold(state); apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    group = state.pending_trigger_order['groups'][str(seat)]
    assert all(x['payload']['__trigger_source_reference'] == ref(state.cards[x['source_card_id']]) for x in group)
    state = act(state, seat, {'type': 'choose_trigger_order', 'trigger_order': [x['_choice_id'] for x in reversed(group)]})
    assert len(state.stack) == 2 and state.cards[cid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_trigger_retains_source_reference_after_original_is_countered(seat):
    state, cid = ready(seat, count=0)
    etb(state, cid); original = state.stack[-1].id
    resolve_effect(state, 3-seat, 'copy_ability', {'target_stack_id': original})
    assert len(state.stack) == 2 and state.stack[-1].controller == 3-seat
    assert state.stack[-1].payload['__trigger_source_reference'] == ref(state.cards[cid])
    resolve_effect(state, seat, 'counter_ability', {'target_stack_id': original})
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    resolve_effect(state, seat, 'counter_ability', {'target_stack_id': state.stack[-1].id})
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_real_etb_resolution_pause_retains_trigger_reference_until_choice_finishes(seat):
    state, cid = ready(seat, count=0)
    state.mechanic_choice_players = {seat}
    etb(state, cid)
    assert not resolve_top_of_stack(state) and state.pending_mechanic_choice
    state = cold(state)
    frame = state.pending_mechanic_choice['resolving_item']
    assert frame['payload']['__trigger_source_reference'] == ref(state.cards[cid])
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': []})
    assert state.cards[cid].zone == Zone.GRAVEYARD and not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_stifle_counters_defeat_then_native_sba_moves_battle(seat):
    printing = row('Stifle', 1)
    assert printing['object'] == 'card' and len(printing) >= 50 and printing.get('oracle_id')
    state, cid = ready(seat, extra=('Stifle', 'Island'))
    spell = place(state, seat, 'Stifle', Zone.HAND)
    island = place(state, seat, 'Island', Zone.BATTLEFIELD)
    assert remove(state, cid, 3) == 3
    target = defeat_items(state, cid)[0].id
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell, 'cost_choice': {'id': 'base'},
                             'targets': {'target_stack_id': target}})
    assert state.cards[island].tapped and state.cards[spell].zone == Zone.STACK
    for _ in range(8):
        if not state.stack: break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.cards[spell].zone == Zone.GRAVEYARD
    assert state.cards[cid].zone == Zone.GRAVEYARD
    mark('actual-paid-Stifle-defeat-countered-and-native-SBA-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_remove_all_prohibition_route_captures_defeat_before_later_prohibition(seat):
    from rules_engine.retained_counter_prohibition import reference
    state, cid = ready(seat)
    resolve_effect(state, seat, 'retained_counter_prohibition', {
        '__counter_target_kind': 'card', 'target_card_id': cid,
        '__trigger_target_reference': [object_incarnation(state.cards[cid]), state.cards[cid].zone_change_sequence],
        '__counter_source_ref': reference(state.cards[cid])})
    assert not state.cards[cid].counters and len(defeat_items(state, cid)) == 1
    assert state.retained_counter_prohibitions


@pytest.mark.parametrize('seat', [1, 2])
def test_native_source_counter_cost_publishes_defeat_once(seat):
    from rules_engine.costs import apply_activated_costs
    state, cid = ready(seat, count=1)
    # Declared native cost input, not a fabricated printed activated ability.
    assert apply_activated_costs(state, seat, cid, 'Remove a defense counter from this permanent')
    assert len(defeat_items(state, cid)) == 1 and state.cards[cid].counters.get('defense', 0) == 0
    assert not apply_activated_costs(state, seat, cid, 'Remove a defense counter from this permanent')
    assert len(defeat_items(state, cid)) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_transfer_uses_native_removal_transition_and_placement(seat):
    state, cid = ready(seat)
    target = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    resolve_effect(state, seat, 'move_counters', {'from_card_id': cid, 'target_card_id': target,
                                               'counter': 'defense', 'amount': 3})
    assert state.cards[target].counters['defense'] == 3 and len(defeat_items(state, cid)) == 1
    assert state.cards[cid].counters.get('defense', 0) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_transfer_to_prohibited_or_same_object_removes_nothing(seat):
    state, cid = ready(seat, extra=('Solemnity',))
    target = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    place(state, seat, 'Solemnity', Zone.BATTLEFIELD); add_type_effect(state, target, ['Battle'])
    # Solemnity's Land scope prohibits the recipient's defense counters.
    resolve_effect(state, seat, 'move_counters', {'from_card_id': cid, 'target_card_id': target,
                                               'counter': 'defense', 'amount': 3})
    resolve_effect(state, seat, 'move_counters', {'from_card_id': cid, 'target_card_id': cid,
                                               'counter': 'defense', 'amount': 3})
    assert state.cards[cid].counters['defense'] == 3 and not defeat_items(state, cid)


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_transfer_replacement_choice_resumes_once_after_snapshot(seat):
    state, cid = ready(seat, count=1, extra=('Doubling Season', 'Vorinclex, Monstrous Raider'))
    place(state, seat, 'Doubling Season', Zone.BATTLEFIELD)
    place(state, 3-seat, 'Vorinclex, Monstrous Raider', Zone.BATTLEFIELD)
    target = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    state.replacement_choice_required = True; state.replacement_choice_players = {seat}
    resolve_effect(state, seat, 'move_counters', {'from_card_id': cid, 'target_card_id': target,
                                               'counter': 'defense', 'amount': 1})
    assert state.pending_replacement_choice and state.cards[cid].counters['defense'] == 1
    assert not defeat_items(state, cid)
    state = cold(state)
    option = next(x for x in state.pending_replacement_choice['options'] if x['operation'] == 'double')
    state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert not state.pending_replacement_choice and state.cards[target].counters['defense'] == 1
    assert state.cards[cid].counters.get('defense', 0) == 0 and len(defeat_items(state, cid)) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_transfer_choice_rejects_changed_source_before_removal_atomically(seat):
    from rules_engine.action_validation import ActionRejected, checked_action
    from rules_engine.engine import RulesEngine
    state, cid = ready(seat, count=1, extra=('Doubling Season', 'Vorinclex, Monstrous Raider'))
    place(state, seat, 'Doubling Season', Zone.BATTLEFIELD)
    place(state, 3-seat, 'Vorinclex, Monstrous Raider', Zone.BATTLEFIELD)
    target = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    state.replacement_choice_required = True; state.replacement_choice_players = {seat}
    resolve_effect(state, seat, 'move_counters', {'from_card_id': cid, 'target_card_id': target,
                                               'counter': 'defense', 'amount': 1})
    state = cold(state); move(state, cid, Zone.HAND)  # Declared negative retained-context fault.
    option = state.pending_replacement_choice['options'][0]
    before = serialize_match_snapshot(state); rejected = False
    try: checked_action(state, RulesEngine(), seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    except ActionRejected: rejected = True
    assert rejected and serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_currently_resolving_native_trigger_holds_only_during_its_scope(seat):
    from rules_engine.battles import trigger_resolution_scope
    state, cid = ready(seat, count=0)
    etb(state, cid); item = state.stack.pop()
    with trigger_resolution_scope(state, item):
        apply_state_based_actions(state)
        assert state.cards[cid].zone == Zone.BATTLEFIELD
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_departed_battle_trigger_keeps_pre_departure_source_reference(seat):
    from rules_engine.keyword_effects import add_keyword_effect
    state, cid = ready(seat, count=0)
    add_type_effect(state, cid, ['Creature'])
    resolve_effect(state, seat, 'set_base_stats', {'target_card_id': cid, 'base_power': 2, 'base_toughness': 2})
    add_keyword_effect(state, cid, ['undying'])
    previous = ref(state.cards[cid])
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    item = next(x for x in state.stack if x.source_card_id == cid and x.effect_key == 'undying_return')
    assert item.payload['__trigger_source_reference'] == previous
    assert state.cards[cid].zone_change_sequence != previous['zone_change_sequence']


@pytest.mark.parametrize('seat', [1, 2])
def test_indestructible_does_not_prevent_zero_defense_graveyard_move(seat):
    from rules_engine.keyword_effects import add_keyword_effect
    state, cid = ready(seat, count=0)
    add_keyword_effect(state, cid, ['indestructible'])
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_mixed_creature_battle_lethal_and_zero_are_one_departure_with_death_events(seat):
    state, cid = ready(seat, count=0, extra=('Blood Artist',))
    artist = place(state, seat, 'Blood Artist', Zone.BATTLEFIELD)
    add_type_effect(state, cid, ['Creature'])
    resolve_effect(state, seat, 'set_base_stats', {'target_card_id': cid, 'base_power': 2, 'base_toughness': 2})
    state.cards[cid].counters['__damage_marked'] = 2
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD and state.players[seat].graveyard.count(cid) == 1
    assert len([x for x in state.stack if x.source_card_id == artist]) == 1
    assert state.stack[0].payload['__trigger_source_reference'] == ref(state.cards[artist])


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_battle_and_lethal_replacement_source_leave_in_one_prepared_batch(seat):
    state, cid = ready(seat, count=0, extra=('Rest in Peace',))
    rip = place(state, seat, 'Rest in Peace', Zone.BATTLEFIELD)
    add_type_effect(state, rip, ['Creature'])
    resolve_effect(state, seat, 'set_base_stats', {'target_card_id': rip, 'base_power': 0, 'base_toughness': 0})
    apply_state_based_actions(state)
    assert state.cards[rip].zone == Zone.EXILE and state.cards[cid].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_battle_graveyard_replacement_choice_round_trips_and_resumes(seat):
    state, cid = ready(seat, count=0, extra=('Rest in Peace',))
    place(state, seat, 'Rest in Peace', Zone.BATTLEFIELD)
    place(state, 3-seat, 'Rest in Peace', Zone.BATTLEFIELD)
    state.replacement_choice_required = True; state.replacement_choice_players = {seat}
    apply_state_based_actions(state)
    assert state.pending_replacement_choice and state.pending_replacement_choice['target_card_id'] == cid
    state = cold(state); option = state.pending_replacement_choice['options'][0]
    state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert state.cards[cid].zone == Zone.EXILE and not state.pending_replacement_choice


@pytest.mark.parametrize('seat', [1, 2])
def test_battle_equipment_and_battle_creature_cannot_remain_attached(seat):
    for types in (['Artifact', 'Battle'], ['Artifact', 'Creature', 'Battle']):
        state, cid = ready(seat, count=1)
        card = state.cards[cid]
        card.types = types; card.type_line = 'Artifact Battle — Siege Equipment'
        target = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
        add_type_effect(state, target, ['Creature'])
        resolve_effect(state, seat, 'set_base_stats', {'target_card_id': target, 'base_power': 2, 'base_toughness': 2})
        if 'Creature' in types:
            resolve_effect(state, seat, 'set_base_stats', {'target_card_id': cid, 'base_power': 2, 'base_toughness': 2})
        card.attached_to = target
        apply_state_based_actions(state)
        assert card.zone == Zone.BATTLEFIELD and card.attached_to is None
    mark('Battle-attachment-core-policy-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_delayed_draw_and_payment_keep_creation_source_across_a_blink(seat):
    for key, packet in (('schedule_next_turn_draw', {'amount': 1}),
                        ('schedule_upkeep_payment', {'mana_cost': '{0}'})):
        state, cid = ready(seat)
        previous = ref(state.cards[cid])
        resolve_effect(state, seat, key, {**packet, '__source_card_id': cid})
        move(state, cid, Zone.HAND); battle_ready(state, cid, 3-seat, count=0)
        state.turn += 1
        emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
        assert len(state.stack) == 1
        assert state.stack[0].payload['__trigger_source_reference'] == previous
        assert previous != ref(state.cards[cid])
        apply_state_based_actions(state)
        assert state.cards[cid].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_delayed_trigger_from_the_same_continuous_object_can_hold_zero_siege(seat):
    state, cid = ready(seat)
    previous = ref(state.cards[cid])
    resolve_effect(state, seat, 'schedule_next_turn_draw', {'amount': 1, '__source_card_id': cid})
    state.turn += 1
    state.cards[cid].counters['defense'] = 0  # Declared zero-at-upkeep policy input.
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    assert len(state.stack) == 1 and state.stack[0].payload['__trigger_source_reference'] == previous
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_delayed_trigger_missing_creation_reference_cannot_bind_current_battle(seat):
    state, cid = ready(seat, count=0)
    state.delayed_triggers.append({'step': 'upkeep', 'earliest_turn': state.turn,
        'source_card_id': cid, 'controller': seat, 'label': 'Legacy delayed draw policy input',
        'effect_key': 'draw_cards', 'payload': {'amount': 1, 'target_player': seat}})
    emit_event(state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    assert len(state.stack) == 1
    apply_state_based_actions(state)
    assert state.cards[cid].zone == Zone.GRAVEYARD
    mark('Battle-legacy-delayed-source-unknown-control-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_source_counter_cost_retains_its_zero_snapshot_entry(seat):
    from rules_engine.costs import apply_activated_costs
    state, _ = ready(seat)
    cid = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    state.cards[cid].counters['+1/+1'] = 1
    before = serialize_match_snapshot(state)
    assert apply_activated_costs(state, seat, cid, 'Remove a +1/+1 counter from this permanent')
    expected = deepcopy(before); expected['cards'][cid]['counters']['+1/+1'] = 0
    mark('legacy-source-counter-cost-zero-snapshot-entry-assertion-reached')
    assert serialize_match_snapshot(state) == expected
    assert not apply_activated_costs(state, seat, cid, 'Remove a +1/+1 counter from this permanent')
    mark('legacy-source-counter-cost-zero-entry-passed')


@pytest.mark.parametrize('seat', [1, 2])
def test_remove_all_cleans_legacy_zero_entries_and_orphan_counter_timestamps(seat):
    from rules_engine.retained_counter_prohibition import reference
    state, _ = ready(seat)
    cid = next(x for x in state.players[seat].battlefield if state.cards[x].name == 'Forest')
    card = state.cards[cid]
    card.counters.update({'+1/+1': 0, '__damage_marked': 1})
    card.counter_timestamps.update({'+1/+1': 3, 'charge': 7, '__unrelated_internal': 11})
    resolve_effect(state, seat, 'retained_counter_prohibition', {
        '__counter_target_kind': 'card', 'target_card_id': cid,
        '__trigger_target_reference': [object_incarnation(card), card.zone_change_sequence],
        '__counter_source_ref': reference(card)})
    mark('remove-all-legacy-zero-entry-and-counter-timestamp-assertion-reached')
    assert card.counters == {'__damage_marked': 1}
    assert card.counter_timestamps == {'__unrelated_internal': 11}
    mark('Battle-counter-trigger-and-zero-SBA-whole-module-passed')
