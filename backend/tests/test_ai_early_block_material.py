"""Canonical checked combat; no saved private game trace or fitted policy."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.extra_sequence_support import position
from tests.test_ai_friendly_material_conservation import CARDS
from tests.test_linked_damage_targets import raw_card


def attack_position(seat, *, life=20, blocker='Hopeful Initiate', payoff=False,
                    attacker_name='Goblin Guide', attacker_row=None):
    state = position(3-seat, Step.PRECOMBAT_MAIN if blocker=='paid_tokens' else Step.DECLARE_ATTACKERS)
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {}
    state.players[seat].life = life
    attacker = raw_card(state, attacker_row or CARDS[attacker_name], 3-seat, Zone.BATTLEFIELD)
    attacker.summoning_sick=False
    if blocker=='paid_tokens':
        data=json.loads((Path(__file__).parent/'fixtures/immediate_return_product/raise-the-alarm.json').read_text())
        spell=raw_card(state,data,seat,Zone.HAND)
        state.players[seat].mana_pool={'W':2}
        state=checked_action(state,RulesEngine(),3-seat,{'type':'pass_priority'})
        state=checked_action(state,RulesEngine(),seat,{'type':'cast_spell','card_id':spell.id,'targets':{}})
        for _ in range(16):
            if not state.stack: break
            state=checked_action(state,RulesEngine(),state.priority_player,{'type':'pass_priority'})
        assert not state.stack and len(state.players[seat].battlefield)==2
        attacker=state.cards[attacker.id]
        creature=state.cards[state.players[seat].battlefield[0]]
        for _ in range(20):
            if state.step==Step.DECLARE_ATTACKERS and state.priority_player==3-seat:
                break
            state=checked_action(state,RulesEngine(),state.priority_player,{'type':'pass_priority'})
    else:
        creature = raw_card(state, CARDS[blocker], seat, Zone.BATTLEFIELD)
    attacker.summoning_sick = creature.summoning_sick = False
    if payoff:
        raw_card(state, CARDS['Blood Artist'], seat, Zone.BATTLEFIELD)
        state.players[3-seat].life = 1
    rules = RulesEngine()
    state = checked_action(state, rules, 3-seat,
        {'type':'attack','attackers':[attacker.id],
         'attack_targets':{attacker.id:'player:'+str(seat)}})
    for _ in range(40):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat and not state.stack:
            break
        state = checked_action(state,rules,state.priority_player,{'type':'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat and not state.stack
    return state, attacker.id, creature.id


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('life',[18,20])
def test_strong_retains_healthy_early_creature_instead_of_two_life(seat,life):
    state, attacker, creature = attack_position(seat,life=life)
    before=serialize_match_snapshot(state)
    moves=RulesEngine().legal_moves(state,seat)
    offered=deepcopy(moves)
    rng=random.getstate(),state.rng.getstate()
    decision=AIAgent('strong','Aggro','Burn').choose_action(state,moves,seat).action
    assert decision['type'] in {'block','pass_priority'} and not decision.get('blocks')
    result=checked_action(state,RulesEngine(),seat,decision)
    for _ in range(40):
        if result.step==Step.END_COMBAT:
            break
        result=checked_action(result,RulesEngine(),result.priority_player,{'type':'pass_priority'})
    assert result.step==Step.END_COMBAT and result.players[seat].life==life-2
    assert creature in result.players[seat].battlefield
    assert serialize_match_snapshot(state)==before and moves==offered
    assert (random.getstate(),state.rng.getstate())==rng


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('reason',['lethal','trade','winning_death'])
def test_material_retention_preserves_necessary_and_profitable_blocks(seat,reason):
    state, attacker, creature=attack_position(seat,
        life=2 if reason=='lethal' else 20,
        blocker='Recruitment Officer' if reason=='trade' else 'Hopeful Initiate',
        payoff=reason=='winning_death')
    action=AIAgent('strong','Aggro','Burn').choose_action(
        state,RulesEngine().legal_moves(state,seat),seat).action
    assert action['type']=='block'
    assert creature in [cid for values in action['blocks'].values()
                        for cid in ([values] if isinstance(values,str) else values)]
    checked_action(state,RulesEngine(),seat,action)


@pytest.mark.parametrize('seat',[1,2])
def test_equal_oracle_mirror_trade_is_priced_symmetrically(seat):
    state,attacker,creature=attack_position(seat,blocker='Recruitment Officer',
        attacker_name='Recruitment Officer')
    action=AIAgent('strong','Aggro','Aggro').choose_action(
        state,RulesEngine().legal_moves(state,seat),seat).action
    assert action['type']=='block' and action.get('blocks')
    from analytics.decision_quality import _simulate_block_line
    outcome,_=_simulate_block_line(state,seat,action)
    assert outcome.cards[attacker].zone==outcome.cards[creature].zone==Zone.GRAVEYARD
    assert outcome.players[seat].life==20


@pytest.mark.parametrize('seat',[1,2])
def test_nonterminal_death_value_is_not_treated_as_plain_body_loss(seat):
    from tests.test_ai_block_retention import decide_and_finish
    state,_,_=attack_position(seat,payoff=True)
    state.players[3-seat].life=20
    action,outcome=decide_and_finish(state,seat,'Aggro')
    assert action['type']=='block' and action.get('blocks')
    assert outcome.winner is None
    assert outcome.players[seat].life==21 and outcome.players[3-seat].life==19


@pytest.mark.parametrize('seat',[1,2])
def test_actual_paid_tokens_can_still_absorb_damage(seat):
    from tests.test_ai_terminal_draw_product import raw
    state,_,_=attack_position(seat,blocker='paid_tokens',attacker_row=raw('rumbling-baloth'))
    action=AIAgent('strong','Aggro','Burn').choose_action(
        state,RulesEngine().legal_moves(state,seat),seat).action
    assert action['type']=='block' and action.get('blocks')
    from analytics.decision_quality import _simulate_block_line
    outcome,_=_simulate_block_line(state,seat,action)
    assert outcome.players[seat].life==20 and outcome.winner is None
