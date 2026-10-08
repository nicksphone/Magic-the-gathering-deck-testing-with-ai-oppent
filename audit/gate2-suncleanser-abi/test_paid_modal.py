"""Independent public paid actions; original desired32 stay unchanged."""
from copy import deepcopy
import json

import pytest
import test_suncleanser_desired as s
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_match
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.action_validation import ActionRejected
from rules_engine.modal_entry import compile_instruction
from training.environment import TrainingEnvironment

facts = s.facts


def source_entry(state, facts, seat):
    state = s.g.respond(state, seat)
    cid = s.g.add(state, facts, s.SOURCE, seat, s.Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = s.g.cast(state, seat, cid)
    assert state.cards[cid].zone == s.Zone.STACK
    item = next(item for item in state.stack if item.source_card_id == cid)
    assert item.payload['mana_spent'] == 2 and sum(state.players[seat].mana_pool.values()) == 0
    for _ in range(2):
        state = s.g.act(state, state.priority_player, 'pass_priority')
    assert state.cards[cid].zone == s.Zone.BATTLEFIELD
    assert state.pending_mechanic_choice['kind'] == 'entry_mode'
    return state, cid


def select(state, seat, mode, target):
    frame_id = state.pending_mechanic_choice['__stack_id']
    before_queries = serialize_match_snapshot(state)
    moves = s.g.RulesEngine().legal_moves(state, seat)
    assert len(moves) == 1 and not any(key.startswith('__') for key in moves[0])
    assert 'stack_id' not in moves[0]
    env = TrainingEnvironment()
    env._state = state
    view = dict(moves[0])
    view['choice_id'] = s.public_mode_options(moves, seat, mode)[0]
    result = env.lookup_intent(view, seat=seat)
    assert result['action']['type'] == 'choose_mechanic' and result['action']['choice_id'] == view['choice_id']
    public = serialize_match(state)
    assert '__continuation' not in json.dumps(public)
    assert serialize_match_snapshot(state) == before_queries
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        s.g.act(state, 3-seat, 'choose_mechanic', choice_id=view['choice_id'])
    with pytest.raises(ActionRejected):
        s.g.act(state, seat, 'choose_mechanic', choice_id='not-a-mode')
    assert serialize_match_snapshot(state) == before
    state = s.cold(state)
    state = s.g.act(state, seat, 'choose_mechanic', choice_id=view['choice_id'])
    key = 'target_card_id' if mode == 'creature' else 'target_player'
    target_move = next(move for move in s.g.RulesEngine().legal_moves(state, seat)
                       if move['type'] == 'choose_trigger_target' and move.get(key) == target)
    assert target_move['stack_id'] == frame_id
    state = s.g.act(state, seat, 'choose_trigger_target', stack_id=frame_id, **{key: target})
    return s.cold(state)


def resolved(facts, seat, mode):
    state, target = s.prepare(facts, seat, mode)
    state, source = source_entry(state, facts, seat)
    assert s.count(state, mode, target) == 1
    state = select(state, seat, mode, target)
    s.drain(state)
    assert s.count(state, mode, target) == 0
    assert len(state.retained_counter_prohibitions) == 1
    return s.cold(state), source, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['creature', 'player'])
@pytest.mark.parametrize('scenario', ['resolved-abilityloss-leave', 'before-resolution', 'two-sources', 'snapshot'])
def test_paid_retained_lifetime(facts, seat, mode, scenario):
    if scenario == 'before-resolution':
        state, target = s.prepare(facts, seat, mode)
        state, source = source_entry(state, facts, seat)
        state = select(state, seat, mode, target)
        state, _ = s.paid(state, facts, seat, 'Long Goodbye', {'C': 1, 'B': 1}, target_card_id=source)
        assert state.cards[source].zone == s.Zone.GRAVEYARD
        s.drain(state)
        assert s.count(state, mode, target) == 0 and not state.retained_counter_prohibitions
        state = s.placement(state, facts, seat, mode, target)
        assert s.count(state, mode, target) > 0
    else:
        state, source, target = resolved(facts, seat, mode)
        if scenario == 'snapshot':
            packet = serialize_match_snapshot(state)
            state = deserialize_match_snapshot(deepcopy(packet))
            detached = serialize_match_snapshot(state)
            detached['retained_counter_prohibitions'][0]['source_ref']['incarnation'] += 1
            assert serialize_match_snapshot(state) == packet
            legacy = deepcopy(packet)
            legacy.pop('retained_counter_prohibitions')
            assert deserialize_match_snapshot(legacy).retained_counter_prohibitions == []
            query = {'target_card_id': target} if mode == 'creature' else {'target_player': target}
            assert counter_placement_forbidden(state, 'arbitrary-physical-counter', **query)
        else:
            sources = [source]
            if scenario == 'two-sources':
                state, other = source_entry(state, facts, seat)
                state = select(state, seat, mode, target)
                s.drain(state)
                assert len(state.retained_counter_prohibitions) == 2
                sources.append(other)
            else:
                state, _ = s.paid(state, facts, seat, 'Frogify', {'C': 1, 'U': 1}, target_card_id=source)
                s.record('frogify-before-assert-' + mode + '-' + str(seat), state)
                assert s.printed_abilities_suppressed(state, source)
            state = s.placement(state, facts, seat, mode, target)
            assert s.count(state, mode, target) == 0
            for index, cid in enumerate(sources):
                state, _ = s.paid(state, facts, seat, 'Long Goodbye', {'C': 1, 'B': 1}, target_card_id=cid)
                state = s.placement(state, facts, seat, mode, target)
                assert (s.count(state, mode, target) > 0) == (index == len(sources)-1)
    s.record('new-' + scenario + '-' + mode + '-' + str(seat), state,
             independent_public_paid=True, no_manual_retained_frame=True)


@pytest.mark.parametrize('fault', ['null', 'version', 'bool', 'unknown', 'xor', 'bad-ref', 'duplicate', 'controller'])
def test_actual_paid_frame_snapshot_rejects_malformed(facts, fault):
    state, _, _ = resolved(facts, 1, 'creature')
    packet = serialize_match_snapshot(state)
    rows = packet['retained_counter_prohibitions']
    if fault == 'null':
        packet['retained_counter_prohibitions'] = None
    elif fault == 'duplicate':
        rows.append(deepcopy(rows[0]))
    elif fault == 'version':
        rows[0]['version'] = 2
    elif fault == 'bool':
        rows[0]['source_ref']['incarnation'] = True
    elif fault == 'unknown':
        rows[0]['unknown'] = 0
    elif fault == 'xor':
        rows[0]['target_player'] = 2
    elif fault == 'bad-ref':
        rows[0]['target_ref'].pop('zone_change_sequence')
    else:
        rows[0]['trigger_controller'] = 3
    with pytest.raises(ValueError):
        deserialize_match_snapshot(packet)


@pytest.mark.parametrize('suffix', [' Draw a card.', '\nUnknown.', '\n\u2022 Draw a card.', ' unless you pay {1}.'])
def test_complete_printed_body_unknown_suffix(facts, suffix):
    text = facts[s.SOURCE]['oracle_text']
    assert len(compile_instruction(text)) == 2
    assert compile_instruction(text + suffix) is None
    assert compile_instruction(text.replace('for as long as', 'until')) is None
