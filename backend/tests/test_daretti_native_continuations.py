"""Public paid Daretti continuations, not a reduced browser-driver admission."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from effects.handlers import counter_ability, return_permanent_from_graveyard_to_battlefield, sacrifice
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.optional_reveal import public_choice
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_canonical_daretti_full_body_contract import (
    RAW_BODY, activate, advance_to_end, board, choose, get_emblem, put, restored,
)


def resolve_once(state):
    result = resolve_top_of_stack(state)
    assert result is not bool(state.pending_mechanic_choice or state.pending_replacement_choice)
    return state


def reject(state, seat, action):
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


def recycle(seat=1, *, types=('Artifact',), text=''):
    state = board(seat)
    put(state, 'return-me', Zone.GRAVEYARD, owner=seat, types=types, text=text)
    put(state, 'pay-me', Zone.BATTLEFIELD, owner=seat)
    return resolve_once(activate(state, seat, 1, {'target_card_id': 'return-me'}))


@pytest.mark.parametrize('seat', [1, 2])
def test_complete_canonical_paid_cast_then_loyalty_rummage(seat):
    state = board(seat)
    card = state.cards['daretti']
    state.players[seat].battlefield.remove(card.id)
    card.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool = {'R': 1, 'C': 3}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id})
    state = resolve_once(restored(state))
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].loyalty == 3
    assert not any(state.players[seat].mana_pool.values())
    put(state, 'hand-card', Zone.HAND, owner=seat, types=('Land',))
    state = choose(resolve_once(activate(state, seat, 0)), seat, ['hand-card'])
    assert state.cards[card.id].oracle_text == RAW_BODY
    assert state.cards[card.id].loyalty == 5
    assert state.discards_this_turn[seat] == state.draws_this_turn[seat] == 1


def test_resolution_cost_remains_paid_when_replacement_exiles_sacrifice():
    state = recycle()
    put(state, 'replacement', Zone.BATTLEFIELD, types=('Enchantment',),
        text='If a card or token would be put into a graveyard from anywhere, exile it instead.')
    state = choose(restored(state), 1, ['pay-me'])
    assert state.cards['pay-me'].zone == Zone.EXILE
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert not state.pending_mechanic_choice and not state.stack


@pytest.mark.parametrize('bad', ['actor', 'reentry', 'type', 'controller', 'frame'])
def test_invalid_resolution_cost_choice_rejects_unchanged_root(bad):
    state = recycle()
    if bad == 'reentry':
        resolve_effect(state, 1, 'return_permanent_to_hand', {'target_card_id': 'pay-me'})
        state.players[1].hand.remove('pay-me')
        state.cards['pay-me'].move_to_zone(Zone.BATTLEFIELD)
        state.players[1].battlefield.append('pay-me')
    elif bad == 'type':
        state.cards['pay-me'].types = ['Land']
        state.cards['pay-me'].type_line = 'Land'
    elif bad == 'controller':
        state.players[1].battlefield.remove('pay-me')
        state.players[2].battlefield.append('pay-me')
        state.cards['pay-me'].controller = 2
    elif bad == 'frame':
        state.pending_mechanic_choice['effect_payload']['__resolving_item']['controller'] = 2
    reject(state, 2 if bad == 'actor' else 1,
           {'type': 'choose_mechanic', 'card_ids': ['pay-me']})
    assert state.cards['return-me'].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_aura_native_entry_choice_restart_and_private_hints(seat):
    state = recycle(seat, types=('Artifact', 'Enchantment', 'Aura'), text='Enchant creature')
    host = put(state, 'host', Zone.BATTLEFIELD, owner=3-seat, types=('Creature',))
    put(state, 'private-hand-card', Zone.HAND, owner=seat)
    state = choose(state, seat, ['pay-me'])
    assert state.cards['pay-me'].zone == Zone.GRAVEYARD
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert state.pending_mechanic_choice['options'] == [host.id]
    before = serialize_match_snapshot(state)
    for _ in range(2):
        actor = RulesEngine().legal_moves(state, seat)
        assert actor[0]['options'] == [host.id]
        assert RulesEngine().legal_moves(state, 3-seat) == []
        for view in (actor, public_choice(state.pending_mechanic_choice)):
            encoded = json.dumps(view)
            assert 'private-hand-card' not in encoded
            assert 'effect_payload' not in encoded and 'option_references' not in encoded
        assert serialize_match_snapshot(state) == before
    state = checked_action(restored(state), RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'choice_id': host.id})
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert state.cards['return-me'].attached_to == host.id
    assert state.cards['return-me'].controller == seat
    assert state.cards['return-me'].zone_change_sequence == 1
    assert not state.pending_mechanic_choice and not state.stack


def test_aura_without_legal_attachment_stays_in_graveyard_after_paid_cost():
    state = recycle(types=('Artifact', 'Enchantment', 'Aura'), text='Enchant creature')
    state = choose(state, 1, ['pay-me'])
    assert state.cards['pay-me'].zone == Zone.GRAVEYARD
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert not state.pending_mechanic_choice and not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['tapped', 'pay_two_life'])
def test_artifact_land_return_uses_real_native_entry_choice(seat, choice):
    state = recycle(seat, types=('Artifact', 'Land'), text=(
        "As this land enters, you may pay 2 life. If you don't, it enters tapped."))
    state = choose(state, seat, ['pay-me'])
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert set(state.pending_mechanic_choice['options']) == {'tapped', 'pay_two_life'}
    assert 'effect_payload' not in json.dumps(public_choice(state.pending_mechanic_choice))
    state = checked_action(restored(state), RulesEngine(), seat,
                           {'type': 'choose_mechanic', 'choice_id': choice})
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert state.cards['return-me'].tapped is (choice == 'tapped')
    assert state.players[seat].life == (18 if choice == 'pay_two_life' else 20)
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('bad', ['reference', 'controller', 'null-context', 'unknown-context'])
def test_retained_land_return_tamper_rejected_before_payment_or_entry(bad):
    state = choose(recycle(types=('Artifact', 'Land'), text=(
        "As this land enters, you may pay 2 life. If you don't, it enters tapped.")), 1, ['pay-me'])
    payload = state.pending_mechanic_choice['effect_payload']
    if bad == 'reference':
        payload['__graveyard_reference']['zone_change_sequence'] += 1
    elif bad == 'controller':
        payload['__loyalty_return_context']['controller'] = 2
    else:
        payload['__loyalty_return_context'] = None if bad == 'null-context' else {'kind': 'unknown'}
    reject(state, 1, {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'})
    assert state.players[1].life == 20 and state.cards['return-me'].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('sequence', [True, False])
def test_shared_native_return_rejects_retained_graveyard_reference_mismatch(sequence):
    state = board()
    card = put(state, 'return-me', Zone.GRAVEYARD)
    ref = {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
    ref['zone_change_sequence' if sequence else 'incarnation'] += 1
    before = serialize_match_snapshot(state)
    return_permanent_from_graveyard_to_battlefield(state, 1,
        {'target_card_id': card.id, '__graveyard_reference': ref})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('stage', ['first', 'delayed'])
def test_countering_either_real_emblem_trigger_stops_return(stage):
    state, emblem = get_emblem()
    put(state, 'artifact', Zone.BATTLEFIELD)
    sacrifice(state, 1, {'target_card_id': 'artifact'})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == emblem
    if stage == 'delayed':
        state = resolve_once(restored(state))
        advance_to_end(state, 5)
        assert len(state.stack) == 1 and not state.delayed_triggers
    counter_ability(state, 2, {'target_stack_id': state.stack[-1].id})
    assert not state.stack and not state.delayed_triggers
    assert state.cards['artifact'].zone == Zone.GRAVEYARD


def test_artifact_token_can_trigger_but_cannot_return_after_native_cessation():
    from rules_engine.state_based_actions import apply_state_based_actions
    state, emblem = get_emblem()
    put(state, 'token', Zone.BATTLEFIELD).is_token = True
    sacrifice(state, 1, {'target_card_id': 'token'})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == emblem
    apply_state_based_actions(state)
    assert state.cards['token'].zone == Zone.CEASED
    state = resolve_once(restored(state))
    advance_to_end(state, 5)
    state = resolve_once(restored(state))
    assert state.cards['token'].zone == Zone.CEASED
    assert not state.stack and not state.delayed_triggers


@pytest.mark.parametrize('keep', [False, True])
def test_real_paid_ability_copy_uses_native_controller_not_fresh_source(keep):
    raw = json.loads((Path(__file__).parent / 'fixtures/archangel_pair/lithoform-engine.json').read_text())
    state = board()
    put(state, 'return-me', Zone.GRAVEYARD)
    put(state, 'return-2', Zone.GRAVEYARD)
    put(state, 'pay-me', Zone.BATTLEFIELD)
    put(state, 'pay-2', Zone.BATTLEFIELD, owner=2)
    state = activate(state, 1, 1, {'target_card_id': 'return-me'})
    engine = put(state, 'copy-engine', Zone.BATTLEFIELD, text=raw['oracle_text'])
    engine.name, engine.type_line, engine.mana_cost = raw['name'], raw['type_line'], raw['mana_cost']
    state.players[1].mana_pool = {'C': 2}
    state = checked_action(state, RulesEngine(), 1, {'type': 'activate_ability',
        'card_id': engine.id, 'ability_index': 0, 'targets': {'target_stack_id': state.stack[-1].id}})
    state = resolve_once(restored(state))
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    assert 'target_card_id:return-2' in state.pending_mechanic_choice['options']
    state = checked_action(restored(state), RulesEngine(), 1, {'type': 'choose_mechanic',
        'card_ids': ['keep' if keep else 'target_card_id:return-2']})
    assert state.cards['daretti'].loyalty == 1
    assert state.cards[engine.id].tapped and not any(state.players[1].mana_pool.values())
    # Trusted native control change: a fresh source controller is not the copied frame.
    resolve_effect(state, 2, 'change_control', {'target_card_id': 'daretti'})
    state = resolve_once(restored(state))
    if keep:
        assert state.pending_mechanic_choice['player_id'] == 1
        state = choose(restored(state), 1, ['pay-me'])
        assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    else:
        assert state.pending_mechanic_choice['player_id'] == 1
        assert set(state.pending_mechanic_choice['options']) == {'pay-me', engine.id}
        state = choose(restored(state), 1, [engine.id])
        assert state.cards['return-2'].zone == Zone.BATTLEFIELD
        assert state.cards['return-2'].controller == 1
    assert state.cards['pay-2'].zone == Zone.BATTLEFIELD
    assert state.cards['daretti'].controller == 2 and len(state.stack) == 1
    state = resolve_once(state)
    if not keep:
        assert state.cards['pay-me'].zone == Zone.BATTLEFIELD
        state = choose(state, 1, ['pay-me'])
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert not state.stack and not state.pending_mechanic_choice


def counter_return():
    state = recycle(types=('Artifact', 'Creature'))
    put(state, 'entry-provider', Zone.BATTLEFIELD, types=('Creature',),
        text='Each other creature you control enters with an additional +1/+1 counter on it.')
    rows = json.loads((Path(__file__).parent / 'fixtures/counter_replacements.json').read_text())
    for index, name in enumerate(('Doubling Season', "Lae'zel, Vlaakith's Champion")):
        raw = next(row for row in rows if row['name'] == name)
        modifier = put(state, 'modifier-' + str(index), Zone.BATTLEFIELD,
            types=('Enchantment',) if index == 0 else ('Creature',), text=raw['oracle_text'])
        modifier.name, modifier.type_line = raw['name'], raw['type_line']
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    return choose(state, 1, ['pay-me'])


@pytest.mark.parametrize('first,amount', [('double', 3), ('add', 4)])
def test_native_counter_entry_replacements_resume_without_repaying(first, amount):
    state = counter_return()
    assert state.pending_replacement_choice['resume_kind'] == 'counter_event'
    assert state.cards['pay-me'].zone == Zone.GRAVEYARD
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    pending = state.pending_replacement_choice
    option = next(option for option in pending['options'] if option['operation'] == first)
    state = checked_action(restored(state), RulesEngine(), 1, {'type': 'choose_replacement',
        'replacement_source_id': option['source_id']})
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert state.cards['return-me'].counters['+1/+1'] == amount
    assert state.cards['pay-me'].zone_change_sequence == 1
    assert not state.stack and not state.pending_replacement_choice


@pytest.mark.parametrize('bad', ['null', 'unknown', 'controller', 'reference', 'frame', 'unpaid'])
def test_counter_entry_new_context_tamper_rejects_entire_root(bad):
    state = counter_return()
    data = state.pending_replacement_choice['counter_payload']
    context = data['entry_completion_payload']['__loyalty_return_context']
    if bad == 'null':
        data['entry_completion_payload']['__loyalty_return_context'] = None
    elif bad == 'unknown':
        context['kind'] = 'unknown'
    elif bad == 'controller':
        context['controller'] = 2
    elif bad == 'reference':
        context['reference']['zone_change_sequence'] += 1
    elif bad == 'frame':
        context['frame']['controller'] = 2
    else:
        context['paid_cost']['paid'] = False
    option = state.pending_replacement_choice['options'][0]
    reject(state, 1, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert state.cards['pay-me'].zone_change_sequence == 1


def test_two_real_emblems_make_two_delays_but_only_one_retained_object_returns():
    state, first = get_emblem()
    source = state.cards['daretti']
    state.players[1].graveyard.remove(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    state.players[1].battlefield.append(source.id)
    from game_state.state import assign_static_order_on_battlefield_entry
    assign_static_order_on_battlefield_entry(state, source.id)
    source.loyalty = 10
    state = resolve_once(activate(state, 1, 2))
    second = next(cid for cid in state.emblems if cid != first)
    put(state, 'artifact', Zone.BATTLEFIELD, controller=2)
    sacrifice(state, 2, {'target_card_id': 'artifact'})
    assert {item.source_card_id for item in state.stack} == {first, second}
    state = resolve_once(resolve_once(restored(state)))
    assert len(state.delayed_triggers) == 2
    advance_to_end(state, 5)
    assert len(state.stack) == 2 and not state.delayed_triggers
    state = resolve_once(resolve_once(restored(state)))
    assert state.cards['artifact'].zone == Zone.BATTLEFIELD
    assert state.cards['artifact'].controller == 1
    assert state.cards['artifact'].zone_change_sequence == 2
    assert not state.stack


@pytest.mark.parametrize('replacement', ['pay-me', 'exile-source'])
def test_competing_resolution_cost_replacement_uses_native_plan_and_actual_cause(replacement):
    state = recycle()
    state.cards['pay-me'].oracle_text = (
        "If pay-me would be put into a graveyard from anywhere, reveal pay-me and shuffle it into its owner's library instead.")
    put(state, 'exile-source', Zone.BATTLEFIELD, types=('Enchantment',),
        text='If a card or token would be put into a graveyard from anywhere, exile it instead.')
    state = choose(state, 1, ['pay-me'])
    assert state.pending_mechanic_choice['loyalty_operation'] == 'sacrifice_replacement'
    assert set(state.pending_mechanic_choice['options']) == {'pay-me', 'exile-source'}
    assert state.cards['pay-me'].zone == Zone.BATTLEFIELD
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert 'effect_payload' not in json.dumps(public_choice(state.pending_mechanic_choice))
    state = choose(restored(state), 1, [replacement])
    assert state.cards['pay-me'].zone == (Zone.LIBRARY if replacement == 'pay-me' else Zone.EXILE)
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert not state.stack and not state.pending_mechanic_choice


@pytest.mark.parametrize('bad', ['stale-recipient', 'stale-host', 'restriction', 'prohibition'])
def test_paused_aura_entry_revalidates_before_any_entry_mutation(bad):
    state = recycle(types=('Artifact', 'Enchantment', 'Aura'), text='Enchant creature')
    put(state, 'host', Zone.BATTLEFIELD, types=('Creature',))
    state = choose(state, 1, ['pay-me'])
    if bad == 'stale-recipient':
        resolve_effect(state, 1, 'return_from_graveyard', {'target_card_id': 'return-me'})
        from rules_engine.zone_actions import discard_selected
        assert discard_selected(state, 1, ['return-me'])
    elif bad == 'stale-host':
        resolve_effect(state, 1, 'return_permanent_to_hand', {'target_card_id': 'host'})
    elif bad == 'restriction':
        state.cards['host'].types = ['Artifact']
        state.cards['host'].type_line = 'Artifact'
    else:
        put(state, 'prohibition', Zone.BATTLEFIELD, types=('Artifact',), text=(
            "Nonland permanent cards in graveyards and libraries can't enter the battlefield."))
    reject(state, 1, {'type': 'choose_mechanic', 'choice_id': 'host'})
    assert state.cards['return-me'].zone == Zone.GRAVEYARD
    assert state.cards['pay-me'].zone_change_sequence == 1


@pytest.mark.parametrize('token', [False, True])
def test_exile_replacement_never_creates_false_artifact_graveyard_trigger(token):
    state, emblem = get_emblem()
    put(state, 'artifact', Zone.BATTLEFIELD).is_token = token
    put(state, 'exile-source', Zone.BATTLEFIELD, types=('Enchantment',),
        text='If a card or token would be put into a graveyard from anywhere, exile it instead.')
    sacrifice(state, 1, {'target_card_id': 'artifact'})
    assert state.cards['artifact'].zone == Zone.EXILE
    assert not [item for item in state.stack if item.source_card_id == emblem]
    assert not state.delayed_triggers


def test_simultaneous_artifact_deaths_use_both_real_emblems_and_native_apnap():
    state, first = get_emblem()
    source = put(state, 'second-walker', Zone.BATTLEFIELD, owner=2,
                 types=('Planeswalker',), text=RAW_BODY)
    source.name = state.cards['daretti'].name
    source.loyalty = 10
    state.active_player = state.priority_player = 2
    state = checked_action(state, RulesEngine(), 2, {'type': 'activate_loyalty',
        'card_id': source.id, 'ability_index': 2})
    state = resolve_once(state)
    second = next(cid for cid in state.emblems if cid != first)
    put(state, 'artifact-1', Zone.BATTLEFIELD)
    put(state, 'artifact-2', Zone.BATTLEFIELD, owner=2)
    # Native batch primitive; not a claimed paid destructive spell episode.
    resolve_effect(state, 1, 'destroy_all_artifacts', {})
    assert [item.controller for item in state.stack] == [2, 1]
    assert [item.source_card_id for item in state.stack] == [second, first]
    state = resolve_once(resolve_once(restored(state)))
    assert len(state.delayed_triggers) == 2
    advance_to_end(state, 5)
    assert [item.controller for item in state.stack] == [2, 1]
    state = resolve_once(resolve_once(restored(state)))
    assert state.cards['artifact-1'].controller == 1
    assert state.cards['artifact-2'].controller == 2
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in ('artifact-1', 'artifact-2'))


@pytest.mark.parametrize('bad', [None, {}, {'kind': 'unknown'}])
def test_shared_return_malformed_new_context_is_fail_closed(bad):
    state = board()
    put(state, 'return-me', Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    return_permanent_from_graveyard_to_battlefield(state, 1,
        {'target_card_id': 'return-me', '__loyalty_return_context': deepcopy(bad)})
    assert serialize_match_snapshot(state) == before


def test_delayed_return_is_due_on_first_subsequent_native_begin_event_not_a_turn_gate():
    from game_state.state import Step
    from rules_engine.events import emit_event
    state, emblem = get_emblem()
    state.step = Step.END_STEP
    put(state, 'artifact', Zone.BATTLEFIELD)
    sacrifice(state, 1, {'target_card_id': 'artifact'})
    state = resolve_once(restored(state))
    assert len(state.delayed_triggers) == 1 and not state.stack
    # Collector boundary test, not a claimed paid extra-phase episode.
    emit_event(state, 'begin_step', {'step': 'end_step'})
    assert len(state.stack) == 1 and state.stack[0].source_card_id == emblem
    assert not state.delayed_triggers
    state = resolve_once(restored(state))
    assert state.cards['artifact'].zone == Zone.BATTLEFIELD


def test_existing_native_land_return_keeps_legacy_choice_kind():
    state = board()
    put(state, 'return-me', Zone.GRAVEYARD, types=('Artifact', 'Land'), text=(
        "As this land enters, you may pay 2 life. If you don't, it enters tapped."))
    return_permanent_from_graveyard_to_battlefield(state, 1, {'target_card_id': 'return-me'})
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    state = checked_action(restored(state), RulesEngine(), 1,
                           {'type': 'choose_mechanic', 'choice_id': 'pay_two_life'})
    assert state.cards['return-me'].zone == Zone.BATTLEFIELD
    assert state.players[1].life == 18


@pytest.mark.parametrize('bad', ['completion-null', 'completion-missing', 'completion-context-missing',
                                'options-null', 'boolean-controller', 'extra-key'])
def test_counter_return_incomplete_or_unknown_receipt_fails_validator_before_resume(bad):
    from rules_engine.entry_counters import entry_counter_context_matches
    state = counter_return()
    data = state.pending_replacement_choice['counter_payload']
    if bad == 'completion-null':
        data['entry_completion_payload'] = None
    elif bad == 'completion-missing':
        data.pop('entry_completion_payload')
    elif bad == 'completion-context-missing':
        data['entry_completion_payload'].pop('__loyalty_return_context')
    elif bad == 'options-null':
        data['entry_options'] = None
    elif bad == 'boolean-controller':
        data['entry_completion_payload']['__loyalty_return_context']['controller'] = True
    else:
        data['entry_completion_payload']['__loyalty_return_context']['unexpected'] = 'unsupported'
    before = serialize_match_snapshot(state)
    assert entry_counter_context_matches(state, data) is False
    assert serialize_match_snapshot(state) == before
    option = state.pending_replacement_choice['options'][0]
    reject(state, 1, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})


@pytest.mark.parametrize('bad', ['unknown', 'null', 'missing'])
def test_resolution_cost_unknown_operation_cannot_fall_through_to_optional_hand_choice(bad):
    state = recycle()
    if bad == 'missing':
        state.pending_mechanic_choice.pop('loyalty_operation')
    else:
        state.pending_mechanic_choice['loyalty_operation'] = None if bad == 'null' else 'unknown'
    reject(state, 1, {'type': 'choose_mechanic', 'card_ids': ['pay-me']})
    assert state.cards['pay-me'].zone == Zone.BATTLEFIELD
    assert state.cards['return-me'].zone == Zone.GRAVEYARD


def test_counter_actor_hints_are_pure_and_do_not_publish_retained_frames_or_private_hand():
    state = counter_return()
    put(state, 'private-hand-card', Zone.HAND)
    before = serialize_match_snapshot(state)
    for _ in range(2):
        actor = RulesEngine().legal_moves(state, 1)
        assert actor and all(move['type'] == 'choose_replacement' for move in actor)
        encoded = json.dumps(actor)
        assert 'private-hand-card' not in encoded
        assert 'counter_payload' not in encoded and '__loyalty_return_context' not in encoded
        assert 'resolving_item' not in encoded
        assert RulesEngine().legal_moves(state, 2) == []
        assert serialize_match_snapshot(state) == before


def test_unknown_native_frame_fields_cannot_be_echoed_into_both_counter_receipts():
    from rules_engine.entry_counters import entry_counter_context_matches
    state = counter_return()
    data = state.pending_replacement_choice['counter_payload']
    for packet in (data['entry_completion_payload'], data['entry_options']):
        packet['__resolving_item']['unknown'] = 'unsupported'
        packet['__loyalty_return_context']['frame']['unknown'] = 'unsupported'
    before = serialize_match_snapshot(state)
    assert entry_counter_context_matches(state, data) is False
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('bad', ['boolean-reference', 'malformed-announced'])
def test_cost_retained_receipt_tamper_rejected_before_sacrifice(bad):
    state = recycle()
    payload = state.pending_mechanic_choice['effect_payload']
    if bad == 'boolean-reference':
        payload['target_reference']['incarnation'] = False
        payload['__resolving_item']['payload']['effects'][0]['payload']['target_reference']['incarnation'] = False
    else:
        payload['__resolving_item']['payload']['__announced_targets'] = []
    reject(state, 1, {'type': 'choose_mechanic', 'card_ids': ['pay-me']})
    assert state.cards['pay-me'].zone == Zone.BATTLEFIELD
    assert state.cards['return-me'].zone == Zone.GRAVEYARD


def test_new_counter_return_cannot_erase_both_contexts_to_claim_legacy_omission():
    from rules_engine.entry_counters import entry_counter_context_matches
    state = counter_return()
    data = state.pending_replacement_choice['counter_payload']
    for packet in (data['entry_completion_payload'], data['entry_options']):
        packet.pop('__loyalty_return_context')
        packet.pop('loyalty_operation')
    before = serialize_match_snapshot(state)
    assert entry_counter_context_matches(state, data) is False
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('bad', ['echoed-frame-id', 'null-operation', 'unknown-operation'])
def test_counter_return_receipt_must_match_native_pending_frame_and_operation(bad):
    from rules_engine.entry_counters import entry_counter_context_matches
    state = counter_return()
    data = state.pending_replacement_choice['counter_payload']
    for packet in (data['entry_completion_payload'], data['entry_options']):
        if bad == 'echoed-frame-id':
            packet['__resolving_item']['id'] = 'not-the-popped-frame'
            packet['__loyalty_return_context']['frame']['id'] = 'not-the-popped-frame'
        else:
            packet['loyalty_operation'] = None if bad == 'null-operation' else 'unknown'
    before = serialize_match_snapshot(state)
    assert entry_counter_context_matches(state, data) is False
    assert serialize_match_snapshot(state) == before
