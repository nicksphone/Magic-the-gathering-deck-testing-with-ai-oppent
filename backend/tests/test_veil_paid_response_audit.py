"""Full canonical paid Veil response audit, without product edits or injected frames."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from game_state.state import MatchFactory, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
import test_brainstorm_desired as brain

RAW_PATH = Path(__file__).parent/'fixtures/historical_event_catalog/canonical.jsonl'
VEIL = next(row for row in map(json.loads, RAW_PATH.read_text().splitlines())
            if row['name']=='Veil of Summer')
UNSUMMON = json.loads((Path(__file__).parent/
    'fixtures/favor_target_lifecycle/unsummon.json').read_text())

def add_veil(state, seat):
    sample=MatchFactory.from_decks([{**VEIL,'card_name':VEIL['name'],'quantity':1}],[],seed=4)
    card=deepcopy(next(iter(sample.cards.values())))
    card.id=state.allocate_object_id(); card.owner=card.controller=seat
    card.move_to_zone(Zone.HAND); state.cards[card.id]=card; state.players[seat].hand.append(card.id)
    assert card.oracle_text==VEIL['oracle_text'] and card.colors==VEIL['colors']
    return card.id

def add_unsummon(state, seat):
    sample=MatchFactory.from_decks([{**UNSUMMON,'card_name':UNSUMMON['name'],'quantity':1}],[],seed=4)
    card=deepcopy(next(iter(sample.cards.values())))
    card.id=state.allocate_object_id(); card.owner=card.controller=seat
    card.move_to_zone(Zone.HAND); state.cards[card.id]=card; state.players[seat].hand.append(card.id)
    assert card.oracle_text==UNSUMMON['oracle_text'] and card.colors==UNSUMMON['colors']
    return card.id

def priority(state, seat):
    return brain.advance(state,lambda s:s.priority_player==seat)

def resolve_frame(state, frame):
    return brain.advance(state,lambda s:all(item.id!=frame for item in s.stack))

@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('restore',[False,True])
@pytest.mark.parametrize('case',['no-opponent-cast','own-blue-cast','opponent-blue-draw',
                                 'counter-prevention','blue-permanent-protection','unpaid'])
def test_actual_paid_veil_complete_body(seat,restore,case):
    state=brain.position(seat); opponent=3-seat; source=add_veil(state,seat)
    if case=='unpaid':
        state=brain.cold(state) if restore else state
        before=serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            brain.act(state,seat,{'type':'cast_spell','card_id':source,'targets':{}})
        assert serialize_match_snapshot(state)==before
        return
    target=None; response_frame=None; protected_frame=None
    if case=='own-blue-cast':
        state,_=brain.brainstorm(state,seat)
        selected=[cid for cid in state.players[seat].hand if cid!=source][:2]
        state=brain.act(state,seat,{'type':'choose_mechanic','card_ids':selected})
        assert not state.stack and not state.pending_mechanic_choice
        state=priority(state,seat)
    elif case in {'opponent-blue-draw','counter-prevention'}:
        protected=brain.add(state,'Brainstorm',seat,Zone.HAND)
        state,protected_frame=brain.cast(state,seat,protected,{'U':1})
        state=priority(state,opponent)
        counter=brain.add(state,'Counterspell',opponent,Zone.HAND)
        state,response_frame=brain.cast(state,opponent,counter,{'U':2},{'target_stack_id':protected_frame})
        state=priority(state,seat)
    elif case=='blue-permanent-protection':
        target=brain.add(state,'Twinshot Sniper',seat,Zone.BATTLEFIELD)
        state=priority(state,opponent)
        bounce=add_unsummon(state,opponent)
        state,response_frame=brain.cast(state,opponent,bounce,{'U':1},{'target_card_id':target})
        state=priority(state,seat)
    library=list(state.players[seat].library); hand=set(state.players[seat].hand)-{source}
    state,veil_frame=brain.cast(state,seat,source,{'G':1})
    state=brain.cold(state) if restore else state
    state=resolve_frame(state,veil_frame)
    assert state.cards[source].zone==Zone.GRAVEYARD
    if case=='opponent-blue-draw':
        assert state.players[seat].library==library[:-1], 'opponent blue spell must enable Veil draw'
        assert set(state.players[seat].hand)==hand|{library[-1]}
    elif case in {'no-opponent-cast','own-blue-cast'}:
        assert state.players[seat].library==library and set(state.players[seat].hand)==hand
    elif case=='counter-prevention':
        state=resolve_frame(state,response_frame)
        assert any(item.id==protected_frame for item in state.stack), 'Veil-protected spell must survive counter'
    else:
        state=resolve_frame(state,response_frame)
        assert state.cards[target].zone==Zone.BATTLEFIELD, 'blue opponent bounce must lose target legality'
        assert target in state.players[seat].battlefield
    brain.cold(state)
