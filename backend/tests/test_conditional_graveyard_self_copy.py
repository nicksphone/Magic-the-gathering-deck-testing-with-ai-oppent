"""Canonical native self-copy episodes and explicitly scoped copy-layer controls."""
from collections import Counter
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot,deserialize_match_snapshot
from game_state.state import MatchFactory,Step,Zone,assign_static_order_on_battlefield_entry,object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_power,effective_toughness
from rules_engine.copiable_values import apply,values
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from rules_engine.type_effects import effective_types
from tests.test_conditional_player_draw import act
from tests.test_entry_copy_native_936 import raw
from tests.favor_lifecycle_support import ROWS as FAVOR_ROWS
from tests.test_combat_keyword_triggers import CARDS as COMBAT
from tests.cleanup_canonical_db4e import canonical_entry


def row(name,quantity):
    if name=='Sangromancer':return canonical_entry(name,quantity)
    data=(COMBAT[name] if name=='Stifle' else FAVOR_ROWS[name] if name=='Unsummon' else raw(name))
    return {**data,'card_name':name,'quantity':quantity}


def place(state,seat,name,zone):
    player=state.players[seat];front=name.split('//',1)[0].strip()
    cid=next(cid for cid in player.library if state.cards[cid].name==front)
    player.library.remove(cid);getattr(player,zone.value).append(cid)
    card=state.cards[cid];card.move_to_zone(zone)
    if zone==Zone.BATTLEFIELD:
        card.summoning_sick=False;card.entered_turn=state.turn-1
        assign_static_order_on_battlefield_entry(state,cid)
    return cid


def position(seat,*,target='Tarmogoyf',source_name='Shifting Woodland',forests=6,
             grave=('Counterspell','Cultivate','Forest'),hand=(),battlefield=()):
    counts=Counter((source_name,target,*grave,*hand,*battlefield));counts['Forest']+=60-sum(counts.values())
    deck=[row(name,quantity) for name,quantity in counts.items()]
    state=MatchFactory.from_decks(deck,deck,seed=71203)
    state.pregame_pending=False;state.kept_hands={1,2};state.turn=5
    state.active_player=state.priority_player=seat;state.step=Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY);player.library.append(cid)
        player.hand.clear();player.mana_pool={}
        player.lands_played_this_turn=player.land_plays_recorded_on_turn=1
        player.last_land_play_turn=state.turn
    source=place(state,seat,source_name,Zone.BATTLEFIELD)
    for _ in range(forests):place(state,seat,'Forest',Zone.BATTLEFIELD)
    target_id=place(state,seat,target,Zone.GRAVEYARD)
    for name in grave:place(state,seat,name,Zone.GRAVEYARD)
    for name in hand:place(state,seat,name,Zone.HAND)
    for name in battlefield:place(state,seat,name,Zone.BATTLEFIELD)
    return state,source,target_id


def index(state,source,word='copy'):
    abilities=[ability for ability in extract_activated_abilities(state.cards[source],state=state)
               if word in ability['text'].lower()]
    assert len(abilities)==1
    return abilities[0]['index']


def action(state,source,target):
    return {'type':'activate_ability','card_id':source,'ability_index':index(state,source),
            'targets':{'target_card_id':target}}


def copy_offer(state,seat,source):
    return [move for move in RulesEngine().legal_moves(state,seat)
            if move.get('type')=='activate_ability' and move.get('card_id')==source
            and 'copy' in (move.get('ability_label') or '').lower()]


def activate_copy(state,seat,source,target):
    assert len(copy_offer(state,seat,source))==1
    before=sum(card.tapped for cid in state.players[seat].battlefield
               if 'Land' in (card:=state.cards[cid]).types)
    state=act(state,seat,action(state,source,target))
    after=sum(card.tapped for cid in state.players[seat].battlefield
              if 'Land' in (card:=state.cards[cid]).types)
    assert after-before==4 and sum(state.players[seat].mana_pool.values())==0
    return state


def resolve_one(state):
    top=state.stack[-1].id
    for _ in range(8):
        if all(item.id!=top for item in state.stack):return state
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        state=act(state,state.priority_player,{'type':'pass_priority'})
    raise AssertionError('Native top item did not resolve')


def finish(state):
    for _ in range(64):
        if not state.stack and not state.pending_mechanic_choice:return state
        assert not state.pending_trigger_order and not state.pending_replacement_choice
        pending=state.pending_mechanic_choice
        if pending:
            assert pending['kind']=='look_top_select_hand' and pending['count']==2
            state=act(state,pending['player_id'],{'type':'choose_mechanic',
                      'card_ids':pending['options'][:pending['count']]})
        else:state=act(state,state.priority_player,{'type':'pass_priority'})
    raise AssertionError('Native fixture stack did not reach its declared boundary')


def until(state,predicate):
    for _ in range(128):
        if predicate(state):return state
        assert state.winner is None and not state.pending_trigger_order and not state.pending_replacement_choice
        if state.pending_mechanic_choice:
            pending=state.pending_mechanic_choice
            assert pending['kind']=='cleanup_discard'
            state=act(state,pending['player_id'],{'type':'choose_mechanic',
                      'card_ids':pending['options'][:pending['count']]})
        else:state=act(state,state.priority_player,{'type':'pass_priority'})
    raise AssertionError('Native continuation missed its declared boundary')


def reject_unchanged(state,seat,proposed):
    before=serialize_match_snapshot(state);rng=state.rng.getstate()
    with pytest.raises(ActionRejected):act(state,seat,proposed)
    assert serialize_match_snapshot(state)==before and state.rng.getstate()==rng


def materialized_activation(state,seat,source,word):
    idx=index(state,source,word)
    moves=[move for move in RulesEngine().legal_moves(state,seat)
           if move.get('type')=='activate_ability' and move.get('card_id')==source
           and move.get('ability_index')==idx]
    assert len(moves)==1
    before=serialize_match_snapshot(state)
    selected=AIAgent('master')._materialize_action(state,moves[0],seat)
    assert serialize_match_snapshot(state)==before and not selected.get('_invalid_ai_choice')
    return act(state,seat,selected)


@pytest.mark.parametrize('seat',[1,2])
def test_original_native_woodland_mana_control(seat):
    state,source,_=position(seat)
    state=act(state,seat,{'type':'tap_land_for_mana','card_id':source,'color':'G'})
    assert state.cards[source].tapped and state.players[seat].mana_pool.get('G')==1


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('target_name',['Tarmogoyf',"Witch's Oven",'Rest in Peace','Forest','Cauldron Familiar','Nissa, Ascended Animist'])
def test_paid_native_copy_covers_permanent_types_without_entering(target_name,seat):
    state,source,target=position(seat,target=target_name,
        grave=('Counterspell','Cultivate','Forest','Tarmogoyf') if target_name=='Forest'
              else ('Counterspell','Cultivate','Forest'))
    original=deepcopy(state.cards[source].characteristic_record['physical'])
    identity=(source,state.cards[source].owner,state.cards[source].controller,object_incarnation(state.cards[source]))
    life={pid:p.life for pid,p in state.players.items()};grave=list(state.players[seat].graveyard)
    state=activate_copy(state,seat,source,target);tapped=state.cards[source].tapped
    state=finish(state)
    assert state.cards[target].zone==Zone.GRAVEYARD
    if target_name=='Nissa, Ascended Animist':
        assert state.cards[source].zone==Zone.GRAVEYARD and state.cards[source].name=='Shifting Woodland'
        return
    card=state.cards[source]
    assert card.zone==Zone.BATTLEFIELD and card.name==target_name and card.tapped==tapped
    assert (card.id,card.owner,card.controller,object_incarnation(card))==identity
    assert values(card)==values(state.cards[target]) and card.characteristic_record['physical']==original
    assert {pid:p.life for pid,p in state.players.items()}==life and state.players[seat].graveyard==grave
    if target_name=='Tarmogoyf':assert (effective_power(state,source),effective_toughness(state,source))==(4,5)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('status',['tapped','summoning-sick'])
def test_non_tap_copy_cost_does_not_require_source_readiness(seat,status):
    state,source,target=position(seat)
    if status=='tapped':state.cards[source].tapped=True
    else:state.cards[source].summoning_sick=True;state.cards[source].entered_turn=state.turn
    state=finish(activate_copy(state,seat,source,target))
    assert state.cards[source].name=='Tarmogoyf'


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restored',[False,True])
def test_cleanup_restores_copy_base_and_roundtrips_its_lifetime(seat,restored):
    state,source,target=position(seat);turn=state.turn
    physical=deepcopy(state.cards[source].characteristic_record['physical'])
    state=finish(activate_copy(state,seat,source,target))
    if restored:state=deserialize_match_snapshot(serialize_match_snapshot(state))
    assert values(state.cards[source])['name']=='Tarmogoyf'
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].name=='Shifting Woodland' and state.cards[source].types==['Land']
    assert values(state.cards[source])=={key:physical[key] for key in values(state.cards[source])}
    assert not state.cards[source].printed_characteristics
    assert serialize_match_snapshot(deserialize_match_snapshot(serialize_match_snapshot(state)))==serialize_match_snapshot(state)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('boundary',['three-types','short-mana','wrong-color'])
def test_condition_and_native_payment_reject_before_mutation(seat,boundary):
    state,source,target=position(seat,forests=2 if boundary=='short-mana' else 0 if boundary=='wrong-color' else 6,
        grave=('Counterspell','Forest') if boundary=='three-types' else ('Counterspell','Cultivate','Forest'),
        battlefield=('Island',)*6 if boundary=='wrong-color' else (),
        hand=('Cultivate',) if boundary=='three-types' else ())
    if boundary=='three-types':
        for name in ('Tarmogoyf','Counterspell','Cultivate','Forest'):place(state,3-seat,name,Zone.GRAVEYARD)
    assert not copy_offer(state,seat,source)
    reject_unchanged(state,seat,action(state,source,target))


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('boundary',['foreign-graveyard','battlefield','instant'])
def test_wrong_target_zone_owner_or_card_type_is_not_a_copy_choice(seat,boundary):
    state,source,target=position(seat)
    if boundary=='foreign-graveyard':target=place(state,3-seat,'Tarmogoyf',Zone.GRAVEYARD)
    elif boundary=='battlefield':target=source
    else:target=next(cid for cid in state.players[seat].graveyard if state.cards[cid].name=='Counterspell')
    reject_unchanged(state,seat,action(state,source,target))


@pytest.mark.parametrize('seat',[1,2])
def test_wrong_actor_copy_request_preserves_complete_state(seat):
    state,source,target=position(seat)
    reject_unchanged(state,3-seat,action(state,source,target))


@pytest.mark.parametrize('seat',[1,2])
def test_native_Stifle_counters_copy_ability_without_refunding_cost(seat):
    state,source,target=position(seat,hand=('Stifle',),battlefield=('Island',)*4)
    state=activate_copy(state,seat,source,target);target_stack=state.stack[-1].id
    spell=next(cid for cid in state.players[seat].hand if state.cards[cid].name=='Stifle')
    state=act(state,seat,{'type':'cast_spell','card_id':spell,'cost_choice':{'id':'base'},
              'targets':{'target_stack_id':target_stack}})
    state=finish(state)
    assert state.cards[source].name=='Shifting Woodland' and state.cards[spell].zone==Zone.GRAVEYARD
    assert sum(state.cards[cid].tapped for cid in state.players[seat].battlefield)>=5


@pytest.mark.parametrize('seat',[1,2])
def test_delirium_is_only_an_activation_condition_after_real_flashback(seat):
    state,source,target=position(seat,grave=('Memory Deluge','Cultivate','Forest'),battlefield=('Island',)*10)
    state=activate_copy(state,seat,source,target)
    spell=next(cid for cid in state.players[seat].graveyard if state.cards[cid].name=='Memory Deluge')
    state=act(state,seat,{'type':'cast_spell','card_id':spell,'from_graveyard':True,'cost_choice':{'id':'flashback'}})
    state=finish(state)
    from rules_engine.card_types import graveyard_card_types
    assert len(graveyard_card_types(state,[seat]))==3 and state.cards[spell].zone==Zone.EXILE
    assert state.cards[source].name=='Tarmogoyf' and effective_power(state,source)==3


def familiar_food_position(seat):
    state,source,target=position(seat,target='Cauldron Familiar',forests=12,
        battlefield=("Witch's Oven","Witch's Oven",'Grizzly Bears'))
    ovens=[cid for cid in state.players[seat].battlefield if state.cards[cid].name=="Witch's Oven"]
    state=finish(materialized_activation(state,seat,ovens[0],'create'))
    assert any(state.cards[cid].name=='Food' for cid in state.players[seat].battlefield)
    state=activate_copy(state,seat,source,target)
    state=materialized_activation(state,seat,target,'return')
    state=resolve_one(state)
    assert state.cards[target].zone==Zone.BATTLEFIELD
    state=resolve_one(state)  # The actual Familiar entry trigger, above the old copy ability.
    return state,source,target,ovens[1]


@pytest.mark.parametrize('seat',[1,2])
def test_actual_graveyard_departure_makes_copy_target_illegal(seat):
    state,source,target,_=familiar_food_position(seat)
    state=finish(state)
    assert state.cards[target].zone==Zone.BATTLEFIELD and state.cards[source].name=='Shifting Woodland'


@pytest.mark.parametrize('seat',[1,2])
def test_actual_return_and_sacrifice_do_not_retarget_a_new_graveyard_object(seat):
    state,source,target,oven=familiar_food_position(seat)
    state=materialized_activation(state,seat,oven,'create');state=finish(state)
    assert state.cards[target].zone==Zone.GRAVEYARD and state.cards[target].zone_change_sequence>=2
    assert state.cards[source].name=='Shifting Woodland'


@pytest.mark.parametrize('seat',[1,2])
def test_actual_Cloudshift_reentry_does_not_receive_an_old_copy_ability(seat):
    state,source,target=position(seat,forests=12,hand=('Cloudshift',),battlefield=('Plains',)*8)
    state=activate_copy(state,seat,source,target);state=activate_copy(state,seat,source,target)
    state=resolve_one(state);assert state.cards[source].name=='Tarmogoyf'
    incarnation=object_incarnation(state.cards[source])
    spell=next(cid for cid in state.players[seat].hand if state.cards[cid].name=='Cloudshift')
    state=act(state,seat,{'type':'cast_spell','card_id':spell,'cost_choice':{'id':'base'},'targets':{'target_card_id':source}})
    state=finish(state)
    assert state.cards[source].zone==Zone.BATTLEFIELD and state.cards[source].name=='Shifting Woodland'
    assert object_incarnation(state.cards[source])!=incarnation


@pytest.mark.parametrize('seat',[1,2])
def test_multiple_native_copies_resolve_in_order_and_expire_together(seat):
    state,source,target=position(seat,forests=12,grave=('Counterspell','Cultivate','Forest',"Witch's Oven"));turn=state.turn
    other=next(cid for cid in state.players[seat].graveyard if state.cards[cid].name=="Witch's Oven")
    state=activate_copy(state,seat,source,target);state=activate_copy(state,seat,source,other)
    state=resolve_one(state);assert state.cards[source].name=="Witch's Oven"
    state=finish(state);assert state.cards[source].name=='Tarmogoyf'
    state=until(deserialize_match_snapshot(serialize_match_snapshot(state)),lambda s:s.turn>turn)
    assert state.cards[source].name=='Shifting Woodland'


@pytest.mark.parametrize('seat',[1,2])
def test_trusted_later_permanent_copy_is_not_undone_at_cleanup(seat):
    # Existing production copy writer; not a claimed causal permanent-copy spell.
    state,source,target=position(seat,grave=('Counterspell','Cultivate','Forest',"Witch's Oven"));turn=state.turn
    state=finish(activate_copy(state,seat,source,target))
    other=next(cid for cid in state.players[seat].graveyard if state.cards[cid].name=="Witch's Oven")
    apply(state.cards[source],values(state.cards[other]))
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].name=="Witch's Oven"


@pytest.mark.parametrize('seat',[1,2])
def test_trusted_underlying_transform_survives_temporary_copy(seat):
    from rules_engine.card_faces import apply_transform_face
    state,source,target=position(seat,source_name='Delver of Secrets // Insectile Aberration');turn=state.turn
    apply(state.cards[source],values(state.cards[target]),until_end_of_turn=True)
    apply_transform_face(state.cards[source],1)
    assert state.cards[source].name=='Tarmogoyf' and state.cards[source].selected_face_index==1
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].name=='Insectile Aberration' and effective_power(state,source)==3


@pytest.mark.parametrize('seat',[1,2])
def test_trusted_permanent_copy_remains_above_later_underlying_transform(seat):
    from rules_engine.card_faces import apply_transform_face
    state,source,target=position(seat,source_name='Delver of Secrets // Insectile Aberration',
        grave=('Counterspell','Cultivate','Forest','Shifting Woodland'));turn=state.turn
    woodland=next(cid for cid in state.players[seat].graveyard if state.cards[cid].name=='Shifting Woodland')
    apply(state.cards[source],values(state.cards[woodland]))
    state=finish(activate_copy(state,seat,source,target))
    apply_transform_face(state.cards[source],1)
    assert state.cards[source].name=='Tarmogoyf'
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].name=='Shifting Woodland' and state.cards[source].selected_face_index==1


@pytest.mark.parametrize('seat',[1,2])
def test_trusted_bestow_form_stays_above_copy_and_ends_without_losing_copy(seat):
    from rules_engine.bestow import begin_bestow,end_bestow
    state,source,target=position(seat,source_name='Springheart Nantuko',battlefield=('Grizzly Bears',));turn=state.turn
    begin_bestow(state.cards[source])
    state.cards[source].attached_to=next(cid for cid in state.players[seat].battlefield if state.cards[cid].name=='Grizzly Bears')
    apply(state.cards[source],values(state.cards[target]),until_end_of_turn=True)
    assert 'Aura' in state.cards[source].type_line and 'Creature' not in state.cards[source].types
    assert 'Creature' in values(state.cards[source])['types']
    end_bestow(state.cards[source]);assert state.cards[source].name=='Tarmogoyf' and 'Creature' in state.cards[source].types
    state=until(state,lambda s:s.turn>turn);assert state.cards[source].name=='Springheart Nantuko'


@pytest.mark.parametrize('seat',[1,2])
def test_trusted_copy_preserves_live_loyalty_counters_across_type_changes(seat):
    state,source,target=position(seat,source_name='Teferi, Hero of Dominaria',target="Witch's Oven");turn=state.turn
    state.cards[source].loyalty=7  # Explicit retained native-counter position, not copied printed loyalty.
    apply(state.cards[source],values(state.cards[target]),until_end_of_turn=True)
    assert state.cards[source].loyalty==7 and 'Planeswalker' not in state.cards[source].types
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].name=='Teferi, Hero of Dominaria' and state.cards[source].loyalty==7


@pytest.mark.parametrize('seat',[1,2])
def test_native_cleanup_removes_damage_and_expires_copy_before_state_based_actions(seat):
    state,source,target=position(seat,source_name='Grizzly Bears',hand=('Lightning Bolt',),battlefield=('Mountain',)*4);turn=state.turn
    apply(state.cards[source],values(state.cards[target]),until_end_of_turn=True)
    spell=next(cid for cid in state.players[seat].hand if state.cards[cid].name=='Lightning Bolt')
    state=act(state,seat,{'type':'cast_spell','card_id':spell,'cost_choice':{'id':'base'},'targets':{'target_card_id':source}})
    state=finish(state);assert state.cards[source].zone==Zone.BATTLEFIELD
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].zone==Zone.BATTLEFIELD and state.cards[source].name=='Grizzly Bears'


@pytest.mark.parametrize('seat',[1,2])
def test_legacy_record_preserves_recorded_current_base_without_inventing_history(seat):
    state,source,target=position(seat,grave=('Counterspell','Cultivate','Forest',"Witch's Oven"));turn=state.turn
    apply(state.cards[source],values(state.cards[target]))
    saved=serialize_match_snapshot(state);record=saved['cards'][source]['characteristic_record']
    saved['cards'][source]['characteristic_record']={key:deepcopy(record[key]) for key in ('version','physical','values')}
    saved['cards'][source]['characteristic_record']['version']=1
    state=deserialize_match_snapshot(saved)
    other=next(cid for cid in state.players[seat].graveyard if state.cards[cid].name=="Witch's Oven")
    apply(state.cards[source],values(state.cards[other]),until_end_of_turn=True)
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].name=='Tarmogoyf' and state.cards[source].characteristic_record['physical']['name']=='Shifting Woodland'


@pytest.mark.parametrize('fault',['cache','duration','base','duplicate-added','extra-key'])
def test_malformed_copy_history_is_rejected_on_snapshot_restore(fault):
    state,source,target=position(1);state=finish(activate_copy(state,1,source,target))
    saved=serialize_match_snapshot(state);record=saved['cards'][source]['characteristic_record']
    assert record['version']==2
    if fault=='cache':record['values']['name']='Explicit invalid cache'
    elif fault=='duration':record['effects'][0]['until_end_of_turn']=1
    elif fault=='base':record['base']['types']=True
    elif fault=='duplicate-added':record['added_printed_fields']=['name','name']
    else:record['unexpected_protocol_field']=True
    before=serialize_match_snapshot(state)
    with pytest.raises((ActionRejected,ValueError)):deserialize_match_snapshot(saved)
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('forests',[4,3])
def test_automatic_copy_payment_preserves_source_without_losing_necessary_mana(seat,forests):
    state,source,target=position(seat,forests=forests)
    state=activate_copy(state,seat,source,target)
    assert state.cards[source].tapped==(forests==3)
    state=finish(state)
    assert state.cards[source].name=='Tarmogoyf'


@pytest.mark.parametrize('seat',[1,2])
def test_actual_Master_can_copy_and_finish_native_combat(seat):
    state,source,_=position(seat);state.players[3-seat].life=4;agent=AIAgent('master')
    for _ in range(48):
        if state.winner is not None:break
        actor=state.priority_player
        if actor==seat:
            before=serialize_match_snapshot(state);rng=state.rng.getstate()
            chosen=agent.choose_action(state,RulesEngine().legal_moves(state,seat),seat).action
            assert serialize_match_snapshot(state)==before and state.rng.getstate()==rng
        else:chosen={'type':'pass_priority'}
        state=act(state,actor,chosen)
    assert state.winner==seat


@pytest.mark.parametrize('seat',[1,2])
def test_hidden_library_order_does_not_change_public_copy_materialization(seat):
    state,source,target=position(seat);other=deserialize_match_snapshot(serialize_match_snapshot(state))
    other.players[3-seat].library.reverse()
    answers=[]
    for root in (state,other):
        before=serialize_match_snapshot(root);rng=root.rng.getstate()
        view,moves=decision_view(root,seat,RulesEngine().legal_moves(root,seat))
        selected=next(move for move in moves if move.get('type')=='activate_ability'
                      and move.get('card_id')==source and 'copy' in (move.get('ability_label') or '').lower())
        proposed=AIAgent('master')._materialize_action(view,selected,seat)
        assert proposed['targets']['target_card_id']==target
        answers.append(proposed)
        assert serialize_match_snapshot(root)==before and root.rng.getstate()==rng
    assert answers[0]==answers[1]


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('timing',['controlled-before-turn','newly-controlled','copied-haste'])
def test_native_attack_readiness_uses_control_history_and_copied_haste(seat,timing):
    state,source,target=position(seat,target='Dreadhorde Butcher' if timing=='copied-haste' else 'Tarmogoyf')
    if timing!='controlled-before-turn':
        state.cards[source].summoning_sick=True;state.cards[source].entered_turn=state.turn
    state=finish(activate_copy(state,seat,source,target))
    state=until(state,lambda s:s.step==Step.DECLARE_ATTACKERS)
    proposed={'type':'attack','attackers':[source]}
    if timing=='newly-controlled':reject_unchanged(state,seat,proposed)
    else:
        state=act(state,seat,proposed)
        assert source in state.attackers


@pytest.mark.parametrize('seat',[1,2])
def test_trusted_native_control_change_keeps_old_source_and_ability_controller(seat):
    from rules_engine.control_effects import record_control_effect
    state,source,target=position(seat)
    state=activate_copy(state,seat,source,target);identity=object_incarnation(state.cards[source])
    record_control_effect(state,state.cards[source],3-seat)
    state=finish(state)
    assert state.cards[source].name=='Tarmogoyf' and state.cards[source].controller==3-seat
    assert state.cards[source].owner==seat and object_incarnation(state.cards[source])==identity
    assert state.cards[target].zone==Zone.GRAVEYARD and target in state.players[seat].graveyard


@pytest.mark.parametrize('seat',[1,2])
def test_actual_later_layer_animation_and_counters_survive_copy(seat):
    from rules_engine.counter_placement import put_counters
    state,source,target=position(seat,battlefield=('Liquimetal Coating',));turn=state.turn
    coating=next(cid for cid in state.players[seat].battlefield if state.cards[cid].name=='Liquimetal Coating')
    state=act(state,seat,{'type':'activate_ability','card_id':coating,'ability_index':0,
                        'targets':{'target_card_id':source}})
    state=finish(state);assert 'Artifact' in effective_types(state,source)
    put_counters(state,'+1/+1',1,target_card_id=source)
    state=finish(activate_copy(state,seat,source,target))
    assert {'Artifact','Creature'}<=set(effective_types(state,source)) and effective_power(state,source)==5
    state=until(state,lambda s:s.turn>turn)
    assert state.cards[source].types==['Land'] and state.cards[source].counters.get('+1/+1')==1


@pytest.mark.parametrize('seat',[1,2])
def test_copy_created_during_actual_cleanup_priority_expires_in_repeat_cleanup(seat):
    state,source,target=position(seat,forests=12,hand=('Forest',)*8,
        grave=('Counterspell','Cultivate','Forest','Sangromancer'));turn=state.turn
    place(state,3-seat,'Sangromancer',Zone.BATTLEFIELD)
    state.mechanic_choice_players={seat}
    state=finish(activate_copy(state,seat,source,target))
    state=until(state,lambda s:s.step==Step.CLEANUP and s.pending_mechanic_choice is not None)
    assert state.cards[source].name=='Tarmogoyf'
    pending=state.pending_mechanic_choice;assert pending['kind']=='cleanup_discard' and pending['count']==1
    state=act(state,seat,{'type':'choose_mechanic','card_ids':pending['options'][:1]})
    assert state.stack and state.cleanup_repeat_required and state.cards[source].name=='Shifting Woodland'
    state=finish(activate_copy(state,seat,source,target))
    assert state.cards[source].name=='Tarmogoyf' and state.step==Step.CLEANUP and state.turn==turn
    state=deserialize_match_snapshot(serialize_match_snapshot(state))
    for _ in range(2):state=act(state,state.priority_player,{'type':'pass_priority'})
    assert state.step==Step.CLEANUP and state.turn==turn and not state.cleanup_repeat_required
    assert state.cards[source].name=='Shifting Woodland'


@pytest.mark.parametrize('fault',['extra-tail','functional-parenthetical','different-condition','opponent-graveyard','different-source'])
def test_complete_copy_instruction_does_not_swallow_unknown_functional_text(fault):
    from rules_engine.conditional_self_copy import compile_instruction
    name='Shifting Woodland'
    text=next(ability['raw_effect_text'] for ability in extract_activated_abilities(
        type('PrintedProtocol',(),{'oracle_text':raw(name)['oracle_text'],'name':name})())
        if 'copy' in ability['text'].lower())
    if fault=='extra-tail':text+=' Draw a card.'
    elif fault=='functional-parenthetical':text+=' (Draw a card.)'
    elif fault=='different-condition':text=text.replace('four or more card types among cards in your graveyard','seven or more cards in your hand')
    elif fault=='opponent-graveyard':text=text.replace('target permanent card in your graveyard',"target permanent card in an opponent's graveyard")
    else:text='Another permanent becomes'+text.split(' becomes',1)[1]
    assert compile_instruction(text,name) is None


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('missing',['source','target'])
def test_legacy_missing_copiable_metadata_stays_legal_but_unavailable_at_resolution(seat,missing):
    state,source,target=position(seat)
    state.cards[source if missing=='source' else target].characteristic_record={}
    assert len(copy_offer(state,seat,source))==1
    state=activate_copy(state,seat,source,target)
    state=act(state,state.priority_player,{'type':'pass_priority'})
    reject_unchanged(state,state.priority_player,{'type':'pass_priority'})
    assert state.stack and state.cards[source].name=='Shifting Woodland'
