"""NEW independent paid edges. Canonical sources unchanged; no injected frames."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
import test_paid_context_goldens as c
from game_state.state import Step, Zone, object_incarnation
from game_state.serializers import deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_power, effective_toughness, has_keyword, printed_abilities_suppressed
from rules_engine.card_types import is_token_card
from rules_engine.targeting import stack_object_kind

basefacts = c.facts

@pytest.fixture
def facts(basefacts):
    rows = deepcopy(basefacts)
    for relative in ('audit/gate2-stormdrake/qualifier-v2-canonical.json',
                     'audit/gate2-springheart/fixtures/edges/canonical.json'):
        rows.update(json.loads((c.SOURCE/relative).read_bytes()))
    for relative in ('backend/tests/fixtures/global_flash_timing_audit/krosan-grip.json',
                     'backend/tests/fixtures/veil_turn_protection/fatal-push.json',
                     'backend/tests/fixtures/veil_turn_protection/thoughtseize.json',
                     'backend/tests/fixtures/favor_target_lifecycle/cloudshift.json'):
        raw=json.loads((c.SOURCE/relative).read_bytes());rows[raw['name']]=raw
    rows.update(json.loads((c.ROOT/'delta/auxiliary-canonical.json').read_bytes()))
    rows.update({n:r['canonical'] for n,r in c.CANON.items()})
    original=deepcopy(rows)
    yield rows
    assert rows==original

@pytest.fixture(autouse=True)
def action_receipt(request):
    c.ACTIONS.clear()
    yield
    (c.OUT/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()+'-actions.json')).write_text(
        json.dumps({'node':request.node.nodeid,'checked_actions':c.ACTIONS},indent=2)+'\n')

def add(state,facts,name,seat,zone=Zone.HAND):
    return c.g.add(state,facts,name,seat,zone)

def frame_done(state,frame):
    return c.advance(state,lambda s:all(i.id!=frame for i in s.stack))

def response(state,facts,seat,name,pool,targets):
    source=add(state,facts,name,seat)
    state,frame=c.paid(state,seat,source,pool,targets)
    return frame_done(c.cold(state),frame),source

def drain(state):
    return c.advance(state,lambda s:not s.stack)

def reject(state,seat,action):
    before=c.snapshot(state)
    with pytest.raises(ActionRejected):
        result=checked_action(state,c.RULES,seat,action)
        c.ACTIONS.append({'unexpected_acceptance':True,'seat':seat,'action':deepcopy(action),
                          'input_unchanged':c.snapshot(state)==before,
                          'input':before,'output':c.snapshot(result)})
    assert c.snapshot(state)==before

def log(request,state,name,episode):
    c.record(request,c.cold(state),name,['independent actual paid edge'],episode=episode)

def tokens(state,seat):
    return [state.cards[i] for i in state.players[seat].battlefield if is_token_card(state.cards[i])]

def optional(state,seat,pay):
    moves=c.offers(state,seat)
    selected=[m for m in moves if m['type'] in {'choose_optional_effect','choose_mechanic'} and m.get('accept') is pay]
    assert len(selected)==1,'Actual advertised optional action required'
    return c.act(c.cold(state),seat,selected[0])

def land_boundary(state,seat,land):
    state=c.priority(c.cold(state),seat)
    state=c.act(state,seat,{'type':'play_land','card_id':land})
    assert state.cards[land].zone==Zone.BATTLEFIELD
    return state

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('episode',['creature','own-invalid','source-bounce','blink','counter'])
def test_archangel_edges(facts,seat,episode,request):
    state=c.g.position(facts,seat)
    source=add(state,facts,'Archangel of Wrath',seat)
    victim=add(state,facts,'Wall of Omens',seat if episode=='own-invalid' else 3-seat,Zone.BATTLEFIELD)
    state,frame=c.paid(state,seat,source,{'C':2,'W':2,'B':1,'R':1},choice='kicker_1_2')
    state=frame_done(state,frame)
    if episode=='own-invalid':
        for _ in range(8):
            moves=c.offers(state,seat)
            if any(m['type']=='choose_trigger_target' for m in moves):break
            order=next(m for m in moves if m['type']=='choose_trigger_order')
            state=c.act(c.cold(state),seat,order)
        else:raise AssertionError('8 actual public order bound')
        selected=next(m for m in c.offers(state,seat) if m['type']=='choose_trigger_target')
        reject(state,seat,{**selected,'target_card_id':state.players[3-seat].library[0], 'target_player':None})
    state=c.choose_target(state,seat,{'target_card_id':victim} if episode in {'creature','own-invalid'} else {'target_player':3-seat})
    assert len(state.stack)==2
    old=object_incarnation(state.cards[source])
    if episode=='source-bounce':
        state,_=response(state,facts,3-seat,'Unsummon',{'U':1},{'target_card_id':source})
        assert state.cards[source].zone==Zone.HAND
    elif episode=='blink':
        state,_=response(state,facts,seat,'Flicker of Fate',{'C':1,'W':1},{'target_card_id':source})
        assert object_incarnation(state.cards[source])!=old and state.cards[source].kicker_count is None
    elif episode=='counter':
        target=state.stack[-1].id
        state,_=response(state,facts,3-seat,'Stifle',{'U':1},{'target_stack_id':target})
        assert len(state.stack)==1
    state=drain(c.cold(state))
    amount=2 if episode=='counter' else 4
    assert state.players[seat].life==20+amount
    if episode in {'creature','own-invalid'}:assert state.cards[victim].zone==Zone.GRAVEYARD
    else:assert state.players[3-seat].life==20-amount
    log(request,state,'Archangel of Wrath',episode)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('episode',['toughness','invalid-host','host-departure','source-departure','copy-LKI','foreign-host'])
def test_springheart_edges(facts,seat,episode,request):
    state=c.g.position(facts,seat)
    host_name='Hopeful Eidolon' if episode=='copy-LKI' else 'Raging Goblin'
    host=add(state,facts,host_name,3-seat if episode=='foreign-host' else seat,Zone.BATTLEFIELD)
    source=add(state,facts,'Springheart Nantuko',seat)
    land=add(state,facts,'Forest',seat)
    power,toughness=effective_power(state,host),effective_toughness(state,host)
    if episode=='invalid-host':
        state.players[seat].mana_pool={'C':1,'G':1}
        reject(state,seat,{'type':'cast_spell','card_id':source,'cost_choice':{'id':'bestow'},'targets':{'target_card_id':land}})
    state,frame=c.paid(state,seat,source,{'C':1,'G':1},{'target_card_id':host},'bestow')
    state=frame_done(state,frame)
    assert state.cards[source].attached_to==host
    assert effective_power(state,host)==power+1 and effective_toughness(state,host)==toughness+1
    state=land_boundary(state,seat,land)
    assert len(state.stack)==1 and state.stack[-1].source_card_id==source
    if episode=='host-departure':
        state,_=response(state,facts,3-seat,'Unsummon',{'U':1},{'target_card_id':host})
        assert state.cards[source].attached_to is None
    elif episode=='source-departure':
        state,_=response(state,facts,3-seat,'Naturalize',{'C':1,'G':1},{'target_card_id':source})
        assert state.cards[source].zone==Zone.GRAVEYARD
    elif episode=='copy-LKI':
        state,_=response(state,facts,3-seat,'Back to Nature',{'C':1,'G':1},{})
        assert state.cards[host].zone==state.cards[source].zone==Zone.GRAVEYARD
    state.players[seat].mana_pool={'C':1,'G':1}
    state=c.advance(c.cold(state),lambda s:s.pending_mechanic_choice or s.pending_trigger_order or not s.stack)
    copy=episode not in {'host-departure','foreign-host'}
    if state.pending_trigger_order or state.pending_mechanic_choice:
        state=optional(state,seat,True)
    state=drain(c.cold(state))
    result=tokens(state,seat);assert len(result)==1
    if copy:
        assert result[0].name==host_name and result[0].oracle_text==facts[host_name]['oracle_text']
        assert sum(state.players[seat].mana_pool.values())==0
    else:
        assert 'Insect' in result[0].type_line and sum(state.players[seat].mana_pool.values())==2
    log(request,state,'Springheart Nantuko',episode)

# Existing causal helpers use actual paid sources/land causes and never inject ETB state.
@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('mode',['creature','player'])
@pytest.mark.parametrize('episode',['multiple-kinds','suppression','before-ETB-departure','after-reentry'])
def test_suncleanser_edges(facts,seat,mode,episode,request):
    state,target=c.sun.prepare(facts,seat,mode)
    if episode=='multiple-kinds':
        if mode=='creature':
            state,_=response(state,facts,seat,'Boon of Safety',{'W':1},{'target_card_id':target})
            if state.pending_mechanic_choice:
                moves=c.offers(state,seat);move=next(m for m in moves if m['type']=='choose_mechanic')
                state=c.act(state,seat,{'type':'choose_mechanic','card_ids':[]})
            assert len([k for k,v in state.cards[target].counters.items() if v and not k.startswith('__')])>=2
        else:
            state=c.sun.advance_main(state,target)
            state,tower=c.sun.paid(state,facts,target,'Dynavolt Tower',{'C':3})
            state,_=response(state,facts,target,'Lightning Bolt',{'R':1},{'target_player':seat})
            state=drain(state)
            c.record(request,c.cold(state),'Suncleanser',['auxiliary paid multiple-counter producer boundary'],
                     episode=episode+'-'+mode,tower_id=tower,
                     tower_body=state.cards[tower].oracle_text)
            assert state.players[target].counters.get('energy',0)>=2
            assert state.players[target].counters.get('experience',0)>=1
            state=c.sun.advance_main(state,seat)
    source=add(state,facts,'Suncleanser',seat)
    state,frame=c.paid(state,seat,source,{'C':1,'W':1})
    state=frame_done(state,frame)
    options=c.sun.public_mode_options(c.offers(state,seat),seat,mode);assert len(options)==1
    state=c.act(c.cold(state),seat,{'type':'choose_mechanic','choice_id':options[0]})
    state=c.choose_target(state,seat,{'target_card_id':target} if mode=='creature' else {'target_player':target})
    if episode=='before-ETB-departure':
        state,_=response(state,facts,seat,'Long Goodbye',{'C':1,'B':1},{'target_card_id':source})
        assert state.cards[source].zone==Zone.GRAVEYARD
    state=drain(c.cold(state));assert c.sun.count(state,mode,target)==0
    if episode=='suppression':
        state,_=response(state,facts,seat,'Frogify',{'C':1,'U':1},{'target_card_id':source})
        assert printed_abilities_suppressed(state,source)
    if episode=='after-reentry':
        old=object_incarnation(state.cards[source])
        state,_=response(state,facts,seat,'Flicker of Fate',{'C':1,'W':1},{'target_card_id':source})
        assert object_incarnation(state.cards[source])!=old
        # The old prohibition must expire even while the new incarnation's ETB is unresolved.
        options=c.sun.public_mode_options(c.offers(state,seat),seat,mode);assert len(options)==1
        state=c.act(state,seat,{'type':'choose_mechanic','choice_id':options[0]})
        state=c.choose_target(state,seat,{'target_card_id':target} if mode=='creature' else {'target_player':target})
        state=c.sun.placement_before_etb_resolution(state,facts,seat,mode,target)
        assert c.sun.count(state,mode,target)>0
    else:
        state=c.sun.placement(c.cold(state),facts,seat,mode,target)
        assert (c.sun.count(state,mode,target)>0) is (episode=='before-ETB-departure')
    log(request,state,'Suncleanser',episode+'-'+mode)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('episode',['next-turn','split-second','suppression','zero-target','invalid-untapped','cleanup-firststrike'])
def test_emperor_edges(facts,seat,episode,request):
    state=c.g.position(facts,seat)
    if episode!='suppression':state.active_player=3-seat;state.step=Step.END_STEP
    source=add(state,facts,'The Wandering Emperor',seat)
    victim=add(state,facts,'Raging Goblin',seat,Zone.BATTLEFIELD)
    state,frame=c.paid(state,seat,source,{'C':2,'W':2})
    state=frame_done(state,frame)
    if episode!='split-second':state=c.priority(c.cold(state),seat)
    action={'type':'activate_loyalty','card_id':source,'ability_index':1,'targets':{}}
    if episode=='next-turn':
        turn=state.turn
        state=c.advance(state,lambda s:s.turn>turn and s.step==Step.UPKEEP)
        state=c.priority(state,seat);reject(state,seat,action)
    elif episode=='split-second':
        artifact=add(state,facts,'Rod of Ruin',seat,Zone.BATTLEFIELD)
        grip=add(state,facts,'Krosan Grip',3-seat)
        state=c.priority(state,3-seat);state.players[3-seat].mana_pool={'C':2,'G':1}
        c.record(request,c.cold(state),'The Wandering Emperor',['auxiliary split-second paid cast boundary'],
                 grip_id=grip,artifact_id=artifact,public_moves=c.offers(state,3-seat))
        state,frame=c.paid(state,3-seat,grip,{'C':2,'G':1},{'target_card_id':artifact})
        state=c.priority(state,seat);reject(state,seat,action)
    elif episode=='suppression':
        moon=add(state,facts,'Imprisoned in the Moon',seat)
        state=c.priority(state,seat);state.players[seat].mana_pool={'C':2,'U':1}
        c.record(request,c.cold(state),'The Wandering Emperor',['auxiliary ability-suppression paid cast boundary'],
                 moon_id=moon,emperor_id=source,public_moves=c.offers(state,seat))
        state,frame=c.paid(state,seat,moon,{'C':2,'U':1},{'target_card_id':source})
        state=frame_done(c.cold(state),frame)
        assert printed_abilities_suppressed(state,source)
        state=c.priority(state,seat);reject(state,seat,action)
    elif episode=='invalid-untapped':
        action.update(ability_index=2,targets={'target_card_id':victim})
        assert not state.cards[victim].tapped;reject(state,seat,action)
    else:
        action.update(ability_index=0,targets={} if episode=='zero-target' else {'target_card_id':victim})
        state=c.act(state,seat,action);assert state.cards[source].loyalty==4
        state=drain(state)
        if episode=='zero-target':assert not state.cards[victim].counters.get('+1/+1')
        else:
            assert has_keyword(state,victim,'first strike') and state.cards[victim].counters['+1/+1']==1
            turn=state.turn;state=c.advance(state,lambda s:s.turn>turn)
            assert not has_keyword(state,victim,'first strike') and state.cards[victim].counters['+1/+1']==1
    log(request,state,'The Wandering Emperor',episode)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('episode',['black-draw','red-no-draw','blue-player','black-ability','red-allowed','own-blue','legacy-unknown','cleanup'])
def test_veil_edges(facts,seat,episode,request):
    opponent=3-seat;state=c.g.position(facts,opponent)
    target=add(state,facts,'Raging Goblin',seat,Zone.BATTLEFIELD)
    source=add(state,facts,'Veil of Summer',seat)
    capsule=None
    if episode=='black-ability':
        capsule=add(state,facts,"Executioner's Capsule",opponent)
        state,frame=c.paid(state,opponent,capsule,{'B':1});state=frame_done(state,frame)
    elif episode=='black-draw':
        state,_=response(state,facts,opponent,'Fatal Push',{'B':1},{'target_card_id':target})
    elif episode=='red-no-draw':
        state,_=response(state,facts,opponent,'Lightning Bolt',{'R':1},{'target_player':seat})
    elif episode in {'own-blue','legacy-unknown'}:
        bounce=add(state,facts,'Unsummon',seat)
        state,frame=c.paid(state,seat,bounce,{'U':1},{'target_card_id':target})
        state=frame_done(state,frame)
    if episode=='legacy-unknown':
        packet=c.snapshot(state);packet.pop('spell_color_history');packet.pop('spell_color_history_known')
        state=deserialize_match_snapshot(packet);assert not state.spell_color_history_known
    library=list(state.players[seat].library)
    state,frame=c.paid(state,seat,source,{'G':1})
    if episode=='legacy-unknown':
        state=c.act(state,state.priority_player,{'type':'pass_priority'})
        reject(state,state.priority_player,{'type':'pass_priority'})
        assert not state.turn_spell_protection and state.cards[source].zone==Zone.STACK
        log(request,state,'Veil of Summer',episode);return
    state=frame_done(state,frame)
    assert state.players[seat].library==(library[:-1] if episode in {'black-draw','black-ability'} else library)
    if episode in {'blue-player','black-ability','red-allowed'}:
        state=c.priority(state,opponent)
        if episode=='blue-player':
            spell=add(state,facts,'Peek',opponent);state.players[opponent].mana_pool={'U':1}
            reject(state,opponent,{'type':'cast_spell','card_id':spell,'targets':{'target_player':seat}})
            state,frame=c.paid(state,opponent,spell,{'U':1},{'target_player':opponent})
            state=frame_done(state,frame)
        elif episode=='red-allowed':
            state,_=response(state,facts,opponent,'Lightning Bolt',{'R':1},{'target_card_id':target})
            assert state.cards[target].zone==Zone.GRAVEYARD
        else:
            own=add(state,facts,'Raging Goblin',opponent,Zone.BATTLEFIELD)
            state.players[opponent].mana_pool={'C':1,'B':1}
            action={'type':'activate_ability','card_id':capsule,'ability_index':0,'targets':{'target_card_id':target}}
            reject(state,opponent,action)
            action['targets']['target_card_id']=own
            state=c.act(state,opponent,action)
            assert state.cards[capsule].zone==Zone.GRAVEYARD and sum(state.players[opponent].mana_pool.values())==0
            assert stack_object_kind(state,state.stack[-1])=='activated'
            state=drain(c.cold(state));assert state.cards[own].zone==Zone.GRAVEYARD and state.cards[target].zone==Zone.BATTLEFIELD
    elif episode=='cleanup':
        turn=state.turn;state=c.advance(state,lambda s:s.turn>turn)
        assert not state.turn_spell_protection and not state.turn_player_hexproof
        assert not has_keyword(state,target,'hexproof from blue')
    log(request,state,'Veil of Summer',episode)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('episode',['activated-shield','triggered-shield','spell-legal','insufficient-energy','source-departure','target-blink'])
def test_stormdrake_edges(facts,seat,episode,request):
    state=c.g.position(facts,seat)
    if episode in {'activated-shield','triggered-shield','spell-legal'}:
        source=add(state,facts,'Volatile Stormdrake',3-seat,Zone.BATTLEFIELD)
        lawful=add(state,facts,'Raging Goblin',3-seat,Zone.BATTLEFIELD)
        if episode=='spell-legal':
            state,_=response(state,facts,seat,'Lightning Bolt',{'R':1},{'target_card_id':source})
            assert state.cards[source].zone==Zone.GRAVEYARD
        elif episode=='activated-shield':
            rod=add(state,facts,'Rod of Ruin',seat)
            state,frame=c.paid(state,seat,rod,{'C':4});state=frame_done(state,frame)
            state.players[seat].mana_pool={'C':3}
            action={'type':'activate_ability','card_id':rod,'ability_index':0,'targets':{'target_card_id':source}}
            reject(state,seat,action);action['targets']['target_card_id']=lawful
            state=c.act(state,seat,action)
            assert state.cards[rod].tapped and sum(state.players[seat].mana_pool.values())==0
            assert stack_object_kind(state,state.stack[-1])=='activated'
            state=drain(state);assert state.cards[lawful].zone==Zone.GRAVEYARD and state.cards[source].zone==Zone.BATTLEFIELD
        else:
            cleanser=add(state,facts,'Suncleanser',seat)
            state,frame=c.paid(state,seat,cleanser,{'C':1,'W':1});state=frame_done(state,frame)
            option=c.sun.public_mode_options(c.offers(state,seat),seat,'creature');assert len(option)==1
            state=c.act(state,seat,{'type':'choose_mechanic','choice_id':option[0]})
            selected=next(m for m in c.offers(state,seat) if m['type']=='choose_trigger_target' and m.get('target_card_id')==lawful)
            reject(state,seat,{**selected,'target_card_id':source})
            state=c.act(state,seat,selected);state=drain(state)
            assert len(state.retained_counter_prohibitions)==1 and state.cards[source].zone==Zone.BATTLEFIELD
    else:
        source=add(state,facts,'Volatile Stormdrake',seat)
        target=add(state,facts,'Atraxa, Grand Unifier' if episode=='insufficient-energy' else 'Raging Goblin',3-seat,Zone.BATTLEFIELD)
        state,frame=c.paid(state,seat,source,{'C':1,'U':1});state=frame_done(state,frame)
        state=c.choose_target(state,seat,{'target_card_id':target})
        if episode=='source-departure':
            state,_=response(state,facts,seat,'Unsummon',{'U':1},{'target_card_id':source})
            state=drain(state);assert state.players[seat].counters.get('energy',0)==0
        elif episode=='target-blink':
            old=object_incarnation(state.cards[target])
            state,_=response(state,facts,seat,'Flicker of Fate',{'C':1,'W':1},{'target_card_id':target})
            assert object_incarnation(state.cards[target])!=old
            state=drain(state);assert state.players[seat].counters.get('energy',0)==0
        else:
            state=c.advance(state,lambda s:s.pending_mechanic_choice or not s.stack)
            assert state.players[seat].counters['energy']==4
            moves=c.offers(state,seat);assert all('pay' not in m.get('options',[]) for m in moves)
            assert any('decline' in m.get('options',[]) for m in moves)
            state=c.act(c.cold(state),seat,{'type':'choose_mechanic','choice_id':'decline'})
            state=drain(state);assert state.cards[target].zone==Zone.GRAVEYARD and target in state.players[3-seat].graveyard
    log(request,state,'Volatile Stormdrake',episode)
