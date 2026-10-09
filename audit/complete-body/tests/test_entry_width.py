"""Actual offered width/optional/private contracts, not canonical Ugin or optimality.

Calls the unchanged trusted hand-entry producer to construct explicit menus.
Latency values observe agent calls under this guard; no attribution/threshold claim.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import time
import pytest
import test_loyalty_entry_lifecycle as e
from ai.agent import AIAgent
from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.loyalty_instructions import reference_matches
from rules_engine.optional_reveal import public_choice


def setup(seat, cards, targets):
    state=e.position(seat)
    for i in range(targets):
        e.raw_card(state,e.AURAS['Llanowar Elves'],seat if i%2==0 else 3-seat,Zone.BATTLEFIELD)
    auras=[e.raw_card(state,e.AURAS[('Octopus Umbra','Pacifism')[i%2]],seat,Zone.HAND).id
           for i in range(cards)]
    hidden=e.raw_card(state,e.AURAS['Colossal Dreadmaw'],3-seat,Zone.HAND)
    return state,auras,hidden.id


def select(state, seat, receipts):
    before=serialize_match_snapshot(state)
    pending=deepcopy(state.pending_mechanic_choice)
    assert pending and pending['player_id']==seat
    rules=RulesEngine()
    offered=next(m for m in rules.legal_moves(state,seat) if m.get('type')=='choose_mechanic')
    assert not any(m.get('type')=='choose_mechanic' for m in rules.legal_moves(state,3-seat))
    public=public_choice(pending)
    assert 'option_references' not in public and 'effect_payload' not in public
    if pending['kind']=='loyalty_cards':
        assert 'options' not in public and 'option_labels' not in public
    opaque, _=decision_view(state,3-seat,[])
    for cid in state.players[seat].hand:
        assert not opaque.cards[cid].name and not opaque.cards[cid].oracle_text
    started=time.monotonic()
    decision=AIAgent(archetype='Midrange').choose_action(state,[offered],seat)
    elapsed=time.monotonic()-started
    action=decision.action
    assert action['type']=='choose_mechanic'
    if pending['kind']=='loyalty_cards':
        ids=action['card_ids']
        assert 0<=len(ids)<=offered['count'] and len(ids)==len(set(ids))
        assert all(cid in offered['options'] and cid in state.players[seat].hand
                   and reference_matches(state,cid,pending['option_references'].get(cid)) for cid in ids)
    else:
        assert pending['kind']=='loyalty_attachment'
        cid=action['choice_id']
        assert cid in offered['options'] and reference_matches(state,cid,pending['option_references'].get(cid))
        assert pending['entry_card_id'] in state.players[seat].hand
    encoded=json.dumps(action)
    assert all(cid not in encoded for cid in state.players[3-seat].hand+state.players[3-seat].library)
    assert serialize_match_snapshot(state)==before
    result=checked_action(state,rules,seat,action)
    assert serialize_match_snapshot(state)==before
    receipts.append({'kind':pending['kind'],'offered_count':len(offered['options']),
                     'count_limit':offered.get('count'),'action':action,
                     'agent_seconds':elapsed,'reason':decision.reasoning})
    return result,action


def finish(state, seat, receipts, *, restore=True):
    for _ in range(12):
        if not state.pending_mechanic_choice:
            assert not state.stack and not state.pending_replacement_choice and not state.pending_trigger_order
            return state
        if restore:state=e.cold(state)
        state,_=select(state,seat,receipts)
    raise AssertionError('12 unchanged-producer continuation bound')


def record(request,initial,final,receipts,**scope):
    (Path(os.environ['GAP6_EVIDENCE'])/(request.node.name+'.json')).write_text(json.dumps({
        'node':request.node.nodeid,'scope':scope,'initial':initial,
        'final':serialize_match_snapshot(final),'actual_choices':receipts},indent=2)+'\n')


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('width',[2,16,17])
@pytest.mark.parametrize('limit',[0,2])
def test_real_optional_multiple_aura_offer_width_progress(seat,width,limit,request):
    state,auras,hidden=setup(seat,width,2)
    resolve_effect(state,seat,'loyalty_hand_entry',{'count':limit})
    assert len(state.pending_mechanic_choice['options'])==width
    initial=serialize_match_snapshot(state);receipts=[]
    state,action=select(e.cold(state),seat,receipts)
    assert len(action['card_ids'])==limit
    chosen=action['card_ids']
    state=finish(state,seat,receipts)
    assert sum(r['kind']=='loyalty_attachment' for r in receipts)==limit
    for cid in auras:
        assert state.cards[cid].zone==(Zone.BATTLEFIELD if cid in chosen else Zone.HAND)
        if cid in chosen:assert state.cards[cid].attached_to in state.cards
    assert state.cards[hidden].zone==Zone.HAND
    record(request,initial,state,receipts,menu_width=width,optional_limit=limit,
           seam='Unchanged trusted hand-entry producer; no canonical Ugin claim')


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('width',[2,16,17])
@pytest.mark.parametrize('restored',[False,True])
def test_real_multiple_aura_attachment_width_private_identity_invariant(seat,width,restored,request):
    state,auras,hidden=setup(seat,2,width)
    state=e.hand_entry(state,seat,auras)
    assert state.pending_mechanic_choice['kind']=='loyalty_attachment'
    assert len(state.pending_mechanic_choice['options'])==width
    initial=serialize_match_snapshot(state)
    alternate=e.cold(state)
    private_ids=[hidden,*alternate.players[3-seat].library]
    for cid in private_ids:
        alternate.cards[cid].name='Unseen replacement'
        alternate.cards[cid].types=['Instant']
        alternate.cards[cid].oracle_text='Counter target spell.'
        alternate.cards[cid].mana_cost='{U}{U}'
    if restored:state=e.cold(state)
    left=[];right=[]
    state=finish(state,seat,left,restore=restored)
    alternate=finish(alternate,seat,right,restore=restored)
    assert len(left)==len(right)==2
    assert [r['action'] for r in left]==[r['action'] for r in right]
    assert all(cid not in json.dumps([r['action'] for r in left]) for cid in private_ids)
    for cid in auras:
        assert state.cards[cid].zone==alternate.cards[cid].zone==Zone.BATTLEFIELD
        assert state.cards[cid].attached_to==alternate.cards[cid].attached_to
    assert state.cards[hidden].zone==alternate.cards[hidden].zone==Zone.HAND
    record(request,initial,state,left,attachment_width=width,restored_each_choice=restored,
           alternate_choices=right,seam='Real two-Aura attachment offers from trusted producer')
