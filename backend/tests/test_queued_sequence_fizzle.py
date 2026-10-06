"""Canonical target becoming protected: a rules position, not a played shield claim."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from game_state.state import MatchFactory, Zone
from rules_engine.stack_engine import resolve_top_of_stack
from tests.queued_sequence_support import position, cast, act, resume

FIXTURE=Path(__file__).parent/'fixtures/queued_fizzle'
RAW=json.loads((FIXTURE/'canonical.json').read_text())


def test_full_canonical_shield_intake():
    proof=json.loads((FIXTURE/'provenance.json').read_text())
    assert proof['facts_modified'] is False and proof['intake_before_tests']
    assert proof['canonical_sha256']==hashlib.sha256((FIXTURE/'canonical.json').read_bytes()).hexdigest()
    assert proof['id']==RAW['id'] and proof['oracle_id']==RAW['oracle_id']
    assert proof['raw_sha256']==hashlib.sha256(json.dumps(RAW,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def protect_position(state,seat):
    sample=MatchFactory.from_decks([{**RAW,'card_name':RAW['name'],'quantity':1}],[],seed=7214)
    card=deepcopy(next(iter(sample.cards.values())))
    card.id=state.allocate_object_id();card.owner=card.controller=seat
    card.move_to_zone(Zone.BATTLEFIELD)
    state.cards[card.id]=card;state.players[seat].battlefield.append(card.id)
    return card.id


@pytest.mark.parametrize('seat',[1,2])
def test_targeted_extra_turn_fizzles_if_target_now_has_hexproof(seat):
    state=position(seat)
    state,source=cast(state,'Time Warp',seat,{'target_player':3-seat})
    # Explicit canonical battlefield position before resolution. No claim that
    # this module implements a particular shield-entry spell or opening-hand play.
    protect_position(state,3-seat)
    state=resume(state)
    assert resolve_top_of_stack(state)
    assert not state.extra_turns and not state.stack
    assert state.cards[source].zone==Zone.GRAVEYARD and state.spells_cast_this_turn[seat]==1


@pytest.mark.parametrize('seat',[1,2])
def test_copied_target_fizzles_independently_of_original_controller(seat):
    state=position(seat)
    state,source=cast(state,'Time Warp',seat,{'target_player':seat})
    target=state.stack[-1].id;state.priority_player=3-seat
    state,_=cast(state,'Twincast',3-seat,{'target_stack_id':target})
    resolved=resolve_top_of_stack(state)
    if state.pending_mechanic_choice:
        assert not resolved and state.pending_mechanic_choice['kind']=='copy_target'
        state=act(state,3-seat,{'type':'choose_mechanic','card_ids':['keep']})
    else:
        assert resolved
    protect_position(state,seat)
    state=resume(state)
    assert state.stack[-1].payload['__stack_copy_kind']=='spell'
    assert resolve_top_of_stack(state) and not state.extra_turns
    assert resolve_top_of_stack(state)
    assert len(state.extra_turns)==1 and state.extra_turns[0]['recipient']==seat
    assert state.cards[source].zone==Zone.GRAVEYARD
