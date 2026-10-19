"""Canonical actual free-cast/control-change producers; no fabricated stack metadata."""
import hashlib,json,os
from pathlib import Path
import pytest
import domain_paid_support as g
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind
from free_owner_support import fund,finish
R=Path(os.environ["MTG_FREE_OWNER_OUTPUT_ROOT"]).resolve()
P=Path(__file__).resolve().parent/"fixtures/native_free_owner"

@pytest.fixture(scope='module')
def facts():
    rows=json.loads((P/'canonical.json').read_bytes())
    pins=json.loads((P/'provenance.json').read_bytes())
    assert len(rows)==18
    for name,raw in rows.items():
        digest=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        assert digest==pins['cards'][name]['canonical_fullrow_sha256']
    return rows

def receipt(request,state,phase,**extra):
    label=hashlib.sha256(request.node.nodeid.encode()).hexdigest()
    (R/'evidence'/f'{label}-{phase}.json').write_text(json.dumps({
        'node':request.node.nodeid,'phase':phase,'actual_complete_root':serialize_match_snapshot(state),**extra},indent=2)+'\n')

@pytest.mark.parametrize('seat',[1,2])
def test_actual_paid_ray_borrowed_abjure_resource_owner_graveyard(facts,seat,request):
    other=3-seat
    state=g.position(facts,other)
    borrowed=g.add(state,facts,'Hapless Researcher',other,Zone.HAND)
    fund(state,other,U=1)
    state=g.cast(state,other,borrowed)
    assert state.stack[-1].payload['mana_spent']==1
    state=finish(state,borrowed)
    assert state.cards[borrowed].zone==Zone.BATTLEFIELD
    bolt=g.add(state,facts,'Lightning Bolt',other,Zone.HAND)
    fund(state,other,R=1)
    state=g.cast(state,other,bolt,target_player=seat)
    sid=state.stack[-1].id
    assert state.stack[-1].payload['mana_spent']==1
    state=g.respond(state,seat)
    ray=g.add(state,facts,'Ray of Command',seat,Zone.HAND)
    fund(state,seat,C=3,U=1)
    state=g.cast(state,seat,ray,target_card_id=borrowed)
    assert state.stack[-1].payload['mana_spent']==4
    state=finish(g.restore(state),ray)
    receipt(request,state,'control-change',paid_source=ray,borrowed=borrowed,original_target_stack_id=sid)
    assert state.cards[borrowed].owner==other and state.cards[borrowed].controller==seat
    assert borrowed in state.players[seat].battlefield and borrowed not in state.players[other].battlefield
    state=g.respond(state,seat)
    owned=g.add(state,facts,'Hapless Researcher',seat)
    source=g.add(state,facts,'Abjure',seat,Zone.HAND)
    fund(state,seat,U=1)
    move=next(m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id')==source)
    proposal={'type':'cast_spell','card_id':source,'targets':{'target_stack_id':sid},
              'cost_choice':{'id':'base','sacrifice_card_ids':[borrowed]}}
    before=serialize_match_snapshot(state)
    paid=checked_action(state,RulesEngine(),seat,proposal)
    assert serialize_match_snapshot(state)==before
    receipt(request,paid,'paid-boundary',actual_action=proposal,actual_pre_cost_root=before,
            actual_pre_payer_reference=before['cards'][borrowed])
    announced=[item for item in paid.stack if item.source_card_id==source
               and stack_object_kind(paid,item)=='spell']
    assert len(announced)==1
    assert announced[0].controller==seat and announced[0].payload['mana_spent']==1
    assert announced[0].payload['__announced_targets']['target_stack_id']==sid
    assert '__announced_target_references' in announced[0].payload
    assert borrowed in paid.players[other].graveyard and borrowed not in paid.players[seat].graveyard
    assert paid.cards[owned].zone==Zone.BATTLEFIELD
    terminal=finish(g.restore(paid),source)
    assert terminal.cards[bolt].zone==Zone.GRAVEYARD and not terminal.stack
    assert terminal.players[seat].life==20
    receipt(request,terminal,'terminal',actual_offered_move=move,actual_action=proposal,actual_paid_root=serialize_match_snapshot(paid))

@pytest.mark.parametrize('seat',[1,2])
def test_actual_paid_gearhulk_free_abjure_still_sacrifices(facts,seat,request):
    other=3-seat
    state=g.position(facts,seat)
    payer=g.add(state,facts,'Hapless Researcher',seat,Zone.HAND)
    fund(state,seat,U=1)
    state=g.cast(state,seat,payer)
    assert state.stack[-1].payload['mana_spent']==1
    state=finish(state,payer)
    state=g.respond(state,other)
    bolt=g.add(state,facts,'Lightning Bolt',other,Zone.HAND)
    fund(state,other,R=1)
    state=g.cast(state,other,bolt,target_player=seat)
    sid=state.stack[-1].id
    assert state.stack[-1].payload['mana_spent']==1
    state=g.respond(state,seat)
    # Declared starting graveyard instant, not a claimed prior discard/cast.
    abjure=g.add(state,facts,'Abjure',seat,Zone.GRAVEYARD)
    gear=g.add(state,facts,'Torrential Gearhulk',seat,Zone.HAND)
    fund(state,seat,C=4,U=2)
    state=g.cast(state,seat,gear)
    assert state.stack[-1].payload['mana_spent']==6
    state=finish(g.restore(state),gear)
    assert state.cards[gear].zone==Zone.BATTLEFIELD
    choices=[]
    for _ in range(24):
        receipt(request,state,'permission-boundary',actual_permission_actions=choices)
        if state.pending_mechanic_choice and state.pending_mechanic_choice['kind']=='effect_cast':break
        pid=state.priority_player
        offered=RulesEngine().legal_moves(state,pid)
        target=next((m for m in offered if m['type']=='choose_trigger_target' and m.get('target_card_id')==abjure),None)
        accept=next((m for m in offered if m['type']=='choose_optional_effect' and m.get('accept') is True),None)
        proposal=target or accept or next((m for m in offered if m['type']=='pass_priority'),None)
        assert proposal is not None,'Native Gearhulk permission has no supported public continuation'
        choices.append({'player':pid,'actual_offered_action':proposal})
        state=checked_action(state,RulesEngine(),pid,proposal)
    else:raise AssertionError('Native Gearhulk did not reach free-cast permission')
    offered=RulesEngine().legal_moves(state,seat)
    receipt(request,state,'free-cast-offer',actual_offered_moves=offered,actual_permission_actions=choices)
    move=next(m for m in offered if m['type']=='cast_spell' and m.get('card_id')==abjure)
    assert move.get('from_graveyard') is True
    proposal={'type':'cast_spell','card_id':abjure,'from_graveyard':True,
              'targets':{'target_stack_id':sid},'cost_choice':{'id':'base','sacrifice_card_ids':[payer]}}
    before=serialize_match_snapshot(state)
    paid=checked_action(state,RulesEngine(),seat,proposal)
    assert serialize_match_snapshot(state)==before
    frame=next(x for x in paid.stack if x.source_card_id==abjure)
    assert stack_object_kind(paid,frame)=='spell' and frame.payload['mana_spent']==0
    assert not any(paid.players[seat].mana_pool.values())
    assert payer in paid.players[seat].graveyard
    terminal=finish(g.restore(paid),abjure)
    assert terminal.cards[bolt].zone==Zone.GRAVEYARD and terminal.players[seat].life==20
    assert terminal.cards[abjure].zone==Zone.EXILE
    assert terminal.cards[gear].zone==Zone.BATTLEFIELD
    receipt(request,terminal,'terminal',actual_offered_move=move,actual_action=proposal,actual_paid_root=serialize_match_snapshot(paid))
