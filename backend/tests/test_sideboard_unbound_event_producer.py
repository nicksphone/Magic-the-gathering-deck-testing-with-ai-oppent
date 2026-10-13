"""Paid canonical events and strict witness negatives; not whole-game strength."""
from copy import deepcopy

import pytest

from ai import sideboard_facts as facts
from effects.registry import resolve_effect
from game_state.observations import observe_cards
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, draw_card
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_empty_hand_attack_witness import ROWS, position
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat',[1,2])
def test_actual_paid_unbound_creature_remains_playable_and_cannot_certify_sideboard(seat):
    state,cid=position(seat,'Torrential Gearhulk')
    assert cid not in state.sideboard_facts['inventory'] and state.cards[cid].is_token is False
    # Existing native bounce of a canonical trusted-board source; its new cast
    # and payment are real, not a natural opening or paid bounce certificate.
    resolve_effect(state,seat,'return_permanent_to_hand',{'target_card_id':cid})
    state.players[seat].mana_pool={'U':2,'C':4}
    state=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':cid})
    assert state.stack[-1].payload['mana_spent']==6
    assert resolve_top_of_stack(state)
    assert state.cards[cid].zone==Zone.BATTLEFIELD
    assert state.sideboard_facts['coverage_ok'] is False and state.sideboard_facts['complete'] is False
    observed=state.sideboard_facts['seats'][str(3-seat)]
    assert cid not in observed['observed_creatures'] and cid not in observed['observed_creature_sources']
    restored=deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[cid].zone==Zone.BATTLEFIELD
    assert facts.summary_for(restored,seat)=={'qualified':False}
    assert not facts.seal_game(restored)


@pytest.mark.parametrize('seat',[1,2])
def test_actual_paid_inventory_bound_creature_preserves_valid_observation(seat):
    deck=[{**ROWS['Mountain'],'card_name':'Mountain','quantity':56},
          {**ROWS['Torrential Gearhulk'],'card_name':'Torrential Gearhulk','quantity':4}]
    state=MatchFactory.from_decks(deck,deepcopy(deck),seed=13)
    state.pregame_pending=False;state.kept_hands={1,2}
    state.active_player=state.priority_player=seat;state.step=Step.PRECOMBAT_MAIN
    while state.players[seat].library: draw_card(state,seat)
    cid=next(cid for cid in state.players[seat].hand if state.cards[cid].name=='Torrential Gearhulk')
    assert cid in state.sideboard_facts['inventory']
    state.players[seat].mana_pool={'U':2,'C':4}
    state=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':cid})
    assert state.stack[-1].payload['mana_spent']==6 and resolve_top_of_stack(state)
    assert state.sideboard_facts['coverage_ok'] is True
    witness=state.sideboard_facts['seats'][str(3-seat)]['observed_creature_sources'][cid]
    assert witness['owner']==witness['controller']==seat and 'Creature' in witness['effective_types']
    assert deserialize_match_snapshot(serialize_match_snapshot(state)).sideboard_facts==state.sideboard_facts


@pytest.mark.parametrize('seat',[1,2])
def test_real_native_token_batch_is_not_an_unbound_nontoken_exception(seat):
    deck=[{**ROWS['Mountain'],'card_name':'Mountain','quantity':60}]
    state=MatchFactory.from_decks(deck,deepcopy(deck),seed=13)
    before=set(state.cards)
    # Trusted real resolver instruction, NOT a paid token-spell certificate.
    resolve_effect(state,seat,'create_token',{'name':'Goblin','power':1,'toughness':1,
        'types':['Creature'],'amount':2})
    created=set(state.cards)-before
    assert len(created)==2 and all(state.cards[cid].is_token is True for cid in created)
    assert not created.intersection(state.sideboard_facts['inventory'])
    assert created.issubset(state.sideboard_facts['seats'][str(3-seat)]['observed_creatures'])
    assert state.sideboard_facts['coverage_ok'] is True
    assert deserialize_match_snapshot(serialize_match_snapshot(state)).sideboard_facts==state.sideboard_facts


@pytest.mark.parametrize('seat',[1,2])
def test_tampered_unbound_historical_witness_still_rejects_exact_validator(seat):
    deck=[{**ROWS['Mountain'],'card_name':'Mountain','quantity':60}]
    state=MatchFactory.from_decks(deck,deepcopy(deck),seed=13)
    card=raw_card(state,ROWS['Torrential Gearhulk'],seat,Zone.BATTLEFIELD)
    observe_cards(state,[card.id])
    observed=state.sideboard_facts['seats'][str(3-seat)]
    # Deliberate invalid private witness insertion; not a real event receipt.
    observed['observed_creatures'].append(card.id)
    observed['observed_creature_sources'][card.id]={'cid':card.id,'owner':seat,'controller':seat,
        'zone_change_sequence':card.zone_change_sequence,'effective_types':['Artifact','Creature']}
    with pytest.raises(ValueError,match='Invalid retained public creature source'):
        facts.copy_facts(state.sideboard_facts,state)
