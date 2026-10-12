"""Full official RAW, checked paid rules outcomes; trusted board/pools, not AI/D13."""
import hashlib
import json
from pathlib import Path
import random
import pytest

from game_state.state import CardInstance, MatchState, PlayerState, Step, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind

ROOT=Path(__file__).resolve().parent
RAW_BYTES=(ROOT/'fixtures/vraska-scryfall-raw.json').read_bytes()
assert hashlib.sha256(RAW_BYTES).hexdigest()=='d05bc8f4d639536deb46eabb9f1ee807373418591be1deb1af7d57548d79423f'
RAW=json.loads(RAW_BYTES)
BEAR=json.loads((ROOT/'fixtures/grizzly-bears-scryfall-raw.json').read_bytes())
ISLAND=json.loads((ROOT/'fixtures/island-scryfall-raw.json').read_bytes())
STIFLE=json.loads((ROOT/'fixtures/stifle-scryfall-raw.json').read_bytes())


def add(state, raw, seat, zone, *, old_board=False):
    type_line=raw['type_line']
    types=[kind for kind in ('Creature','Artifact','Enchantment','Planeswalker','Instant','Sorcery','Land')
           if kind in type_line.split('\u2014',1)[0].split()]
    card=CardInstance(state.allocate_object_id(),raw['name'],seat,seat,zone,types,
        mana_cost=raw['mana_cost'],oracle_text=raw['oracle_text'],type_line=type_line,
        colors=raw['colors'],keywords=raw.get('keywords',[]),layout=raw.get('layout','normal'),
        power=int(raw['power']) if raw.get('power','').isdigit() else None,
        toughness=int(raw['toughness']) if raw.get('toughness','').isdigit() else None,
        loyalty=int(raw['loyalty']) if raw.get('loyalty','').isdigit() else None,
        summoning_sick=not old_board)
    state.cards[card.id]=card
    getattr(state.players[seat],zone.value).append(card.id)
    return card


def bare(seat):
    state=MatchState('full-vraska-pure',players={i:PlayerState(i,'Declared rules fixture') for i in (1,2)},
        cards={},stack=[],rng=random.Random(718),active_player=seat,priority_player=seat,
        step=Step.PRECOMBAT_MAIN,pregame_pending=False,kept_hands={1,2})
    # Explicit trusted mana/old board, no mana creation or canonical paid-birth claim for these fixtures.
    for player in (1,2):
        state.players[player].mana_pool={c:20 for c in ('W','U','B','R','G','C')}
        for _ in range(20):add(state,ISLAND,player,Zone.LIBRARY)
    return state


def act(state,seat,action):
    before=serialize_match_snapshot(state)
    result=checked_action(state,RulesEngine(),seat,action)
    assert serialize_match_snapshot(state)==before,'Checked action must not mutate original root'
    return result


def settle(state):
    for _ in range(80):
        if not state.stack or state.winner is not None:return state
        assert state.pending_trigger_order is None,'Fixture must explicitly choose any unexpected order'
        state=act(state,state.priority_player,{'type':'pass_priority'})
    pytest.fail('Declared stack did not settle within80 actual actions')


def paid_cast(state,seat,card,spent):
    assert any(m.get('type')=='cast_spell' and m.get('card_id')==card.id
        for m in RulesEngine().legal_moves(state,seat)), 'Complete canonical spell is not offered'
    before=sum(state.players[seat].mana_pool.values())
    state=act(state,seat,{'type':'cast_spell','card_id':card.id,'targets':{}})
    assert before-sum(state.players[seat].mana_pool.values())==spent
    assert state.stack[-1].payload['mana_spent']==spent
    assert stack_object_kind(state,state.stack[-1])=='spell'
    state=settle(state)
    assert state.cards[card.id].zone==Zone.BATTLEFIELD
    return state


def born(seat):
    state=bare(seat)
    victim=add(state,BEAR,3-seat,Zone.BATTLEFIELD,old_board=True)
    walker=add(state,RAW,seat,Zone.HAND)
    state=paid_cast(state,seat,walker,5)
    assert state.cards[walker.id].oracle_text==RAW['oracle_text']
    assert state.cards[walker.id].loyalty==5
    return state,walker.id,victim.id


def activate(state,seat,walker,index,targets=None):
    offered=RulesEngine().legal_moves(state,seat)
    assert any(m.get('type')=='activate_loyalty' and m.get('card_id')==walker
        and m.get('ability_index')==index for m in offered),'Original printed ability must be offered'
    state=act(state,seat,{'type':'activate_loyalty','card_id':walker,'ability_index':index,'targets':targets or {}})
    assert stack_object_kind(state,state.stack[-1])=='activated'
    return state


def advance(state,seat,step,*,after_turn=0):
    for _ in range(240):
        if not state.stack and state.active_player==seat and state.step==step and state.turn>after_turn:return state
        assert state.winner is None,'No forced/deckout win may stand in for the requested rule'
        state=act(state,state.priority_player,{'type':'pass_priority'})
    pytest.fail('Declared phase not reached within240 actual priority actions')


def combat(state,attacker_seat,attacker,target):
    state=advance(state,attacker_seat,Step.DECLARE_ATTACKERS)
    state=act(state,attacker_seat,{'type':'attack','attackers':[attacker],'attack_targets':{attacker:target}})
    for _ in range(80):
        if state.winner is not None or state.step==Step.END_COMBAT:return state
        state=act(state,state.priority_player,{'type':'pass_priority'})
    pytest.fail('Actual combat did not finish within80 actions')


def test_full_canonical_three_ability_body_has_no_erasure():
    compiled=compile_body(RAW['oracle_text'],RAW['name'])
    assert compiled is not None,'Full verified three-ability surface is unsupported'
    assert [a['delta'] for a in compiled['abilities']]==[1,-3,-7]
    assert len(compiled['abilities'])==len(RAW['oracle_text'].splitlines())==3


@pytest.mark.parametrize('seat',[1,2])
def test_real_paid_birth_retains_full_three_ability_menu(seat):
    state,walker,_=born(seat)
    state.cards[walker].loyalty=7  # Menu/cost boundary only; ultimate outcome below earns7 through actual+1 turns.
    before=serialize_match_snapshot(state)
    moves=[m for m in RulesEngine().legal_moves(state,seat) if m.get('card_id')==walker and m.get('type')=='activate_loyalty']
    assert {m['ability_index'] for m in moves}=={0,1,2}
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
def test_control_real_paid_grizzly_birth_without_SQL_or_network(seat):
    state=bare(seat);bear=add(state,BEAR,seat,Zone.HAND)
    state=paid_cast(state,seat,bear,2)
    assert state.cards[bear.id].summoning_sick and state.winner is None


@pytest.mark.parametrize('seat',[1,2])
def test_minus_three_paid_destroy_and_snapshot_continuation(seat):
    state,walker,victim=born(seat)
    state=activate(state,seat,walker,1,{'target_card_id':victim})
    assert state.cards[walker].loyalty==2
    state=deserialize_match_snapshot(serialize_match_snapshot(state))
    state=settle(state)
    assert state.cards[victim].zone==Zone.GRAVEYARD and victim in state.players[3-seat].graveyard
    assert state.cards[walker].loyalty==2 and state.cards[walker].oracle_text==RAW['oracle_text']


@pytest.mark.parametrize('seat',[1,2])
def test_minus_three_illegal_land_target_preserves_root_atomically(seat):
    state,walker,_=born(seat);land=add(state,ISLAND,3-seat,Zone.BATTLEFIELD,old_board=True)
    before=serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):checked_action(state,RulesEngine(),seat,{'type':'activate_loyalty','card_id':walker,'ability_index':1,'targets':{'target_card_id':land.id}})
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('seat',[1,2])
def test_plus_one_real_planeswalker_combat_creates_and_resolves_destruction_trigger(seat):
    state,walker,attacker=born(seat)
    state=settle(activate(state,seat,walker,0))
    assert state.cards[walker].loyalty==6
    state=deserialize_match_snapshot(serialize_match_snapshot(state))
    state=combat(state,3-seat,attacker,'planeswalker:'+walker)
    assert state.cards[walker].loyalty==4 and state.cards[walker].zone==Zone.BATTLEFIELD
    assert state.cards[attacker].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
def test_plus_one_expires_at_next_controller_turn_not_arbitrary_cleanup(seat):
    state,walker,attacker=born(seat)
    initial_turn=state.turn
    state=settle(activate(state,seat,walker,0))
    state=advance(state,seat,Step.PRECOMBAT_MAIN,after_turn=initial_turn)
    state=combat(state,3-seat,attacker,'planeswalker:'+walker)
    assert state.cards[walker].loyalty==4
    assert state.cards[attacker].zone==Zone.BATTLEFIELD


@pytest.mark.parametrize('seat',[1,2])
def test_real_paid_stifle_counters_activated_destruction_without_refunding_loyalty(seat):
    state,walker,victim=born(seat)
    stifle=add(state,STIFLE,3-seat,Zone.HAND)
    state=activate(state,seat,walker,1,{'target_card_id':victim});stack_id=state.stack[-1].id
    state=act(state,seat,{'type':'pass_priority'})
    state=act(state,3-seat,{'type':'cast_spell','card_id':stifle.id,'targets':{'target_stack_id':stack_id}})
    assert state.stack[-1].payload['mana_spent']==1
    state=settle(state)
    assert state.cards[walker].loyalty==2 and state.cards[victim].zone==Zone.BATTLEFIELD
    assert state.cards[stifle.id].zone==Zone.GRAVEYARD


@pytest.mark.parametrize('seat',[1,2])
def test_minus_seven_earns_loyalty_creates_three_real_tokens_and_actual_player_loss(seat):
    state,walker,_=born(seat)
    for expected in (6,7):
        prior_turn=state.turn
        state=settle(activate(state,seat,walker,0))
        assert state.cards[walker].loyalty==expected
        state=advance(state,seat,Step.PRECOMBAT_MAIN,after_turn=prior_turn)
    state=settle(activate(state,seat,walker,2))
    assert state.cards[walker].zone==Zone.GRAVEYARD
    tokens=[state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert len(tokens)==3 and all(c.power==c.toughness==1 and c.colors==['B'] and 'Assassin' in c.type_line for c in tokens)
    assert all('loses the game' in c.oracle_text for c in tokens)
    state=deserialize_match_snapshot(serialize_match_snapshot(state))
    state=advance(state,seat,Step.DECLARE_ATTACKERS,after_turn=state.turn)
    state=combat(state,seat,tokens[0].id,'player:'+str(3-seat))
    assert state.winner==seat and state.players[3-seat].life==19


@pytest.mark.parametrize('seat',[1,2])
def test_unpayable_ultimate_is_atomic_without_tokens(seat):
    state,walker,_=born(seat);before=serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):checked_action(state,RulesEngine(),seat,{'type':'activate_loyalty','card_id':walker,'ability_index':2,'targets':{}})
    assert serialize_match_snapshot(state)==before and not any(c.is_token for c in state.cards.values())
