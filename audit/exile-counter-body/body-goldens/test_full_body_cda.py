"""Strict whole-creature goldens; frozen Detritivore selector dependency is explicit."""
import pytest
from game_state.state import Zone, Step
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_exiled_time_counter_bodies import (setup, choose_order, choose_targets, remove_time_counters,
                                                  one, NAMES, resume)

@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_real_freecast_body_resolves_cda_and_cleanup_does_not_expire_suspend_haste(name, seat):
    state,cid,land=setup(name,seat,1)
    remove_time_counters(state,cid)
    state=choose_targets(choose_order(state,seat,name,True),seat,land)
    state=one(resume(state))
    state=one(resume(state))
    assert state.pending_mechanic_choice['kind']=='suspend_cast'
    pool=dict(state.players[seat].mana_pool)
    state=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':cid,'from_exile':True})
    assert state.spells_cast_this_turn[seat]==1 and state.players[seat].mana_pool==pool
    state=one(resume(state))
    assert state.cards[cid].zone==Zone.BATTLEFIELD
    assert effective_power(state,cid)==effective_toughness(state,cid)==1
    assert has_keyword(state,cid,'haste')
    state.step=Step.CLEANUP
    for _ in range(2):
        state=checked_action(state,RulesEngine(),state.priority_player,{'type':'pass_priority'})
    assert state.cards[cid].zone==Zone.BATTLEFIELD and has_keyword(state,cid,'haste')
    assert effective_power(state,cid)==effective_toughness(state,cid)==1
