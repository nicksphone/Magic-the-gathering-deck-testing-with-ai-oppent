"""Desired paid canonical ETB contracts; missing public mode witnesses stay RED."""
import hashlib
import json
import os
from pathlib import Path

import pytest

import domain_paid_support as g
from game_state.state import Step, Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.targeting import stack_object_kind

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / 'evidence'
PHASE = os.environ.get('ADMISSION_PHASE')
SOURCE = 'Suncleanser'
MODES = {
    'creature': "Remove all counters from target creature. It can't have counters put on it for as long as this creature remains on the battlefield.",
    'player': "Target opponent loses all counters. That player can't get counters for as long as this creature remains on the battlefield.",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


@pytest.fixture(scope='module')
def facts():
    proof = json.loads((HERE / 'provenance.json').read_text())
    raws = {}
    for name, row in proof['cards'].items():
        raw = json.loads((HERE / row['file']).read_text())
        assert raw['name'] == name and raw['id'] == row['id']
        assert digest(raw) == row['canonical_hash']
        raws[name] = raw
    assert raws[SOURCE]['id'] == '3644df41-b690-4581-ac7d-c85cec75411f'
    assert digest(raws[SOURCE]) == '85411b480f87089ea55e466d60b00d05575f1dd07ad67c9ff73790d614e431df'
    if PHASE:
        with (OUT / (PHASE + '-facts.json')).open('x') as stream:
            json.dump(proof, stream, indent=2, sort_keys=True)
    return raws


def record(label, state, **observed):
    if not PHASE:
        return
    with (OUT / (PHASE + '-' + label + '.json')).open('x') as stream:
        json.dump({'snapshot': serialize_match_snapshot(state), 'observed': observed}, stream, indent=2, sort_keys=True)


def cold(state):
    packet = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(packet)))
    assert serialize_match_snapshot(restored) == packet
    return restored


def paid(state, facts, actor, name, pool, **targets):
    state = g.respond(state, actor)
    cid = g.add(state, facts, name, actor, Zone.HAND)
    state.players[actor].mana_pool = dict(pool)
    state = g.cast(state, actor, cid, **targets)
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.players[actor].mana_pool.values()) == 0
    item = next(item for item in state.stack if item.source_card_id == cid)
    assert item.controller == actor and stack_object_kind(state, item) == 'spell'
    assert item.payload['mana_spent'] == sum(pool.values())
    g.resolve(state)
    return state, cid


def drain(state):
    for _ in range(8):
        if not state.stack:
            return state
        assert not state.pending_trigger_order and not state.pending_mechanic_choice
        g.resolve(state)
    raise AssertionError('Bounded fixture trigger drain exceeded')


def advance_main(state, actor):
    for _ in range(96):
        if state.active_player == actor and state.step == Step.PRECOMBAT_MAIN and not state.stack:
            return g.respond(state, actor)
        seat = state.priority_player
        moves = g.RulesEngine().legal_moves(state, seat)
        assert not state.pending_trigger_order and not state.pending_mechanic_choice
        if any(move['type'] == 'attack' for move in moves):
            state = g.act(state, seat, 'attack', attackers=[])
        elif any(move['type'] == 'block' for move in moves):
            state = g.act(state, seat, 'block', blocks={})
        else:
            assert any(move['type'] == 'pass_priority' for move in moves)
            state = g.act(state, seat, 'pass_priority')
    raise AssertionError('Bounded public turn advancement exceeded')


def prepare(facts, seat, mode):
    actor = seat if mode == 'creature' else 3-seat
    state = g.position(facts, actor)
    if mode == 'creature':
        target = g.add(state, facts, 'Monastery Swiftspear', 3-seat)
        state, _ = paid(state, facts, seat, 'Battlegrowth', {'G': 1}, target_card_id=target)
        assert state.cards[target].counters['+1/+1'] == 1
    else:
        target = actor
        state, _ = paid(state, facts, actor, 'Toph, Earthbending Master', {'C': 3, 'G': 1})
        land = g.add(state, facts, 'Forest', actor, Zone.HAND)
        state = g.act(g.respond(state, actor), actor, 'play_land', card_id=land)
        drain(state)
        assert state.players[target].counters['experience'] == 1
        state = advance_main(state, seat)
    return state, target


def count(state, mode, target):
    if mode == 'creature':
        return sum(value for key, value in state.cards[target].counters.items() if not key.startswith('__'))
    player = state.players[target]
    return player.poison + sum(player.counters.values())


def placement(state, facts, seat, mode, target):
    if mode == 'creature':
        state, _ = paid(state, facts, seat, 'Battlegrowth', {'G': 1}, target_card_id=target)
    else:
        state = advance_main(state, target)
        land = g.add(state, facts, 'Forest', target, Zone.HAND)
        state = g.act(state, target, 'play_land', card_id=land)
        drain(state)
        state = advance_main(state, seat)
    return cold(state)


def placement_before_etb_resolution(state, facts, seat, mode, target):
    depth = len(state.stack)
    if mode == 'creature':
        state, _ = paid(state, facts, seat, 'Battlegrowth', {'G': 1}, target_card_id=target)
    else:
        land = g.add(state, facts, 'Forest', target, Zone.HAND)
        state = g.respond(state, target)
        spiral = g.add(state, facts, 'Growth Spiral', target, Zone.HAND)
        state.players[target].mana_pool = {'G': 1, 'U': 1}
        state = g.cast(state, target, spiral)
        assert state.cards[spiral].zone == Zone.STACK
        assert sum(state.players[target].mana_pool.values()) == 0
        item = next(item for item in state.stack if item.source_card_id == spiral)
        assert item.controller == target and stack_object_kind(state, item) == 'spell'
        assert item.payload['mana_spent'] == 2
        assert g.resolve_top_of_stack(state) is False
        pending = state.pending_mechanic_choice
        assert pending and pending['kind'] == 'land_from_hand' and land in pending['options']
        assert pending['resolving_item']['source_card_id'] == spiral
        state = g.act(state, target, 'choose_mechanic', card_ids=[land])
        assert state.cards[spiral].zone == Zone.GRAVEYARD
        assert not state.pending_mechanic_choice
        for _ in range(8):
            if len(state.stack) == depth:
                break
            assert len(state.stack) > depth
            g.resolve(state)
        assert state.cards[land].zone == Zone.BATTLEFIELD
    assert len(state.stack) == depth
    return cold(state)


def public_mode_options(offered, seat, mode):
    result = []
    printed = ' '.join(MODES[mode].split()).rstrip('.')
    for move in offered:
        if move['type'] != 'choose_mechanic' or move.get('player_id') != seat:
            continue
        labels = move.get('option_labels', {})
        for option in move.get('options', []):
            if isinstance(option, str) and ' '.join(str(labels.get(option, '')).split()).rstrip('.') == printed:
                result.append(option)
    return result


def choose_public(state, source, seat, mode, target, label):
    offered = g.RulesEngine().legal_moves(state, seat)
    record(label + '-actual-public-boundary', state, source=source, offered=offered,
           desired_mode=MODES[mode], canonical_source=state.cards[source].oracle_text)
    matches = public_mode_options(offered, seat, mode)
    assert len(matches) == 1, 'Desired explicit modal ETB public witness absent or ambiguous'
    # Submit the existing typed ABI with an actual actor-visible server option ID.
    state = g.act(state, seat, 'choose_mechanic', choice_id=matches[0])
    choices = g.RulesEngine().legal_moves(state, seat)
    key = 'target_card_id' if mode == 'creature' else 'target_player'
    valid = [move for move in choices if move['type'] == 'choose_trigger_target' and move.get(key) == target]
    assert len(valid) == 1, 'Desired selected-mode public target witness absent or ambiguous'
    return state, valid[0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('control', ['creature-counter', 'player-counter', 'paid-source', 'paid-suppression'])
def test_independent_actual_paid_fixture_causes(facts, seat, control):
    mode = 'player' if control == 'player-counter' else 'creature'
    state, target = prepare(facts, seat, mode)
    assert count(state, mode, target) == 1
    if control == 'paid-source':
        state, source = paid(state, facts, seat, SOURCE, {'C': 1, 'W': 1})
        assert state.cards[source].zone == Zone.BATTLEFIELD
    elif control == 'paid-suppression':
        state, source = paid(state, facts, seat, 'Dress Down', {'C': 1, 'U': 1})
        drain(state)
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert printed_abilities_suppressed(state, target)
        assert count(state, mode, target) == 1
    record('control-' + control + '-' + str(seat), state, counter_count=count(state, mode, target))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['creature', 'player'])
@pytest.mark.parametrize('scenario', ['remove-ban-leave', 'departure-before-resolution',
    'suppressed-before-entry', 'suppressed-after-resolution', 'invalid-atomic', 'protected-atomic'])
def test_desired_complete_paid_suncleanser_family(facts, seat, mode, scenario):
    label = scenario + '-' + mode + '-' + str(seat)
    state, target = prepare(facts, seat, mode)
    original = count(state, mode, target)
    if scenario == 'suppressed-before-entry':
        state, suppression = paid(state, facts, seat, 'Dress Down', {'C': 1, 'U': 1})
        drain(state)
    if scenario == 'protected-atomic':
        if mode == 'player':
            state = advance_main(state, target)
            state, _ = paid(state, facts, target, 'Leyline of Sanctity', {'C': 2, 'W': 2})
            state = advance_main(state, seat)
        else:
            protector = g.add(state, facts, 'Sylvan Safekeeper', 3-seat)
            land = g.add(state, facts, 'Forest', 3-seat)
            state = g.respond(state, 3-seat)
            state = g.act(state, 3-seat, 'activate_ability', card_id=protector, ability_index=0,
                          targets={'target_card_id': target}, payment_choices={'sacrifice_card_ids': [land]})
            drain(state)
            assert state.cards[land].zone == Zone.GRAVEYARD
    state, source = paid(state, facts, seat, SOURCE, {'C': 1, 'W': 1})
    assert state.cards[source].zone == Zone.BATTLEFIELD
    incarnation = object_incarnation(state.cards[source])
    assert count(state, mode, target) == original, 'No counter removal before real ETB resolution'
    query = {'target_card_id': target} if mode == 'creature' else {'target_player': target}
    assert not counter_placement_forbidden(state, '+1/+1' if mode == 'creature' else 'experience', **query)
    if scenario == 'suppressed-before-entry':
        assert printed_abilities_suppressed(state, source)
        assert not any(item.source_card_id == source for item in state.stack)
        assert count(state, mode, target) == original
        state, _ = paid(state, facts, seat, 'Abrupt Decay', {'B': 1, 'G': 1}, target_card_id=suppression)
        assert state.cards[suppression].zone == Zone.GRAVEYARD
        state = placement(state, facts, seat, mode, target)
        assert count(state, mode, target) > original
        record(label + '-final', state, no_etb_ban=True)
        return
    if scenario == 'protected-atomic' and mode == 'player':
        offered = g.RulesEngine().legal_moves(state, seat)
        record(label + '-actual-public-boundary', state, offered=offered, protected_opponent=target)
        lawful = public_mode_options(offered, seat, 'creature')
        assert len(lawful) == 1, 'Desired lawful alternative mode public witness absent'
        assert not public_mode_options(offered, seat, 'player')
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            g.act(state, seat, 'choose_mechanic', choice_id='missing-public-mode-id')
        assert serialize_match_snapshot(state) == before
        record(label + '-final', state, protected_mode_rejected_atomic=True)
        return
    control_target = source if scenario == 'protected-atomic' else target
    state, valid = choose_public(cold(state), source, seat, mode, control_target, label)
    if scenario in {'invalid-atomic', 'protected-atomic'}:
        bad = dict(valid)
        key = 'target_card_id' if mode == 'creature' else 'target_player'
        bad[key] = ('missing-object' if mode == 'creature' else seat) if scenario == 'invalid-atomic' else target
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            g.act(state, seat, bad['type'], **{k: v for k, v in bad.items() if k != 'type'})
        assert serialize_match_snapshot(state) == before
        record(label + '-final', state, invalid_write_atomic=True)
        return
    state = g.act(state, seat, valid['type'], **{k: v for k, v in valid.items() if k != 'type'})
    if scenario == 'departure-before-resolution':
        state = placement_before_etb_resolution(state, facts, seat, mode, target)
        assert count(state, mode, target) > original
        state, _ = paid(state, facts, seat, 'Long Goodbye', {'C': 1, 'B': 1}, target_card_id=source)
        assert state.cards[source].zone == Zone.GRAVEYARD
    else:
        assert object_incarnation(state.cards[source]) == incarnation
    drain(state)
    assert count(state, mode, target) == 0
    if scenario == 'departure-before-resolution':
        state = placement(state, facts, seat, mode, target)
        assert count(state, mode, target) > 0
    else:
        if scenario == 'suppressed-after-resolution':
            state, _ = paid(state, facts, seat, 'Frogify', {'C': 1, 'U': 1}, target_card_id=source)
            assert printed_abilities_suppressed(state, source)
        state = placement(state, facts, seat, mode, target)
        assert count(state, mode, target) == 0, 'Resolved duration survives ability loss, not source departure'
        state, _ = paid(state, facts, seat, 'Long Goodbye', {'C': 1, 'B': 1}, target_card_id=source)
        assert state.cards[source].zone == Zone.GRAVEYARD
        state = placement(state, facts, seat, mode, target)
        assert count(state, mode, target) > 0
    record(label + '-final', state, removed_all=True, real_duration=True)
