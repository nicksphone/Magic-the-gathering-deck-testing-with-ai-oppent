"""Canonical resolution-time discard counts survive owned choices and restart."""
import json
from pathlib import Path
import pytest
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import add
from tests.test_legendary_channels import choice, resolve_to_choice
from tests.test_api_input_contracts import game

ROWS = {row['name']:row for row in json.loads((Path(__file__).parent/'fixtures/linked_discard.json').read_text())}
SPELLS = ['Rites of Spring', 'Tolarian Winds', 'Dangerous Wager']


def setup(name, seat=1, hand_names=('Island','Swamp','Grizzly Bears'), pause=True, cast=True):
    state = board(seat)
    state.mechanic_choice_players = {1,2}
    spell = raw_add(state, name, seat, Zone.HAND, cards=ROWS)
    hand = [add(state,name,seat,Zone.HAND) for name in hand_names]
    for _ in range(4):
        add(state, 'Swamp', seat, Zone.LIBRARY)
    state.players[seat].mana_pool.update(U=3,R=3,G=3,C=3)
    if not cast:
        return state, spell, hand
    state = checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':spell.id})
    return (resolve_to_choice(state) if pause else state), spell, hand


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[0,1,2,3])
def test_variable_discard_then_exact_bounded_basic_search(seat,count):
    state,spell,hand=setup('Rites of Spring',seat)
    assert state.pending_mechanic_choice['min_count']==0
    assert state.pending_mechanic_choice['count']==3
    before=serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): choice(state,3-seat,[hand[0].id])
    assert serialize_match_snapshot(state)==before
    state=deserialize_match_snapshot(serialize_match_snapshot(state))
    state=choice(state,seat,[c.id for c in hand[:count]])
    if count:
        assert state.pending_mechanic_choice['kind']=='search_library'
        assert state.pending_mechanic_choice['count']==count
        state=deserialize_match_snapshot(serialize_match_snapshot(state))
        ids=state.pending_mechanic_choice['options'][:count]
        state=choice(state,seat,ids)
        assert all(state.cards[cid].zone==Zone.HAND for cid in ids)
    assert not state.pending_mechanic_choice
    assert len(state.players[seat].hand)==3
    assert state.cards[spell.id].zone==Zone.GRAVEYARD
    assert sum('shuffles their library' in line for line in state.log)==1


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Tolarian Winds','Dangerous Wager'])
def test_whole_hand_discard_then_actual_or_fixed_draw(seat,name):
    state,spell,hand=setup(name,seat)
    assert state.pending_mechanic_choice['kind']=='discard'
    assert state.pending_mechanic_choice['count']==3
    state=choice(deserialize_match_snapshot(serialize_match_snapshot(state)),seat,[c.id for c in hand])
    assert len(state.players[seat].hand)==(3 if name=='Tolarian Winds' else 2)
    assert all(state.cards[c.id].zone==Zone.GRAVEYARD for c in hand)
    assert state.cards[spell.id].zone==Zone.GRAVEYARD
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('invalid',['duplicate','opponent','source','too-many'])
def test_discard_choice_rejections_preserve_resolution(seat,invalid):
    state,spell,hand=setup('Rites of Spring',seat)
    ids=[hand[0].id]
    if invalid=='duplicate': ids*=2
    elif invalid=='source': ids=[spell.id]
    elif invalid=='opponent': ids=[state.players[3-seat].library[0]]
    else: ids=[c.id for c in hand]+[spell.id]
    before=serialize_match_snapshot(state)
    with pytest.raises(ActionRejected): choice(state,seat,ids)
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('find',[0,1])
def test_search_can_fail_to_find_without_undoing_discard(seat,find):
    state,spell,hand=setup('Rites of Spring',seat)
    state=choice(state,seat,[c.id for c in hand[:2]])
    ids=state.pending_mechanic_choice['options'][:find]
    state=choice(state,seat,ids)
    assert len(state.players[seat].hand)==1+find
    assert all(state.cards[c.id].zone==Zone.GRAVEYARD for c in hand[:2])
    assert state.cards[spell.id].zone==Zone.GRAVEYARD
    assert sum('shuffles their library' in line for line in state.log)==1


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Tolarian Winds','Dangerous Wager'])
@pytest.mark.parametrize('modifier',['Thought Reflection','Spirit of the Labyrinth'])
def test_followup_draw_obeys_replacements_and_caps(seat,name,modifier):
    from tests.test_draw_forecast import ROWS as DRAW
    state,spell,hand=setup(name,seat)
    raw_add(state,modifier,seat,cards=DRAW)
    state.draws_this_turn[seat]=1
    state=choice(state,seat,[c.id for c in hand])
    amount=3 if name=='Tolarian Winds' else 2
    assert len(state.players[seat].hand)==(2*amount if modifier=='Thought Reflection' else 0)
    assert state.cards[spell.id].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('level',['casual','strong','master'])
def test_ai_optional_discard_is_bounded_and_avoids_unneeded_land_dump(seat,level):
    from ai.agent import AIAgent
    state,_,hand=setup('Rites of Spring',seat)
    before=serialize_match_snapshot(state)
    agent=AIAgent(level)
    selected=agent.choose_action(state,RulesEngine().legal_moves(state,seat),seat).action
    assert selected['card_ids']==[hand[-1].id]
    assert serialize_match_snapshot(state)==before
    paid=choice(state,seat,selected['card_ids'])
    assert paid.pending_mechanic_choice['count']==1
    for _ in range(5): add(state,'Swamp',seat)
    assert agent.choose_action(state,RulesEngine().legal_moves(state,seat),seat).action['card_ids']==[]


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('level',['casual','strong','master'])
@pytest.mark.parametrize('name',['Tolarian Winds','Dangerous Wager'])
def test_ai_hand_refresh_preserves_good_hand_and_rejects_doubled_deckout(seat,level,name):
    from ai.agent import AIAgent
    from tests.test_draw_forecast import ROWS as DRAW
    state=board(seat)
    spell=raw_add(state,name,seat,Zone.HAND,cards=ROWS)
    for other in ['Island','Swamp','Grizzly Bears']: add(state,other,seat,Zone.HAND)
    move={'type':'cast_spell','card_id':spell.id}
    agent=AIAgent(level)
    before=serialize_match_snapshot(state)
    assert agent._bad_shared_draw_cast(state,move,seat)
    assert serialize_match_snapshot(state)==before
    for _ in range(5): add(state,'Swamp',seat)
    assert not agent._bad_shared_draw_cast(state,move,seat)
    raw_add(state,'Thought Reflection',seat,cards=DRAW)
    state.players[seat].library=state.players[seat].library[:3]
    assert agent._bad_shared_draw_cast(state,move,seat)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',SPELLS)
def test_empty_hand_and_countered_spell_do_not_invent_discards(seat,name):
    from effects.registry import resolve_effect
    state,spell,_=setup(name,seat,hand_names=())
    assert not state.pending_mechanic_choice
    assert len(state.players[seat].hand)==(2 if name=='Dangerous Wager' else 0)
    assert state.cards[spell.id].zone==Zone.GRAVEYARD
    state,spell,hand=setup(name,seat,pause=False)
    resolve_effect(state,3-seat,'counter_spell',{'target_stack_id':state.stack[-1].id})
    assert state.players[seat].hand==[c.id for c in hand]
    assert not state.pending_mechanic_choice


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Tolarian Winds','Dangerous Wager'])
def test_copies_recount_the_current_hand_at_each_resolution(seat,name):
    from effects.registry import resolve_effect
    state,spell,hand=setup(name,seat,pause=False)
    resolve_effect(state,seat,'copy_spell',{'target_stack_id':state.stack[-1].id})
    for index in range(2):
        state=resolve_to_choice(state)
        assert state.pending_mechanic_choice['kind']=='discard'
        ids=list(state.players[seat].hand)
        assert len(ids)==(3 if index==0 or name=='Tolarian Winds' else 2)
        state=choice(deserialize_match_snapshot(serialize_match_snapshot(state)),seat,ids)
    assert len(state.players[seat].hand)==(3 if name=='Tolarian Winds' else 2)
    assert state.cards[spell.id].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',SPELLS)
def test_http_owned_choices_and_sqlite_recovery(game,seat,name):
    from tests.test_api_input_contracts import persist,rejected
    import main
    client,controller=game
    state,spell,hand=setup(name,seat)
    state.id=controller.state.id
    controller.state=state
    persist(controller)
    rejected(client,controller,{'type':'choose_mechanic','card_ids':[hand[0].id]},3-seat)
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(f'/matches/{state.id}').status_code==200
    controller=main.ACTIVE_MATCHES[state.id]
    assert controller.state.pending_mechanic_choice['followup_effect']
    ids=[hand[0].id] if name=='Rites of Spring' else [c.id for c in hand]
    response=client.post(f'/matches/{state.id}/action',json={'player_id':seat,'action':{'type':'choose_mechanic','card_ids':ids}})
    assert response.status_code==200,response.text
    if name=='Rites of Spring':
        assert controller.state.pending_mechanic_choice['count']==1
        rejected(client,controller,{'type':'choose_mechanic','card_ids':controller.state.pending_mechanic_choice['options'][:2]},seat)
        response=client.post(f'/matches/{state.id}/action',json={'player_id':seat,'action':{'type':'choose_mechanic','card_ids':[]}})
        assert response.status_code==200,response.text
    assert not controller.state.pending_mechanic_choice
    assert controller.state.cards[spell.id].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Tolarian Winds','Dangerous Wager'])
def test_discard_destination_replacement_does_not_erase_linked_count(seat,name):
    state,spell,hand=setup(name,seat)
    raw_add(state,'Leyline of the Void',3-seat,cards=ROWS)
    state=choice(state,seat,[c.id for c in hand])
    assert all(state.cards[c.id].zone==Zone.EXILE for c in hand)
    assert len(state.players[seat].hand)==(3 if name=='Tolarian Winds' else 2)
    assert state.cards[spell.id].zone==Zone.EXILE


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Tolarian Winds','Dangerous Wager'])
def test_nested_draw_replacement_choices_resume_original_spell_once(seat,name):
    state,spell,hand=setup(name,seat)
    raw_add(state,'Stinkweed Imp',seat,Zone.GRAVEYARD,cards=ROWS)
    state=choice(state,seat,[c.id for c in hand])
    amount=3 if name=='Tolarian Winds' else 2
    for _ in range(amount):
        assert state.pending_mechanic_choice['kind']=='draw'
        state=deserialize_match_snapshot(serialize_match_snapshot(state))
        state=checked_action(state,RulesEngine(),seat,{'type':'choose_mechanic','choice_id':'draw'})
    assert not state.pending_mechanic_choice
    assert len(state.players[seat].hand)==amount
    assert state.cards[spell.id].zone==Zone.GRAVEYARD
    assert sum('discards 3.' in line for line in state.log)==1


@pytest.mark.parametrize('seat',[1,2])
def test_discard_turn_history_is_admitted_as_a_counted_effect(seat):
    from rules_engine.costs import collect_cost_options
    from rules_engine.coverage import known_unsupported_mechanics
    state=board(seat)
    spell=raw_add(state,'Change of Fortune',seat,Zone.HAND,cards=ROWS)
    state.players[seat].mana_pool.update(R=2, C=8)
    assert 'linked discard sequence fidelity' not in known_unsupported_mechanics(spell.oracle_text,card_name=spell.name)
    assert collect_cost_options(state,seat,spell)


@pytest.mark.parametrize('seat',[1,2])
def test_opposing_controller_copy_discards_and_draws_its_own_hand(seat):
    from effects.registry import resolve_effect
    state,spell,hand=setup('Tolarian Winds',seat,pause=False)
    other=3-seat
    copied_hand=[add(state,name,other,Zone.HAND) for name in ['Island','Swamp']]
    resolve_effect(state,other,'copy_spell',{'target_stack_id':state.stack[-1].id})
    state=resolve_to_choice(state)
    assert state.pending_mechanic_choice['player_id']==other
    assert state.pending_mechanic_choice['count']==2
    state=choice(deserialize_match_snapshot(serialize_match_snapshot(state)),other,[card.id for card in copied_hand])
    assert state.players[seat].hand==[card.id for card in hand]
    assert len(state.players[other].hand)==2
    assert all(state.cards[card.id].zone==Zone.GRAVEYARD for card in copied_hand)
    state=resolve_to_choice(state)
    state=choice(state,seat,[card.id for card in hand])
    assert len(state.players[seat].hand)==3
    assert len(state.players[other].hand)==2


@pytest.mark.parametrize('seat',[1,2])
def test_opposing_ability_copy_loots_for_its_current_controller(seat):
    from effects.registry import resolve_effect
    state=board(seat)
    state.mechanic_choice_players={1,2}
    looter=raw_add(state,'Merfolk Looter',seat,cards=ROWS)
    looter.summoning_sick=False
    other=3-seat
    own_hand=[add(state,'Island',seat,Zone.HAND)]
    other_hand=[add(state,'Swamp',other,Zone.HAND)]
    move=next(m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id')==looter.id and m['type']=='activate_ability')
    state=checked_action(state,RulesEngine(),seat,{'type':'activate_ability','card_id':looter.id,'ability_index':move['ability_index']})
    resolve_effect(state,other,'copy_ability',{'target_stack_id':state.stack[-1].id})
    state=resolve_to_choice(state)
    assert state.pending_mechanic_choice['player_id']==other
    assert len(state.players[other].hand)==2
    state=choice(deserialize_match_snapshot(serialize_match_snapshot(state)),other,[other_hand[0].id])
    assert state.players[seat].hand==[own_hand[0].id]
    state=resolve_to_choice(state)
    assert state.pending_mechanic_choice['player_id']==seat
    state=choice(state,seat,[own_hand[0].id])
    assert len(state.players[seat].hand)==len(state.players[other].hand)==1
    assert state.cards[looter.id].zone==Zone.BATTLEFIELD
    assert state.cards[looter.id].tapped
