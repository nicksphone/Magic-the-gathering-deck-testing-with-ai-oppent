"""Ordinary friendly-board availability regression; canonical paid creature birth."""
import json

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_task23_numeric_priority_baseline import position
from tests.vraska_full import test_full_vraska as rules


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_own_creature_does_not_hide_low_opponent_profile_priority(seat):
    state, removal, value, engine, opponent = position(seat, 'Llanowar Elves')
    state.players[3 - seat].battlefield.remove(engine)
    state.players[3 - seat].library.append(engine)
    state.cards[engine].move_to_zone(rules.Zone.LIBRARY)
    # Fixed original pool covers genuine creature birth plus each competing cast.
    state.players[seat].mana_pool['G'] = 1
    own = rules.add(state, rules.BEAR, seat, rules.Zone.HAND)
    state = rules.paid_cast(state, seat, own, 2)
    assert state.cards[own.id].zone == rules.Zone.BATTLEFIELD
    legal = RulesEngine().legal_moves(state, seat)
    moves = {m['card_id']: m for m in legal if m['type'] == 'cast_spell'}
    assert {removal, value} <= set(moves)
    assert {own.id, opponent} <= {t['id'] for t in moves[removal]['target_hints']['creature_targets']}
    original = serialize_match_snapshot(state)
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    biases = {cid: actor._cast_bias(state, moves[cid], seat) for cid in (removal, value)}
    decision = actor.choose_action(state, legal, seat)
    actual = rules.settle(rules.act(state, seat, decision.action))
    assert actual.winner is None
    # Both competing actions actually execute; no assumed future draw payoff.
    destroy = rules.act(state, seat, {'type': 'cast_spell', 'card_id': removal,
                                     'targets': {'target_card_id': opponent}})
    assert destroy.stack[-1].payload['mana_spent'] == 2
    destroy = rules.settle(destroy)
    assert destroy.cards[opponent].zone == rules.Zone.GRAVEYARD
    assert destroy.cards[own.id].zone == rules.Zone.BATTLEFIELD
    draw = rules.act(state, seat, {'type': 'cast_spell', 'card_id': value, 'targets': {}})
    assert draw.stack[-1].payload['mana_spent'] == 3
    draw = rules.settle(draw)
    assert len(draw.players[seat].hand) == len(state.players[seat].hand) + 1
    assert draw.cards[opponent].zone == draw.cards[own.id].zone == rules.Zone.BATTLEFIELD
    assert serialize_match_snapshot(state) == original
    print('FRIENDLY_BASELINE=' + json.dumps({'seat': seat, 'cast_biases': biases,
        'action': decision.action, 'reasoning': decision.reasoning}, sort_keys=True))
    assert biases[removal] < biases[value]
