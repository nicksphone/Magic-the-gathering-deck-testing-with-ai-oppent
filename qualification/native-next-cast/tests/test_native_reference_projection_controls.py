"""Native non-intrinsic entry receipts; real checked responses, no recaptured refs."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_combat_stats
from rules_engine.entry_counters import entry_counter_context_matches
from rules_engine.move_generator import legal_moves
from rules_engine.next_creature_entry_trigger import digest, binding_matches
from test_native_next_creature_entry import SOURCES, RESPONSES, source_ready, choose_type, finish_entry
from tests.test_graveyard_self_activation_product import ROWS, raw_card, act, snapshot
from tests.test_resident_entry_counter_provider import RENATA, resident


def record(request, **data):
    target = Path(os.environ['MTG_NATIVE_REFERENCE_CONTROLS']) / (
        hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    with target.open('x') as stream:
        json.dump({'node': request.node.nodeid, **data}, stream, indent=2, sort_keys=True)


def armed(seat, family, subtype):
    state, _ = source_ready(seat, family)
    if family == SOURCES[0]:
        state = choose_type(state, seat, subtype)
    return state


def until_pending(state):
    for _ in range(16):
        if state.pending_replacement_choice:
            return state
        assert state.stack
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('No real entry replacement within16 actions')


def resolve_one(state):
    count = len(state.stack)
    for _ in range(8):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
        if len(state.stack) < count:
            return state
    raise AssertionError('Actual response did not resolve within8 passes')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', SOURCES)
def test_native_only_pending_restore_wrong_actor_and_exact_projection(request, seat, family):
    state = armed(seat, family, 'bear')
    resident(state, RENATA, seat)
    root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']) / 'backend/tests/fixtures/global_flash_timing_audit'
    recipient = raw_card(state, json.loads((root / 'grizzly-bears.json').read_text()), seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 1}
    state.replacement_choice_players = {seat}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': recipient.id, 'targets': {}})
    paid = snapshot(state)
    state = until_pending(state)
    pending = deepcopy(state.pending_replacement_choice)
    receipt = pending['counter_payload']['__next_entry_counter']
    assert receipt['kind'] == 'native_spell_bound'
    assert state.cards[recipient.id].zone == Zone.STACK
    assert not state.cards[recipient.id].counters.get('+1/+1')
    assert len(pending['options']) == 2
    assert not any(option['operation'] == 'intrinsic_entry' for option in pending['options'])
    before = snapshot(state)
    restored = deserialize_match_snapshot(before)
    assert snapshot(restored) == before
    assert entry_counter_context_matches(restored, pending['counter_payload'])
    assert snapshot(restored) == before
    native = next(option for option in pending['options'] if option.get('next_entry_producer') is True)
    assert native['operation'] == 'add' and type(native['operand']) is int and native['operand'] == 1
    assert native['entry_producer'] is True and native['clause'] is None
    assert len(receipt['bindings']) == 1
    binding = receipt['bindings'][0]
    assert binding_matches(binding)
    assert native['source_id'] == binding['frame']['id'] + ':entry-producer'
    assert native['instruction_ref'] == digest(binding)
    publication = binding['frame']['payload']['__native_publication']
    assert publication['stack_id'] == binding['frame']['id']
    assert publication['cast']['stack_id'] == receipt['frame_id']
    assert publication['cast']['reference'] == receipt['reference']
    assert publication['source_pre'] == binding['frame']['payload']['__native_creation']['__entry_origin']['publication']
    action = {'type': 'choose_replacement', 'replacement_source_id': native['source_id']}
    with pytest.raises(ActionRejected):
        act(restored, 3-seat, action)
    assert snapshot(restored) == before
    result = finish_entry(act(restored, seat, action), seat)
    assert result.cards[recipient.id].zone == Zone.BATTLEFIELD
    assert result.cards[recipient.id].counters['+1/+1'] == 2
    assert effective_combat_stats(result, recipient.id) == (4, 4)
    assert not result.pending_entry_counters and not result.pending_replacement_choice
    repeat = finish_entry(act(deserialize_match_snapshot(before), seat, action), seat)
    assert snapshot(repeat) == snapshot(result)
    record(request, paid=paid, pending=before, final=snapshot(result))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', SOURCES)
def test_actual_counter_self_return_recast_recipient_aba_rejects_old_context(request, seat, family):
    state = armed(seat, family, 'skeleton')
    resident(state, RENATA, seat)
    root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']) / 'backend/tests/fixtures/global_flash_timing_audit'
    raw_card(state, json.loads((root / 'vedalken-orrery.json').read_text()), seat, Zone.BATTLEFIELD)
    recipient = raw_card(state, ROWS['Sanitarium Skeleton'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'B': 1}
    state.replacement_choice_players = {seat}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': recipient.id, 'targets': {}})
    original_spell, original_bind = deepcopy(state.stack[-2:])
    paid = snapshot(state)
    # A separate real resolution branch yields the retained context; no fabricated frame.
    pending_branch = until_pending(deserialize_match_snapshot(paid))
    retained = deepcopy(pending_branch.pending_replacement_choice['counter_payload'])
    counter = raw_card(state, RESPONSES['Counterspell'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': counter.id,
                             'targets': {'target_stack_id': original_spell.id}})
    state = resolve_one(state)
    assert state.cards[recipient.id].zone == Zone.GRAVEYARD
    assert state.stack[-1].id == original_bind.id
    state.players[seat].mana_pool = {'B': 1, 'C': 2}
    offers = [move for move in legal_moves(state, seat)
              if move['type'] == 'activate_ability' and move.get('card_id') == recipient.id]
    assert len(offers) == 1
    state = act(state, seat, {'type': 'activate_ability', 'card_id': recipient.id,
                             'ability_index': offers[0]['ability_index']})
    state = resolve_one(state)
    assert state.cards[recipient.id].zone == Zone.HAND
    state.players[seat].mana_pool = {'B': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': recipient.id, 'targets': {}})
    assert state.stack[-1].id != original_spell.id
    assert sum(item.effect_key == 'bind_creature_spell_entry_counter' for item in state.stack) == 1
    before = snapshot(state)
    assert not entry_counter_context_matches(state, retained)
    assert snapshot(state) == before
    result = finish_entry(deserialize_match_snapshot(before), seat)
    assert result.cards[recipient.id].zone == Zone.BATTLEFIELD
    # Only the genuinely resident Renata applies to the new object; old native reward cannot transfer.
    assert result.cards[recipient.id].counters['+1/+1'] == 1
    assert effective_combat_stats(result, recipient.id) == (2, 3)
    assert not result.pending_entry_counters and not result.pending_replacement_choice
    record(request, original_paid=paid, old_pending=snapshot(pending_branch),
           actual_recast=before, final=snapshot(result))
