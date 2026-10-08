"""Paid turn protection boundaries, plus explicitly labeled serializer/compiler checks."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from game_state.state import MatchFactory, Zone, object_incarnation, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_keywords
from rules_engine.targeting import spell_cant_be_countered, stack_object_kind
from rules_engine.turn_spell_protection import compile_instruction
import test_brainstorm_desired as brain
from test_veil_paid_response_audit import add_veil, priority, resolve_frame, add_unsummon, VEIL

FIX=Path(__file__).parent/'fixtures'
RAW={name:json.loads((FIX/path).read_text()) for name,path in {
    'Fatal Push':'veil_turn_protection/fatal-push.json',
    'Thoughtseize':'veil_turn_protection/thoughtseize.json',
    'Cloudshift':'favor_target_lifecycle/cloudshift.json',
    'Monastery Swiftspear':'empty_hand_attack_witness/monastery-swiftspear.json',
    'Twincast':'canonical_magecraft_audit/twincast.json',
}.items()}

def add_raw(state,name,seat):
    row=RAW[name]; sample=MatchFactory.from_decks([{**row,'card_name':name,'quantity':1}],[],seed=4)
    card=deepcopy(next(iter(sample.cards.values())))
    card.id=state.allocate_object_id();card.owner=card.controller=seat;card.move_to_zone(Zone.HAND)
    state.cards[card.id]=card;state.players[seat].hand.append(card.id)
    assert card.oracle_text==row['oracle_text']
    return card.id

def veil(state,seat,restore):
    source=add_veil(state,seat);state=priority(state,seat)
    state,frame=brain.cast(state,seat,source,{'G':1})
    state=resolve_frame(brain.cold(state) if restore else state,frame)
    assert seat in state.turn_spell_protection
    return state

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
@pytest.mark.parametrize('case',['later-spell','later-permanent','blink-permanent','cleanup',
                                 'black-draw','black-permanent','black-player','ability-not-spell'])
def test_paid_turn_protection_lifecycle(seat,restore,case):
    state=brain.position(seat);opponent=3-seat
    target=brain.add(state,'Twinshot Sniper',seat,Zone.BATTLEFIELD)
    if case in {'black-draw','black-permanent'}:
        target=add_raw(state,'Monastery Swiftspear',seat)
        state.players[seat].hand.remove(target);state.players[seat].battlefield.append(target)
        state.cards[target].move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state,target)
    if case=='black-player':
        # A real instant Veil during the opponent's main phase, not a sorcery timing override.
        state.active_player=opponent
    if case=='black-draw':
        state=priority(state,opponent);push=add_raw(state,'Fatal Push',opponent)
        # Independent real paid control: this same target dies without Veil.
        control,control_frame=brain.cast(state,opponent,push,{'B':1},{'target_card_id':target})
        control=resolve_frame(control,control_frame)
        assert control.cards[target].zone==Zone.GRAVEYARD
        state,frame=brain.cast(state,opponent,push,{'B':1},{'target_card_id':target})
        library=list(state.players[seat].library)
        state=veil(state,seat,restore)
        assert state.players[seat].library==library[:-1]
        assert state.spell_color_history[opponent]=={'B'}
        state=resolve_frame(state,frame)
        assert state.cards[target].zone==Zone.BATTLEFIELD
        return
    state=veil(state,seat,restore)
    if case=='later-spell':
        state=priority(state,seat);source=brain.add(state,'Brainstorm',seat,Zone.HAND)
        state,protected=brain.cast(state,seat,source,{'U':1});state=priority(state,opponent)
        counter=brain.add(state,'Counterspell',opponent,Zone.HAND)
        state,frame=brain.cast(state,opponent,counter,{'U':2},{'target_stack_id':protected})
        state=resolve_frame(brain.cold(state) if restore else state,frame)
        assert any(i.id==protected for i in state.stack)
        return
    if case=='ability-not-spell':
        state=priority(state,seat);source=brain.add(state,'Twinshot Sniper',seat,Zone.HAND)
        state.players[seat].mana_pool={'C':1,'R':1}
        state=brain.act(state,seat,{'type':'activate_ability','card_id':source,'ability_index':0,
                                  'targets':{'target_player':opponent}})
        item=next(i for i in state.stack if i.source_card_id==source)
        assert stack_object_kind(state,item)=='activated'
        assert not spell_cant_be_countered(state,item)
        assert state.spell_color_history[seat]=={'G'}
        return
    if case=='cleanup':
        turn=state.turn;state=brain.advance(state,lambda s:s.turn>turn)
        assert not state.turn_spell_protection and not state.turn_player_hexproof
        assert not any(k.startswith('hexproof from') for k in effective_keywords(state,target))
        assert state.spell_color_history=={1:set(),2:set()}
        return
    if case=='black-player':
        state=priority(state,opponent);spell=add_raw(state,'Thoughtseize',opponent)
        state.players[opponent].mana_pool={'B':1};before=serialize_match_snapshot(state)
        assert state.active_player==opponent and not state.stack
        with pytest.raises(ActionRejected):
            brain.act(state,opponent,{'type':'cast_spell','card_id':spell,'targets':{'target_player':seat}})
        assert serialize_match_snapshot(state)==before
        return
    if case=='black-permanent':
        state=priority(state,opponent);spell=add_raw(state,'Fatal Push',opponent)
        state.players[opponent].mana_pool={'B':1};before=serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            brain.act(state,opponent,{'type':'cast_spell','card_id':spell,'targets':{'target_card_id':target}})
        assert serialize_match_snapshot(state)==before
        return
    if case=='blink-permanent':
        state=priority(state,seat);old=object_incarnation(state.cards[target])
        blink=add_raw(state,'Cloudshift',seat)
        state,frame=brain.cast(state,seat,blink,{'W':1},{'target_card_id':target})
        state=resolve_frame(state,frame)
        assert object_incarnation(state.cards[target])>old
    else:
        state=priority(state,seat);target=brain.add(state,'Twinshot Sniper',seat,Zone.HAND)
        state,frame=brain.cast(state,seat,target,{'C':3,'R':1})
        state=brain.advance(state,lambda s:not s.stack)
        assert state.cards[target].zone==Zone.BATTLEFIELD
    assert not any(k.startswith('hexproof from') for k in effective_keywords(state,target))
    state=priority(state,opponent);bounce=add_unsummon(state,opponent)
    state,frame=brain.cast(state,opponent,bounce,{'U':1},{'target_card_id':target})
    state=resolve_frame(brain.cold(state) if restore else state,frame)
    assert state.cards[target].zone==Zone.HAND

@pytest.mark.parametrize('suffix',[' Then invent a reward.',' If a missing condition holds.',
                                   ' You may choose a hidden extra result.'])
def test_compiler_unknown_complete_tail_has_no_partial_reward(suffix):
    key,payload=compile_instruction(VEIL['oracle_text']+suffix)
    assert key=='noop' and payload['__unsupported_instruction']

@pytest.mark.parametrize('field,value',[
    ('spell_color_history',{'1':['U','U'],'2':[]}),('spell_color_history',{'1':['blue'],'2':[]}),
    ('spell_color_history',{'1':[]}),('spell_color_history',{'1':[],'2':[],'3':[]}),
    ('spell_color_history',None),('spell_color_history_known',1),
    ('turn_spell_protection',[True]),('turn_spell_protection',[1,1]),
    ('turn_player_hexproof',{'1':['blue','blue']}),('turn_player_hexproof',{'3':['blue']}),
    ('turn_player_hexproof',{'1':['U']}),('turn_player_hexproof',None),
])
def test_new_serializer_protocol_rejects_malformed_fields(field,value):
    packet=serialize_match_snapshot(brain.position(1)); packet[field]=value
    with pytest.raises(ValueError):deserialize_match_snapshot(packet)

@pytest.mark.parametrize('seat',[1,2])
def test_real_cast_legacy_snapshot_missing_history_is_explicitly_unknown(seat):
    state=brain.position(seat);source=brain.add(state,'Brainstorm',seat,Zone.HAND)
    state,_=brain.cast(state,seat,source,{'U':1});packet=serialize_match_snapshot(state)
    packet.pop('spell_color_history');packet.pop('spell_color_history_known')
    restored=deserialize_match_snapshot(packet)
    assert not restored.spell_color_history_known
    packet=serialize_match_snapshot(restored);rebuilt=deserialize_match_snapshot(packet)
    assert serialize_match_snapshot(rebuilt)==packet

@pytest.mark.parametrize('seat',[1,2])
def test_legacy_unknown_history_resolution_rejects_without_partial_reward(seat):
    state=brain.position(seat);opponent=3-seat
    protected=brain.add(state,'Brainstorm',seat,Zone.HAND)
    state,protected_frame=brain.cast(state,seat,protected,{'U':1})
    state=priority(state,opponent);counter=brain.add(state,'Counterspell',opponent,Zone.HAND)
    state,_=brain.cast(state,opponent,counter,{'U':2},{'target_stack_id':protected_frame})
    state=priority(state,seat)
    packet=serialize_match_snapshot(state);packet.pop('spell_color_history');packet.pop('spell_color_history_known')
    state=deserialize_match_snapshot(packet);source=add_veil(state,seat)
    state,_=brain.cast(state,seat,source,{'G':1})
    state=brain.act(state,seat,{'type':'pass_priority'})
    before=serialize_match_snapshot(state)
    with pytest.raises(ActionRejected,match='color history'):
        brain.act(state,opponent,{'type':'pass_priority'})
    assert serialize_match_snapshot(state)==before
    assert not state.turn_spell_protection and state.cards[source].zone==Zone.STACK

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
def test_real_opponent_spell_copy_not_protected_by_physical_source_controller(seat,restore):
    state=veil(brain.position(seat),seat,restore);opponent=3-seat
    state=priority(state,seat);source=brain.add(state,'Brainstorm',seat,Zone.HAND)
    state,original=brain.cast(state,seat,source,{'U':1});state=priority(state,opponent)
    before={item.id for item in state.stack};twincast=add_raw(state,'Twincast',opponent)
    state,frame=brain.cast(state,opponent,twincast,{'U':2},{'target_stack_id':original})
    state=resolve_frame(state,frame)
    copies=[item for item in state.stack if item.id not in before]
    assert len(copies)==1
    copied=copies[0]
    assert copied.controller==opponent and copied.source_card_id==source
    assert stack_object_kind(state,copied)=='spell'
    assert not spell_cant_be_countered(state,copied)
    assert spell_cant_be_countered(state,next(item for item in state.stack if item.id==original))
    state=priority(brain.cold(state) if restore else state,seat)
    counter=brain.add(state,'Counterspell',seat,Zone.HAND)
    state,frame=brain.cast(state,seat,counter,{'U':2},{'target_stack_id':copied.id})
    state=resolve_frame(state,frame)
    assert all(item.id!=copied.id for item in state.stack)
    assert any(item.id==original for item in state.stack)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
@pytest.mark.parametrize('replacement',['reflection','dredge'])
def test_paid_conditional_draw_replacement_finishes_before_protection(seat,restore,replacement):
    state=brain.position(seat);opponent=3-seat
    if replacement=='reflection':
        reflection=brain.add(state,'Thought Reflection',seat,Zone.HAND)
        state,frame=brain.cast(state,seat,reflection,{'C':4,'U':3})
        state=resolve_frame(state,frame)
        assert state.cards[reflection].zone==Zone.BATTLEFIELD
    else:
        # Canonical graveyard fixture; the draw/replacement and all spell frames are real.
        imp=brain.add(state,'Stinkweed Imp',seat,Zone.GRAVEYARD)
    state=priority(state,seat);protected=brain.add(state,'Brainstorm',seat,Zone.HAND)
    state,original=brain.cast(state,seat,protected,{'U':1})
    state=priority(state,opponent);counter=brain.add(state,'Counterspell',opponent,Zone.HAND)
    state,counter_frame=brain.cast(state,opponent,counter,{'U':2},{'target_stack_id':original})
    state=priority(state,seat);source=add_veil(state,seat)
    library=list(state.players[seat].library);hand=set(state.players[seat].hand)-{source}
    state,frame=brain.cast(state,seat,source,{'G':1})
    state=brain.cold(state) if restore else state
    state=brain.advance(state,lambda s:bool(s.pending_mechanic_choice) or
                        all(i.id!=frame for i in s.stack))
    if replacement=='dredge':
        assert state.pending_mechanic_choice['kind']=='draw'
        assert imp in state.pending_mechanic_choice['options']
        assert not state.turn_spell_protection and not state.turn_player_hexproof
        state=brain.act(brain.cold(state) if restore else state,seat,
                        {'type':'choose_mechanic','choice_id':imp})
        assert state.players[seat].library==library[:-5]
        assert set(state.players[seat].hand)==hand|{imp}
        assert all(state.cards[cid].zone==Zone.GRAVEYARD for cid in library[-5:])
    else:
        assert state.players[seat].library==library[:-2]
        assert set(state.players[seat].hand)==hand|set(library[-2:])
    assert not state.pending_mechanic_choice
    assert state.cards[source].zone==Zone.GRAVEYARD
    assert seat in state.turn_spell_protection and state.turn_player_hexproof[seat]=={'blue','black'}
    assert any(i.id==original for i in state.stack)
    state=resolve_frame(brain.cold(state) if restore else state,counter_frame)
    assert any(i.id==original for i in state.stack)
