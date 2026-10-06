"""Desired admission safety, distinct from unsupported scheduler contracts."""
from dataclasses import asdict
import hashlib
import json
import pickle
import pytest
from game_state.state import Zone
from rules_engine.ability_model import build_spell_spec
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.spell_admission_safety_support import FIXTURE, RAW, UNSUPPORTED, add, position, resume


def test_full_unmodified_intake_hashes():
    proof = json.loads((FIXTURE / 'provenance.json').read_text())
    assert proof['facts_modified'] is False and proof['intake_before_tests'] is True
    assert proof['canonical_sha256'] == hashlib.sha256((FIXTURE / 'canonical.json').read_bytes()).hexdigest()
    for name, raw in RAW.items():
        assert proof['rows'][name]['id'] == raw['id']
        assert proof['rows'][name]['oracle_id'] == raw['oracle_id']
        assert proof['rows'][name]['raw_sha256'] == hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',UNSUPPORTED)
def test_unsupported_full_spell_not_offered_and_rejected_before_costs(seat,name):
    state = position(seat)
    state.players[seat].mana_pool = {'W':20,'U':20,'B':20,'R':20,'G':20,'C':20}
    source = add(state,name,seat)
    before = pickle.dumps(state)
    moves = RulesEngine().legal_moves(state,seat)
    assert not any(m['type']=='cast_spell' and m.get('card_id')==source.id for m in moves)
    assert pickle.dumps(state)==before
    with pytest.raises(ActionRejected,match='Unsupported spell resolution'):
        checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':source.id,'targets':{'target_player':seat}})
    assert pickle.dumps(state)==before
    info = asdict(build_spell_spec(resume(state),resume(state).cards[source.id],seat))
    assert info['unsupported_resolution']


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Opt','Lightning Bolt','Raise the Alarm','Grizzly Bears','Intangible Virtue'])
def test_supported_real_spell_controls_still_cast_and_resolve(seat,name):
    state = position(seat)
    state.players[seat].mana_pool = {'W':20,'U':20,'B':20,'R':20,'G':20,'C':20}
    source = add(state,name,seat)
    targets = {'target_player':3-seat} if name=='Lightning Bolt' else {}
    before = pickle.dumps(state)
    candidate = checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':source.id,'targets':targets})
    assert pickle.dumps(state)==before
    assert not getattr(build_spell_spec(candidate,candidate.cards[source.id],seat,targets),'unsupported_resolution',())
    candidate = resume(candidate)
    if name=='Opt':
        assert not resolve_top_of_stack(candidate)
        assert candidate.pending_mechanic_choice['kind']=='scry'
        candidate=checked_action(candidate,RulesEngine(),seat,{'type':'choose_mechanic','card_ids':[]})
    else:
        assert resolve_top_of_stack(candidate)
    assert candidate.cards[source.id].zone == (Zone.BATTLEFIELD if name in {'Grizzly Bears','Intangible Virtue'} else Zone.GRAVEYARD)
    if name=='Lightning Bolt':assert candidate.players[3-seat].life==17
    if name=='Raise the Alarm':assert sum(candidate.cards[c].is_token for c in candidate.players[seat].battlefield)==2
    if name=='Opt':assert candidate.pending_mechanic_choice is None and len(candidate.players[seat].hand)==1


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',UNSUPPORTED)
def test_direct_strict_engine_rejection_is_byte_pure_before_payment(seat,name):
    state=position(seat)
    state.players[seat].mana_pool={'W':20,'U':20,'B':20,'R':20,'G':20,'C':20}
    source=add(state,name,seat)
    targets={'target_player':seat} if name in {'Time Warp','Worst Fears'} else {}
    before=pickle.dumps(state)
    with pytest.raises(ActionRejected,match='Unsupported spell resolution'):
        RulesEngine().take_action(state,seat,{'type':'cast_spell','card_id':source.id,'targets':targets},reject_invalid=True)
    assert pickle.dumps(state)==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('name',['Time Warp','Ponder'])
def test_caller_mode_text_cannot_replace_nonmodal_full_oracle(seat,name):
    state=position(seat)
    source=add(state,name,seat)
    before=pickle.dumps(state)
    with pytest.raises(ActionRejected,match='Unsupported spell resolution'):
        checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':source.id,
            'targets':{'target_player':seat,'mode_text':'Draw a card'}})
    assert pickle.dumps(state)==before


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('fizzle',[False,True])
def test_supported_counter_and_later_fizzle_are_not_unsupported_noops(seat,fizzle):
    state=position(seat)
    state.players[seat].mana_pool={'U':20,'R':20,'C':20}
    state.players[3-seat].mana_pool={'U':20,'R':20,'C':20}
    bolt=add(state,'Lightning Bolt',seat)
    counter=add(state,'Counterspell',3-seat)
    second=add(state,'Counterspell',seat) if fizzle else None
    state=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':bolt.id,'targets':{'target_player':3-seat}})
    target=state.stack[-1].id
    state=checked_action(state,RulesEngine(),seat,{'type':'pass_priority'})
    state=checked_action(state,RulesEngine(),3-seat,{'type':'cast_spell','card_id':counter.id,'targets':{'target_stack_id':target}})
    if fizzle:
        state=checked_action(state,RulesEngine(),3-seat,{'type':'pass_priority'})
        state=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':second.id,'targets':{'target_stack_id':target}})
        assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    assert not state.stack and state.players[3-seat].life==20
    assert state.cards[bolt.id].zone==state.cards[counter.id].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
def test_unrecognized_resolution_without_a_known_schema_is_rejected_at_actual_choices(seat):
    state=position(seat)
    state.players[seat].mana_pool={'U':20,'C':20}
    source=add(state,'Distorting Wake',seat)
    target=add(state,'Grizzly Bears',3-seat,Zone.BATTLEFIELD)
    targets={'x_value':1,'target_card_id':target.id,'target_card_ids':[target.id]}
    before=pickle.dumps(state)
    with pytest.raises(ActionRejected,match='Unsupported spell resolution: unrecognized spell resolution'):
        checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':source.id,'targets':targets})
    assert pickle.dumps(state)==before
    assert build_spell_spec(resume(state),resume(state).cards[source.id],seat,targets).unsupported_resolution==('unrecognized spell resolution',)
