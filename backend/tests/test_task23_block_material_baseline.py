"""Actual full-menu block baseline; trusted old boards/counters, not paid births.

Full canonical bodies and native checked combat are retained. Counters make
vanilla Bears effective 1/1 without inventing Oracle text or a combat outcome.
Printed future-engine value is an advisory material metric, not a game win.
"""
from copy import deepcopy
import json

import pytest

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from game_state.serializers import serialize_match_snapshot
from knowledge.service import estimate_for
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_ai_terminal_draw_product import raw
from tests.test_task23_checked_removal_baseline import RAW, add_profiled
from tests.test_task23_canonical_block_outcomes import blocked
from tests.vraska_full.test_full_vraska import bare, act, Zone, Step


def position(seat, order, variant='known'):
    root = bare(3 - seat)
    root.turn = 6
    root.step = Step.DECLARE_ATTACKERS
    root.mechanic_choice_players = {1, 2}
    for player in root.players.values():
        player.mana_pool = {}
    attacker = add_profiled(root, raw('grizzly-bears'), 3 - seat, Zone.BATTLEFIELD)
    attacker.counters['-1/-1'] = 1
    cards = {}
    for role in order:
        cards[role] = add_profiled(root, RAW['Zulaport Cutthroat'] if role == 'engine'
                                  else raw('grizzly-bears'), seat, Zone.BATTLEFIELD)
    engine, vanilla = cards['engine'], cards['vanilla']
    vanilla.counters['-1/-1'] = 1
    assert engine.oracle_text == RAW['Zulaport Cutthroat']['oracle_text']
    assert vanilla.oracle_text == attacker.oracle_text == raw('grizzly-bears')['oracle_text']
    assert estimate_for(engine).tier == 3 and estimate_for(vanilla).tier == 1
    if variant == 'missing':
        engine.knowledge_snapshot = {}
    elif variant == 'stale':
        engine.knowledge_snapshot = deepcopy(engine.knowledge_snapshot)
        engine.knowledge_snapshot['root']['oracle_text'] += '\n'
    elif variant == 'suppressed':
        add_keyword_effect(root, engine.id, ['all abilities'], operation='remove')
    assert all((effective_power(root, c.id), effective_toughness(root, c.id)) == (1, 1)
               for c in (attacker, engine, vanilla))
    root = act(root, 3 - seat, {'type': 'attack', 'attackers': [attacker.id],
                'attack_targets': {attacker.id: 'player:' + str(seat)}})
    for _ in range(40):
        if root.step == Step.DECLARE_BLOCKERS and root.priority_player == seat:
            break
        root = act(root, root.priority_player, {'type': 'pass_priority'})
    assert root.step == Step.DECLARE_BLOCKERS and root.priority_player == seat
    moves = RulesEngine().legal_moves(root, seat)
    block = next(move for move in moves if move['type'] == 'block')
    assert {item['id'] for item in block['blockers']} == {engine.id, vanilla.id}
    assert any(move['type'] == 'pass_priority' for move in moves)
    assert root.winner is None and not root.stack
    return root, moves, block, attacker.id, engine.id, vanilla.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['master', 'strong'])
@pytest.mark.parametrize('order', [('engine', 'vanilla'), ('vanilla', 'engine')])
def test_full_menu_actual_material_choice_retains_engine_when_checked_trade_dominates(seat, difficulty, order):
    root, moves, block, attacker, engine, vanilla = position(seat, order)
    before = serialize_match_snapshot(root)
    better = blocked(root, seat, attacker, [vanilla])
    worse = blocked(root, seat, attacker, [engine])
    for result, lost, retained in ((better, vanilla, engine), (worse, engine, vanilla)):
        assert result.players[seat].life == 21
        assert result.players[3 - seat].life == 19
        assert result.winner is None
        assert result.cards[attacker].zone == result.cards[lost].zone == Zone.GRAVEYARD
        assert result.cards[retained].zone == Zone.BATTLEFIELD
    assert evaluate_board(better, seat) > evaluate_board(worse, seat)
    actor = AIAgent(difficulty=difficulty, archetype='Midrange')
    search = actor._search_block_assignments(root, block['attackers'], block['blockers'])
    if difficulty == 'strong':
        assert search is not None  # Scoped recurring-material admission now uses checked outcomes.
    else:
        assert search is not None
    decision = actor.choose_action(root, moves, seat)
    assert serialize_match_snapshot(root) == before
    assert decision.action['type'] == 'block'
    selected = (decision.action.get('blocks') or {}).get(attacker) or []
    if isinstance(selected, str):
        selected = [selected]
    actual = blocked(root, seat, attacker, selected)
    print(json.dumps({'seat': seat, 'difficulty': difficulty, 'order': order,
        'selected': ['engine' if cid == engine else 'vanilla' for cid in selected],
        'life': actual.players[seat].life, 'opponent_life': actual.players[3-seat].life,
        'winner': actual.winner, 'engine_zone': actual.cards[engine].zone.value,
        'vanilla_zone': actual.cards[vanilla].zone.value,
        'checked_better_board': evaluate_board(better, seat),
        'checked_worse_board': evaluate_board(worse, seat),
        'checked_actual_board': evaluate_board(actual, seat)}, sort_keys=True))
    assert actual.players[seat].life == better.players[seat].life
    assert actual.winner == better.winner
    assert serialize_match_snapshot(root) == before
    assert actual.cards[engine].zone == Zone.BATTLEFIELD, 'Same checked trade retains the actual recurring engine'
    assert evaluate_board(actual, seat) >= evaluate_board(better, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', ['missing', 'stale', 'suppressed'])
def test_unavailable_or_suppressed_carrier_does_not_fabricate_effective_value(seat, variant):
    root, moves, block, attacker, engine, vanilla = position(seat, ('engine', 'vanilla'), variant)
    before = serialize_match_snapshot(root)
    if variant in {'missing', 'stale'}:
        assert estimate_for(root.cards[engine]) is None
    better = blocked(root, seat, attacker, [vanilla])
    other = blocked(root, seat, attacker, [engine])
    if variant == 'suppressed':
        assert better.players[seat].life == other.players[seat].life == 20
        assert better.players[3-seat].life == other.players[3-seat].life == 20
        assert evaluate_board(better, seat) == evaluate_board(other, seat)
    else:
        assert better.players[seat].life == other.players[seat].life == 21
        assert evaluate_board(better, seat) > evaluate_board(other, seat)
    for difficulty in ('master', 'strong'):
        actor = AIAgent(difficulty=difficulty, archetype='Midrange')
        decision = actor.choose_action(root, moves, seat)
        assert decision.action['type'] in {'block', 'pass_priority'}
        if decision.action['type'] == 'block':
            selected = (decision.action.get('blocks') or {}).get(attacker) or []
            if isinstance(selected, str):
                selected = [selected]
            result = blocked(root, seat, attacker, selected)
            assert result.winner is None
        assert serialize_match_snapshot(root) == before
