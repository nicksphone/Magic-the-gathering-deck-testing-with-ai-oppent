"""Independent canonical fixed-cost/mana boards; no private EVAL roots or labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from ai.action_contract import complete_action
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory,Step,Zone
from rules_engine.action_validation import ActionRejected,checked_action
from rules_engine.costs import collect_cost_options,check_cost_option_available
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card

FIXTURES=Path(__file__).parent/'fixtures'
PROVENANCE=json.loads((FIXTURES/'ai_joint_cast_resources/provenance.json').read_bytes())
for filename,pin in PROVENANCE['sources'].items():
    assert hashlib.sha256((FIXTURES/filename).read_bytes()).hexdigest()==pin
ROWS=json.loads((FIXTURES/'cost_reservation_overlap/canonical.json').read_bytes())
ROWS['Treasure']=json.loads((FIXTURES/'manual_mana_leftovers_a227/treasure.raw.json').read_bytes())
RULES=RulesEngine()


def position(seat,spell='Deadly Dispute',lands=1):
    names={spell,'Swamp','Forest','Island','Raging Goblin'}
    entries=[]
    for name in sorted(names):
        raw=ROWS[name]
        assert raw['object']=='card' and raw['id'] and raw['oracle_id'] and raw['uri']
        entries.append({**raw,'quantity':24 if name=='Island' else 3,'card_name':name,'image_uri':None})
    state=MatchFactory.from_decks(entries,entries,seed=61102)
    state.pregame_pending=False;state.kept_hands={1,2}
    state.step=Step.PRECOMBAT_MAIN;state.active_player=state.priority_player=seat;state.turn=5
    for p in state.players.values():
        for cid in list(p.hand):
            p.hand.remove(cid);p.library.append(cid);state.cards[cid].move_to_zone(Zone.LIBRARY)
        p.lands_played_this_turn=1
    def place(name,zone):
        if name=='Treasure':
            card=raw_card(state,ROWS[name],seat,zone);cid=card.id;card.is_token=True
        else:
            p=state.players[seat];cid=next(cid for cid in p.library if state.cards[cid].name==name)
            p.library.remove(cid);getattr(p,zone.value).append(cid);card=state.cards[cid]
            card.move_to_zone(zone)
        card.tapped=card.summoning_sick=False
        assert all(getattr(card,key)==ROWS[name][key] for key in ('oracle_text','type_line','mana_cost'))
        return cid
    cid=place(spell,Zone.HAND)
    if spell=='Crop Rotation':
        first=place('Forest',Zone.BATTLEFIELD);second=place('Swamp',Zone.BATTLEFIELD)
    else:
        for _ in range(lands):place('Swamp',Zone.BATTLEFIELD)
        first=place('Treasure',Zone.BATTLEFIELD);second=place('Raging Goblin',Zone.BATTLEFIELD)
    move=next(m for m in RULES.legal_moves(state,seat) if m.get('type')=='cast_spell' and m.get('card_id')==cid)
    return state,cid,first,second,move


def snapshot(state):
    return json.dumps(serialize_match_snapshot(state),sort_keys=True,separators=(',',':'))


def materialize(state,move,seat):
    before=snapshot(state);global_rng=random.getstate();local=state.rng.getstate();old=deepcopy(move)
    result=AIAgent('master','Drain')._materialize_action(state,move,seat)
    assert snapshot(state)==before and move==old
    assert random.getstate()==global_rng and state.rng.getstate()==local
    return result


def settle(state):
    for _ in range(24):
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order)
        if not state.stack:return state
        state=checked_action(state,RULES,state.priority_player,{'type':'pass_priority'})
    raise AssertionError('Unit native settlement bound')


@pytest.mark.parametrize('seat',[1,2])
def test_joint_additional_cost_reserves_mana_source_and_body_really_resolves(seat):
    state,cid,treasure,goblin,move=position(seat)
    option=next(o for o in collect_cost_options(state,seat,state.cards[cid]) if o.id=='base')
    assert not check_cost_option_available(state,seat,state.cards[cid],option,cost_choice={'id':'base','sacrifice_card_ids':[treasure]})
    assert check_cost_option_available(state,seat,state.cards[cid],option,cost_choice={'id':'base','sacrifice_card_ids':[goblin]})
    action=materialize(state,move,seat)
    assert not action.get('_invalid_ai_choice')
    assert action['cost_choice']=={'id':'base','sacrifice_card_ids':[goblin]}
    assert action['targets']=={}
    after=checked_action(state,RULES,seat,complete_action(action))
    assert after.stack[-1].payload['mana_spent']==2
    after=settle(after)
    assert len(set(after.players[seat].hand)-set(state.players[seat].hand))==2
    assert len(after.players[seat].library)==len(state.players[seat].library)-2
    assert len([x for x in after.players[seat].battlefield if x not in state.players[seat].battlefield and after.cards[x].name=='Treasure'])==1


@pytest.mark.parametrize('seat',[1,2])
def test_affordable_original_cheapest_selection_is_not_changed(seat):
    state,cid,treasure,goblin,move=position(seat,lands=2)
    action=materialize(state,move,seat)
    assert action['cost_choice']=={'id':'base','sacrifice_card_ids':[treasure]}
    assert action['targets']=={}
    after=settle(checked_action(state,RULES,seat,complete_action(action)))
    assert len(set(after.players[seat].hand)-set(state.players[seat].hand))==2


@pytest.mark.parametrize('seat',[1,2])
def test_land_additional_cost_uses_native_joint_feasibility_not_card_names(seat):
    state,cid,forest,swamp,move=position(seat,'Crop Rotation')
    option=next(o for o in collect_cost_options(state,seat,state.cards[cid]) if o.id=='base')
    assert check_cost_option_available(state,seat,state.cards[cid],option,cost_choice={'id':'base','sacrifice_card_ids':[forest]})
    assert check_cost_option_available(state,seat,state.cards[cid],option,cost_choice={'id':'base','sacrifice_card_ids':[swamp]})
    action=materialize(state,move,seat)
    assert not action.get('_invalid_ai_choice')
    assert action['cost_choice']=={'id':'base','sacrifice_card_ids':[swamp]}
    assert action['targets']=={}
    after=checked_action(state,RULES,seat,complete_action(action))
    assert after.cards[forest].tapped and after.cards[swamp].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
def test_explicit_land_can_tap_for_mana_before_being_sacrificed(seat):
    state,cid,forest,swamp,move=position(seat,'Crop Rotation')
    original={'id':'base','sacrifice_card_ids':[forest]}
    action=materialize(state,{**move,'cost_choice':original},seat)
    assert not action.get('_invalid_ai_choice') and action['cost_choice']==original
    after=checked_action(state,RULES,seat,complete_action(action))
    assert after.cards[forest].zone==Zone.GRAVEYARD and not after.cards[swamp].tapped


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('payable',[False,True])
def test_explicit_resource_selection_is_preserved_not_silently_repaired(seat,payable):
    state,cid,treasure,goblin,move=position(seat,lands=2 if payable else 1)
    selected=goblin if payable else treasure
    original={'id':'base','sacrifice_card_ids':[selected]}
    move={**move,'cost_choice':deepcopy(original),'resource_payment':{}}
    action=materialize(state,move,seat)
    assert action['cost_choice']==original and action['resource_payment']=={}
    assert bool(action.get('_invalid_ai_choice')) is not payable
    if payable:checked_action(state,RULES,seat,complete_action(action))


@pytest.mark.parametrize('seat',[1,2])
def test_stale_unpayable_offer_is_invalid_and_no_bad_cast_is_publicly_selected(seat):
    state,cid,treasure,goblin,move=position(seat)
    state.players[seat].battlefield.remove(goblin);state.players[seat].graveyard.append(goblin)
    state.cards[goblin].move_to_zone(Zone.GRAVEYARD)
    assert materialize(state,move,seat).get('_invalid_ai_choice')
    legal=RULES.legal_moves(state,seat)
    assert not any(x.get('type')=='cast_spell' and x.get('card_id')==cid for x in legal)
    decision=AIAgent('master','Drain').choose_action(state,legal,seat).action
    assert decision.get('card_id')!=cid
    checked_action(state,RULES,seat,decision)


@pytest.mark.parametrize('seat',[1,2])
def test_explicit_unsupported_resource_branch_is_not_replaced_by_an_automatic_one(seat):
    state,cid,treasure,goblin,move=position(seat,lands=2)
    resources={'improvise':[treasure]}
    choice={'id':'base','sacrifice_card_ids':[goblin]}
    action=materialize(state,{**move,'cost_choice':choice,'resource_payment':resources},seat)
    assert action['resource_payment']==resources and action['cost_choice']==choice
    assert action.get('_invalid_ai_choice')


@pytest.mark.parametrize('seat',[1,2])
def test_inference_never_erases_explicit_target_or_other_selected_fields(seat):
    state,cid,treasure,goblin,move=position(seat,lands=2)
    targets={'target_card_id':treasure}
    action=materialize(state,{**move,'targets':targets,'cost_choice':{'id':'base','sacrifice_card_ids':[goblin]}},seat)
    assert action['targets']==targets


@pytest.mark.parametrize('seat',[1,2])
def test_payment_completion_is_pure_and_hidden_library_identity_invariant(monkeypatch,seat):
    state,cid,treasure,goblin,move=position(seat)
    view,moves=decision_view(state,seat,[move]);before=snapshot(view)
    def no_simulation(*_args,**_kwargs):raise AssertionError('Cost completion must not resolve hypothetical futures')
    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine,'take_action',no_simulation)
        a=materialize(view,moves[0],seat)
    assert snapshot(view)==before
    other=deepcopy(state)
    other.players[seat].library.reverse();other.players[3-seat].library.reverse()
    second,offered=decision_view(other,seat,[move])
    b=materialize(second,offered[0],seat)
    assert a==b and a['cost_choice']['sacrifice_card_ids']==[goblin]
