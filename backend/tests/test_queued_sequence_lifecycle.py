"""Full canonical lifecycle interactions without events or Oracle replacement."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle
import pytest
from game_state.state import MatchFactory, Zone, Step
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.action_validation import ActionRejected
from tests.queued_sequence_support import add, cast, act, position, resume, facts
from tests.desired_extra_sequence_contracts import next_upkeep

FIXTURE = Path(__file__).parent / 'fixtures/queued_lifecycle'
RAW = json.loads((FIXTURE/'canonical.json').read_text())


def put(state, name, seat):
    sample=MatchFactory.from_decks([{**RAW[name],'card_name':name,'quantity':1}],[],seed=7214)
    card=deepcopy(next(iter(sample.cards.values())))
    card.id=state.allocate_object_id();card.owner=card.controller=seat
    card.move_to_zone(Zone.BATTLEFIELD);card.entered_turn=state.turn
    state.cards[card.id]=card;state.players[seat].battlefield.append(card.id)
    return card


def test_independent_canonical_lifecycle_intake():
    proof=json.loads((FIXTURE/'provenance.json').read_text())
    assert proof['intake_before_tests'] and not proof['facts_modified']
    assert proof['canonical_sha256']==hashlib.sha256((FIXTURE/'canonical.json').read_bytes()).hexdigest()
    for name,row in RAW.items():
        assert proof['rows'][name]['id']==row['id']
        assert proof['rows'][name]['raw_sha256']==hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@pytest.mark.parametrize('seat',[1,2])
def test_actual_extra_upkeep_apnap_both_canonical_sources_once(seat):
    state=position(seat)
    sources=[put(state,'Verdant Force',pid).id for pid in (seat,3-seat)]
    state,_=cast(state,'Time Warp',seat,{'target_player':seat})
    assert resolve_top_of_stack(state)
    next_upkeep(state)
    assert state.turn==6 and state.active_player==seat
    assert [s.controller for s in state.stack]==[seat,3-seat]
    assert [s.source_card_id for s in state.stack]==sources
    saved=serialize_match_snapshot(state);state=resume(state)
    assert serialize_match_snapshot(state)==saved
    for expected in (3-seat,seat):
        assert state.stack[-1].controller==expected and resolve_top_of_stack(state)
    tokens=[c for c in state.cards.values() if c.is_token]
    assert len(tokens)==2 and {c.controller for c in tokens}=={1,2}
    assert all(c.power==c.toughness==1 and c.colors==['G'] and 'Saproling' in c.type_line for c in tokens)
    RulesEngine().next_step(state)
    assert state.step==Step.DRAW and not state.stack
    assert len([c for c in state.cards.values() if c.is_token])==2


@pytest.mark.parametrize('seat',[1,2])
def test_actual_cleanup_discard_trigger_then_repeat_before_queued_turn(seat):
    state=position(seat)
    source=put(state,'Sangromancer',3-seat)
    state,_=cast(state,'Time Warp',seat,{'target_player':seat})
    assert resolve_top_of_stack(state)
    for _ in range(8):add(state,'Island',seat)
    state.mechanic_choice_players={seat}
    while state.step!=Step.CLEANUP:RulesEngine().next_step(state)
    pending=state.pending_mechanic_choice
    state=act(state,seat,{'type':'choose_mechanic','card_ids':pending['options'][:pending['count']]})
    assert state.stack[-1].source_card_id==source.id and state.cleanup_repeat_required
    assert state.turn==5 and len(state.extra_turns)==1
    cursor=state.phase_cursor;state=resume(state)
    if state.stack[-1].payload.get('__optional'):
        available=RulesEngine().legal_moves(state,state.priority_player)
        if any(a['type']=='choose_optional_effect' for a in available):
            state=act(state,state.priority_player,next(a for a in available if a.get('accept') is True))
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life==23
    assert state.turn==5 and state.phase_cursor==cursor and len(state.extra_turns)==1
    RulesEngine().next_step(state)
    assert state.step==Step.CLEANUP and state.turn==5 and not state.cleanup_repeat_required
    RulesEngine().next_step(state)
    assert state.turn==6 and state.active_player==seat


@pytest.mark.parametrize('seat',[1,2])
def test_first_strike_real_sba_death_does_not_advance_visit_twice(seat):
    state=position(seat,Step.POSTCOMBAT_MAIN)
    assault=add(state,'Aggravated Assault',seat,Zone.BATTLEFIELD)
    knight=add(state,'Youthful Knight',seat,Zone.BATTLEFIELD)
    bear=add(state,'Grizzly Bears',3-seat,Zone.BATTLEFIELD)
    state.cards[knight.id].summoning_sick=False;state.cards[knight.id].entered_turn=4
    state=act(state,seat,{'type':'activate_ability','card_id':assault.id,'ability_index':0})
    assert resolve_top_of_stack(state)
    RulesEngine().next_step(state);RulesEngine().next_step(state)
    state=act(state,seat,{'type':'attack','attackers':[knight.id]})
    RulesEngine().next_step(state)
    state=act(state,3-seat,{'type':'block','blocks':{knight.id:[bear.id]}})
    RulesEngine().next_step(state)
    assert state.combat_damage_stage=='first'
    assert state.cards[bear.id].zone==Zone.GRAVEYARD and state.cards[knight.id].zone==Zone.BATTLEFIELD
    cursor=state.phase_cursor;state=resume(state)
    RulesEngine().next_step(state)
    assert state.phase_cursor==cursor and state.combat_damage_stage=='regular'
    RulesEngine().next_step(state)
    assert state.phase_cursor==cursor and state.step==Step.END_COMBAT
    RulesEngine().next_step(state)
    assert state.phase_cursor==cursor+1 and state.step==Step.POSTCOMBAT_MAIN


@pytest.mark.parametrize('seat',[1,2])
def test_copied_controller_instruction_uses_copy_controller_not_original(seat):
    state=position(seat)
    state,_=cast(state,'Temporal Manipulation',seat)
    target=state.stack[-1].id;state.priority_player=3-seat
    state,_=cast(state,'Twincast',3-seat,{'target_stack_id':target})
    assert resolve_top_of_stack(state)
    assert state.stack[-1].controller==3-seat
    assert resolve_top_of_stack(state)
    assert state.extra_turns[-1]['recipient']==3-seat
    assert resolve_top_of_stack(state)
    for expected in (seat,3-seat,3-seat):
        next_upkeep(state);assert state.active_player==expected


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('invalid',['target','mana','timing'])
def test_admitted_family_invalid_actions_keep_root_rng_exact(seat,invalid):
    state=position(seat)
    source=add(state,'Time Warp' if invalid=='target' else 'Aggravated Assault',seat,
               Zone.HAND if invalid=='target' else Zone.BATTLEFIELD)
    action={'type':'cast_spell','card_id':source.id,'targets':{'target_player':3}} if invalid=='target' else {
        'type':'activate_ability','card_id':source.id,'ability_index':0}
    if invalid=='mana':state.players[seat].mana_pool={}
    if invalid=='timing':state.step=Step.UPKEEP
    before=pickle.dumps(state)
    with pytest.raises(ActionRejected):act(state,seat,action)
    assert pickle.dumps(state)==before


@pytest.mark.parametrize('seat',[1,2])
def test_real_day_night_card_transform_on_extra_turn_untap(seat):
    from rules_engine.card_faces import apply_transform_face
    state=position(seat)
    cathar=add(state,'Brutal Cathar // Moonrage Brute',seat,Zone.BATTLEFIELD)
    apply_transform_face(cathar,1)
    cathar.tapped=True
    state.day_night='night'
    for name in ('Time Warp','Temporal Manipulation'):
        state.priority_player=seat
        state,_=cast(state,name,seat,{'target_player':seat} if name=='Time Warp' else {})
        assert resolve_top_of_stack(state)
    next_upkeep(state)
    assert state.active_player==seat and state.day_night=='day'
    assert state.cards[cathar.id].selected_face_index==0 and not state.cards[cathar.id].tapped
    assert state.spells_cast_last_turn==2 and state.spells_cast_this_turn=={1:0,2:0}
