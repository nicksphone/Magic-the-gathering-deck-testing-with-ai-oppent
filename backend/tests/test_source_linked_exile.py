"""Canonical paid actions on declared resource boards; not natural deck proof."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot as snap, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.closed_loyalty import compile_body
from rules_engine.card_faces import exile_permission
from rules_engine.source_linked_exile import reference, mana_requirements
from tests.test_linked_damage_targets import raw_card
from tests.test_announced_target_reference_product import ROWS
from tests.test_canonical_land_animation_audit import ROWS as LAND_ROWS

ROOT = Path(__file__).resolve().parents[2]
RAW = json.loads((ROOT/'backend/tests/fixtures/modal_spell_faces.json').read_text())[
    'Valki, God of Lies // Tibalt, Cosmic Impostor']
FACE = RAW['card_faces'][1]
FACTS = json.loads((ROOT/'backend/tests/fixtures/source_linked_exile/nadu-facts.json').read_text())
BOOMERANG = json.loads((ROOT/'backend/tests/fixtures/source_linked_exile/boomerang.json').read_text())


def action(state, seat, value):
    if state.priority_player != seat:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type':'pass_priority'})
    return checked_action(state, RulesEngine(), seat, value)


def cast(state, seat, cid, targets=None, **extra):
    before = sum(state.players[seat].mana_pool.values())
    untapped={i for i in state.players[seat].battlefield if not state.cards[i].tapped}
    state = action(state, seat, {'type':'cast_spell','card_id':cid,'targets':targets or {},**extra})
    assert state.cards[cid].zone == Zone.STACK
    assert sum(state.players[seat].mana_pool.values()) < before or any(state.cards[i].tapped for i in untapped)
    assert resolve_top_of_stack(state)
    return deserialize_match_snapshot(snap(state))


def position(seat):
    deck=[{**RAW,'card_name':RAW['name'],'quantity':60}]
    state=MatchFactory.from_decks(deck,deck,seed=151)
    state.pregame_pending=False
    state.kept_hands={1,2}
    state.active_player=state.priority_player=seat
    state.step=Step.PRECOMBAT_MAIN
    for player in state.players.values():
        player.mana_pool={'C':30,'W':10,'U':10,'B':10,'R':10,'G':10}
        for name in ('Forest','Island','Swamp','Mountain'):
            for _ in range(5):raw_card(state,FACTS[name],player.id,Zone.BATTLEFIELD)
    cid=state.players[seat].hand[0]
    state=cast(state,seat,cid,selected_face_index=1)
    assert state.cards[cid].loyalty==5 and len(state.emblems)==1
    return state,cid


def activate(state,seat,cid,index,targets=None):
    state=action(state,seat,{'type':'activate_loyalty','card_id':cid,'ability_index':index,'targets':targets or {}})
    assert state.stack and resolve_top_of_stack(state)
    return deserialize_match_snapshot(snap(state))


def next_main(state,seat):
    turn=state.turn
    for _ in range(400):
        if state.turn>turn and state.active_player==seat and state.step==Step.PRECOMBAT_MAIN and not state.stack:
            return state
        if state.step==Step.UNTAP and not state.stack:
            assert RulesEngine().advance_no_priority_step(state)
        else:
            actor=state.pending_mechanic_choice['player_id'] if state.pending_mechanic_choice else state.priority_player
            moves=RulesEngine().legal_moves(state,actor)
            if state.pending_mechanic_choice:
                move=next(m for m in moves if m['type']=='choose_mechanic')
                move=deepcopy(move)
                move['card_ids']=list(state.pending_mechanic_choice['options'])[:state.pending_mechanic_choice['count']]
            else:move={'type':'pass_priority'}
            state=checked_action(state,RulesEngine(),actor,move)
    raise AssertionError('actual next-own-main transition exceeded bound')


@pytest.mark.parametrize('variant',['original','renamed','parameters','tail','line','reminder','wrong_source','wrong_link'])
def test_complete_raw_compiler(variant):
    text=FACE['oracle_text'];name=FACE['name']
    if variant=='renamed':text=text.replace('Tibalt, Cosmic Impostor','Renamed Source').replace('As Tibalt enters','As Renamed Source enters');name='Renamed Source'
    if variant=='parameters':text=text.replace('top card','top three cards').replace('{R}{R}{R}','{U}{G}')
    bad={'tail':' Unknown tail.','line':'\nUnknown line.','reminder':' (Unknown reminder.)'}
    if variant in bad:text+=bad[variant]
    if variant=='wrong_source':text=text.replace('As Tibalt enters','As Unrelated enters')
    if variant=='wrong_link':text=text.replace('exiled with Tibalt, Cosmic Impostor','exiled with Unrelated')
    compiled=compile_body(text,name)
    assert (compiled is not None)==(variant in {'original','renamed','parameters'})


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('case',['entry','top_spell','top_land','artifact','creature','ultimate','incarnation','departure'])
def test_actual_paid_source_linked_exile(case,seat):
    state,cid=position(seat)
    if case=='entry':
        from rules_engine.source_linked_exile import commit_entry
        before=snap(state);commit_entry(state,state.cards[cid]);assert snap(state)==before
        assert state.loyalty_permissions[0]['source']==reference(state.cards[cid])
        return
    if case in {'artifact','creature'}:
        target=raw_card(state,FACTS['Shuko' if case=='artifact' else 'Elvish Mystic'],3-seat,Zone.HAND)
        state=next_main(state,3-seat)
        state=cast(state,3-seat,target.id)
        state=next_main(state,seat)
        state=activate(state,seat,cid,1,{'target_card_id':target.id})
        assert state.cards[target.id].zone==Zone.EXILE
        assert exile_permission(state,seat,target.id) and not exile_permission(state,3-seat,target.id)
        return
    if case=='ultimate':
        for actor in (seat,3-seat):
            bolt=raw_card(state,ROWS['Lightning Bolt'],actor,Zone.HAND)
            state=cast(state,actor,bolt.id,{'target_player':3-actor})
        state=activate(state,seat,cid,0)
        state=next_main(state,seat);state=activate(state,seat,cid,0)
        state=next_main(state,seat)
        graves=[i for p in state.players.values() for i in p.graveyard]
        assert len(graves)>=2 # Real intervening cleanup may also discard cards.
        before=state.players[seat].mana_pool.get('R',0)
        state=activate(state,seat,cid,2)
        assert state.players[seat].mana_pool.get('R',0)==before+3
        assert all(state.cards[i].zone==Zone.EXILE and exile_permission(state,seat,i) for i in graves)
        return
    if case=='top_land':raw_card(state,FACTS['Forest'],3-seat,Zone.LIBRARY)
    if case=='top_spell':raw_card(state,FACTS['Elvish Mystic'],3-seat,Zone.LIBRARY)
    state=activate(state,seat,cid,0)
    refs=deepcopy(state.loyalty_permissions[0]['cards']);assert len(refs)==2
    enemy=next(r['id'] for r in refs if state.cards[r['id']].owner==3-seat)
    assert exile_permission(state,seat,enemy) and not exile_permission(state,3-seat,enemy)
    if case=='top_land':
        state=action(state,seat,{'type':'play_land','card_id':enemy,'from_exile':True})
        assert state.cards[enemy].zone==Zone.BATTLEFIELD
        assert state.cards[enemy].owner==3-seat and state.cards[enemy].controller==seat
        assert state.players[seat].lands_played_this_turn==1
    elif case=='incarnation':
        old=reference(state.cards[cid])
        bounce=raw_card(state,BOOMERANG,seat,Zone.HAND)
        state=cast(state,seat,bounce.id,{'target_card_id':cid})
        assert state.cards[cid].zone==Zone.HAND
        state=cast(state,seat,cid,selected_face_index=1)
        assert reference(state.cards[cid])!=old and len(state.emblems)==2
        assert state.loyalty_permissions[1]['cards']==[]
        assert exile_permission(state,seat,enemy)
        state=next_main(state,seat);state=activate(state,seat,cid,0)
        assert len(state.loyalty_permissions[0]['cards'])==2 and len(state.loyalty_permissions[1]['cards'])==2
    elif case=='departure':
        for _ in range(3):
            bolt=raw_card(state,ROWS['Lightning Bolt'],3-seat,Zone.HAND)
            state=cast(state,3-seat,bolt.id,{'target_card_id':cid})
        assert state.cards[cid].zone==Zone.GRAVEYARD
        assert exile_permission(state,seat,enemy)
    else:
        req={'generic':1,'W':2,'U':0,'B':0,'R':0,'G':0,'C':1,'S':1,'life':2}
        adjusted=mana_requirements(state,seat,enemy,req,'spell')
        assert adjusted['generic']==3 and adjusted['W']==0 and adjusted['C']==1 and adjusted['S']==1 and adjusted['life']==2
        assert mana_requirements(state,seat,enemy,req,'activation')==req
        state.players[seat].mana_pool={'C':1} # Declared physical payment resource; never a free cast.
        state=cast(state,seat,enemy,from_exile=True)
        assert state.cards[enemy].zone==Zone.BATTLEFIELD and state.cards[enemy].controller==seat
        assert state.players[seat].mana_pool['C']==0 and not exile_permission(state,seat,enemy)
