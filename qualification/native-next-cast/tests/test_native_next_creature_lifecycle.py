"""Actual paid canonical continuations; constructed positions, not natural games."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, Step, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.move_generator import legal_moves
from rules_engine.next_creature_entry_trigger import NOTE_KIND, history, history_key
from training import TrainingEnvironment
from test_native_next_creature_entry import (
    SOURCES, RESPONSES, source_ready, choose_type, cast_recipient, finish_entry,
)
from tests.test_graveyard_self_activation_product import raw_card, act, snapshot

ROOT = Path(__file__).resolve().parents[1]
FROZEN = Path(os.environ['MTG_ISOLATED_TEST_ROOT']) / 'backend/tests/fixtures'


def canonical(directory, filename):
    return json.loads((FROZEN / directory / filename).read_text())


def record(request, **data):
    target = Path(os.environ['MTG_NATIVE_LIFECYCLE_EVIDENCE']) / (
        hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    with target.open('x') as stream:
        json.dump({'node': request.node.nodeid, **data}, stream, indent=2, sort_keys=True)


def armed(seat, family):
    state, sid = source_ready(seat, family)
    if family == SOURCES[0]:
        state = choose_type(state, seat)
    return state, sid


def next_note(state, seat, limit=128):
    for _ in range(limit):
        if state.pending_mechanic_choice:
            assert state.pending_mechanic_choice['kind'] == 'note_creature_type'
            return state
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Next actual chapter note exceeded128 passes')


@pytest.mark.parametrize('seat', [1, 2])
def test_real_next_chapter_excludes_noted_type_and_restores_history(request, seat):
    state, sid = armed(seat, SOURCES[0])
    first_key = history_key(state.pending_entry_counters[0]['__entry_origin'])
    state = next_note(state, seat)
    assert state.cards[sid].counters['__lore'] == 2
    pending = deepcopy(state.pending_mechanic_choice)
    assert pending['history_key'] == first_key and pending['history_before'] == ['construct']
    assert 'creature-type:construct' not in pending['options']
    assert 'creature-type:elf' in pending['options']
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_mechanic', 'choice_id': 'creature-type:construct'})
    assert snapshot(state) == before
    state = choose_type(deserialize_match_snapshot(before), seat, 'elf')
    assert history(state, first_key) == ['construct', 'elf']
    assert snapshot(deserialize_match_snapshot(snapshot(state))) == snapshot(state)
    record(request, before=before, after=snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_real_source_blink_new_incarnation_can_note_same_type(request, seat):
    state, sid = armed(seat, SOURCES[0])
    prior = deepcopy(state.pending_entry_counters[0])
    old_incarnation = object_incarnation(state.cards[sid])
    raw = canonical('cloudshift_compound_audit', 'flicker-of-fate.json')
    spell = raw_card(state, raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {'W': 1, 'C': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell.id,
                             'targets': {'target_card_id': sid}})
    state = next_note(state, seat, 16)
    assert object_incarnation(state.cards[sid]) != old_incarnation
    assert state.pending_mechanic_choice['history_before'] == []
    assert 'creature-type:construct' in state.pending_mechanic_choice['options']
    state = choose_type(deserialize_match_snapshot(snapshot(state)), seat)
    assert state.pending_entry_counters[0] == prior
    assert len([row for row in state.delayed_triggers if row.get('kind') == NOTE_KIND]) == 2
    state, cid = cast_recipient(state, seat)
    assert sum(i.effect_key == 'bind_creature_spell_entry_counter' for i in state.stack) == 2
    state = finish_entry(state, seat)
    assert state.cards[cid].counters['+1/+1'] == 4
    record(request, after=snapshot(state), old_packet=prior)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_source_departure_does_not_rebind_delayed_instruction(request, seat):
    state, sid = armed(seat, SOURCES[1])
    original = deepcopy(state.pending_entry_counters[0]['__entry_origin'])
    response = raw_card(state, RESPONSES['Unsummon'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': response.id,
                             'targets': {'target_card_id': sid}})
    state = finish_entry(state, seat)
    assert state.cards[sid].zone == Zone.HAND
    assert state.pending_entry_counters[0]['__entry_origin'] == original
    state, cid = cast_recipient(state, seat)
    publication = deepcopy(state.stack[-1].payload['__native_publication'])
    assert publication['source_pre'] == original['publication']
    state = finish_entry(deserialize_match_snapshot(snapshot(state)), seat)
    assert state.cards[cid].counters['+1/+1'] == 3
    record(request, original=original, publication=publication, after=snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', SOURCES)
def test_countered_real_spell_consumes_occurrence_without_transfer(request, seat, family):
    state, _ = armed(seat, family)
    counter = raw_card(state, RESPONSES['Counterspell'], seat, Zone.HAND)
    state, cid = cast_recipient(state, seat)
    original_spell = state.stack[-2]
    state.players[seat].mana_pool = {'U': 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': counter.id,
                             'targets': {'target_stack_id': original_spell.id}})
    paid = snapshot(state)
    state = finish_entry(deserialize_match_snapshot(paid), seat)
    assert state.cards[cid].zone == Zone.GRAVEYARD and not state.pending_entry_counters
    state, next_id = cast_recipient(state, seat)
    assert len(state.stack) == 1
    state = finish_entry(state, seat)
    assert state.cards[next_id].counters['+1/+1'] == 2
    record(request, paid=paid, after=snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', SOURCES)
def test_actual_noncreature_cast_preserves_waiting_packet(request, seat, family):
    state, _ = armed(seat, family)
    waiting = deepcopy(state.pending_entry_counters)
    spell = raw_card(state, canonical('global_flash_timing_audit', 'opt.json'), seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}})
    assert state.pending_entry_counters == waiting and len(state.stack) == 1
    state = finish_entry(state, seat)
    assert state.pending_entry_counters == waiting
    assert state.pending_mechanic_choice['kind'] == 'scry'
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': []})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.pending_entry_counters == waiting
    state, cid = cast_recipient(state, seat)
    state = finish_entry(state, seat)
    assert state.cards[cid].counters['+1/+1'] == 3
    record(request, waiting=waiting, after=snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_actual_flash_creature_does_not_consume_creator_packet(request, seat):
    state, _ = armed(seat, SOURCES[1])
    waiting = deepcopy(state.pending_entry_counters)
    other = 3-seat
    raw_card(state, canonical('global_flash_timing_audit', 'vedalken-orrery.json'), other, Zone.BATTLEFIELD)
    from tests.test_resident_entry_counter_provider import BALLISTA
    card = raw_card(state, BALLISTA, other, Zone.HAND)
    state.players[other].mana_pool = {'C': 4}
    state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, other, {'type': 'cast_spell', 'card_id': card.id, 'targets': {'x_value': 2}})
    assert len(state.stack) == 1 and state.pending_entry_counters == waiting
    state = finish_entry(state, other)
    assert state.cards[card.id].counters['+1/+1'] == 2
    assert state.pending_entry_counters == waiting
    record(request, after=snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_next_turn_cannot_trigger_expired_packet(request, seat):
    state, _ = armed(seat, SOURCES[1])
    waiting_turn = state.turn
    raw_card(state, canonical('global_flash_timing_audit', 'vedalken-orrery.json'), seat, Zone.BATTLEFIELD)
    for _ in range(64):
        if state.turn > waiting_turn and state.step == Step.PRECOMBAT_MAIN:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    else:
        raise AssertionError('Actual next turn exceeded64 priority passes')
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    state, cid = cast_recipient(state, seat)
    assert len(state.stack) == 1
    state = finish_entry(state, seat)
    assert state.cards[cid].counters['+1/+1'] == 2
    record(request, after=snapshot(state), expired_turn=waiting_turn)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['frame', 'history', 'record'])
def test_retained_note_corruption_is_root_atomic(seat, fault):
    state, _ = source_ready(seat, SOURCES[0])
    pending = state.pending_mechanic_choice
    if fault == 'frame':
        pending['resolving_item']['id'] += '-stale'
    elif fault == 'history':
        pending['history_before'] = ['elf']
    else:
        pending['record']['amount'] = 2
    before = snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_mechanic', 'choice_id': 'creature-type:construct'})
    assert snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_two_real_paid_sources_compete_with_explicit_order_and_entry_choices(request, seat):
    from test_mixed_entry_origin_audit import ROWS
    state, sid = armed(seat, SOURCES[0])
    second = raw_card(state, ROWS[SOURCES[0]], seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': second.id, 'targets': {}})
    state = next_note(state, seat, 16)
    state = choose_type(state, seat)
    assert len(state.pending_entry_counters) == 2
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    state, cid = cast_recipient(state, seat)
    pending = deepcopy(state.pending_trigger_order)
    assert pending['current_controller'] == seat
    group = pending['groups'][str(seat)]
    assert len(group) == 2 and {row['source_card_id'] for row in group} == {sid, second.id}
    before = snapshot(state)
    ids = [str(row['_choice_id']) for row in group]
    with pytest.raises(ActionRejected):
        act(state, 3-seat, {'type': 'choose_trigger_order', 'trigger_order': ids})
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_trigger_order', 'trigger_order': ids[:1]})
    assert snapshot(state) == before
    state = act(deserialize_match_snapshot(before), seat,
                {'type': 'choose_trigger_order', 'trigger_order': list(reversed(ids))})
    trace = []
    for _ in range(24):
        if state.pending_replacement_choice:
            trace.append(snapshot(state))
            options = state.pending_replacement_choice['options']
            option = next((o for o in options if o.get('next_entry_producer')), options[0])
            state = act(deserialize_match_snapshot(snapshot(state)), seat,
                        {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
        elif state.stack:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        else:
            break
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].counters['+1/+1'] == 4 and not state.pending_entry_counters
    record(request, group=pending, before=before, per_choice=trace, after=snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_public_whole_view_training_admission_and_privacy(request, seat):
    state, _ = source_ready(seat, SOURCES[0])
    environment = TrainingEnvironment()
    # Only the actual canonical retained state is installed; no forged provenance,
    # reset/restore envelope, or invented source/resolving frame is supplied.
    environment._state = state
    move = legal_moves(state, seat)[0]
    before = snapshot(state)
    observation = environment.observe(seat)
    prompt = environment.prompts(seat)[0]
    assert environment.prompts(3-seat) == []
    assert 'hand' not in observation['players'][str(3-seat)]
    assert not any(key in prompt['hint'] for key in ('record', 'resolving_item', 'history_key'))
    changed = deepcopy(state)
    changed.players[3-seat].library.reverse()
    changed.rng.random()
    changed.log.append('PRIVATE ONLY')
    other = TrainingEnvironment()
    other._state = changed
    assert other.observe(seat) == observation and other.prompts(seat) == environment.prompts(seat)
    intent = {**move, 'choice_id': 'creature-type:construct'}
    try:
        admitted = environment.lookup_intent(intent, seat)
    except ActionRejected as error:
        assert snapshot(state) == before
        record(request, prompt=prompt, move=move, intent=intent,
               error=str(error), actual_snapshot=before)
        raise
    assert admitted['action']['choice_id'] == intent['choice_id']
    assert snapshot(state) == before
    record(request, prompt=prompt, intent=intent, admitted=admitted)
