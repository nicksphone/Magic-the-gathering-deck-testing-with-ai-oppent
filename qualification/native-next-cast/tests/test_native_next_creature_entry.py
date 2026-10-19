"""Full canonical paid sources; constructed starting mana/board, not natural games."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.move_generator import legal_moves
from rules_engine.next_creature_entry_trigger import compile_instruction, ANY, NOTED, history_key, history
from tests.test_graveyard_self_activation_product import position, FAMILIES, raw_card, act, snapshot
from tests.test_resident_entry_counter_provider import BALLISTA
from test_mixed_entry_origin_audit import ROWS, finish_priority

RESPONSES = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/responses.json').read_text())['rows']
SOURCES = ('Long List of the Ents', 'Summon: Fenrir')


def source_ready(seat, family):
    state, _ = position(seat, FAMILIES[0])
    for cid in list(state.players[seat].library[:4]):
        state.players[seat].library.remove(cid)
        state.players[seat].battlefield.append(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, cid)
        state.cards[cid].summoning_sick = False
    source = raw_card(state, ROWS[family], seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 2}
    state = finish_priority(act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}}))
    if family == 'Summon: Fenrir':
        for _ in range(96):
            item = next((i for i in state.stack if i.source_card_id == source.id
                         and i.payload.get('__chapter_number') == 2), None)
            if item:
                state = finish_priority(state)
                break
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        else:
            raise AssertionError('Native chapterII did not arrive within96 actual passes')
    return state, source.id


def choose_type(state, seat, subtype='construct'):
    assert state.pending_mechanic_choice['kind'] == 'note_creature_type'
    before = snapshot(state)
    moves = legal_moves(state, seat)
    assert snapshot(state) == before
    assert not legal_moves(state, 3-seat)
    assert set(moves[0]) == {'type','kind','player_id','options','count','label','option_labels','option_type_lines'}
    assert not any(key in moves[0] for key in ('record','resolving_item','history_key','history_before'))
    action = {'type':'choose_mechanic','choice_id':'creature-type:'+subtype}
    assert action['choice_id'] in moves[0]['options']
    return act(state, seat, action)


def cast_recipient(state, seat):
    card = raw_card(state, BALLISTA, seat, Zone.HAND)
    state.players[seat].mana_pool = {'C':4}
    state.replacement_choice_players = {seat}
    state = act(state, seat, {'type':'cast_spell','card_id':card.id,'targets':{'x_value':2}})
    return state, card.id


def finish_entry(state, seat):
    for _ in range(24):
        if state.pending_replacement_choice:
            option = state.pending_replacement_choice['options'][0]
            state = act(state, seat, {'type':'choose_replacement','replacement_source_id':option['source_id']})
        elif state.stack:
            state = act(state, state.priority_player, {'type':'pass_priority'})
        else:
            return state
    raise AssertionError('Native entry exceeded24 declared actions')


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('family',SOURCES)
def test_full_paid_sources_publish_real_bind_then_exact_entry(request,seat,family):
    state, sid = source_ready(seat,family)
    if family == SOURCES[0]:
        assert not state.pending_entry_counters
        state = choose_type(state,seat)
    assert len(state.pending_entry_counters)==1
    waiting = deepcopy(state.pending_entry_counters)
    state = deserialize_match_snapshot(snapshot(state))
    state, cid = cast_recipient(state,seat)
    assert not state.pending_entry_counters
    assert len(state.stack)==2 and state.stack[-1].effect_key=='bind_creature_spell_entry_counter'
    assert state.stack[-1].payload['__native_cast']['stack_id']==state.stack[-2].id
    before = snapshot(state)
    state = finish_entry(state,seat)
    assert state.cards[cid].zone==Zone.BATTLEFIELD and state.cards[cid].counters['+1/+1']==3
    path=Path(os.environ['MTG_NATIVE_EVIDENCE'])/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()+'.json')
    with path.open('x') as f:json.dump({'family':family,'seat':seat,'source':sid,'waiting':waiting,
        'actual_cast':before,'after':snapshot(state)},f,sort_keys=True,indent=2)


@pytest.mark.parametrize('seat',[1,2])
def test_type_note_invalid_choices_are_atomic_then_real_choice(seat):
    state,_=source_ready(seat,SOURCES[0]); before=snapshot(state)
    for actor,choice in ((3-seat,'construct'),(seat,'invented-type')):
        with pytest.raises(ActionRejected):act(state,actor,{'type':'choose_mechanic','choice_id':'creature-type:'+choice})
        assert snapshot(state)==before
    state=choose_type(deserialize_match_snapshot(before),seat)
    assert history(state,history_key(state.pending_entry_counters[0]['__entry_origin']))==['construct']


@pytest.mark.parametrize('seat',[1,2])
def test_unmatching_creature_does_not_consume_noted_cast(seat):
    state,_=source_ready(seat,SOURCES[0]);state=choose_type(state,seat,'elf')
    waiting=deepcopy(state.pending_entry_counters)
    state,cid=cast_recipient(state,seat)
    assert len(state.stack)==1 and state.pending_entry_counters==waiting
    state=finish_entry(state,seat)
    assert state.cards[cid].counters['+1/+1']==2 and state.pending_entry_counters==waiting


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('family',SOURCES)
def test_stifle_consumes_next_occurrence_without_entry_reward(seat,family):
    state,_=source_ready(seat,family)
    if family==SOURCES[0]:state=choose_type(state,seat)
    stifle=raw_card(state,RESPONSES['Stifle'],seat,Zone.HAND)
    state,cid=cast_recipient(state,seat)
    bind=state.stack[-1];state.players[seat].mana_pool={'U':1}
    state=act(state,seat,{'type':'cast_spell','card_id':stifle.id,'targets':{'target_stack_id':bind.id}})
    state=finish_entry(state,seat)
    assert state.cards[cid].counters['+1/+1']==2 and not state.pending_entry_counters
    state,cid2=cast_recipient(state,seat);assert len(state.stack)==1
    state=finish_entry(state,seat);assert state.cards[cid2].counters['+1/+1']==2


@pytest.mark.parametrize('body',[ANY,NOTED])
@pytest.mark.parametrize('extra',[' Draw a card.',' If you control a Forest.',' and draw a card.'])
def test_unknown_complete_tails_do_not_partially_compile(body,extra):
    assert compile_instruction(body+extra) is None


@pytest.mark.parametrize('body',[ANY,NOTED])
def test_closed_grammar_matches_exact_supported_complete_body(body):
    assert compile_instruction(body) is not None
