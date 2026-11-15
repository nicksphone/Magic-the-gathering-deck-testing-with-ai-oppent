"""Paid color-qualified draws and native paused draw-before-wipe continuations."""
import json
import pytest
from card_data.seed_cards import SEED_CARD_DATA
from game_state.state import MatchFactory,Zone
from game_state.serializers import deserialize_match_snapshot,serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.cast_choice import build_cast_hints
from rules_engine.colors import card_color_symbols
from rules_engine.engine import RulesEngine
from rules_engine.query_context import rule_query_scope
from tests.test_ai_recurring_engines import CARDS as RECURRING,fixture,add as fixture_add
from tests.pending_permanent_fullraw import raw_card as canonical_row
from tests.test_linked_damage_targets import raw_card
from tests.test_color_domain_audit import convert,add as layer_add
from rules_engine.type_effects import effective_types
import test_brainstorm_desired as brain

def seed_add(state,name,seat,zone=Zone.HAND):
    row=SEED_CARD_DATA[name]
    sample=MatchFactory.from_decks([{**row,'card_name':name,'quantity':1}],[],seed=83)
    card=next(card for card in sample.cards.values() if card.name==name)
    card.id=state.allocate_object_id();card.owner=card.controller=seat;card.move_to_zone(zone)
    state.cards[card.id]=card;getattr(state.players[seat],zone.value).append(card.id)
    assert card.oracle_text==row['oracle_text'] and card.colors==row['colors']
    return card.id

def target(state,name,seat):
    row=canonical_row(name);card=raw_card(state,row,seat,Zone.BATTLEFIELD)
    assert card.oracle_text==row['oracle_text'] and card.colors==row['colors']
    return card.id

def position(seat,name='Depopulate',case='only-opponent'):
    state=fixture();state.active_player=state.priority_player=seat
    if name=='Depopulate':
        spell=seed_add(state,name,seat)
        assert state.cards[spell].oracle_text=='Each player who controls a multicolored creature draws a card. Then destroy all creatures.'
    else:
        card=fixture_add(state,name,seat,Zone.HAND);spell=card.id
        assert card.oracle_text==RECURRING[name]['oracle_text']
    multi={seat} if case=='only-caster' else {seat,3-seat} if case=='both' else set() if case=='neither' else {3-seat}
    creatures=[target(state,'Sprite Dragon' if owner in multi else 'Prodigal Pyromancer',owner) for owner in (seat,3-seat)]
    if case=='duplicates':creatures.append(target(state,'Sprite Dragon',3-seat))
    if case=='neither':
        bear=fixture_add(state,'Grizzly Bears',3-seat,full_printing=True)
        assert card_color_symbols(bear,state)=={'G'};creatures.append(bear.id)
    for owner in (1,2):state.players[owner].mana_pool={}
    state.players[seat].mana_pool={'W' if name=='Depopulate' else 'B':2,'C':2}
    return state,spell,creatures,multi

def act(state,seat,action):
    before=serialize_match_snapshot(state);rng=state.rng.getstate()
    result=checked_action(state,RulesEngine(),seat,action)
    assert serialize_match_snapshot(state)==before and state.rng.getstate()==rng
    return result

def cold(state,enabled):
    before=serialize_match_snapshot(state)
    result=deserialize_match_snapshot(json.loads(json.dumps(before))) if enabled else state
    assert serialize_match_snapshot(result)==before
    return result

def cast(state,seat,spell,amount=4,targets=None):
    pool=sum(state.players[seat].mana_pool.values())
    action={'type':'cast_spell','card_id':spell,'cost_choice':{'id':'base'}}
    if targets is not None:action['targets']=targets
    paid=act(state,seat,action)
    item=next(item for item in paid.stack if item.source_card_id==spell and item.controller==seat)
    assert item.payload['mana_spent']==amount and sum(paid.players[seat].mana_pool.values())==pool-amount
    return paid,item.id

def advance(state,predicate):
    for _ in range(64):
        if predicate(state):return state
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        state=act(state,state.priority_player,{'type':'pass_priority'})
    raise AssertionError('Native fixture stack did not reach the declared boundary')

def finish(state):return advance(state,lambda s:not s.stack)

@pytest.mark.parametrize('seat',[1,2])
def test_native_unconditional_wipe_pays_and_destroys_without_draw(seat):
    state,spell,creatures,_=position(seat,'Damnation')
    counts={owner:len(state.players[owner].library) for owner in (1,2)}
    paid,_=cast(state,seat,spell);done=finish(paid)
    assert all(done.cards[cid].zone==Zone.GRAVEYARD for cid in creatures)
    assert {owner:len(done.players[owner].library) for owner in (1,2)}==counts
    assert done.winner is None

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
@pytest.mark.parametrize('case',['only-opponent','only-caster','both','neither','duplicates'])
def test_paid_conditional_draw_uses_each_current_controller_once(seat,restored,case):
    state,spell,creatures,eligible=position(seat,case=case);state=cold(state,restored)
    before=serialize_match_snapshot(state);rng=state.rng.getstate()
    with rule_query_scope(state):
        build_cast_hints(state,state.cards[spell],seat);RulesEngine().legal_moves(state,seat)
    assert serialize_match_snapshot(state)==before and state.rng.getstate()==rng
    counts={owner:len(state.players[owner].library) for owner in (1,2)}
    paid,_=cast(state,seat,spell);done=finish(cold(paid,restored))
    assert all(done.cards[cid].zone==Zone.GRAVEYARD for cid in creatures)
    assert {owner:len(done.players[owner].library) for owner in (1,2)}=={owner:counts[owner]-(owner in eligible) for owner in (1,2)}
    assert done.cards[spell].zone==Zone.GRAVEYARD and done.winner is None

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
def test_real_removal_response_changes_draw_eligibility_before_pending_wipe(seat,restored):
    state,spell,creatures,_=position(seat);enemy=3-seat
    bolt=raw_card(state,canonical_row('Lightning Bolt'),enemy,Zone.HAND).id
    state.players[enemy].mana_pool={'R':1};counts={p:len(state.players[p].library) for p in (1,2)}
    state,frame=cast(state,seat,spell);state=act(state,seat,{'type':'pass_priority'})
    state,_=cast(state,enemy,bolt,1,{'target_card_id':creatures[1]})
    state=advance(cold(state,restored),lambda s:len(s.stack)==1 and s.stack[0].id==frame)
    assert state.cards[creatures[1]].zone==Zone.GRAVEYARD and state.cards[spell].zone==Zone.STACK
    done=finish(cold(state,restored))
    assert {p:len(done.players[p].library) for p in (1,2)}==counts
    assert all(done.cards[cid].zone==Zone.GRAVEYARD for cid in creatures)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
def test_paid_theft_draws_for_current_controller_rather_than_original_owner(seat,restored):
    state,spell,creatures,_=position(seat);enemy=3-seat
    claim=seed_add(state,'Claim the Firstborn',seat);state.players[seat].mana_pool['R']=1
    state,_=cast(state,seat,claim,1,{'target_card_id':creatures[1]});state=finish(state)
    assert state.cards[creatures[1]].owner==enemy and state.cards[creatures[1]].controller==seat
    counts={p:len(state.players[p].library) for p in (1,2)}
    state,_=cast(cold(state,restored),seat,spell);done=finish(cold(state,restored))
    assert {p:len(done.players[p].library) for p in (1,2)}=={seat:counts[seat]-1,enemy:counts[enemy]}
    assert all(done.cards[cid].zone==Zone.GRAVEYARD for cid in creatures)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
def test_supported_conversion_uses_current_colorless_creature_not_printed_multicolor(seat,restored):
    state,spell,creatures,_=position(seat,case='only-caster');cid=creatures[0]
    nissa=layer_add(state,'Nissa, Who Shakes the World',seat)
    state.players[seat].mana_pool={'G':1,'C':4,'W':2}
    state=convert(state,cid,seat)
    assert state.cards[cid].counters['+1/+1']==1
    state=finish(act(state,seat,{'type':'activate_loyalty','card_id':nissa.id,
        'ability_index':0,'targets':{'target_card_id':cid}}))
    assert state.cards[cid].counters['+1/+1']==4
    assert {'Land','Creature'}<=set(effective_types(state,cid))
    assert set(state.cards[cid].colors)=={'U','R'}
    assert card_color_symbols(state.cards[cid],state)==set()
    counts={p:len(state.players[p].library) for p in (1,2)}
    state,_=cast(cold(state,restored),seat,spell);done=finish(cold(state,restored))
    assert {p:len(done.players[p].library) for p in (1,2)}==counts
    assert all(done.cards[cid].zone==Zone.GRAVEYARD for cid in creatures)

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
def test_both_actual_dredge_choices_finish_in_active_order_before_wipe(seat,restored):
    state,spell,creatures,_=position(seat,case='both')
    imps={p:brain.add(state,'Stinkweed Imp',p,Zone.GRAVEYARD) for p in (1,2)}
    counts={p:len(state.players[p].library) for p in (1,2)}
    state,_=cast(state,seat,spell)
    state=advance(cold(state,restored),lambda s:bool(s.pending_mechanic_choice))
    for owner in (seat,3-seat):
        assert state.pending_mechanic_choice['kind']=='draw' and state.pending_mechanic_choice['player_id']==owner
        assert imps[owner] in state.pending_mechanic_choice['options']
        assert all(state.cards[cid].zone==Zone.BATTLEFIELD for cid in creatures)
        state=act(cold(state,restored),owner,{'type':'choose_mechanic','choice_id':imps[owner]})
    done=finish(cold(state,restored))
    assert not done.pending_mechanic_choice and not done.pending_replacement_choice
    assert {p:len(done.players[p].library) for p in (1,2)}=={p:counts[p]-5 for p in (1,2)}
    assert all(done.cards[cid].zone==Zone.GRAVEYARD for cid in creatures)
    assert all(done.cards[imps[p]].zone==Zone.HAND for p in (1,2))

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
def test_multicolored_noncreature_and_colorless_creature_do_not_qualify(seat,restored):
    state,spell,creatures,_=position(seat,case='neither');enemy=3-seat
    teferi=seed_add(state,'Teferi, Time Raveler',enemy,Zone.BATTLEFIELD)
    myr=target(state,'Darksteel Myr',enemy)
    assert card_color_symbols(state.cards[teferi],state)=={'W','U'} and card_color_symbols(state.cards[myr],state)==set()
    counts={p:len(state.players[p].library) for p in (1,2)}
    state,_=cast(cold(state,restored),seat,spell);done=finish(cold(state,restored))
    assert {p:len(done.players[p].library) for p in (1,2)}==counts
    assert all(done.cards[cid].zone==Zone.GRAVEYARD for cid in creatures)
    assert done.cards[teferi].zone==done.cards[myr].zone==Zone.BATTLEFIELD

@pytest.mark.parametrize('quality',['white','blue','black','red','green','monocolored','multicolored','colorless'])
def test_diagnostic_compiler_matches_complete_reusable_quality_clause(quality):
    from rules_engine.conditional_player_draw import compile_instruction
    assert compile_instruction('Each player who controls a '+quality+' creature draws a card.')==('conditional_player_draw',{'quality':quality})

@pytest.mark.parametrize('text',[
    'Each player who controls an artifact creature draws a card.',
    'Each player who controls a purple creature draws a card.',
    'Each player who controls a multicolored creature draws two cards.',
    'Each player who controls a multicolored creature draws a card if a hidden condition holds.',
    'Each player who controls a multicolored creature draws a card. Then invent a reward.',
],ids=['artifact','unknown','quantity','condition','tail'])
def test_diagnostic_unknown_partial_or_changed_quantity_is_not_a_complete_match(text):
    from rules_engine.conditional_player_draw import compile_instruction
    assert compile_instruction(text) is None
