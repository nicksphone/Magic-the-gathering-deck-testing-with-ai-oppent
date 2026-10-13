"""Task4.3 public test support; exact historical helper bodies, no tests."""
from copy import deepcopy
import json

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_value
from rules_engine.targeting import stack_object_kind
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.test_task23_checked_removal_baseline import add_profiled
from tests.vraska_full import test_full_vraska as rules


def replay(state, enabled):
    before = serialize_match_snapshot(state)
    if enabled:
        state = deserialize_match_snapshot(deepcopy(before))
    assert serialize_match_snapshot(state) == before
    return state



def choose(state, seat, first, second):
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    assert {first, second} <= {m.get('card_id') for m in legal if m['type'] == 'cast_spell'}
    actor = AIAgent(difficulty='strong', archetype='Control')
    ranked = actor._rank_moves(state, legal, seat)
    cast_order = [m['card_id'] for m in ranked if m['type'] == 'cast_spell']
    decision = actor.choose_action(state, legal, seat)
    assert serialize_match_snapshot(state) == before
    print('TASK43_DECISION=' + json.dumps({'seat': seat, 'turn': state.turn,
        'first': state.cards[first].name, 'second': state.cards[second].name,
        'cast_order': [state.cards[cid].name for cid in cast_order],
        'action_type': decision.action['type'],
        'selected': state.cards[decision.action['card_id']].name if decision.action.get('card_id') else None,
        'first_bias': actor._cast_bias(state, next(m for m in legal if m.get('card_id') == first and m['type'] == 'cast_spell'), seat),
        'second_bias': actor._cast_bias(state, next(m for m in legal if m.get('card_id') == second and m['type'] == 'cast_spell'), seat),
        'knowledge_usage': decision.knowledge_usage}, sort_keys=True))
    return decision.action, cast_order



def checked_cast(state, seat, action):
    before = serialize_match_snapshot(state)
    assert action['type'] == 'cast_spell', 'Genuine policy did not choose a cast; never force one'
    card = state.cards[action['card_id']]
    pool = sum(state.players[seat].mana_pool.values())
    result = rules.act(state, seat, action)
    spent = mana_value(card.mana_cost)
    assert result.stack[-1].source_card_id == card.id
    assert stack_object_kind(result, result.stack[-1]) == 'spell'
    assert result.stack[-1].payload['mana_spent'] == spent
    assert pool - sum(result.players[seat].mana_pool.values()) == spent
    result = rules.settle(result)
    assert not result.stack and result.winner is None
    expected = rules.Zone.BATTLEFIELD if 'Creature' in card.types else rules.Zone.GRAVEYARD
    assert result.cards[card.id].zone == expected
    assert result.cards[card.id].oracle_text == card.oracle_text
    assert serialize_match_snapshot(state) == before
    print('TASK43_CHECKED=' + json.dumps({'seat': seat, 'source': card.name,
        'spent': spent, 'zone': expected.value, 'turn': result.turn}, sort_keys=True))
    return result
