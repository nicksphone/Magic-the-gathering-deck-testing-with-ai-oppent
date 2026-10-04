"""Search perspective must not replace the actual actor of a future reply."""
from collections import Counter
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai import agent as agent_module
from ai.pending_effects import planning_copy
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.stack_engine import add_to_stack


def actor_correct_reference(ai, state, move, perspective, depth, actor=None):
    """Original replaying search with the recursive actor corrected, not optimized."""
    try:
        sim = planning_copy(state)
        ai.engine.take_action(sim, perspective if actor is None else actor, move, reject_invalid=True)
    except Exception:
        return -9999.0
    score = agent_module.evaluate_board(sim, perspective)
    score += ai._strategic_features(sim, perspective)
    score += ai._stack_two_ply_value(sim, perspective)
    if depth <= 0 or sim.winner is not None:
        return score
    pid = sim.priority_player
    legal = ai._rank_moves(sim, ai.engine.legal_moves(sim, pid), pid, shallow=True)
    beam = []
    for candidate in legal[:6]:
        try:
            action = ai._materialize_action(sim, candidate, pid)
            if action.get('_invalid_ai_choice') or ai._is_unplayable_x_action(action):
                continue
            child = planning_copy(sim)
            ai.engine.take_action(child, pid, action, reject_invalid=True)
            value = (agent_module.evaluate_board(child, perspective)
                     + ai._strategic_features(child, perspective)
                     + ai._stack_two_ply_value(child, perspective))
            beam.append((value, action))
        except Exception:
            continue
    if not beam:
        return score
    beam.sort(key=lambda row: row[0], reverse=pid == perspective)
    return .6 * score + .4 * actor_correct_reference(ai, sim, beam[0][1], perspective, depth-1, pid)


def bare_state(seat=1):
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck, seed=6781)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        player.library.extend(player.hand)
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.hand.clear()
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_reply_uses_the_priority_owner_not_the_score_perspective(seat):
    state = bare_state(seat)
    ai = AIAgent(archetype='Control')
    before = serialize_match_snapshot(state)
    with patch.object(ai, '_strategic_features', return_value=0), patch.object(ai, '_stack_two_ply_value', return_value=0):
        score = ai._strategic_line_score(state, {'type': 'pass_priority'}, seat, 1)
    assert score == 0
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_selected_reply_is_executed_once_as_its_real_actor(monkeypatch, seat):
    state = bare_state(seat)
    ai = AIAgent(archetype='Midrange')
    calls = []
    def take(sim, actor, action, **kwargs):
        assert actor == sim.priority_player, 'wrong simulated actor'
        calls.append((actor, action['branch']))
        if action['branch'] == 'root':
            sim.priority_player = 3-seat
        elif action['branch'] == 'punish':
            sim.players[seat].life -= 5
    replies = [{'type': 'pass_priority', 'branch': name} for name in ['safe', 'punish']]
    monkeypatch.setattr(ai.engine, 'take_action', take)
    monkeypatch.setattr(ai.engine, 'legal_moves', lambda *_: replies)
    monkeypatch.setattr(ai, '_rank_moves', lambda _s, moves, _p, **kw: moves)
    monkeypatch.setattr(ai, '_strategic_features', lambda *_: 0)
    monkeypatch.setattr(ai, '_stack_two_ply_value', lambda *_: 0)
    monkeypatch.setattr(agent_module, 'evaluate_board', lambda sim, _p: float(sim.players[seat].life))
    assert ai._strategic_line_score(state, {'type': 'pass_priority', 'branch': 'root'}, seat, 1) == 18
    assert Counter(calls) == Counter([(seat, 'root'), (3-seat, 'safe'), (3-seat, 'punish')])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('depth', [0, 1, 2, 3])
@pytest.mark.parametrize('archetype', ['Control', 'Tempo', 'Tokens', 'Ramp', 'Aggro', 'Midrange'])
def test_real_counter_response_matches_actor_correct_reference(seat, depth, archetype):
    state = bare_state(seat)
    opponent = 3-seat
    bolt = CardInstance('bolt', 'Lightning Bolt', seat, seat, Zone.STACK, ['Instant'],
                        mana_cost='{R}', oracle_text='Lightning Bolt deals 3 damage to any target.')
    counter = CardInstance('counter', 'Counterspell', opponent, opponent, Zone.HAND, ['Instant'],
                           mana_cost='{U}{U}', oracle_text='Counter target spell.')
    state.cards[bolt.id] = bolt
    state.cards[counter.id] = counter
    state.players[opponent].hand.append(counter.id)
    state.players[opponent].mana_pool = {'U': 2}
    add_to_stack(state, bolt.id, seat, bolt.name, 'deal_damage', {'target_player': opponent, 'amount': 3})
    state.priority_player = seat
    ai = AIAgent(archetype=archetype, difficulty='master_plus')
    before = serialize_match_snapshot(state)
    move = {'type': 'pass_priority'}
    reference = actor_correct_reference(ai, state, move, seat, depth)
    assert serialize_match_snapshot(state) == before
    assert ai._strategic_line_score(state, move, seat, depth) == reference
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('terminal', [False, True])
def test_equal_scores_keep_ranked_order_and_terminal_branch_stops(monkeypatch, seat, terminal):
    state = bare_state(seat)
    ai = AIAgent(archetype='Tokens')
    evaluated = []
    def take(sim, actor, move, **kwargs):
        assert actor == sim.priority_player
        sim.log.append(move['branch'])
        if move['branch'] == 'root':
            sim.priority_player = 3-seat
        if terminal and move['branch'] == 'first':
            sim.winner = seat
    def legal(sim, pid):
        evaluated.append(sim.log[-1])
        if sim.log[-1] == 'root':
            return [{'type': 'pass_priority', 'branch': x} for x in ['first', 'second']]
        return []
    monkeypatch.setattr(ai.engine, 'take_action', take)
    monkeypatch.setattr(ai.engine, 'legal_moves', legal)
    monkeypatch.setattr(ai, '_rank_moves', lambda _s, moves, _p, **kw: moves)
    monkeypatch.setattr(ai, '_strategic_features', lambda *_: 0)
    monkeypatch.setattr(ai, '_stack_two_ply_value', lambda *_: 0)
    monkeypatch.setattr(agent_module, 'evaluate_board', lambda *_: 0)
    assert ai._strategic_line_score(state, {'type': 'pass_priority', 'branch': 'root'}, seat, 2) == 0
    assert evaluated == (['root'] if terminal else ['root', 'first'])


def test_rejected_reply_is_not_scored_or_replayed(monkeypatch):
    state = bare_state()
    ai = AIAgent(archetype='Ramp')
    calls = []
    def take(sim, actor, move, **kwargs):
        calls.append(move['branch'])
        if move['branch'] == 'bad':
            raise ValueError('illegal simulated move')
        sim.priority_player = 2
    monkeypatch.setattr(ai.engine, 'take_action', take)
    monkeypatch.setattr(ai.engine, 'legal_moves', lambda *_: [{'type': 'pass_priority', 'branch': 'bad'}])
    monkeypatch.setattr(ai, '_rank_moves', lambda _s, moves, _p, **kw: moves)
    monkeypatch.setattr(ai, '_strategic_features', lambda *_: 0)
    monkeypatch.setattr(ai, '_stack_two_ply_value', lambda *_: 0)
    monkeypatch.setattr(agent_module, 'evaluate_board', lambda *_: 7)
    assert ai._strategic_line_score(state, {'type': 'pass_priority', 'branch': 'root'}, 1, 3) == 7
    assert calls == ['root', 'bad']
