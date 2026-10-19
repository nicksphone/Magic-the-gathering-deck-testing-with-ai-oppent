"""Actual paid prerequisite closure; parser probes are explicitly synthetic."""
from copy import deepcopy
import hashlib
import json
import pytest
import test_paid_edges as e
from game_state.state import Zone, object_incarnation
from rules_engine.attachments import enchant_restriction, attachment_target_is_legal
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.oracle_effects import infer_target_restrictions, _target_card_matches_restrictions
from rules_engine.player_counters import gain_clause
from rules_engine.type_effects import effective_types

c = e.c
basefacts = e.basefacts
existingfacts = e.facts
action_receipt = e.action_receipt

@pytest.fixture
def facts(existingfacts):
    rows = deepcopy(existingfacts)
    rows.update(json.loads((c.ROOT/'delta/prerequisite-canonical.json').read_bytes()))
    original = deepcopy(rows)
    yield rows
    assert rows == original

def record(request, state, facts, names, **observed):
    restored = c.cold(state)
    receipt = {'node':request.node.nodeid, 'observed':observed,
               'canonical_facts':{n:facts[n] for n in names},
               'checked_actions':c.ACTIONS, 'snapshot':c.snapshot(restored)}
    path = c.OUT/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()+'.json')
    path.write_text(json.dumps(receipt,indent=2)+'\n')

def tap_paid(state, facts, actor, target):
    source = e.add(state,facts,'Icy Manipulator',actor)
    state,frame = c.paid(state,actor,source,{'C':4})
    state = e.frame_done(state,frame)
    state = c.priority(c.cold(state),actor)
    state.players[actor].mana_pool = {'C':1}
    moves = c.offers(state,actor)
    assert any(m['type']=='activate_ability' and m.get('card_id')==source for m in moves)
    state = c.act(state,actor,{'type':'activate_ability','card_id':source,
                            'ability_index':0,'targets':{'target_card_id':target}})
    assert state.cards[source].tapped and sum(state.players[actor].mana_pool.values())==0
    state = e.drain(c.cold(state))
    assert state.cards[target].tapped
    return state

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['The Wandering Emperor','Assassinate','Asphyxiate'])
@pytest.mark.parametrize('episode',['legal','invalid-state','invalid-root','changes-before-resolve'])
def test_real_paid_tap_restrictions(facts,seat,name,episode,request):
    state = c.g.position(facts,seat)
    victim = e.add(state,facts,'Raging Goblin',3-seat,Zone.BATTLEFIELD)
    land = e.add(state,facts,'Forest',3-seat,Zone.BATTLEFIELD)
    needs_tapped = name!='Asphyxiate'
    responder = None
    if episode=='changes-before-resolve':
        # Current target-free preview needs another-side creature; the earlier
        # single-sided-board REDs remain separately preserved and unqualified.
        e.add(state,facts,'Raging Goblin',seat,Zone.BATTLEFIELD)
        state=c.sun.advance_main(c.cold(state),3-seat)
        responder=e.add(state,facts,'Seeker of Skybreak' if needs_tapped else 'Icy Manipulator',3-seat)
        state,frame=c.paid(state,3-seat,responder,{'C':1,'G':1} if needs_tapped else {'C':4})
        state=e.frame_done(state,frame)
        state=c.sun.advance_main(c.cold(state),seat)
        if needs_tapped:
            state=c.sun.advance_main(c.cold(state),3-seat)
            state=c.sun.advance_main(c.cold(state),seat)
            assert not state.cards[responder].summoning_sick
    if needs_tapped != (episode=='invalid-state'):
        state = tap_paid(state,facts,seat,victim)
    source = e.add(state,facts,name,seat)
    if name=='The Wandering Emperor':
        state,frame = c.paid(state,seat,source,{'C':2,'W':2})
        state = e.frame_done(state,frame)
        state = c.priority(c.cold(state),seat)
        action = {'type':'activate_loyalty','card_id':source,'ability_index':2,
                  'targets':{'target_card_id':victim}}
    else:
        state = c.priority(c.cold(state),seat)
        state.players[seat].mana_pool = {'C':2,'B':1} if name=='Assassinate' else {'C':1,'B':2}
        action = {'type':'cast_spell','card_id':source,'cost_choice':{'id':'base'},
                  'targets':{'target_card_id':victim}}
    c.offers(state,seat)
    if episode in {'invalid-state','invalid-root'}:
        if episode=='invalid-root':action['targets']['target_card_id']=land
        e.reject(state,seat,action)
        record(request,state,facts,[name,'Icy Manipulator'],episode=episode)
        return
    state = c.act(state,seat,action)
    if name=='The Wandering Emperor':assert state.cards[source].loyalty==1
    else:
        assert sum(state.players[seat].mana_pool.values())==0
        assert next(i for i in state.stack if i.source_card_id==source).payload['mana_spent']==3
    if episode=='changes-before-resolve':
        state=c.priority(c.cold(state),3-seat)
        state.players[3-seat].mana_pool={} if needs_tapped else {'C':1}
        record(request,state,facts,[name,'Seeker of Skybreak','Icy Manipulator'],
               episode=episode,boundary='actual response announcement',public_moves=c.offers(state,3-seat))
        state=c.act(state,3-seat,{'type':'activate_ability','card_id':responder,'ability_index':0,
                                'targets':{'target_card_id':victim}})
        assert state.cards[responder].tapped and sum(state.players[3-seat].mana_pool.values())==0
        frame=state.stack[-1].id
        state=e.frame_done(c.cold(state),frame)
        assert state.cards[victim].tapped is (not needs_tapped)
    state = e.drain(c.cold(state))
    record(request,state,facts,[name,'Icy Manipulator','Seeker of Skybreak'],episode=episode)
    expected = Zone.BATTLEFIELD if episode=='changes-before-resolve' else Zone.EXILE if name=='The Wandering Emperor' else Zone.GRAVEYARD
    assert state.cards[victim].zone==expected
    if name=='The Wandering Emperor':assert state.players[seat].life==(20 if episode=='changes-before-resolve' else 22)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('spell',['Lightning Bolt','Asphyxiate','Raging Goblin'])
@pytest.mark.parametrize('caster',['own','foreign'])
def test_real_paid_energy_controller_and_spell_type(facts,seat,spell,caster,request):
    state=c.g.position(facts,seat)
    tower=e.add(state,facts,'Dynavolt Tower',seat)
    state,frame=c.paid(state,seat,tower,{'C':3});state=e.frame_done(state,frame)
    actor=seat if caster=='own' else 3-seat
    state=c.sun.advance_main(c.cold(state),actor)
    source=e.add(state,facts,spell,actor)
    targets={'target_player':3-actor} if spell=='Lightning Bolt' else {}
    if spell=='Asphyxiate':
        victim=e.add(state,facts,'Raging Goblin',3-actor,Zone.BATTLEFIELD)
        targets={'target_card_id':victim}
    assert not state.players[seat].counters.get('energy',0)
    state,frame=c.paid(state,actor,source,{'C':1,'B':2} if spell=='Asphyxiate' else {'R':1},targets)
    state=e.frame_done(state,frame);state=e.drain(c.cold(state))
    record(request,state,facts,['Dynavolt Tower',spell],caster=caster)
    assert state.players[seat].counters.get('energy',0)==(2 if caster=='own' and spell!='Raging Goblin' else 0)
    assert not state.players[3-seat].counters.get('energy',0)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('kind',['creature','land','planeswalker'])
@pytest.mark.parametrize('owner',['own','foreign'])
def test_real_paid_enchant_union_and_wrong_root(facts,seat,kind,owner,request):
    state=c.g.position(facts,seat);target_owner=seat if owner=='own' else 3-seat
    target_name={'creature':'Raging Goblin','land':'Forest','planeswalker':'The Wandering Emperor'}[kind]
    target=e.add(state,facts,target_name,target_owner,Zone.HAND if kind=='planeswalker' else Zone.BATTLEFIELD)
    if kind=='planeswalker':
        state,frame=c.paid(state,target_owner,target,{'C':2,'W':2})
        state=e.frame_done(state,frame)
    moon=e.add(state,facts,'Imprisoned in the Moon',seat)
    invalid=e.add(state,facts,'Rod of Ruin',3-seat,Zone.BATTLEFIELD)
    state=c.priority(c.cold(state),seat);state.players[seat].mana_pool={'C':2,'U':1}
    c.offers(state,seat)
    e.reject(state,seat,{'type':'cast_spell','card_id':moon,'cost_choice':{'id':'base'},
                         'targets':{'target_card_id':invalid}})
    state,frame=c.paid(state,seat,moon,{'C':2,'U':1},{'target_card_id':target})
    state=e.frame_done(c.cold(state),frame)
    record(request,state,facts,['Imprisoned in the Moon',target_name],kind=kind,owner=owner)
    assert state.cards[moon].attached_to==target
    assert set(effective_types(state,state.cards[target]))=={'Land'}
    assert printed_abilities_suppressed(state,target)
    if kind=='planeswalker':
        state=c.priority(state,target_owner)
        e.reject(state,target_owner,{'type':'activate_loyalty','card_id':target,'ability_index':1,'targets':{}})

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('style',['bare','parenthetical'])
def test_actual_malformed_energy_instruction_no_reward(facts,seat,style,request):
    derived=deepcopy(facts)
    lines=derived['Dynavolt Tower']['oracle_text'].splitlines()
    lines[0]=lines[0].replace(' (two energy counters)','')
    lines[0]+=' UNPARSED-SUFFIX.' if style=='bare' else ' (UNPARSED-SUFFIX.)'
    derived['Dynavolt Tower']['oracle_text']='\n'.join(lines)
    state=c.g.position(facts,seat)
    tower=e.add(state,derived,'Dynavolt Tower',seat)
    state,frame=c.paid(state,seat,tower,{'C':3});state=e.frame_done(state,frame)
    source=e.add(state,facts,'Lightning Bolt',seat)
    state,frame=c.paid(state,seat,source,{'R':1},{'target_player':3-seat})
    state=e.frame_done(state,frame);state=e.drain(c.cold(state))
    record(request,state,derived,['Dynavolt Tower'],synthetic_probe=True,style=style)
    assert not state.players[seat].counters.get('energy',0)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('style',['bare','parenthetical'])
def test_actual_malformed_enchant_instruction_rejected(facts,seat,style,request):
    derived=deepcopy(facts);lines=derived['Imprisoned in the Moon']['oracle_text'].splitlines()
    lines[0]+=' UNPARSED-SUFFIX' if style=='bare' else ' (UNPARSED-SUFFIX)'
    derived['Imprisoned in the Moon']['oracle_text']='\n'.join(lines)
    state=c.g.position(facts,seat);target=e.add(state,facts,'Raging Goblin',seat,Zone.BATTLEFIELD)
    source=e.add(state,derived,'Imprisoned in the Moon',seat)
    state.players[seat].mana_pool={'C':2,'U':1}
    e.reject(state,seat,{'type':'cast_spell','card_id':source,'cost_choice':{'id':'base'},
                       'targets':{'target_card_id':target}})
    record(request,state,derived,['Imprisoned in the Moon'],synthetic_probe=True,style=style)

@pytest.mark.parametrize('status',['tapped','untapped'])
@pytest.mark.parametrize('kind',['artifact','creature','land','permanent'])
def test_synthetic_tap_qualifier_grammar(status,kind):
    result=infer_target_restrictions(None,'Exile target '+status+' '+kind+'.',1)
    assert result['tap_status']==status
    if kind!='permanent':assert result['allowed_types']==[kind.title()]

@pytest.mark.parametrize('line',['Exile target untapped nonsense.','Exile target tapped creature spell.',
    'Untap target creature.','Exile target tappedness creature.','Target creature becomes tapped.'])
def test_synthetic_unknown_tap_root_not_invented(line):
    assert 'tap_status' not in infer_target_restrictions(None,line,1)

@pytest.mark.parametrize('amount',[1,2,5,64])
@pytest.mark.parametrize('reminder',[False,True])
def test_synthetic_complete_energy_instruction(amount,reminder):
    line='Whenever you cast an instant or sorcery spell, you get '+'{E}'*amount
    if reminder:line+=' ('+str(amount)+' energy counters)'
    assert gain_clause(line+'.')==('cast',amount,'energy','instant or sorcery',None)

@pytest.mark.parametrize('line',[
    'Whenever you cast an instant or sorcery spell, you get {E}{E}. UNPARSED-SUFFIX.',
    'Whenever you cast an instant or sorcery spell, you get {E}{E} (three energy counters).',
    'Whenever you cast an instant or sorcery spell, you get {E}{E} (UNPARSED-SUFFIX).',
    'Whenever you perform an unspecified operation, you get {E}{E}.',
    'Whenever you cast an instant spell, you get '+'{E}'*65+'.',
    'Whenever you cast an instant spell, you get .',
    'Whenever you cast an instant spell, you get {E}{X}.',
    'Whenever you cast an instant spell with mana value unknown or greater, you get {E}.'])
def test_synthetic_unknown_energy_complete_line(line):
    assert gain_clause(line) is None

@pytest.mark.parametrize('line',[
    'Enchant creature','Enchant creature or land','Enchant creature, land, or planeswalker',
    'Enchant creature, artifact, land or planeswalker you control',
    'Enchant nonbasic land or artifact an opponent controls','Enchant artifact creature or land'])
def test_synthetic_closed_enchant_union(line):
    result=enchant_restriction(line+'\nAn unrelated printed instruction.')
    assert result is not None and len(result.groups())==4

@pytest.mark.parametrize('line',[
    'Enchant creature UNPARSED-SUFFIX','Enchant creature. UNPARSED-SUFFIX.',
    'Enchant creature (UNPARSED-SUFFIX)','Enchant creature or nonsense',
    'Enchant creature, land, or planeswalker, or nonsense',
    'Enchant '+', '.join(['creature']*8), 'Enchant '+'creature '*100, 'Enchant '])
def test_synthetic_unknown_enchant_line(line):
    assert enchant_restriction(line) is None

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['The Wandering Emperor','Assassinate'])
def test_paid_selected_untap_mode_tapped_target_recheck(facts,seat,name,request):
    state=c.g.position(facts,seat)
    target=e.add(state,facts,'Raging Goblin',3-seat,Zone.BATTLEFIELD)
    state=tap_paid(state,facts,seat,target)
    source=e.add(state,facts,name,seat)
    if name=='The Wandering Emperor':
        state,frame=c.paid(state,seat,source,{'C':2,'W':2})
        state=e.frame_done(state,frame);state=c.priority(c.cold(state),seat)
        state=c.act(state,seat,{'type':'activate_loyalty','card_id':source,'ability_index':2,
                              'targets':{'target_card_id':target}})
        assert state.cards[source].loyalty==1
    else:
        state,frame=c.paid(state,seat,source,{'C':2,'B':1},{'target_card_id':target})
    before_incarnation=(object_incarnation(state.cards[target]),state.cards[target].zone_change_sequence)
    charm=e.add(state,facts,'Emerald Charm',3-seat)
    state=c.priority(c.cold(state),3-seat)
    state.players[3-seat].mana_pool={'G':1}
    offered=next(m for m in c.offers(state,3-seat)
                 if m['type']=='cast_spell' and m.get('card_id')==charm)
    modes=offered['target_hints']['modes']
    mode=next(m for m in modes if m.casefold().rstrip('.')=='untap target permanent')
    state,frame=c.paid(state,3-seat,charm,{'G':1},
                      {'mode_text':mode,'target_card_id':target})
    state=e.frame_done(c.cold(state),frame)
    assert not state.cards[target].tapped
    assert (object_incarnation(state.cards[target]),state.cards[target].zone_change_sequence)==before_incarnation
    state=e.drain(c.cold(state))
    record(request,state,facts,[name,'Icy Manipulator','Emerald Charm'],
           selected_mode=mode,public_modes=modes,other_modes='not certified',same_object=True)
    assert state.cards[target].zone==Zone.BATTLEFIELD
    assert state.players[seat].life==20
