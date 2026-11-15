"""Actual deferred-payment decisions and native deadlines, not fitted strength."""
from collections import Counter
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from card_data.seed_cards import SEED_CARD_DATA
from game_state.state import MatchFactory,Step,Zone,assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands
from tests.test_conditional_player_draw import act,cold,cast,finish,seed_add
from tests.test_deferred_upkeep_payment import due_trigger,offer,mana_entry,COPY_PRINTINGS
from tests.test_ai_recurring_engines import add as fixture_add
from tests.test_cast_resource_payments import ROWS as RESOURCE_ROWS
from tests.test_combat_keyword_triggers import CARDS as COMBAT
from tests.browser_positive83_canonical import entry as browser_entry
from tests.test_forge_negative_life_diagnostic import canonical_entry
from tests.stack_copy_printed_b720 import canonical_deck_entry


def row(name,quantity=1):
    if name in {'Forest','Swamp','Island','Mountain'}:data=mana_entry(name)
    elif name=='Grizzly Bears':data=browser_entry(name)
    elif name=='Llanowar Elves':data=RESOURCE_ROWS[name]
    elif name=='Stifle':data=COMBAT[name]
    elif name=='Twincast':data=COPY_PRINTINGS['twincast']
    elif name=='Platinum Angel':data=canonical_entry(name)
    elif name=='Lithoform Engine':return canonical_deck_entry(name,quantity)
    else:data=SEED_CARD_DATA[name]
    return {**data,'card_name':name,'quantity':quantity}


def position(seat,lands=('Forest','Swamp'),*,creature='Grizzly Bears',hand=(),battlefield=(),pacts=1):
    counts=Counter(lands);counts["Summoner's Pact"]+=pacts;counts[creature]+=1
    counts.update(hand);counts.update(battlefield)
    counts['Swamp']+=60-sum(counts.values())
    own=[row(name,quantity) for name,quantity in counts.items() if quantity]
    other=[row('Swamp',60)]
    state=MatchFactory.from_decks(own if seat==1 else other,other if seat==1 else own,seed=941)
    state.pregame_pending=False;state.kept_hands={1,2};state.turn=5
    state.step=Step.PRECOMBAT_MAIN;state.active_player=state.priority_player=seat
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY);player.library.append(cid)
        player.hand.clear();player.mana_pool={}
        player.lands_played_this_turn=player.land_plays_recorded_on_turn=1
        player.last_land_play_turn=state.turn
    def place(name,zone):
        player=state.players[seat]
        cid=next(cid for cid in player.library if state.cards[cid].name==name)
        player.library.remove(cid);getattr(player,zone.value).append(cid);card=state.cards[cid]
        card.move_to_zone(zone)
        if zone==Zone.BATTLEFIELD:
            card.summoning_sick=False;card.entered_turn=state.turn-1
            assign_static_order_on_battlefield_entry(state,cid)
        return cid
    spells=[place("Summoner's Pact",Zone.HAND) for _ in range(pacts)]
    extras={name:place(name,Zone.HAND) for name in hand}
    for name in [*lands,*battlefield]:place(name,Zone.BATTLEFIELD)
    return state,spells,extras


def decision(state,agent,seat):
    before=serialize_match_snapshot(state);rng=state.rng.getstate()
    result=agent.choose_action(state,RulesEngine().legal_moves(state,seat),seat)
    assert serialize_match_snapshot(state)==before and state.rng.getstate()==rng
    return result.action


def main_phase(state,agent,seat,watched):
    committed=False
    for _ in range(24):
        if not state.stack and state.step not in {Step.PRECOMBAT_MAIN,Step.POSTCOMBAT_MAIN}:
            return state,committed
        actor=state.priority_player
        action=decision(state,agent,seat) if actor==seat else {'type':'pass_priority'}
        committed|=action.get('type')=='cast_spell' and action.get('card_id')==watched
        state=act(state,actor,action)
        if state.pending_mechanic_choice or state.stack:
            if state.pending_mechanic_choice:
                state=act(state,seat,decision(state,agent,seat))
            else:state=finish(state)
    raise AssertionError('Native main phase did not reach its declared boundary')


def through_upkeep(state,agent,seat,start,*,finance=()):
    for _ in range(128):
        if state.winner is not None:return state
        if state.turn>start and state.active_player==seat and state.step==Step.DRAW:return state
        actor=state.priority_player
        pending=state.pending_mechanic_choice or state.pending_trigger_order or state.pending_replacement_choice
        own_due=state.turn>start and state.active_player==seat and state.step==Step.UPKEEP
        finance_available=any(state.cards[cid].zone==Zone.HAND for cid in finance)
        use_ai=actor==seat and (pending or own_due or finance_available)
        action=decision(state,agent,seat) if use_ai else {'type':'pass_priority'}
        state=act(state,actor,action)
    raise AssertionError('Native financial continuation did not reach the next own draw')


def activated_copy_position(seat,sources):
    state,spells,_=position(seat,('Forest',)*sources,battlefield=('Lithoform Engine',))
    source=next(cid for cid in state.players[seat].battlefield if state.cards[cid].name=='Lithoform Engine')
    state,target=cast(state,seat,spells[0],0)
    return state,source,target


def activated_copy_window(state,agent,seat,source,target):
    copied=False
    for _ in range(24):
        if all(item.id!=target for item in state.stack):return finish(state),copied
        actor=state.priority_player
        action=decision(state,agent,seat) if actor==seat else {'type':'pass_priority'}
        copied|=(action.get('type')=='activate_ability' and action.get('card_id')==source
                 and action.get('ability_index')==1)
        state=act(state,actor,action)
        if state.pending_mechanic_choice:
            state=act(state,seat,decision(state,agent,seat))
    raise AssertionError('Original native Pact did not leave its response window')


@pytest.mark.parametrize('seat',[1,2])
def test_AI_pays_funded_native_obligation_control(seat):
    state,spells,_=position(seat,('Forest',)*4);start=state.turn
    state,_=cast(state,seat,spells[0],0)
    state=offer(due_trigger(finish(state),seat,start))
    state=act(cold(state,True),seat,decision(state,AIAgent('master'),seat))
    assert state.winner is None and state.pending_mechanic_choice is None
    assert all(state.cards[cid].tapped for cid in state.players[seat].battlefield)


@pytest.mark.parametrize('seat',[1,2])
def test_funded_native_activated_copy_remains_legal_and_pays_both_obligations(seat):
    from ai.deferred_payment_policy import DeferredPaymentPolicy
    from ai.information import decision_view
    from ai.pending_effects import decision_projection_scope
    state,source,target=activated_copy_position(seat,8);start=state.turn
    action={'type':'activate_ability','card_id':source,'ability_index':1,'targets':{'target_stack_id':target}}
    view,moves=decision_view(state,seat,RulesEngine().legal_moves(state,seat))
    with decision_projection_scope(view,seat,128):
        assert DeferredPaymentPolicy(AIAgent('master'),view,seat).permits(action)
    state=finish(act(state,seat,action))
    assert len([row for row in state.delayed_triggers if row.get('effect_key')=='deferred_upkeep_payment'])==2
    assert through_upkeep(cold(state,True),AIAgent('master'),seat,start).winner is None


@pytest.mark.parametrize('seat',[1,2])
def test_Master_keeps_a_proved_payment_line_before_an_uncertain_extra_loan(monkeypatch,seat):
    from ai.deferred_payment_policy import DeferredPaymentPolicy
    state,source,target=activated_copy_position(seat,7);start=state.turn;accepted=[]
    original=DeferredPaymentPolicy.permits
    def observe(self,move):
        answer=original(self,move)
        if (move.get('type')=='activate_ability' and move.get('card_id')==source
                and move.get('ability_index')==1):accepted.append(answer)
        return answer
    monkeypatch.setattr(DeferredPaymentPolicy,'permits',observe)
    agent=AIAgent('master')
    state,copied=activated_copy_window(state,agent,seat,source,target)
    state=through_upkeep(cold(state,True),agent,seat,start)
    assert state.winner is None and not copied
    assert True in accepted


@pytest.mark.parametrize('seat',[1,2])
def test_learned_activation_proposal_keeps_the_same_proved_payment_fallback(monkeypatch,seat):
    from ai import learned_policy,learned_qv
    from tests.test_live_learned_policy import _binding
    from tests.test_training_reference_context import _expanded,_field
    state,source,target=activated_copy_position(seat,7);start=state.turn
    proposed={'type':'activate_ability','card_id':source,'ability_index':1,'targets':{'target_stack_id':target}}
    monkeypatch.setattr(AIAgent,'_strategic_top_actions',lambda *args:[deepcopy(proposed),{'type':'pass_priority'}])
    class Scores:
        def predict(self,pack):
            kind=_field(_expanded(pack),'type')['value']
            return {'q':1.0 if kind=='activate_ability' else 0.0,'v':0.0}
    monkeypatch.setattr(learned_qv.QVPolicy,'prepare',lambda *args:Scores())
    original=learned_policy.choose_learned_action;selected=[]
    def observe(*args,**kwargs):
        action=original(*args,**kwargs)
        selected.append(action is not None and action.get('card_id')==source)
        return action
    monkeypatch.setattr(learned_policy,'choose_learned_action',observe)
    agent=AIAgent('master',learned_binding=_binding(learned_policy))
    action=decision(state,agent,seat)
    assert selected==[True] and action=={'type':'pass_priority'}
    state=finish(act(state,seat,action))
    assert through_upkeep(cold(state,True),agent,seat,start).winner is None


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('difficulty',['master','strong'])
def test_AI_holds_unfunded_Pact_instead_of_taking_native_upkeep_loss(seat,difficulty):
    state,spells,_=position(seat);agent=AIAgent(difficulty);start=state.turn
    state,committed=main_phase(cold(state,True),agent,seat,spells[0])
    if committed:
        state=through_upkeep(state,agent,seat,start)
        assert state.winner is None
    assert not committed and state.cards[spells[0]].zone==Zone.HAND


@pytest.mark.parametrize('seat',[1,2])
def test_AI_funded_cast_remains_available_and_pays_after_real_untap(seat):
    state,spells,_=position(seat,('Forest',)*4);start=state.turn;agent=AIAgent('master')
    state,committed=main_phase(state,agent,seat,spells[0]);assert committed
    state=through_upkeep(cold(state,True),agent,seat,start)
    assert state.winner is None and state.cards[spells[0]].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
def test_currently_tapped_lands_can_fund_next_untap_payment(seat):
    state,spells,_=position(seat,('Forest',)*4)
    for cid in state.players[seat].battlefield:state.cards[cid].tapped=True
    start=state.turn;agent=AIAgent('master')
    state,committed=main_phase(state,agent,seat,spells[0]);assert committed
    assert through_upkeep(state,agent,seat,start).winner is None


@pytest.mark.parametrize('seat',[1,2])
def test_current_floating_mana_does_not_fund_next_upkeep(seat):
    state,spells,_=position(seat,());state.players[seat].mana_pool={'G':4}
    state,committed=main_phase(state,AIAgent('master'),seat,spells[0])
    assert not committed and state.cards[spells[0]].zone==Zone.HAND


@pytest.mark.parametrize('seat',[1,2])
def test_four_wrong_color_sources_do_not_fund_the_payment(seat):
    state,spells,_=position(seat,('Swamp',)*4)
    state,committed=main_phase(state,AIAgent('master'),seat,spells[0])
    assert not committed and state.cards[spells[0]].zone==Zone.HAND


@pytest.mark.parametrize('seat',[1,2])
def test_cast_only_mana_does_not_fund_the_future_effect(seat):
    from tests.test_land_type_layers import add
    state,spells,_=position(seat,())
    for _ in range(4):add(state,'Ancient Ziggurat',seat)
    state,committed=main_phase(state,AIAgent('master'),seat,spells[0])
    assert not committed


@pytest.mark.parametrize('seat',[1,2])
def test_existing_obligation_is_not_double_funded_by_four_lands(seat):
    state,spells,_=position(seat,('Forest',)*4,pacts=2);start=state.turn;agent=AIAgent('master')
    state,_=cast(state,seat,spells[0],0);state=finish(state)
    state,committed=main_phase(cold(state,True),agent,seat,spells[1])
    assert not committed and state.cards[spells[1]].zone==Zone.HAND
    assert through_upkeep(state,agent,seat,start).winner is None


@pytest.mark.parametrize('seat',[1,2])
def test_known_search_mana_creature_finances_the_commitment(seat):
    state,spells,_=position(seat,('Forest','Swamp','Swamp'),creature='Llanowar Elves')
    start=state.turn;agent=AIAgent('master')
    state,committed=main_phase(state,agent,seat,spells[0]);assert committed
    elf=next(cid for cid in state.players[seat].hand+state.players[seat].battlefield if state.cards[cid].name=='Llanowar Elves')
    state=through_upkeep(cold(state,True),agent,seat,start,finance=(elf,))
    assert state.winner is None and state.cards[elf].zone==Zone.BATTLEFIELD


@pytest.mark.parametrize('seat',[1,2])
def test_native_resource_spell_preserves_and_finances_payment(seat):
    state,spells,extras=position(seat,('Forest','Forest','Swamp'),hand=('Deadly Dispute',),battlefield=('Grizzly Bears',))
    start=state.turn;agent=AIAgent('master')
    state,committed=main_phase(state,agent,seat,spells[0]);assert committed
    state=through_upkeep(cold(state,True),agent,seat,start,finance=(extras['Deadly Dispute'],))
    assert state.winner is None and state.cards[extras['Deadly Dispute']].zone==Zone.GRAVEYARD
    assert len([cid for cid in state.players[seat].battlefield if 'Land' in state.cards[cid].types])==3


@pytest.mark.parametrize('seat',[1,2])
def test_native_Stifle_continuation_can_cancel_the_payment(seat):
    state,spells,extras=position(seat,('Forest','Island'),hand=('Stifle',))
    start=state.turn;agent=AIAgent('master')
    state,committed=main_phase(state,agent,seat,spells[0]);assert committed
    state=through_upkeep(cold(state,True),agent,seat,start,finance=(extras['Stifle'],))
    assert state.winner is None and state.cards[extras['Stifle']].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
def test_borrowed_mana_source_returns_before_the_deadline(seat):
    state,spells,extras=position(seat,('Forest','Forest','Mountain'),hand=('Claim the Firstborn',))
    elf=fixture_add(state,'Llanowar Elves',3-seat,cards=RESOURCE_ROWS)
    elf.summoning_sick=False
    state.players[seat].mana_pool={'R':1}
    state,_=cast(state,seat,extras['Claim the Firstborn'],1,{'target_card_id':elf.id});state=finish(state)
    assert can_pay_with_pool_and_lands(state,seat,'{2}{G}{G}',payment_kind='effect',apply_modifiers=False)
    state,committed=main_phase(state,AIAgent('master'),seat,spells[0])
    assert not committed and state.cards[spells[0]].zone==Zone.HAND


@pytest.mark.parametrize('seat',[1,2])
def test_AI_does_not_copy_a_Pact_into_unfunded_double_obligations(seat):
    state,spells,extras=position(seat,('Forest',)*4+('Island',)*2,hand=('Twincast',))
    state,target=cast(state,seat,spells[0],0)
    action=decision(state,AIAgent('master'),seat)
    assert not (action.get('type')=='cast_spell' and action.get('card_id')==extras['Twincast'])
    state=act(state,seat,action)
    assert state.cards[extras['Twincast']].zone==Zone.HAND


@pytest.mark.parametrize('seat',[1,2])
def test_copy_remains_funded_when_the_original_is_countered(seat):
    from ai.deferred_payment_policy import DeferredPaymentPolicy
    from ai.information import decision_view
    state,spells,extras=position(seat,('Forest',)*4,hand=('Twincast',))
    counter=seed_add(state,'Counterspell',3-seat)
    state.players[seat].mana_pool={'U':2};state.players[3-seat].mana_pool={'U':2}
    start=state.turn;state,target=cast(state,seat,spells[0],0)
    state=act(state,seat,{'type':'pass_priority'})
    state,_=cast(state,3-seat,counter,2,{'target_stack_id':target})
    state=act(state,3-seat,{'type':'pass_priority'})
    action={'type':'cast_spell','card_id':extras['Twincast'],'cost_choice':{'id':'base'},'targets':{'target_stack_id':target}}
    view,moves=decision_view(state,seat,RulesEngine().legal_moves(state,seat))
    assert DeferredPaymentPolicy(AIAgent('master'),view,seat).permits(action)
    state=act(state,seat,action);state=finish(state)
    assert through_upkeep(state,AIAgent('master'),seat,start).winner is None


@pytest.mark.parametrize('seat',[1,2])
def test_loss_prohibition_preserves_a_native_unfunded_line(seat):
    from ai.deferred_payment_policy import DeferredPaymentPolicy
    from ai.information import decision_view
    state,spells,_=position(seat,battlefield=('Platinum Angel',));start=state.turn
    action={'type':'cast_spell','card_id':spells[0],'cost_choice':{'id':'base'}}
    view,moves=decision_view(state,seat,RulesEngine().legal_moves(state,seat))
    assert DeferredPaymentPolicy(AIAgent('master'),view,seat).permits(action)
    state=act(state,seat,action);state=finish(state)
    assert through_upkeep(state,AIAgent('master'),seat,start).winner is None


@pytest.mark.parametrize('seat',[1,2])
def test_checked_winning_stack_finishes_before_the_new_payment(seat):
    from ai.deferred_payment_policy import DeferredPaymentPolicy
    from ai.information import decision_view
    state,spells,extras=position(seat,hand=('Lightning Bolt',))
    state.players[3-seat].life=3;state.players[seat].mana_pool={'R':1}
    state,_=cast(state,seat,extras['Lightning Bolt'],1,{'target_player':3-seat})
    action={'type':'cast_spell','card_id':spells[0],'cost_choice':{'id':'base'}}
    view,moves=decision_view(state,seat,RulesEngine().legal_moves(state,seat))
    assert DeferredPaymentPolicy(AIAgent('master'),view,seat).permits(action)
    state=finish(act(state,seat,action))
    assert state.winner==seat


@pytest.mark.parametrize('seat',[1,2])
def test_hidden_library_order_does_not_change_the_financial_decision(seat):
    state,spells,_=position(seat)
    changed=cold(state,True);changed.players[seat].library.reverse()
    a=decision(state,AIAgent('master'),seat);b=decision(changed,AIAgent('master'),seat)
    assert a==b=={'type':'pass_priority'}


@pytest.mark.parametrize('seat',[1,2])
def test_learned_Q_proposal_uses_the_same_native_financial_guard(monkeypatch,seat):
    from ai import learned_policy,learned_qv
    from tests.test_live_learned_policy import _binding
    from tests.test_training_reference_context import _expanded,_field
    state,spells,_=position(seat)
    proposed={'type':'cast_spell','card_id':spells[0],'cost_choice':{'id':'base'}}
    monkeypatch.setattr(AIAgent,'_strategic_top_actions',lambda *args:[deepcopy(proposed),{'type':'pass_priority'}])
    class Scores:
        def predict(self,pack):
            kind=_field(_expanded(pack),'type')['value']
            return {'q':1.0 if kind=='cast_spell' else 0.0,'v':0.0}
    monkeypatch.setattr(learned_qv.QVPolicy,'prepare',lambda *args:Scores())
    original=learned_policy.choose_learned_action;selected=[]
    def observe(*args,**kwargs):
        action=original(*args,**kwargs)
        selected.append(action is not None and action.get('card_id')==spells[0])
        return action
    monkeypatch.setattr(learned_policy,'choose_learned_action',observe)
    agent=AIAgent('master',learned_binding=_binding(learned_policy))
    action=decision(state,agent,seat)
    assert selected==[True] and action=={'type':'pass_priority'}
    assert act(state,seat,action).cards[spells[0]].zone==Zone.HAND


def test_exhausted_forecast_does_not_turn_unknown_into_a_loss_proof():
    from ai.deferred_payment_policy import DeferredPaymentPolicy
    from ai.information import decision_view
    from ai.pending_effects import decision_projection_scope
    state,spells,_=position(1,hand=('Stifle',),lands=('Forest','Island'))
    view,moves=decision_view(state,1,RulesEngine().legal_moves(state,1))
    before=serialize_match_snapshot(view)
    with decision_projection_scope(view,1,0):
        assert DeferredPaymentPolicy(AIAgent('master'),view,1).permits({
            'type':'cast_spell','card_id':spells[0],'cost_choice':{'id':'base'}})
    assert serialize_match_snapshot(view)==before
    from ai.pending_effects import combat_expansion_available
    state,source,target=activated_copy_position(1,7)
    view,moves=decision_view(state,1,RulesEngine().legal_moves(state,1));before=serialize_match_snapshot(view)
    copy={'type':'activate_ability','card_id':source,'ability_index':1,'targets':{'target_stack_id':target}}
    with decision_projection_scope(view,1,0):
        assert not combat_expansion_available(charge=True)
        policy=DeferredPaymentPolicy(AIAgent('master'),view,1)
        assert policy.permits(copy) and policy.funded_alternative(copy,moves) is None
    with decision_projection_scope(view,1,1):
        policy=DeferredPaymentPolicy(AIAgent('master'),view,1)
        assert policy.permits({'type':'pass_priority'}) and policy.permits(copy)
        for _ in range(2):combat_expansion_available(charge=True)
        assert not combat_expansion_available()
        assert policy.funded_alternative(copy,moves)=={'type':'pass_priority'}
    assert serialize_match_snapshot(view)==before
