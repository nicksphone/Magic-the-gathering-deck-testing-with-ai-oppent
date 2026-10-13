"""Full-method guard checks; altered Oracle bodies are protocol fixtures, not cards.

The two positives use unchanged canonical RAWs. Every stack spell comes from a
checked cast; profiling observes the additive guard, not a replacement policy.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from knowledge.service import estimate_for
from rules_engine.engine import RulesEngine
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.test_task23_checked_removal_baseline import add_profiled
from tests.test_task42_checked_interaction_hold import base
from tests.vraska_full import test_full_vraska as rules


MEMNITE = next(raw for raw in json.loads((Path(__file__).parent /
    'fixtures/regression_agent_wave2/cards.json').read_bytes()) if raw['name'] == 'Memnite')
BODY_CASES = {
    'vanilla': [None],
    'simple_mana': [None],
    'win_tail': ['{T}: Add {G}. You win the game.'],
    'static_tail': ['{T}: Add {G}.\nYou win the game.'],
    'conditional_tail': ['{T}: Add {G}. If you control an Elf, draw a card.',
                         '{T}: Add {G}. Spend this mana only to cast creature spells.'],
    'paid_cost': ['{1}, {T}: Add {G}.', '{T}, Pay 1 life: Add {G}.'],
}


def choose_with_guard(state, seat):
    actor = AIAgent(difficulty='strong', archetype='Control')
    moves = RulesEngine().legal_moves(state, seat)
    observed = []
    code = AIAgent._choose_action.__code__

    def profile(frame, event, arg):
        if event == 'return' and frame.f_code is code and frame.f_locals.get('self') is actor:
            observed.append(frame.f_locals.get('hold_printed_low'))

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        decision = actor.choose_action(state, moves, seat)
    finally:
        sys.setprofile(previous)
    assert len(observed) == 1 and type(observed[0]) is bool
    return decision.action, observed[0], moves


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['pool', 'paid_lands'])
@pytest.mark.parametrize('kind', list(BODY_CASES))
def test_full_method_only_vanilla_or_complete_free_fixed_tap_mana_holds(seat, context, kind):
    for body in BODY_CASES[kind]:
        raw = deepcopy(MEMNITE if kind == 'vanilla' else RAW['Llanowar Elves'])
        if body is not None:
            raw['oracle_text'] = body  # Explicit adversarial profile carrier, not official RAW.
        state, counter = base(seat)
        islands = []
        if context == 'paid_lands':
            state.players[seat].mana_pool = {}
            islands = [add_profiled(state, RAW['Island'], seat, rules.Zone.BATTLEFIELD).id
                       for _ in range(2)]
            forest = add_profiled(state, RAW['Forest'], 3 - seat, rules.Zone.BATTLEFIELD)
            state = rules.act(state, 3 - seat,
                              {'type': 'tap_land_for_mana', 'card_id': forest.id, 'color': 'G'})
            assert state.cards[forest.id].tapped
        else:
            state.players[3 - seat].mana_pool = {'G': 1}
        source = add_profiled(state, raw, 3 - seat, rules.Zone.HAND)
        assert source.oracle_text == raw['oracle_text']
        assert estimate_for(source).tier == 1
        state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': source.id})
        assert state.stack[-1].source_card_id == source.id
        assert state.stack[-1].payload['mana_spent'] == (0 if kind == 'vanilla' else 1)
        state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
        before = serialize_match_snapshot(state)
        action, guard, moves = choose_with_guard(state, seat)
        assert any(move['type'] == 'cast_spell' and move['card_id'] == counter for move in moves)
        positive = kind in {'vanilla', 'simple_mana'}
        assert guard is positive, (kind, context, body, 'complete-body hold guard')
        if positive:
            assert action['type'] == 'pass_priority'
            held = rules.settle(rules.act(state, seat, action))
            assert held.cards[source.id].zone == rules.Zone.BATTLEFIELD
            assert held.cards[counter].zone == rules.Zone.HAND
            assert all(not held.cards[cid].tapped for cid in islands)
        else:
            legacy = deepcopy(state)
            legacy.cards[source.id].knowledge_snapshot = {}
            legacy_action, legacy_guard, _ = choose_with_guard(legacy, seat)
            assert legacy_guard is False and action == legacy_action
        paid = rules.act(state, seat, {'type': 'cast_spell', 'card_id': counter,
                                      'targets': {'target_stack_id': state.stack[-1].id}})
        assert paid.stack[-1].payload['mana_spent'] == 2
        assert all(paid.cards[cid].tapped for cid in islands)
        paid = rules.settle(paid)
        assert paid.cards[source.id].zone == rules.Zone.GRAVEYARD
        assert paid.cards[counter].zone == rules.Zone.GRAVEYARD
        assert serialize_match_snapshot(state) == before
