"""Tests-only actual cast/copy/counter sequence with a departed Adventure card."""
import hashlib
import json

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import stack_source_card
from tests.test_multicast_subject_audit import DIRECTORY, add, announce, position, restart
from tests.test_spell_trigger_surface_audit import cards, record


COUNTER = json.loads((DIRECTORY / 'counter-control.jsonl').read_text())
cards.ROWS[COUNTER['name']] = COUNTER


def test_counter_control_is_an_unchanged_real_row():
    meta = json.loads((DIRECTORY / 'counter-provenance.json').read_text())
    assert meta['offline'] and not meta['facts_modified']
    assert hashlib.sha256((DIRECTORY / 'counter-control.jsonl').read_bytes()).hexdigest() == meta['fixture_sha256']
    assert COUNTER['oracle_id'] == meta['rows'][0]['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
def test_played_copy_of_surviving_adventure_copy_uses_its_stack_subject(request, seat):
    state, source = position(seat, 'Bonecrusher Giant // Stomp')
    listener = add(state, 'Storm-Kiln Artist', seat)
    first = add(state, 'Reverberate', seat, Zone.HAND)
    second = add(state, 'Reverberate', seat, Zone.HAND)
    counter = add(state, 'Negate', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    trace = []

    def capture(stage):
        trace.append({'stage': stage, 'snapshot': serialize_match_snapshot(state)})
        record(request, {'trace': trace, 'current': serialize_match_snapshot(state)})

    def act(actor, action):
        nonlocal state
        capture('before ' + repr(action))
        with cards.unchanged_root(state):
            state = checked_action(state, RulesEngine(), actor, action)
        state = restart(state)
        capture('after ' + repr(action))

    def keep_target():
        pending = state.pending_mechanic_choice
        assert pending and pending['kind'] == 'copy_target' and 'keep' in pending['options']
        act(pending['player_id'], {'type': 'choose_mechanic', 'card_ids': ['keep']})

    def resolve():
        nonlocal state
        capture('before resolve_top')
        resolved = resolve_top_of_stack(state)
        assert resolved or state.pending_mechanic_choice or state.pending_trigger_order or state.pending_replacement_choice
        state = restart(state)
        capture('after resolve_top')

    def receive_priority(actor):
        if state.priority_player != actor:
            act(state.priority_player, {'type': 'pass_priority'})
        assert state.priority_player == actor

    state, action = announce(state, seat, source, face=1)
    capture('actual Stomp cast ' + repr(action))
    original = next(item for item in state.stack if item.source_card_id == source.id)
    act(seat, {'type': 'cast_spell', 'card_id': first.id, 'targets': {'target_stack_id': original.id}})
    for _ in range(12):
        copies = [item for item in state.stack if item.payload.get('__stack_copy_kind') == 'spell']
        if copies:
            break
        if state.pending_mechanic_choice:
            keep_target()
        else:
            resolve()
    else:
        pytest.fail('First actual Reverberate copy did not materialize')
    first_copy = copies[0]
    while state.pending_mechanic_choice:
        keep_target()
    receive_priority(3-seat)
    act(3-seat, {'type': 'cast_spell', 'card_id': counter.id, 'targets': {'target_stack_id': original.id}})
    assert state.stack[-1].source_card_id == counter.id
    resolve()
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert state.cards[source.id].types == ['Creature']
    assert stack_source_card(state, first_copy).types == ['Instant']
    capture('countered original; creature card vs surviving Instant copy')
    receive_priority(seat)
    act(seat, {'type': 'cast_spell', 'card_id': second.id, 'targets': {'target_stack_id': first_copy.id}})
    for _ in range(12):
        copies = [item for item in state.stack if item.payload.get('__stack_copy_kind') == 'spell']
        if len(copies) == 2:
            break
        if state.pending_mechanic_choice:
            keep_target()
        else:
            resolve()
    else:
        pytest.fail('Second actual Reverberate copy did not materialize')
    after_copy = serialize_match_snapshot(state)
    for _ in range(24):
        if state.pending_mechanic_choice:
            keep_target()
        elif state.stack:
            resolve()
        else:
            break
    else:
        pytest.fail('Bounded actual copy/counter continuation did not finish')
    treasures = [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].name == 'Treasure']
    record(request, {'trace': trace, 'copy_event_subject_checkpoint': after_copy,
                     'source_id': source.id, 'listener_id': listener.id, 'expected_treasures': 5,
                     'actual_treasures': len(treasures), 'resolved': serialize_match_snapshot(state)})
    assert state.players[3-seat].life == 16
    assert len(treasures) == 5
