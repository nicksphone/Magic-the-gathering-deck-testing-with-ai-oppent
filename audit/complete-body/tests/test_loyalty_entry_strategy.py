"""Real offered entry choices; concrete harm, not an optimal-strategy claim."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pytest
import test_loyalty_entry_lifecycle as e
from test_loyalty_ai_continuations import decide
from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_power
from effects.registry import resolve_effect

facts = e.facts


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('aura_name', ['Octopus Umbra', 'Dead Weight'])
@pytest.mark.parametrize('route', ['attachment', 'hand', 'paid_ugin'])
def test_actual_ai_real_offered_aura_choice_avoids_demonstrable_friendly_harm(facts, seat, aura_name, route, request):
    rows = deepcopy(facts); rows.update(deepcopy(e.AURAS)); rows.update(deepcopy(e.COUNTER_ROWS))
    rows['Ugin, the Spirit Dragon'] = deepcopy(e.SEED['Ugin, the Spirit Dragon'])
    state = e.paid.g.position(rows, seat)
    own = e.paid.g.add(state, rows, 'Llanowar Elves', seat)
    enemy = e.paid.g.add(state, rows, 'Llanowar Elves', 3-seat)
    aura = e.paid.g.add(state, rows, aura_name, seat, Zone.HAND)
    receipts=[]
    if route == 'paid_ugin':
        e.paid.g.add(state, rows, 'Doubling Season', seat)
        source = e.paid.g.add(state, rows, 'Ugin, the Spirit Dragon', seat, Zone.HAND)
        state, _ = e.paid.paid(state, seat, source, {'C':8})
        while state.stack:state=e.paid.act(state,state.priority_player,{'type':'pass_priority'})
        state=e.paid.priority(state,seat)
        state=e.paid.act(state,seat,{'type':'activate_loyalty','card_id':source,'ability_index':2,'targets':{}})
    else:
        resolve_effect(state, seat, 'loyalty_hand_entry', {'count':1})
        if route == 'attachment':state=e.action(state,seat,card_ids=[aura])
    before = serialize_match_snapshot(state)
    for _ in range(96):
        state=e.cold(state)
        if state.pending_mechanic_choice:
            kind=state.pending_mechanic_choice['kind']; offered=deepcopy(state.pending_mechanic_choice)
            state, move=decide(state,state.pending_mechanic_choice['player_id'])
            receipts.append({'kind':kind,'action':move,'offered':offered})
        elif state.pending_replacement_choice:
            state,_=decide(state,state.pending_replacement_choice['player_id'])
        elif state.pending_trigger_order:
            state,_=decide(state,state.pending_trigger_order['current_controller'])
        elif state.stack:state=e.paid.act(state,state.priority_player,{'type':'pass_priority'})
        else:break
    else:raise AssertionError('96 public continuation bound')
    attach=next(x for x in receipts if x['kind']=='loyalty_attachment')
    assert {own,enemy} <= set(attach['offered']['options']), 'Both are genuinely offered existing objects'
    expected=own if aura_name=='Octopus Umbra' else enemy
    assert attach['action']['choice_id']==expected
    if aura_name=='Octopus Umbra':
        assert state.cards[aura].attached_to==own
        assert effective_power(state,own)==8 and effective_power(state,enemy)==1
    else:
        assert state.cards[enemy].zone==Zone.GRAVEYARD
        assert state.cards[own].zone==Zone.BATTLEFIELD and effective_power(state,own)==1
    (Path(os.environ['GAP6_EVIDENCE'])/(request.node.name+'.json')).write_text(json.dumps({
        'node':request.node.nodeid,'canonical_aura':rows[aura_name],'initial':before,
        'actual_ai_choices':receipts,'final':serialize_match_snapshot(state)},indent=2)+'\n')


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_ai_optional_hand_entry_declines_aura_that_only_kills_own_creature(seat):
    state=e.position(seat)
    own=e.raw_card(state,e.AURAS['Llanowar Elves'],seat,Zone.BATTLEFIELD)
    aura=e.raw_card(state,e.AURAS['Dead Weight'],seat,Zone.HAND)
    resolve_effect(state,seat,'loyalty_hand_entry',{'count':1})
    state,move=decide(state,seat)
    assert move=={'type':'choose_mechanic','card_ids':[]}
    assert state.cards[aura.id].zone==Zone.HAND and state.cards[own.id].zone==Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_scored_attachment_ignores_unseen_opponent_identity(seat):
    for aura_name in ('Octopus Umbra', 'Dead Weight', 'Pacifism'):
        state=e.position(seat)
        own=e.raw_card(state,e.AURAS['Llanowar Elves'],seat,Zone.BATTLEFIELD)
        enemy=e.raw_card(state,e.AURAS['Llanowar Elves'],3-seat,Zone.BATTLEFIELD)
        aura=e.raw_card(state,e.AURAS[aura_name],seat,Zone.HAND)
        hidden=e.raw_card(state,e.AURAS['Colossal Dreadmaw'],3-seat,Zone.HAND)
        library=e.raw_card(state,e.SEED['Forest'],3-seat,Zone.LIBRARY)
        state=e.hand_entry(state,seat,[aura.id])
        alternate=e.cold(state)
        for cid in (hidden.id,library.id):
            alternate.cards[cid].name='Unobserved alternative'
            alternate.cards[cid].types=['Instant']
            alternate.cards[cid].oracle_text='Counter target spell.'
            alternate.cards[cid].mana_cost='{U}{U}'
        first,move=decide(state,seat)
        second,other=decide(alternate,seat)
        expected=own.id if aura_name=='Octopus Umbra' else enemy.id
        assert move==other=={'type':'choose_mechanic','choice_id':expected}
        assert hidden.id not in move.values() and library.id not in move.values()
        assert first.cards[hidden.id].zone==second.cards[hidden.id].zone==Zone.HAND
        if aura_name == 'Pacifism':
            from rules_engine.restrictions import card_cant_attack, card_cant_block
            assert card_cant_attack(first,enemy.id) and card_cant_block(first,enemy.id)
            assert not card_cant_attack(first,own.id) and not card_cant_block(first,own.id)
