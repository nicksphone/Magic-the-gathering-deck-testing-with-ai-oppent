"""Synthetic malformed input probes, NOT rewritten canonical cards or positive witnesses."""
from copy import deepcopy
import pytest
import test_paid_edges as e
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_power
from game_state.state import Zone, Step

basefacts=e.basefacts
facts=e.facts
action_receipt=e.action_receipt
NAMES=['Archangel of Wrath','Springheart Nantuko','Suncleanser','The Wandering Emperor','Veil of Summer','Volatile Stormdrake']

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('style',['bare','parenthetical'])
def test_actual_malformed_paid_body_no_partial_reward(facts,name,seat,style,request):
    c=e.c
    derived=deepcopy(facts)
    tail='\nThen perform an unspecified operation.' if style=='bare' else ' (Then perform an unspecified operation.)'
    derived[name]['oracle_text']+=tail
    context=derived[name]
    labels=known_unsupported_mechanics(context['oracle_text'],card_name=name,canonical_context=context)
    assert labels,'Malformed complete body must retain an admission diagnostic'
    if name=='Suncleanser':state,target=c.sun.prepare(facts,seat,'creature')
    else:
        state=c.g.position(facts,seat)
        target=e.add(state,facts,'Raging Goblin',3-seat if name=='Volatile Stormdrake' else seat,Zone.BATTLEFIELD)
    if name=='The Wandering Emperor':state.active_player=3-seat;state.step=Step.END_STEP
    if name=='Veil of Summer':
        bounce=e.add(state,facts,'Unsummon',3-seat)
        state,frame=c.paid(state,3-seat,bounce,{'U':1},{'target_card_id':target})
    source=e.add(state,derived,name,seat)
    pool={
        'Archangel of Wrath':{'C':2,'W':2,'B':1,'R':1},'Springheart Nantuko':{'C':1,'G':1},
        'Suncleanser':{'C':1,'W':1},'The Wandering Emperor':{'C':2,'W':2},
        'Veil of Summer':{'G':1},'Volatile Stormdrake':{'C':1,'U':1},
    }[name]
    state=c.priority(state,seat);state.players[seat].mana_pool=dict(pool)
    targets={'target_card_id':target} if name=='Springheart Nantuko' else {}
    choice='kicker_1_2' if name=='Archangel of Wrath' else 'bestow' if name=='Springheart Nantuko' else 'base'
    action={'type':'cast_spell','card_id':source,'cost_choice':{'id':choice},'targets':targets}
    before=c.snapshot(state);library=list(state.players[seat].library)
    host_power=effective_power(state,target)
    try:state=c.act(state,seat,action)
    except ActionRejected:
        assert c.snapshot(state)==before
        c.record(request,state,name,['malformed actual action rejected atomically'],
                 synthetic_probe=True,style=style,actual_body=context['oracle_text'],labels=labels)
        return
    frame=next(i.id for i in state.stack if i.source_card_id==source)
    assert sum(state.players[seat].mana_pool.values())==0
    assert next(i for i in state.stack if i.id==frame).payload['mana_spent']==sum(pool.values())
    state=e.frame_done(state,frame)
    if name=='Veil of Summer':
        c.record(request,state,name,['malformed paid response observed'],synthetic_probe=True,
                 style=style,actual_body=context['oracle_text'],labels=labels)
        assert state.players[seat].library==library
        assert not state.turn_spell_protection and not state.turn_player_hexproof
        return
    if name=='Springheart Nantuko':
        land=e.add(state,facts,'Forest',seat)
        state=e.land_boundary(state,seat,land)
        state.players[seat].mana_pool={'C':1,'G':1}
    elif name=='The Wandering Emperor':
        state=c.priority(state,seat)
        activate={'type':'activate_loyalty','card_id':source,'ability_index':1,'targets':{}}
        try:state=c.act(state,seat,activate)
        except ActionRejected:
            c.record(request,state,name,['malformed loyalty rejected'],synthetic_probe=True,
                     style=style,actual_body=context['oracle_text'],labels=labels)
            return
    for _ in range(24):
        if not state.stack and not state.pending_trigger_order and not state.pending_mechanic_choice:break
        if state.pending_mechanic_choice:
            kind=state.pending_mechanic_choice['kind']
            moves=c.offers(state,seat)
            if kind=='entry_mode':
                options=c.sun.public_mode_options(moves,seat,'creature');assert len(options)==1
                state=c.act(state,seat,{'type':'choose_mechanic','choice_id':options[0]})
            elif kind=='exchange_energy_payment':
                assert any('decline' in m.get('options',[]) for m in moves)
                state=c.act(state,seat,{'type':'choose_mechanic','choice_id':'decline'})
            else:state=e.optional(state,seat,True)
        elif state.pending_trigger_order:
            if name=='Springheart Nantuko':state=e.optional(state,seat,True)
            else:
                state=c.choose_target(state,seat,{'target_card_id':target} if name in {'Suncleanser','Volatile Stormdrake'} else {'target_player':3-seat})
        else:state=c.act(state,state.priority_player,{'type':'pass_priority'})
    else:raise AssertionError('24 real public continuation bound')
    c.record(request,c.cold(state),name,['malformed paid effect observed'],synthetic_probe=True,
             style=style,actual_body=context['oracle_text'],labels=labels)
    if name=='Archangel of Wrath':assert state.players[seat].life==state.players[3-seat].life==20
    elif name=='Springheart Nantuko':assert not e.tokens(state,seat) and effective_power(state,target)==host_power
    elif name=='Suncleanser':assert c.sun.count(state,'creature',target)==1 and not state.retained_counter_prohibitions
    elif name=='The Wandering Emperor':assert not e.tokens(state,seat)
    else:
        assert state.players[seat].counters.get('energy',0)==0
        assert state.cards[source].controller==seat and state.cards[target].controller==3-seat
