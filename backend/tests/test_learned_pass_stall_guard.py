"""Public canonical positions and synthetic adverse Q, never fitted-model proof."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ai import learned_policy, learned_qv, pending_effects
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import inspect_target_hints
from tests.test_ai_strategy_fundamentals import position
from tests.test_learned_tactical_guard import _cast
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _field

RULES=RulesEngine()
WAIT={'type':'pass_priority'}


def synthetic_q(monkeypatch, *, bad_last=False, only_main=False):
    calls={'scores':[],'states':[],'events':[]}
    class Scores:
        def __init__(self,bias):self.bias=bias
        def predict(self,pack):
            kind=_field(pack['root'],'type')['value']
            calls['scores'].append(kind);calls['events'].append('score')
            return {'q':float('nan') if bad_last and len(calls['scores'])==2
                    else (.193 if kind=='pass_priority' else -.708) if self.bias else 0.0,'v':0.0}
    def prepare(_policy,pack):
        calls['states'].append(deepcopy(pack))
        step=_field(_field(pack['root'],'observation'),'step')['value']
        return Scores(not only_main or step in {'precombat_main','postcombat_main'})
    monkeypatch.setattr(learned_qv.QVPolicy,'prepare',prepare)
    return calls


def candidate(state,cards,seat,name):
    if name=='Boros Charm':
        mode=next(text for text in inspect_target_hints(state,state.cards[cards[name]],seat)['modes']
                  if 'deals 4 damage' in text)
        action=_cast(state,cards,seat,name,{'mode_text':mode,'target_player':3-seat})
    else:
        action=_cast(state,cards,seat,name,{'target_player':3-seat}
                     if name in {'Lightning Bolt','Lava Spike'} else {})
    checked_action(state,RULES,seat,action)
    return action


def route(monkeypatch,state,seat,proposals,*,agent=None,bad_last=False,forecasts=None):
    calls=synthetic_q(monkeypatch,bad_last=bad_last)
    binding=_binding(learned_policy)
    agent=agent or AIAgent(difficulty='master',archetype='Burn')
    monkeypatch.setattr(agent,'_strategic_top_actions',lambda *_:deepcopy(proposals))
    wins,losses=pending_effects.unanswered_action_wins,pending_effects.unanswered_action_loses
    def win(view,pid,action,**kwargs):
        calls['events'].append('win')
        return forecasts(action)[0] if forecasts else wins(view,pid,action,**kwargs)
    def loss(view,pid,action,**kwargs):
        calls['events'].append('loss')
        return forecasts(action)[1] if forecasts else losses(view,pid,action,**kwargs)
    monkeypatch.setattr(pending_effects,'unanswered_action_wins',win)
    monkeypatch.setattr(pending_effects,'unanswered_action_loses',loss)
    before=serialize_match_snapshot(state)
    moves=RULES.legal_moves(deepcopy(state),seat);old_moves=deepcopy(moves)
    view,supplied=decision_view(state,seat,moves)
    answer=learned_policy.choose_learned_action(binding,agent,view,supplied,seat,
        admit=lambda action:checked_action(state,RULES,seat,action))
    assert serialize_match_snapshot(state)==before and moves==old_moves
    return answer,calls


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name,lands',[('Boros Charm',['Plateau','Mountain']),
                                     ('Llanowar Elves',['Forest'])])
def test_actual_existing_proactive_helper_overrides_adverse_q_pass(monkeypatch,seat,name,lands):
    state,cards,_,_=position(seat,[name],lands)
    action=candidate(state,cards,seat,name)
    result,calls=route(monkeypatch,state,seat,[WAIT,action])
    assert calls['scores']==['pass_priority','cast_spell']
    assert result==action
    after=checked_action(state,RULES,seat,result)
    assert after.stack and after.stack[-1].source_card_id==cards[name]


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('window',['control','opponent-turn','nonempty-stack','forced-pass','unpayable'])
def test_existing_hold_windows_do_not_force_proactive_conversion(monkeypatch,seat,window):
    if window=='nonempty-stack':
        state,cards,_,_=position(seat,['Monastery Swiftspear','Lightning Bolt'],['Mountain']*2)
        state=checked_action(state,RULES,seat,_cast(state,cards,seat,'Monastery Swiftspear'))
        action=candidate(state,cards,seat,'Lightning Bolt')
    elif window in {'forced-pass','unpayable'}:
        state,cards,_,_=position(seat,['Lightning Bolt'] if window=='unpayable' else [],[])
        action=None
    else:
        state,cards,_,_=position(seat,['Opt'] if window=='control' else ['Lightning Bolt'],
                                  ['Island'] if window=='control' else ['Mountain'])
        if window=='opponent-turn':state.active_player=3-seat
        action=candidate(state,cards,seat,'Opt' if window=='control' else 'Lightning Bolt')
    agent=AIAgent(difficulty='master',archetype='Control' if window=='control' else 'Burn')
    proposals=[WAIT]+([action] if action else [])
    result,_=route(monkeypatch,state,seat,proposals,agent=agent)
    assert result==WAIT


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('mode',['winning-pass','losing-alternative','equal-class'])
def test_terminal_prefix_constrains_helper_after_all_qv_and_forecasts(monkeypatch,seat,mode):
    state,cards,_,_=position(seat,['Llanowar Elves'],['Forest'])
    action=candidate(state,cards,seat,'Llanowar Elves')
    agent=AIAgent(difficulty='master',archetype='Burn');offered=[]
    def proactive(rows,view,pid):
        offered.append(deepcopy(rows))
        assert view.ai_information_player==pid==seat
        assert events['scores']==['pass_priority','cast_spell']
        assert events['events']==['score','win','loss','score','win','loss']
        return deepcopy(rows[0])
    monkeypatch.setattr(agent,'_best_proactive_non_pass',proactive)
    def forecasts(move):
        if mode=='winning-pass' and move['type']=='pass_priority':return True,None
        return False, mode=='losing-alternative' and move['type']!='pass_priority'
    events={}
    # Capture the live score observer before the helper runs.
    original_prepare=synthetic_q
    def capture(*args,**kwargs):
        result=original_prepare(*args,**kwargs);events.update(result);return result
    monkeypatch.setattr(__import__(__name__,fromlist=['synthetic_q']),'synthetic_q',capture)
    result,_=route(monkeypatch,state,seat,[WAIT,action],agent=agent,forecasts=forecasts)
    assert result==(action if mode=='equal-class' else WAIT)
    assert offered==([ [action] ] if mode=='equal-class' else [])


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('mode',['unadmitted','mutated','empty-attack'])
def test_helper_cannot_escape_exact_preadmitted_subset(monkeypatch,seat,mode):
    state,cards,_,_=position(seat,['Llanowar Elves','Monastery Swiftspear'],['Forest','Mountain'])
    action=candidate(state,cards,seat,'Llanowar Elves')
    outside=candidate(state,cards,seat,'Monastery Swiftspear')
    agent=AIAgent(difficulty='master',archetype='Burn')
    def proactive(rows,_view,_seat):
        assert rows==[action]
        if mode=='unadmitted':return deepcopy(outside)
        if mode=='empty-attack':return {'type':'attack','attackers':[]}
        rows[0]['targets']['unadmitted_choice']=1
        return rows[0]
    monkeypatch.setattr(agent,'_best_proactive_non_pass',proactive)
    result,_=route(monkeypatch,state,seat,[WAIT,action],agent=agent)
    assert result==WAIT and 'unadmitted_choice' not in action['targets']


@pytest.mark.parametrize('seat',[1,2])
def test_existing_x_veto_retains_pass(monkeypatch,seat):
    state,cards,_,_=position(seat,['Llanowar Elves'],['Forest'])
    action=candidate(state,cards,seat,'Llanowar Elves')
    agent=AIAgent(difficulty='master',archetype='Burn')
    # Explicit helper-veto protocol; the fixture is NOT represented as an X spell.
    monkeypatch.setattr(agent,'_is_unplayable_x_action',lambda move:move==action)
    monkeypatch.setattr(agent,'_best_proactive_non_pass',lambda *_:pytest.fail('Vetoed option offered'))
    result,_=route(monkeypatch,state,seat,[WAIT,action],agent=agent)
    assert result==WAIT


@pytest.mark.parametrize('seat',[1,2])
def test_only_resource_tapping_does_not_trigger_proactive_helper(monkeypatch,seat):
    state,_,_,_=position(seat,[],['Forest'])
    moves=RULES.legal_moves(deepcopy(state),seat)
    offered=next(move for move in moves if move['type']=='activate_mana_ability')
    action=complete_action({'type':offered['type'],'card_id':offered['card_id'],
                           'ability_index':offered['ability_index'],'color':'G'})
    checked_action(state,RULES,seat,action)
    agent=AIAgent(difficulty='master',archetype='Burn')
    view,supplied=decision_view(state,seat,moves)
    assert agent._should_break_stall(view,supplied,seat) is True
    result,_=route(monkeypatch,state,seat,[WAIT,action],agent=agent)
    assert result==WAIT


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('winning_pass',[False,True])
def test_late_nan_rejects_before_proactive_or_winning_pass_return(monkeypatch,seat,winning_pass):
    state,cards,_,_=position(seat,['Llanowar Elves'],['Forest'])
    action=candidate(state,cards,seat,'Llanowar Elves')
    agent=AIAgent(difficulty='master',archetype='Burn')
    monkeypatch.setattr(agent,'_best_proactive_non_pass',lambda *_:pytest.fail('Late NaN bypassed'))
    result,_=route(monkeypatch,state,seat,[WAIT,action],agent=agent,bad_last=True,
        forecasts=lambda move:(True,None) if winning_pass and move['type']=='pass_priority' else (False,False))
    assert result is None


def test_old_protocol_agent_without_helpers_keeps_existing_pass(monkeypatch):
    state,cards,_,_=position(1,['Llanowar Elves'],['Forest'])
    action=candidate(state,cards,1,'Llanowar Elves')
    agent=SimpleNamespace(_strategic_top_actions=lambda *_:None)
    result,_=route(monkeypatch,state,1,[WAIT,action],agent=agent)
    assert result==WAIT


@pytest.mark.parametrize('seat',[1,2])
def test_hidden_identity_order_and_private_log_do_not_change_proactive_guard(monkeypatch,seat):
    state,cards,_,_=position(seat,['Llanowar Elves'],['Forest'])
    opponent=state.players[3-seat]
    for _ in range(2):
        cid=opponent.library.pop();state.cards[cid].move_to_zone(Zone.HAND);opponent.hand.append(cid)
    action=candidate(state,cards,seat,'Llanowar Elves')
    first,calls=route(monkeypatch,state,seat,[WAIT,action])
    hidden=deepcopy(state);hidden.players[3-seat].hand.reverse();hidden.players[3-seat].library.reverse()
    hidden.log.append('PRIVATE_STALL_GUARD_CANARY')
    second,changed=route(monkeypatch,hidden,seat,[WAIT,action])
    assert first==second==action and calls['states']==changed['states']
    assert 'PRIVATE_STALL_GUARD_CANARY' not in json.dumps(calls['states'])


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('pending',[False,True])
@pytest.mark.parametrize('spell',['Lava Spike','Lightning Bolt'])
def test_actual_full_turn_after_checked_spear_spends_available_burn(monkeypatch,seat,pending,spell):
    state,cards,_,_=position(seat,['Monastery Swiftspear',spell],['Mountain']*2)
    state.players[seat].life=state.players[3-seat].life=12
    state=checked_action(state,RULES,seat,_cast(state,cards,seat,'Monastery Swiftspear'))
    if not pending:
        for _ in range(8):
            if not state.stack:break
            state=checked_action(state,RULES,state.priority_player,WAIT)
        assert not state.stack
    # Bias only the main-phase pass/burn comparison; combat ties retain the
    # genuine strategic shortlist order rather than introducing a second bug.
    synthetic_q(monkeypatch,only_main=True)
    agent=AIAgent(difficulty='master',archetype='Burn',opponent_archetype='Tribal',
                  learned_binding=_binding(learned_policy))
    turn=state.turn;own=[]
    for _ in range(64):
        if state.turn!=turn or state.winner is not None:break
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order)
        actor=state.priority_player
        moves=RULES.legal_moves(deepcopy(state),actor)
        before=serialize_match_snapshot(state);old_moves=deepcopy(moves)
        if actor==seat:
            action=agent.choose_action(state,moves,seat).action
            own.append((bool(state.stack),deepcopy(action)))
        else:
            action={'type':'block','blocks':{}} if any(m['type']=='block' for m in moves) else WAIT
        after=checked_action(state,RULES,actor,action)
        assert serialize_match_snapshot(state)==before and moves==old_moves
        state=after
    assert state.turn!=turn and state.winner is None
    assert state.players[3-seat].life==7, own
    assert state.cards[cards[spell]].zone==Zone.GRAVEYARD
    assert any(not stack and a.get('card_id')==cards[spell] for stack,a in own)
    if pending:assert own[0]==(True,WAIT)
