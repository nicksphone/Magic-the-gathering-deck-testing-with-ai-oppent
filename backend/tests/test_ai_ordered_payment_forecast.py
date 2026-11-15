"""Native simultaneous payment ordering cannot certify an incomplete forecast."""
import pytest

from ai.agent import AIAgent
from ai.deferred_payment_policy import DeferredPaymentPolicy
from ai.information import decision_view
from ai.pending_effects import decision_projection_scope
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_ai_deferred_payments import position,through_upkeep
from tests.test_conditional_player_draw import cast,finish,cold


def two_obligations(seat,sources):
    state,spells,_=position(seat,('Forest',)*sources,pacts=2)
    start=state.turn
    for spell in spells:
        state,_=cast(state,seat,spell,0)
        state=finish(state)
    assert len([row for row in state.delayed_triggers
                if row.get('effect_key')=='deferred_upkeep_payment'])==2
    state.trigger_order_choice_required=True
    state.trigger_order_choice_players={seat}
    return cold(state,True),start


@pytest.mark.parametrize('seat',[1,2])
def test_native_ordered_funded_payment_control(seat):
    state,start=two_obligations(seat,8)
    state=through_upkeep(state,AIAgent('master'),seat,start)
    assert state.winner is None
    assert not state.delayed_triggers and not state.pending_trigger_order
    assert not state.pending_mechanic_choice
    assert all(state.cards[cid].tapped for cid in state.players[seat].battlefield)


@pytest.mark.parametrize('seat',[1,2])
def test_unresolved_native_payment_order_is_not_a_survival_proof(seat):
    state,start=two_obligations(seat,4);agent=AIAgent('master')
    view,_=decision_view(state,seat,RulesEngine().legal_moves(state,seat))
    before=serialize_match_snapshot(view);rng=view.rng.getstate()
    with decision_projection_scope(view,seat,128):
        outcome=DeferredPaymentPolicy(agent,view,seat)._forecast(view,0,allow_financing=False)
    assert serialize_match_snapshot(view)==before and view.rng.getstate()==rng
    state=through_upkeep(state,agent,seat,start)
    assert state.winner==3-seat
    assert outcome is None
