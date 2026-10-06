"""Desired runtime contracts, separate from the immutable missing-trigger audit."""
from copy import deepcopy
import json
import pickle
from pathlib import Path
import pytest
from effects.registry import resolve_effect
from game_state.state import Step,Zone
from rules_engine.engine import RulesEngine
from rules_engine.costs import collect_cost_options
from rules_engine.action_validation import checked_action,ActionRejected
from rules_engine.continuous import has_keyword
from rules_engine.events import emit_event,flush_staged_triggers
from tests.nth_spell_trigger_support import RAW,add
from tests.readiness_rules_seam_support import position,cast,resolve,resume
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client


def spirits(state,seat):
    return [state.cards[cid] for cid in state.players[seat].battlefield
            if state.cards[cid].is_token and 'Spirit' in state.cards[cid].type_line]


@pytest.mark.parametrize('seat',[1,2])
def test_clarion_strict_first_second_third_checked_cast_and_reload(seat):
    state=position(seat);source=add(state,'Clarion Spirit',seat)
    counts=[]
    for i in range(1,4):
        spell=add(state,'Intangible Virtue',seat,Zone.HAND)
        state=cast(state,spell)
        triggers=[s for s in state.stack if s.source_card_id==source.id]
        assert len(triggers)==(1 if i==2 else 0)
        if triggers:
            p=triggers[0].payload
            assert p['name']=='Spirit' and p['colors']==['W'] and p['power']==p['toughness']==1
            assert p['amount']==1 and p['keywords']==['flying']
        state=resolve(resume(state));counts.append(len(spirits(state,seat)))
    assert counts==[0,1,1]
    assert has_keyword(state,spirits(state,seat)[0].id,'flying')


@pytest.mark.parametrize('seat',[1,2])
def test_distinct_same_controller_clauses_both_fire_without_conflation(seat):
    state=position(seat)
    sources=[add(state,n,seat) for n in ['Clarion Spirit','Jori En, Ruin Diver','Wingblade Disciple']]
    for i in range(1,3):
        spell=add(state,'Intangible Virtue',seat,Zone.HAND)
        state=cast(state,spell)
        triggered=[s for s in state.stack if s.source_card_id in {c.id for c in sources}]
        assert len(triggered)==(3 if i==2 else 0)
        before=len(state.players[seat].hand)
        state=resolve(resume(state))
        if i==2:
            assert len(state.players[seat].hand)==before+1
    assert len(spirits(state,seat))==1
    birds=[state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token and 'Bird' in state.cards[cid].type_line]
    assert len(birds)==1 and birds[0].colors==['W'] and has_keyword(state,birds[0].id,'flying')


@pytest.mark.parametrize('seat',[1,2])
def test_spell_counter_resets_both_seats_and_preserves_previous_active_count(seat):
    state=position(seat);state.spells_cast_this_turn={seat:3,3-seat:2}
    state.step=Step.CLEANUP
    RulesEngine().next_step(state)
    assert state.spells_cast_last_turn==3
    assert state.spells_cast_this_turn=={1:0,2:0}
    assert resume(state).spells_cast_this_turn=={1:0,2:0}


@pytest.mark.parametrize('seat',[1,2])
def test_first_spell_opponent_turn_clause_and_controller_count(seat):
    state=position(3-seat);state.priority_player=seat
    source=add(state,'Wavebreak Hippocamp',seat)
    for i in range(1,3):
        spell=add(state,'Think Twice',seat,Zone.HAND)
        state.priority_player=seat
        state=cast(state,spell)
        assert sum(s.source_card_id==source.id for s in state.stack)==(1 if i==1 else 0)
        state=resolve(resume(state))


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('method',['flashback','exile','effect_authorized'])
def test_alternate_real_cast_methods_count_as_second_spell(seat,method):
    state=position(seat);source=add(state,'Clarion Spirit',seat)
    state=resolve(cast(state,add(state,'Intangible Virtue',seat,Zone.HAND)))
    if method=='exile':
        spell=add(state,'Intangible Virtue',seat,Zone.EXILE)
        state.players[seat].exile_play_until[spell.id]=state.turn
        action={'type':'cast_spell','card_id':spell.id,'from_exile':True,'targets':{}}
        state=checked_action(state,RulesEngine(),seat,action)
    else:
        spell=add(state,'Think Twice',seat,Zone.GRAVEYARD)
        if method=='effect_authorized':
            resolve_effect(state,seat,'cast_from_graveyard',{'target_card_id':spell.id})
            flush_staged_triggers(state)
        else:
            option=next(o for o in collect_cost_options(state,seat,spell) if o.id.startswith('flashback'))
            state=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':spell.id,'from_graveyard':True,'cost_option_id':option.id,'targets':{}})
    assert state.spells_cast_this_turn[seat]==2
    assert sum(s.source_card_id==source.id for s in state.stack)==1
    state=resolve(resume(state));assert len(spirits(state,seat))==1


@pytest.mark.parametrize('seat',[1,2])
def test_real_twincast_copy_is_not_an_extra_cast_or_trigger(seat):
    state=position(seat);source=add(state,'Clarion Spirit',seat)
    alarm=add(state,'Raise the Alarm',seat,Zone.HAND)
    state=cast(state,alarm);target=state.stack[-1].id
    copy=add(state,'Twincast',seat,Zone.HAND)
    state=cast(state,copy,target_stack_id=target)
    state=resolve(resume(state))
    assert state.spells_cast_this_turn[seat]==2 and len(spirits(state,seat))==1
    assert sum(state.cards[cid].is_token and 'Soldier' in state.cards[cid].type_line for cid in state.players[seat].battlefield)==4


@pytest.mark.parametrize('seat',[1,2])
def test_unsupported_remaining_instruction_not_partial_token_or_counter(seat):
    state=position(seat)
    cutter=add(state,'Cori-Steel Cutter',seat)
    vance=add(state,'Captain Ripley Vance',seat)
    for _ in range(3):
        state=resolve(resume(cast(state,add(state,'Intangible Virtue',seat,Zone.HAND))))
    assert not any(state.cards[cid].is_token for cid in state.players[seat].battlefield)
    assert not state.cards[vance.id].counters
    assert any('Unsupported nth-spell trigger instruction' in line and 'Cori-Steel Cutter' in line for line in state.log)
    assert any('Unsupported nth-spell trigger instruction' in line and 'Captain Ripley Vance' in line for line in state.log)


@pytest.mark.parametrize('seat',[1,2])
def test_source_departure_after_trigger_does_not_cancel_independent_token(seat):
    from rules_engine.zone_actions import sacrifice_selected
    state=position(seat);source=add(state,'Clarion Spirit',seat)
    state=resolve(cast(state,add(state,'Intangible Virtue',seat,Zone.HAND)))
    state=cast(state,add(state,'Intangible Virtue',seat,Zone.HAND))
    assert sacrifice_selected(state,seat,[source.id])
    state=resolve(resume(state));assert len(spirits(state,seat))==1


@pytest.mark.parametrize('seat',[1,2])
def test_real_http_strict_second_token_and_snapshot_resume(repo,client,seat):
    import main
    from tests.readiness_rules_seam_support import seed_cache
    seed_cache(repo)
    deck=[{'card_name':'Island','quantity':8}]
    r=client.post('/matches/start',json={'deck_a':deck,'deck_b':deck,'sandbox':True,'controller_a':'human','controller_b':'human','seed':6214})
    assert r.status_code==200,r.text
    c=main.ACTIVE_MATCHES[r.json()['id']]
    state=position(seat);state.id=c.state.id;add(state,'Clarion Spirit',seat)
    spells=[add(state,'Intangible Virtue',seat,Zone.HAND) for _ in range(3)]
    c.state=state;main._persist_active_match(repo,c)
    counts=[]
    for spell in spells:
        r=client.post('/matches/'+state.id+'/action',json={'player_id':seat,'action':{'type':'cast_spell','card_id':spell.id,'targets':{}}})
        assert r.status_code==200,r.text
        c.state=resume(c.state);main._persist_active_match(repo,c)
        for _ in range(12):
            if not c.state.stack:break
            r=client.post('/matches/'+state.id+'/action',json={'player_id':c.state.priority_player,'action':{'type':'pass_priority'}})
            assert r.status_code==200,r.text
        else:pytest.fail('Bounded HTTP stack did not settle')
        counts.append(len(spirits(c.state,seat)))
    assert counts==[0,1,1]


@pytest.mark.parametrize('seat',[1,2])
def test_ordered_draw_then_printed_wall_retains_both_instructions(seat):
    state=position(seat);source=add(state,'Rammas Echor, Ancient Shield',seat)
    state=resolve(cast(state,add(state,'Intangible Virtue',seat,Zone.HAND)))
    state=cast(state,add(state,'Intangible Virtue',seat,Zone.HAND))
    item=next(s for s in state.stack if s.source_card_id==source.id)
    assert [e['effect_key'] for e in item.payload['effects']]==['draw_cards','create_token']
    before=len(state.players[seat].hand)
    state=resolve(resume(state))
    walls=[state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert len(state.players[seat].hand)==before+1 and len(walls)==1
    assert walls[0].power==0 and walls[0].toughness==3 and walls[0].colors==['W']
    assert 'Wall' in walls[0].type_line and has_keyword(state,walls[0].id,'defender')


@pytest.mark.parametrize('seat',[1,2])
def test_opponent_casts_do_not_trigger_actor_second_clause(seat):
    state=position(seat);source=add(state,'Clarion Spirit',seat)
    for _ in range(3):
        state.priority_player=3-seat
        state=resolve(resume(cast(state,add(state,'Think Twice',3-seat,Zone.HAND))))
    assert state.spells_cast_this_turn[3-seat]==3 and state.spells_cast_this_turn[seat]==0
    assert not spirits(state,seat)


@pytest.mark.parametrize('seat',[1,2])
def test_actual_fresh_process_http_restart_retains_second_trigger_and_receipts(tmp_path,seat):
    import os,subprocess,sys
    root=tmp_path/'restart';root.mkdir()
    worker=Path(__file__).with_name('nth_spell_restart_worker.py')
    env={**os.environ,'PYTHONPATH':str(worker.parents[1]),'MTG_DEBUG_HANDS':'0'}
    results=[]
    for phase in ['seed','restore']:
        p=subprocess.run([sys.executable,str(worker),phase,str(seat),str(root)],env=env,capture_output=True,text=True,timeout=90)
        (root/(phase+'.log')).write_text(p.stdout+p.stderr)
        assert p.returncode==0,p.stdout+p.stderr
        results.append(json.loads((root/(phase+'-evidence.json')).read_text()))
    assert results[0]['pid']!=results[1]['pid']


@pytest.mark.parametrize('seat',[1,2])
def test_printed_ability_suppression_blocks_second_trigger_not_later_retroactive(seat):
    from rules_engine.zone_actions import sacrifice_selected
    state=position(seat);source=add(state,'Clarion Spirit',seat)
    suppressor=add(state,'Dress Down',3-seat)
    for _ in range(2):state=resolve(resume(cast(state,add(state,'Intangible Virtue',seat,Zone.HAND))))
    assert not spirits(state,seat)
    assert sacrifice_selected(state,3-seat,[suppressor.id])
    state=resolve(resume(cast(state,add(state,'Intangible Virtue',seat,Zone.HAND))))
    assert state.spells_cast_this_turn[seat]==3 and not spirits(state,seat)


@pytest.mark.parametrize('seat',[1,2])
def test_new_opponent_turn_first_instant_restarts_actor_count(seat):
    state=position(seat);source=add(state,'Wavebreak Hippocamp',seat)
    state.spells_cast_this_turn[seat]=3
    state.step=Step.CLEANUP
    RulesEngine().next_step(state)
    state.step=Step.PRECOMBAT_MAIN;state.priority_player=seat
    state.players[seat].mana_pool={'U':5,'C':5}
    state=cast(state,add(state,'Think Twice',seat,Zone.HAND))
    assert state.spells_cast_this_turn[seat]==1
    assert sum(s.source_card_id==source.id for s in state.stack)==1
    state=resolve(resume(state))
