"""Native announced-X search limits; removing mv_max admits the first illegal Bear."""
import pytest
from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_conditional_player_draw import act,cold,cast,finish,advance,seed_add
from tests.test_deferred_upkeep_payment import position,COPY_PRINTINGS,offer
from tests.test_ai_recurring_engines import add as fixture_add
from tests.test_linked_damage_targets import raw_card
from tests.library_canonical_fixtures import raw_card as library_row
from tests.test_cast_resource_payments import ROWS as RESOURCE_ROWS
from tests.test_free_effect_resource_payment import graveyard_position
from rules_engine.effect_casts import materialize_cast,admit_cast


def setup(seat,x,*,creature=True):
    state,spell=position(seat,spell='Chord of Calling',creature=creature)
    state.players[seat].mana_pool={'G':3,'C':x}
    return state,spell


def chord(state,seat,spell,x,**annotations):
    return cast(state,seat,spell,x+3,{'x_value':x,**annotations})


@pytest.mark.parametrize('seat',[1,2])
def test_paid_equal_bound_control_puts_bear_onto_battlefield(seat):
    state,spell=setup(seat,2)
    state,_=chord(state,seat,spell,2)
    state=finish(cold(state,True))
    assert state.cards[spell].zone==Zone.GRAVEYARD
    assert len(state.players[seat].battlefield)==1
    bear=state.cards[state.players[seat].battlefield[0]]
    assert bear.name=='Grizzly Bears' and bear.summoning_sick and not bear.tapped


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
@pytest.mark.parametrize('x',[0,1])
def test_announced_X_excludes_higher_mana_value_creature(seat,restored,x):
    state,spell=setup(seat,x)
    bear=next(cid for cid in state.players[seat].library if state.cards[cid].name=='Grizzly Bears')
    state,_=chord(cold(state,restored),seat,spell,x)
    state=finish(cold(state,restored))
    assert state.cards[spell].zone==Zone.GRAVEYARD
    assert state.cards[bear].zone==Zone.LIBRARY and not state.players[seat].battlefield
    assert sum(state.players[seat].mana_pool.values())==0


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('x',[3,4])
def test_explicit_colorless_symbol_counts_in_library_mana_value(seat,x):
    state,spell=setup(seat,x,creature=False)
    seer=raw_card(state,library_row('Thought-Knot Seer'),seat,Zone.LIBRARY).id
    assert state.cards[seer].mana_cost=='{3}{C}'
    state,_=chord(state,seat,spell,x)
    state=finish(cold(state,True))
    assert state.cards[seer].zone==(Zone.BATTLEFIELD if x==4 else Zone.LIBRARY)


@pytest.mark.parametrize('seat',[1,2])
def test_X_zero_finds_zero_cost_creature(seat):
    state,spell=setup(seat,0)
    zero=raw_card(state,COPY_PRINTINGS['ornithopter'],seat,Zone.LIBRARY).id
    assert state.cards[zero].mana_cost=='{0}'
    state,_=chord(state,seat,spell,0)
    state=finish(state)
    assert state.cards[zero].zone==Zone.BATTLEFIELD
    assert len(state.players[seat].battlefield)==1


@pytest.mark.parametrize('seat',[1,2])
def test_client_search_annotations_do_not_override_printed_bound_or_type(seat):
    state,spell=setup(seat,1)
    before=serialize_match_snapshot(state);rejected=False
    try:chord(state,seat,spell,1,search_mv_max=99,search_contains='card',search_count=9)
    except ActionRejected:rejected=True
    assert rejected and serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
def test_restored_human_search_contains_only_eligible_options_and_can_fail_to_find(seat):
    state,spell=setup(seat,2)
    state.mechanic_choice_players={seat}
    bear=next(cid for cid in state.players[seat].library if state.cards[cid].name=='Grizzly Bears')
    too_large=raw_card(state,library_row('Thought-Knot Seer'),seat,Zone.LIBRARY).id
    state,_=chord(state,seat,spell,2)
    state=offer(state)
    assert state.pending_mechanic_choice['options']==[bear]
    before=serialize_match_snapshot(state);rejected=False
    try:act(state,seat,{'type':'choose_mechanic','card_ids':[too_large]})
    except ActionRejected:rejected=True
    assert rejected and serialize_match_snapshot(state)==before
    state=act(cold(state,True),seat,{'type':'choose_mechanic','card_ids':[]})
    assert state.cards[spell].zone==Zone.GRAVEYARD
    assert state.cards[bear].zone==Zone.LIBRARY and state.cards[too_large].zone==Zone.LIBRARY


@pytest.mark.parametrize('seat',[1,2])
def test_actual_AI_search_choice_executes_with_bound_and_preserves_caller(seat):
    state,spell=setup(seat,2)
    state.mechanic_choice_players={seat}
    bear=next(cid for cid in state.players[seat].library if state.cards[cid].name=='Grizzly Bears')
    too_large=raw_card(state,library_row('Thought-Knot Seer'),seat,Zone.LIBRARY).id
    state,_=chord(state,seat,spell,2);state=offer(state)
    before=serialize_match_snapshot(state)
    decision=AIAgent().choose_action(state,RulesEngine().legal_moves(state,seat),seat)
    assert serialize_match_snapshot(state)==before
    state=act(cold(state,True),seat,decision.action)
    assert state.cards[bear].zone==Zone.BATTLEFIELD and state.cards[too_large].zone==Zone.LIBRARY


@pytest.mark.parametrize('seat',[1,2])
def test_paid_counterspell_prevents_search(seat):
    state,spell=setup(seat,2)
    counter=seed_add(state,'Counterspell',3-seat)
    state.players[3-seat].mana_pool={'U':2}
    bear=next(cid for cid in state.players[seat].library if state.cards[cid].name=='Grizzly Bears')
    state,target=chord(state,seat,spell,2)
    state=act(state,seat,{'type':'pass_priority'})
    state,_=cast(state,3-seat,counter,2,{'target_stack_id':target})
    state=finish(state)
    assert state.cards[spell].zone==Zone.GRAVEYARD and state.cards[bear].zone==Zone.LIBRARY


@pytest.mark.parametrize('seat',[1,2])
def test_real_copy_retains_announced_X_and_uses_copy_controller_library(seat):
    state,spell=setup(seat,1)
    copy=raw_card(state,COPY_PRINTINGS['twincast'],3-seat,Zone.HAND).id
    fixture_add(state,'Grizzly Bears',3-seat,Zone.LIBRARY,full_printing=True)
    zero=raw_card(state,COPY_PRINTINGS['ornithopter'],3-seat,Zone.LIBRARY).id
    state.players[3-seat].mana_pool={'U':2}
    state,target=chord(state,seat,spell,1)
    state=act(state,seat,{'type':'pass_priority'})
    state,_=cast(state,3-seat,copy,2,{'target_stack_id':target})
    state=finish(cold(state,True))
    assert not state.players[seat].battlefield
    assert state.players[3-seat].battlefield==[zero]


@pytest.mark.parametrize('seat',[1,2])
def test_real_convoke_payment_preserves_announced_X(seat):
    state,spell=setup(seat,1)
    sources=[fixture_add(state,'Llanowar Elves',seat,cards=RESOURCE_ROWS).id for _ in range(3)]
    state.players[seat].mana_pool={'C':1}
    state=act(state,seat,{'type':'cast_spell','card_id':spell,'cost_choice':{'id':'base'},
        'targets':{'x_value':1},'resource_payment':{'convoke':[{'card_id':cid,'pay_as':'G'} for cid in sources]}})
    item=next(item for item in state.stack if item.source_card_id==spell)
    assert item.payload['mana_spent']==1 and all(state.cards[cid].tapped for cid in sources)
    state=finish(cold(state,True))
    assert set(state.players[seat].battlefield)==set(sources)
    assert state.cards[spell].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
def test_native_free_effect_cast_has_X_zero_and_preserves_payment_resources(seat):
    state,spell=graveyard_position(seat,'Chord of Calling')
    zero=raw_card(state,COPY_PRINTINGS['ornithopter'],seat,Zone.LIBRARY).id
    bear=fixture_add(state,'Grizzly Bears',seat,Zone.LIBRARY,full_printing=True).id
    before=serialize_match_snapshot(state)
    action=materialize_cast(state,seat,spell.id)
    assert serialize_match_snapshot(state)==before
    admit_cast(state,seat,action,{'target_card_id':spell.id})
    item=next(item for item in state.stack if item.source_card_id==spell.id)
    assert item.payload['mana_spent']==0
    assert state.players[seat].mana_pool==before['players'][str(seat)]['mana_pool']
    state=finish(cold(state,True))
    assert state.cards[zero].zone==Zone.BATTLEFIELD and state.cards[bear].zone==Zone.LIBRARY


@pytest.mark.parametrize('cost,maximum,expected',[
    ('{3}{C}',3,False),('{3}{C}',4,True),('{G/W}',0,False),('{G/W}',1,True),
    ('{2/W}{2/W}',3,False),('{2/W}{2/W}',4,True),('{X}{X}',0,True),
])
def test_library_filter_uses_complete_mana_value_operand(cost,maximum,expected):
    from types import SimpleNamespace
    from rules_engine.oracle_effects import search_card_matches
    card=SimpleNamespace(types=['Creature'],type_line='Creature',mana_cost=cost)
    assert search_card_matches(card,'creature',maximum) is expected


@pytest.mark.parametrize('x',[None,-1,True,1.5,'2'])
def test_malformed_announced_X_fails_closed_in_compiler(x):
    from rules_engine.oracle_effects import _infer_search_effect
    text='search your library for a creature card with mana value x or less, put it onto the battlefield, then shuffle.'
    result=_infer_search_effect(text,{'x_value':x})
    assert result[0]=='noop' and '__unsupported_instruction' in result[1]


@pytest.mark.parametrize('suffix',[' Draw a card.',' Then gain 2 life.'])
def test_unknown_suffix_is_not_silently_discarded(suffix):
    from rules_engine.oracle_effects import _infer_search_effect
    text='search your library for a creature card with mana value x or less, put it onto the battlefield, then shuffle.'+suffix.lower()
    result=_infer_search_effect(text,{'x_value':2})
    assert result[0]=='noop' and '__unsupported_instruction' in result[1]


def test_missing_chosen_X_defaults_to_zero_in_compiler():
    from rules_engine.oracle_effects import _infer_search_effect
    text='search your library for a creature card with mana value x or less, put it onto the battlefield, then shuffle.'
    assert _infer_search_effect(text,{})[1]['mv_max']==0


@pytest.mark.parametrize('kind,destination,reveal',[
    ('artifact','onto the battlefield tapped',True),('creature','onto the battlefield',False),
    ('instant','into your hand',True),('sorcery','into your graveyard',False),
    ('battle','onto the battlefield',False),
])
def test_complete_variable_search_preserves_printed_destination_and_reveal(kind,destination,reveal):
    from rules_engine.oracle_effects import _infer_search_effect
    article='an' if kind in {'artifact','instant'} else 'a'
    text=f'search your library for {article} {kind} card with mana value x or less, '+('reveal it, ' if reveal else '')+f'put it {destination}, then shuffle.'
    key,payload=_infer_search_effect(text,{'x_value':2,'search_mv_max':99,'search_count':9,'search_contains':'card'})
    assert key=='search_library' and payload['contains']==kind and payload['mv_max']==2 and payload['count']==1
    assert payload['destination']==('battlefield' if destination.startswith('onto') else 'graveyard' if destination.endswith('graveyard') else 'hand')
    assert bool(payload.get('reveal')) is reveal and bool(payload.get('tapped'))==destination.endswith(' tapped')
