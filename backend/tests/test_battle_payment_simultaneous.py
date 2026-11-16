"""Genuine two-Pact continuation from declared midgame; no browser-run claim."""
from copy import deepcopy
import importlib
import importlib.util

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine

RULES=RulesEngine()
KEY='deferred_upkeep_payment'


def fixture(seat):
    name='tests.battle_payment_simultaneous_fixture'
    assert importlib.util.find_spec(name) is not None,'Simultaneous-Pact fixture is missing'
    return importlib.import_module(name).simultaneous_midgame(seat)


def advance(state,predicate):
    for _ in range(160):
        if predicate(state):return state
        assert state.winner is None
        actor=(state.pending_trigger_order or {}).get('current_controller')or state.priority_player
        moves=RULES.legal_moves(state,actor)
        ordered=next((m for m in moves if m['type']=='choose_trigger_order'),None)
        if ordered:
            action={'type':'choose_trigger_order','trigger_order':ordered['trigger_order']}
        elif any(m['type']=='block'for m in moves):action={'type':'block','blocks':{}}
        else:action={'type':'pass_priority'}
        state=checked_action(state,RULES,actor,action)
    raise AssertionError('Real transitions missed the declared continuation boundary')


def cast_both(state,ids,seat):
    for count,cid in enumerate(ids['pacts'],1):
        state=checked_action(state,RULES,seat,{'type':'cast_spell','card_id':cid})
        state=advance(state,lambda s:s.pending_mechanic_choice is not None)
        pending=state.pending_mechanic_choice
        assert pending['kind']=='search_library'and pending['player_id']==seat
        target=next(cid for cid in pending['options']if state.cards[cid].name=='Grizzly Bears')
        state=checked_action(state,RULES,seat,{'type':'choose_mechanic','card_ids':[target]})
        assert len([x for x in state.delayed_triggers if x['effect_key']==KEY])==count
    return state


def paid_count(state):
    return sum('pays {2}{G}{G} for the delayed upkeep ability.'in line for line in state.log)


@pytest.mark.parametrize('seat',[1,2])
def test_birth_preserves_canonical_stock_and_injects_no_obligation(seat):
    from card_data.seed_cards import SEED_CARD_DATA
    before=deepcopy(SEED_CARD_DATA);state,ids=fixture(seat)
    assert len(state.cards)==120
    assert all(sum(c.owner==p for c in state.cards.values())==60 for p in (1,2))
    assert sum(state.cards[cid].name=='Forest'for cid in state.players[seat].battlefield)==8
    assert len(ids['attackers'])==2
    assert sum(state.cards[cid].name=='Grizzly Bears'for cid in state.players[seat].library)==2
    assert len(ids['pacts'])==2 and all(cid in state.players[seat].hand for cid in ids['pacts'])
    assert state.pending_mechanic_choice is None and state.pending_trigger_order is None
    assert state.delayed_triggers==[] and state.stack==[] and state.winner is None
    assert state.trigger_order_choice_required is True and state.trigger_order_choice_players=={1,2}
    assert all(v==0 for player in state.players.values()for v in player.mana_pool.values())
    assert SEED_CARD_DATA==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore_after_first',[False,True])
def test_first_real_payment_preserves_second_debt_in_same_upkeep(seat,restore_after_first):
    state,ids=fixture(seat);start=state.turn
    state=cast_both(state,ids,seat)
    state=advance(state,lambda s:s.pending_trigger_order is not None)
    assert state.active_player==seat and state.step==Step.UPKEEP and state.turn>start
    moves=RULES.legal_moves(state,seat)
    order=next(m for m in moves if m['type']=='choose_trigger_order')
    assert len(order['trigger_order'])==2
    state=checked_action(state,RULES,seat,{'type':'choose_trigger_order','trigger_order':order['trigger_order']})
    assert sum(item.effect_key==KEY for item in state.stack)==2
    state=advance(state,lambda s:s.pending_mechanic_choice is not None)
    due_turn=state.turn
    assert state.pending_mechanic_choice['kind']==KEY and state.pending_mechanic_choice['options']==['pay','decline']
    assert paid_count(state)==0
    state=checked_action(state,RULES,seat,{'type':'choose_mechanic','card_ids':['pay']})
    assert state.winner is None and state.turn==due_turn and state.step==Step.UPKEEP
    assert paid_count(state)==1
    assert any(item.effect_key==KEY for item in state.stack)or(state.pending_mechanic_choice or {}).get('kind')==KEY
    if restore_after_first:
        before=serialize_match_snapshot(state)
        state=deserialize_match_snapshot(deepcopy(before))
        assert serialize_match_snapshot(state)==before
    state=advance(state,lambda s:(s.pending_mechanic_choice or {}).get('kind')==KEY)
    assert state.turn==due_turn and state.step==Step.UPKEEP and state.active_player==seat
    assert state.pending_mechanic_choice['player_id']==seat and state.pending_mechanic_choice['options']==['pay','decline']
    lands=[state.cards[cid]for cid in state.players[seat].battlefield if state.cards[cid].name=='Forest']
    assert sum(card.tapped for card in lands)==4
    state=checked_action(state,RULES,seat,{'type':'choose_mechanic','card_ids':['pay']})
    assert state.pending_mechanic_choice is None and state.pending_trigger_order is None and state.winner is None
    assert paid_count(state)==2 and all(state.cards[c.id].tapped for c in lands)
    assert not any(item.effect_key==KEY for item in state.stack)
    state=advance(state,lambda s:s.step==Step.DRAW)
    assert state.turn==due_turn and state.active_player==seat and paid_count(state)==2
