"""NEW24: canonical paid Force/Twincast; strict public noncreature copy choices."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest
import domain_paid_support as paid
import test_paid_preflight as original
from game_state.state import Zone, object_incarnation
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine

basefacts = original.facts
SOURCE = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['GAP6_EVIDENCE'])


@pytest.fixture(scope='module')
def facts(basefacts):
    rows = deepcopy(basefacts)
    raw = json.loads((SOURCE/'backend/tests/fixtures/coupled_targets/twincast.json').read_bytes())
    assert raw['object'] == 'card' and raw['name'] == 'Twincast'
    assert raw['mana_cost'] == '{U}{U}'
    assert raw['oracle_text'] == 'Copy target instant or sorcery spell. You may choose new targets for the copy.'
    rows['Twincast'] = raw
    before = deepcopy(rows)
    yield rows
    assert rows == before


@pytest.fixture(autouse=True)
def receipts(request):
    rows = []
    yield rows
    (OUT/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()+'.json')).write_text(
        json.dumps({'node':request.node.nodeid, 'observations':rows}, indent=2, sort_keys=True)+'\n')


def note(rows, label, state, **details):
    rows.append({'label':label, 'stack':[{'id':f.id, 'source':f.source_card_id,
        'effect':f.effect_key, 'payload':deepcopy(f.payload), 'targets':list(f.targets)} for f in state.stack],
        'pending':deepcopy(state.pending_mechanic_choice),
        'snapshot_sha256':hashlib.sha256(json.dumps(serialize_match_snapshot(state),sort_keys=True).encode()).hexdigest(),
        **details})


def passes(state):
    for _ in range(2):
        state = paid.act(state, state.priority_player, 'pass_priority')
    return state


def position(facts, seat, count, rows):
    state, source, targets, _, ids = original.setup(facts, seat, 'Force of Vigor', count)
    new = (paid.add(state, facts, "Witch's Oven", 3-seat),
           paid.add(state, facts, 'Intangible Virtue', 3-seat))
    before = serialize_match_snapshot(state)
    input_state = state
    state = original.cast(state, seat, source, targets)
    assert serialize_match_snapshot(input_state) == before
    assert state.cards[source].zone == Zone.STACK and len(state.stack) == 1
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.stack[-1].payload['__announced_targets']['target_card_ids'] == list(ids[:count])
    original_id = state.stack[-1].id
    note(rows, 'actual-paid-force', state, cost_before=before['players'][str(seat)]['mana_pool']
         if str(seat) in before['players'] else before['players'][seat]['mana_pool'],
         canonical_body=facts['Force of Vigor']['oracle_text'])
    return state, source, original_id, ids, new


def copied(state, facts, seat, original_id, rows):
    twincast = paid.add(state, facts, 'Twincast', seat, Zone.HAND)
    state.players[seat].mana_pool = {'U':2}
    offered = next(m for m in RulesEngine().legal_moves(state, seat)
                   if m['type'] == 'cast_spell' and m['card_id'] == twincast)
    assert original_id in json.dumps(offered), 'Upstream: real Twincast must publicly target original spell'
    before = serialize_match_snapshot(state)
    input_state = state
    state = paid.act(state, seat, 'cast_spell', card_id=twincast,
                     targets={'target_stack_id':original_id})
    assert serialize_match_snapshot(input_state) == before
    assert state.cards[twincast].zone == Zone.STACK and len(state.stack) == 2
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.stack[-1].effect_key == 'copy_spell'
    note(rows, 'actual-paid-twincast', state, canonical_body=facts['Twincast']['oracle_text'],
         input_unchanged=True)
    state = passes(paid.restore(state))
    copies = [f for f in state.stack if f.payload.get('__copied_from_stack_id') == original_id]
    assert len(copies) == 1, 'Upstream: paid Twincast must create exactly one real copied ID'
    copy_id = copies[0].id
    assert copy_id != original_id and copies[0].payload['__stack_copy_kind'] == 'spell'
    note(rows, 'actual-created-copy', state, copy_id=copy_id, original_id=original_id)
    return state, twincast, copy_id


def public_choice(state, seat, copy_id, selection, rows):
    pending = state.pending_mechanic_choice
    assert pending and pending['kind'] == 'copy_target', 'Copy defect: missing public noncreature retarget menu'
    assert pending['player_id'] == seat and pending['stack_id'] == copy_id
    assert selection in pending['options'], 'Copy defect: legal noncreature choice absent from public options'
    offered = next(m for m in RulesEngine().legal_moves(state, seat) if m['type'] == 'choose_mechanic')
    assert selection in offered['options']
    before = serialize_match_snapshot(state)
    state = paid.act(state, seat, 'choose_mechanic', card_ids=[selection])
    note(rows, 'public-copy-choice', state, selection=selection, before_sha256=original.inv.canonical_hash(before))
    return paid.restore(state)


def retained_choices_if_exposed(state, seat, copy_id, rows):
    # This witness checks retained references only, NOT public retarget admission.
    for _ in range(2):
        if state.pending_mechanic_choice is None:
            return state
        state = public_choice(state, seat, copy_id, 'keep', rows)
    assert state.pending_mechanic_choice is None
    return state


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[0,1,2])
def test_actual_paid_force_zero_one_two(facts, seat, count, receipts):
    state, source, _, ids, new = position(facts, seat, count, receipts)
    state = passes(paid.restore(state))
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    assert [state.cards[cid].zone for cid in ids[:2]] == [
        Zone.GRAVEYARD if i<count else Zone.BATTLEFIELD for i in range(2)]
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in new)
    note(receipts, 'force-resolved', state)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[0,1,2])
def test_paid_twincast_zero_or_public_keep(facts, seat, count, receipts):
    state, source, original_id, ids, new = position(facts, seat, count, receipts)
    original_frame = deepcopy(state.stack[0].payload)
    state, twin, copy_id = copied(state, facts, seat, original_id, receipts)
    for _ in range(count):
        state = public_choice(state, seat, copy_id, 'keep', receipts)
    assert state.pending_mechanic_choice is None
    assert next(f for f in state.stack if f.id==original_id).payload == original_frame
    assert state.cards[twin].zone == Zone.GRAVEYARD
    state = passes(paid.restore(state))
    assert len(state.stack) == 1 and state.stack[0].id == original_id
    state = passes(paid.restore(state))
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in new)
    note(receipts, 'copy-and-original-resolved', state)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[1,2])
def test_paid_copy_retargets_actual_noncreature_objects(facts, seat, count, receipts):
    state, source, original_id, ids, new = position(facts, seat, count, receipts)
    before = deepcopy(state.stack[0].payload)
    state, twin, copy_id = copied(state, facts, seat, original_id, receipts)
    for target in new[:count]:
        state = public_choice(state, seat, copy_id, 'target_card_id:'+target, receipts)
    frame = next(f for f in state.stack if f.id==copy_id)
    assert frame.payload['__announced_targets']['target_card_ids'] == list(new[:count])
    assert next(f for f in state.stack if f.id==original_id).payload == before
    state = passes(paid.restore(state))
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in new[:count])
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in ids[:count])
    state = passes(paid.restore(state))
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in ids[:count])
    assert not state.stack and state.cards[source].zone == state.cards[twin].zone == Zone.GRAVEYARD
    note(receipts, 'changed-copy-and-original-resolved', state)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[1,2])
def test_actual_paid_response_departure_preserves_retained_references(facts, seat, count, receipts):
    state, source, original_id, ids, new = position(facts, seat, count, receipts)
    state, twin, copy_id = copied(state, facts, seat, original_id, receipts)
    state = retained_choices_if_exposed(state, seat, copy_id, receipts)
    ref = deepcopy(next(f for f in state.stack if f.id==copy_id).payload['__announced_target_references'])
    response = paid.add(state, facts, 'March of Otherworldly Light', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'C':1,'W':1}
    state = paid.respond(state, 3-seat)
    state = original.cast(state, 3-seat, response, {'x_value':1,'target_card_id':ids[0]})
    assert len(state.stack) == 3 and sum(state.players[3-seat].mana_pool.values()) == 0
    state = passes(paid.restore(state))
    assert state.cards[ids[0]].zone == Zone.EXILE
    assert next(f for f in state.stack if f.id==copy_id).payload['__announced_target_references'] == ref
    state = passes(paid.restore(state))
    assert state.cards[ids[0]].zone == Zone.EXILE
    assert state.cards[ids[1]].zone == (Zone.GRAVEYARD if count==2 else Zone.BATTLEFIELD)
    state = passes(paid.restore(state))
    assert not state.stack and all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in new)
    assert state.cards[source].zone == state.cards[twin].zone == state.cards[response].zone == Zone.GRAVEYARD
    note(receipts, 'paid-response-copy-original-resolved', state, retained_references=ref,
         boundary='retained references, not certification of public retarget menu')


@pytest.mark.parametrize('seat',[1,2])
def test_invalid_noncreature_copy_change_is_atomic(facts, seat, receipts):
    state, _, original_id, ids, _ = position(facts, seat, 1, receipts)
    state, _, copy_id = copied(state, facts, seat, original_id, receipts)
    pending = state.pending_mechanic_choice
    assert pending and pending['kind']=='copy_target', 'Copy defect: missing menu before invalid-choice witness'
    assert pending['stack_id']==copy_id and 'target_card_id:'+ids[2] not in pending['options']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        paid.act(state, seat, 'choose_mechanic', card_ids=['target_card_id:'+ids[2]])
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
def test_changed_noncreature_reference_and_child_identity_are_fresh(facts, seat, receipts):
    state, _, original_id, ids, new = position(facts, seat, 1, receipts)
    old_ref = deepcopy(state.stack[0].payload['__announced_target_references'])
    state, _, copy_id = copied(state, facts, seat, original_id, receipts)
    state = public_choice(state, seat, copy_id, 'target_card_id:'+new[0], receipts)
    frame = next(f for f in state.stack if f.id==copy_id)
    expected = {'card_id':new[0], 'incarnation':object_incarnation(state.cards[new[0]]),
                'zone_change_sequence':state.cards[new[0]].zone_change_sequence}
    assert frame.payload['__announced_target_references']['targets']['target_card_ids'] == [expected]
    child = frame.payload['effects'][0]['payload']
    assert child['target_card_id']==new[0] and child['__target_incarnation']==expected['incarnation']
    assert child['__target_zone_sequence']==expected['zone_change_sequence']
    assert next(f for f in state.stack if f.id==original_id).payload['__announced_target_references']==old_ref
    note(receipts, 'changed-reference-proof', state, expected_reference=expected)
