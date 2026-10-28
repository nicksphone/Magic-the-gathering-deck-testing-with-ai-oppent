"""Public canonical idle-policy regressions and explicitly synthetic finite Q."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai import foretell_policy,suspend_policy,learned_policy,learned_qv
from ai.agent import AIAgent
from ai.action_contract import complete_action
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands
from tests import test_learned_pass_stall_guard as support
from tests.test_ai_strategy_fundamentals import position
from tests.test_linked_damage_targets import raw_card
from tests.test_live_learned_policy import _binding

RULES=RulesEngine();WAIT={'type':'pass_priority'}
FIXTURES=Path(position.__code__.co_filename).parent/'fixtures'
FORETELL={r['name']:r for r in json.loads((FIXTURES/'foretell.json').read_bytes())}
RIFT=json.loads((FIXTURES/'suspend_canonical/rift-bolt.json').read_bytes())


def scene(family,seat=1,land=False):
    state,_,_,_=position(seat,[],['Forest'] if land else [])
    state.turn=1;raw=RIFT if family=='suspend' else FORETELL['Doomskar']
    card=raw_card(state,raw,seat,Zone.HAND);card.keywords=deepcopy(raw['keywords'])
    assert all(getattr(card,k)==raw[k] for k in ('name','oracle_text','mana_cost','type_line','keywords'))
    state.players[seat].mana_pool={'R':1} if family=='suspend' else {'C':2}
    action=complete_action(dict(type=family,card_id=card.id))
    checked_action(state,RULES,seat,action)
    return state,action


def hook(monkeypatch,family,callback):
    module,name=(foretell_policy,'idle_foretell_action') if family=='foretell' else (suspend_policy,'idle_suspend')
    monkeypatch.setattr(module,name,callback)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('family',['foretell','suspend'])
@pytest.mark.parametrize('style',['Burn','Control'])
def test_canonical_idle_bank_matches_baseline_without_reserve(monkeypatch,seat,family,style):
    state,action=scene(family,seat);before=serialize_match_snapshot(state)
    moves=RULES.legal_moves(deepcopy(state),seat)
    baseline=AIAgent(difficulty='master',archetype=style).choose_action(state,moves,seat)
    assert baseline.action==action
    support.synthetic_q(monkeypatch)
    agent=AIAgent(difficulty='master',archetype=style,learned_binding=_binding(learned_policy))
    decision=agent.choose_action(state,moves,seat)
    assert decision.reasoning=='Tactical-safeguarded Q ranking over a checked heuristic subset'
    assert decision.action==action and serialize_match_snapshot(state)==before
    after=checked_action(state,RULES,seat,decision.action)
    assert after.cards[action['card_id']].zone==Zone.EXILE and not after.stack
    assert sum(state.players[seat].mana_pool.values())-sum(after.players[seat].mana_pool.values())==(2 if family=='foretell' else 1)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('style',['Burn','Control'])
def test_canonical_affordable_counter_reserve_is_not_banked(monkeypatch,seat,style):
    state,action=scene('foretell',seat)
    counter=raw_card(state,FORETELL['Saw It Coming'],seat,Zone.HAND)
    state.players[seat].mana_pool={'U':3};before=serialize_match_snapshot(state)
    moves=RULES.legal_moves(deepcopy(state),seat)
    options=collect_cost_options(state,seat,counter)
    assert any(can_pay_with_pool_and_lands(state,seat,o.mana_cost,spell_types=counter.types,source_card_id=counter.id) for o in options)
    assert AIAgent(difficulty='master',archetype=style).choose_action(state,moves,seat).action==WAIT
    support.synthetic_q(monkeypatch)
    agent=AIAgent(difficulty='master',archetype=style,learned_binding=_binding(learned_policy))
    assert agent.choose_action(state,moves,seat).action==WAIT
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('family',['foretell','suspend'])
def test_helper_gets_full_public_isolated_inputs_after_all_finite_results(monkeypatch,seat,family):
    state,action=scene(family,seat,land=True);agent=AIAgent(difficulty='master',archetype='Control');seen={}
    original=support.synthetic_q
    def track(*args,**kwargs):seen['events']=original(*args,**kwargs);return seen['events']
    monkeypatch.setattr(support,'synthetic_q',track)
    def stall(view,moves,pid):seen.update(view=view,moves=moves,old_moves=deepcopy(moves));return False
    monkeypatch.setattr(agent,'_should_break_stall',stall)
    def helper(_agent,view,moves,pid):
        assert view is not seen['view'] and moves is not seen['moves']
        assert view.ai_information_player==pid==seat
        assert any(m['type']=='activate_mana_ability' for m in moves)
        assert seen['events']['scores']==['pass_priority',family]
        assert seen['events']['events']==['score','win','loss','score','win','loss']
        view.players[pid].life=999;moves.clear()
        return deepcopy(action)
    hook(monkeypatch,family,helper)
    result,_=support.route(monkeypatch,state,seat,[WAIT,action],agent=agent,forecasts=lambda _:(False,False))
    assert result==action and seen['view'].players[seat].life==20 and seen['moves']==seen['old_moves']


@pytest.mark.parametrize('family',['foretell','suspend'])
@pytest.mark.parametrize('mode',['unadmitted','mutated','nan','list','exception'])
def test_bad_helper_result_keeps_selected_pass(monkeypatch,family,mode):
    state,action=scene(family);other=raw_card(state,FORETELL['Saw It Coming'] if family=='foretell' else RIFT,1,Zone.HAND)
    outside=complete_action(dict(type=family,card_id=other.id));checked_action(state,RULES,1,outside)
    calls=[]
    def helper(*_):
        calls.append(True)
        if mode=='exception':raise ValueError('Protocol helper refusal')
        if mode=='unadmitted':return outside
        if mode=='list':return [action]
        return {**action,'unexpected':float('nan') if mode=='nan' else 1}
    hook(monkeypatch,family,helper)
    result,_=support.route(monkeypatch,state,1,[WAIT,action],agent=AIAgent(archetype='Control'),forecasts=lambda _:(False,False))
    assert result==WAIT and calls==[True]


@pytest.mark.parametrize('family',['foretell','suspend'])
@pytest.mark.parametrize('mode',['losing','unknown-pass-losing-alternative','winning-pass'])
def test_terminal_prefix_does_not_promote_missing_or_lower_class(monkeypatch,family,mode):
    state,action=scene(family)
    hook(monkeypatch,family,lambda *_:pytest.fail('Ineligible terminal prefix reached idle helper'))
    def forecast(a):
        if a['type']=='pass_priority':return (True,None) if mode=='winning-pass' else (None,None) if mode.startswith('unknown') else (False,False)
        return False,mode!='winning-pass'
    result,_=support.route(monkeypatch,state,1,[WAIT,action],agent=AIAgent(archetype='Control'),forecasts=forecast)
    assert result==WAIT


@pytest.mark.parametrize('family',['foretell','suspend'])
@pytest.mark.parametrize('key',['q','v'])
def test_late_nonfinite_rejects_before_idle_helper(monkeypatch,family,key):
    state,action=scene(family);original=support.synthetic_q
    def invalid(*args,**kwargs):
        calls=original(*args,**kwargs);prepare=learned_qv.QVPolicy.prepare
        def prepared(policy,pack):
            scores=prepare(policy,pack);predict=scores.predict
            def predict_last(action_pack):
                result=predict(action_pack)
                if len(calls['scores'])==2:result[key]=float('nan')
                return result
            scores.predict=predict_last;return scores
        monkeypatch.setattr(learned_qv.QVPolicy,'prepare',prepared);return calls
    monkeypatch.setattr(support,'synthetic_q',invalid)
    hook(monkeypatch,family,lambda *_:pytest.fail('Late invalid Q/V bypassed'))
    result,_=support.route(monkeypatch,state,1,[WAIT,action],agent=AIAgent(archetype='Control'))
    assert result is None


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('mode',['late','race'])
def test_existing_suspend_investment_veto_is_not_generic_forced(monkeypatch,seat,mode):
    state,action=scene('suspend',seat)
    if mode=='late':state.turn=10
    else:state.players[seat].life=4
    result,_=support.route(monkeypatch,state,seat,[WAIT,action],agent=AIAgent(archetype='Burn'))
    assert result==WAIT


def test_full_offers_retain_normal_cast_veto_even_when_cast_not_shortlisted(monkeypatch):
    state,action=scene('suspend');state.players[1].mana_pool={'R':3}
    assert any(m['type']=='cast_spell' for m in RULES.legal_moves(deepcopy(state),1))
    result,_=support.route(monkeypatch,state,1,[WAIT,action],agent=AIAgent(archetype='Burn'))
    assert result==WAIT


def test_wrong_family_return_cannot_cross_helper_contract(monkeypatch):
    state,foretell=scene('foretell');rift=raw_card(state,RIFT,1,Zone.HAND);state.players[1].mana_pool['R']=1
    suspend=complete_action(dict(type='suspend',card_id=rift.id))
    hook(monkeypatch,'foretell',lambda *_:suspend);hook(monkeypatch,'suspend',lambda *_:None)
    result,_=support.route(monkeypatch,state,1,[WAIT,foretell,suspend],agent=AIAgent(archetype='Control'),forecasts=lambda _:(False,False))
    assert result==WAIT


def test_no_admitted_idle_family_never_calls_helpers(monkeypatch):
    state,_,_,_=position(1,[],[])
    for family in ('foretell','suspend'):hook(monkeypatch,family,lambda *_:pytest.fail('No admitted family'))
    result,_=support.route(monkeypatch,state,1,[WAIT],agent=AIAgent(archetype='Control'))
    assert result==WAIT
