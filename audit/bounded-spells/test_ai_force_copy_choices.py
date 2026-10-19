"""NEW12: actual AI choices and checked public counterfactuals; no policy edits."""
from copy import deepcopy
import json

import pytest
import test_paid_force_twincast as core
import test_force_copy_boundaries as controls
from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.continuous import effective_power, effective_toughness

basefacts = core.original.facts
facts = core.facts
receipts = core.receipts


def boundary(facts, seat, count, rows, *, swap=False):
    state, force, targets, pool, friendly = core.original.setup(facts, seat, 'Force of Vigor', count)
    opponent_targets = (core.paid.add(state, facts, "Witch's Oven", seat),
                        core.paid.add(state, facts, 'Intangible Virtue', seat))
    secure = core.paid.add(state, facts, 'Secure the Wastes', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C':2, 'W':1}
    old_battlefield = set(state.players[seat].battlefield)
    state = core.paid.act(state, seat, 'cast_spell', card_id=secure, targets={'x_value':2})
    assert sum(state.players[seat].mana_pool.values())==0 and state.cards[secure].zone==Zone.STACK
    state = core.passes(core.paid.restore(state))
    tokens = set(state.players[seat].battlefield)-old_battlefield
    assert len(tokens)==2 and state.cards[secure].zone==Zone.GRAVEYARD
    assert all(effective_power(state, cid)==2 and effective_toughness(state,cid)==2 for cid in tokens)
    state = core.paid.respond(state, seat)
    state.players[seat].mana_pool = deepcopy(pool)
    state = core.original.cast(state, seat, force, targets)
    assert sum(state.players[seat].mana_pool.values())==0 and len(state.stack)==1
    original_id = state.stack[-1].id
    names = ['Searing Blaze','Secure the Wastes']
    if swap:
        names.reverse()
    hidden = [core.paid.add(state, facts, name, seat, zone)
              for name, zone in zip(names, [Zone.HAND,Zone.LIBRARY])]
    actor = 3-seat
    state = core.paid.respond(state, actor)
    state, twin, copy_id = core.copied(state, facts, actor, original_id, rows)
    controls.menu(state,actor,copy_id)
    core.note(rows, 'ai-paid-boundary', state, actor=actor, count=count,
              token_ids=sorted(tokens), opponent_targets=list(opponent_targets),
              friendly_targets=list(friendly[:count]), secure_id=secure)
    return state, actor, copy_id, original_id, friendly, opponent_targets, tokens, hidden


def choose(state, actor, copy_id, agent, rows):
    offered = controls.menu(state,actor,copy_id)
    moves = RulesEngine().legal_moves(state,actor)
    before = serialize_match_snapshot(state)
    moves_before = deepcopy(moves)
    decision = agent.choose_action(state,moves,actor)
    assert serialize_match_snapshot(state)==before and moves==moves_before
    action = decision.action
    assert action['type']=='choose_mechanic' and len(action['card_ids'])==1
    assert action['card_ids'][0] in offered['options']
    core.note(rows,'actual-ai-public-choice',state,action=action,reasoning=decision.reasoning)
    return action


def finish_copy(state, actor, copy_id, choices, rows):
    for option in choices:
        state=core.public_choice(state,actor,copy_id,option,rows)
    assert state.pending_mechanic_choice is None
    state=core.passes(core.paid.restore(state))
    assert all(item.id!=copy_id for item in state.stack)
    return state


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[1,2])
def test_actual_ai_copy_destroys_opponent_not_friendly(facts,seat,count,receipts):
    state,actor,copy_id,original_id,friendly,opponents,tokens,_=boundary(facts,seat,count,receipts)
    payload=deepcopy(controls.frame(state,original_id).payload)
    agent=AIAgent(difficulty='strong',archetype='Midrange')
    decisions=[]
    for _ in range(count):
        action=choose(state,actor,copy_id,agent,receipts)
        decisions.append(action['card_ids'][0])
        state=core.paid.act(state,actor,action['type'],card_ids=action['card_ids'])
    assert state.pending_mechanic_choice is None
    assert controls.frame(state,original_id).payload==payload
    state=core.passes(core.paid.restore(state))
    destroyed=[cid for cid in opponents if state.cards[cid].zone==Zone.GRAVEYARD]
    assert len(destroyed)==count, 'Strict controlled goal: copy must remove opposing public value'
    assert all(state.cards[cid].zone==Zone.BATTLEFIELD for cid in friendly[:count])
    if opponents[1] in destroyed:
        assert all(effective_power(state,cid)==1 and effective_toughness(state,cid)==1 for cid in tokens)
    core.note(receipts,'ai-copy-controlled-goal-resolved',state,decisions=decisions,destroyed=destroyed)
    state=core.passes(core.paid.restore(state))
    assert not state.stack and all(state.cards[cid].zone==Zone.GRAVEYARD for cid in friendly[:count])


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[1,2])
def test_same_boundary_explicit_keep_and_retarget_counterfactuals(facts,seat,count,receipts):
    state,actor,copy_id,original_id,friendly,opponents,tokens,_=boundary(facts,seat,count,receipts)
    before=serialize_match_snapshot(state)
    payload=deepcopy(controls.frame(state,original_id).payload)
    kept=finish_copy(core.paid.restore(state),actor,copy_id,['keep']*count,receipts)
    changed=finish_copy(core.paid.restore(state),actor,copy_id,
                        ['target_card_id:'+cid for cid in opponents[:count]],receipts)
    assert serialize_match_snapshot(state)==before
    assert all(kept.cards[cid].zone==Zone.GRAVEYARD for cid in friendly[:count])
    assert all(kept.cards[cid].zone==Zone.BATTLEFIELD for cid in opponents)
    assert all(changed.cards[cid].zone==Zone.BATTLEFIELD for cid in friendly[:count])
    assert all(changed.cards[cid].zone==Zone.GRAVEYARD for cid in opponents[:count])
    assert controls.frame(kept,original_id).payload==controls.frame(changed,original_id).payload==payload
    core.note(receipts,'checked-public-counterfactuals',state,
              keep_result=serialize_match_snapshot(kept),retarget_result=serialize_match_snapshot(changed))


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('count',[1,2])
def test_actual_ai_hidden_identity_swap_and_root_invariance(facts,seat,count,receipts):
    normal=boundary(facts,seat,count,receipts)
    swapped=boundary(facts,seat,count,receipts,swap=True)
    state,actor,copy_id,_,_,_,_,hidden=normal
    other,other_actor,other_copy,_,_,_,_,other_hidden=swapped
    assert (actor,copy_id,hidden)==(other_actor,other_copy,other_hidden)
    moves=RulesEngine().legal_moves(state,actor)
    assert moves==RulesEngine().legal_moves(other,actor)
    assert all(cid not in json.dumps(moves) for cid in hidden)
    first=choose(state,actor,copy_id,AIAgent(),receipts)
    second=choose(other,actor,copy_id,AIAgent(),receipts)
    assert first==second, 'Opposing hidden identities must not choose a public copy target'
    for position in (state,other):
        before=serialize_match_snapshot(position)
        projected=core.paid.act(position,actor,first['type'],card_ids=first['card_ids'])
        assert serialize_match_snapshot(position)==before
        assert [projected.cards[cid].name for cid in hidden]==[position.cards[cid].name for cid in hidden]
    core.note(receipts,'ai-private-swap-invariant',state,action=first,hidden_ids=hidden)
