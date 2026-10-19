"""Full-menu ranking baseline; trusted canonical old boards/counters only.

This does not change AI policy or infer a chosen target. Each actual decision
is checked unchanged. The independently checked safe block is an alternative,
not a forced winner or the production action.
"""
import json

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from tests.test_ai_terminal_draw_product import raw
from tests.test_task23_checked_removal_baseline import RAW, add_profiled
from tests.test_task23_canonical_block_outcomes import blocked
from tests.vraska_full.test_full_vraska import bare, act, Zone, Step


def position(seat, life, mana_count):
    root = bare(3 - seat)
    root.turn = 6
    root.step = Step.DECLARE_ATTACKERS
    root.mechanic_choice_players = {1, 2}
    root.players[seat].life = life
    for player in root.players.values():
        player.mana_pool = {}
    attacker = add_profiled(root, raw('grizzly-bears'), 3 - seat, Zone.BATTLEFIELD)
    safe = add_profiled(root, raw('grizzly-bears'), seat, Zone.BATTLEFIELD)
    attacker.counters['+1/+1'] = 1
    safe.counters['+1/+1'] = 2
    mana = [add_profiled(root, RAW['Llanowar Elves'], seat, Zone.BATTLEFIELD).id
            for _ in range(mana_count)]
    assert attacker.oracle_text == safe.oracle_text == raw('grizzly-bears')['oracle_text']
    assert all(root.cards[cid].oracle_text == RAW['Llanowar Elves']['oracle_text'] for cid in mana)
    assert (effective_power(root, attacker.id), effective_toughness(root, attacker.id)) == (3, 3)
    assert (effective_power(root, safe.id), effective_toughness(root, safe.id)) == (4, 4)
    root = act(root, 3 - seat, {'type': 'attack', 'attackers': [attacker.id],
                'attack_targets': {attacker.id: 'player:' + str(seat)}})
    for _ in range(40):
        if root.step == Step.DECLARE_BLOCKERS and root.priority_player == seat:
            break
        root = act(root, root.priority_player, {'type': 'pass_priority'})
    assert root.step == Step.DECLARE_BLOCKERS and root.priority_player == seat
    moves = RulesEngine().legal_moves(root, seat)
    block = next(move for move in moves if move['type'] == 'block')
    assert {item['id'] for item in block['blockers']} == {safe.id, *mana}
    assert any(move['type'] == 'pass_priority' for move in moves)
    assert root.winner is None and not root.stack
    return root, moves, attacker.id, safe.id, mana


def settle_actual_decision(root, seat, actor, decision):
    before = serialize_match_snapshot(root)
    state = act(root, seat, decision.action)
    for _ in range(80):
        if state.step == Step.END_COMBAT or state.winner is not None:
            assert serialize_match_snapshot(root) == before
            return state
        pending = state.pending_mechanic_choice
        if pending:
            assert pending['kind'] == 'combat_damage'
            owner = pending['player_id']
            reply = actor.choose_action(state, RulesEngine().legal_moves(state, owner), owner)
            state = act(state, owner, reply.action)
        elif state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat and not state.blockers_declared:
            reply = actor.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
            state = act(state, seat, reply.action)
        else:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Actual selected action did not reach checked combat closure')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('life', [3, 12])
@pytest.mark.parametrize('mana_count', [0, 3])
def test_full_menu_unused_mana_sources_do_not_hide_safe_native_block(seat, difficulty, life, mana_count, monkeypatch):
    root, moves, attacker, safe, mana = position(seat, life, mana_count)
    original = serialize_match_snapshot(root)
    alternative = blocked(root, seat, attacker, [safe])
    assert alternative.players[seat].life == life and alternative.winner is None
    assert alternative.cards[attacker].zone == Zone.GRAVEYARD
    assert all(alternative.cards[cid].zone == Zone.BATTLEFIELD for cid in [safe, *mana])
    actor = AIAgent(difficulty=difficulty, archetype='Midrange')
    observed = []
    original_bias = actor._block_bias

    def observed_bias(state, move, player_id):
        value = original_bias(state, move, player_id)
        observed.append({'blocker_count': len(move.get('blockers') or []), 'bias': value})
        return value

    monkeypatch.setattr(actor, '_block_bias', observed_bias)
    decision = actor.choose_action(root, moves, seat)
    assert serialize_match_snapshot(root) == original
    outcome = settle_actual_decision(root, seat, actor, decision)
    record = {'seat': seat, 'difficulty': difficulty, 'starting_life': life,
        'offered_mana_count': mana_count, 'actual_action': decision.action,
        'reasoning': decision.reasoning, 'observed_block_bias': observed,
        'actual_life': outcome.players[seat].life, 'actual_winner': outcome.winner,
        'actual_safe_zone': outcome.cards[safe].zone.value,
        'actual_attacker_zone': outcome.cards[attacker].zone.value,
        'actual_mana_zones': [outcome.cards[cid].zone.value for cid in mana],
        'alternative_life': alternative.players[seat].life,
        'alternative_winner': alternative.winner}
    print('BLOCK_BIAS_BASELINE=' + json.dumps(record, sort_keys=True))
    assert serialize_match_snapshot(root) == original
    assert outcome.winner == alternative.winner, 'Checked safe block prevents actual loss'
    assert outcome.players[seat].life >= alternative.players[seat].life, 'Available native safe block avoids all damage'
    assert outcome.cards[attacker].zone == Zone.GRAVEYARD
    assert all(outcome.cards[cid].zone == Zone.BATTLEFIELD for cid in [safe, *mana])
