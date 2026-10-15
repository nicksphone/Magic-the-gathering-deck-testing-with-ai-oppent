"""Synthetic mixed-paragraph fixtures with actual checked end-step transitions.

Initial ownership boards are declared fixtures, not invented natural-game history.
No StackItem or event is injected; original 23/34-case modules remain unchanged.
"""
import pytest

from game_state.state import Zone
from rules_engine.end_step_ownership_draw import condition_holds
from tests.test_end_step_ownership_draw import (
    FACTS, end_step, raw_card, record, resolve_real_top,
)
from tests.test_end_step_ownership_draw_guards import CLAUSE, small_position

EACH = 'At the beginning of each end step, draw a card.'


def board(actor, opponent_turn, foreign_count, text):
    state, source = small_position(actor, text)
    state.active_player = state.priority_player = 3-actor if opponent_turn else actor
    for _ in range(foreign_count):
        card = raw_card(state, FACTS['Forest'], 3-actor, Zone.BATTLEFIELD)
        state.players[3-actor].battlefield.remove(card.id)
        card.controller = actor
        state.players[actor].battlefield.append(card.id)
        assert card.owner == 3-actor and card.controller == actor
    assert condition_holds(state, actor, 3) == (foreign_count >= 3)
    return state, source.id


def resolve_actual(state):
    for _ in range(4):
        if not state.stack:
            return state
        state = resolve_real_top(state)
    raise AssertionError('Actual mixed end-step triggers did not resolve within the fixture bound')


@pytest.mark.parametrize('actor', [1, 2])
@pytest.mark.parametrize('opponent_turn', [False, True])
@pytest.mark.parametrize('foreign_count', [2, 3])
@pytest.mark.parametrize('ownership_first', [False, True])
def test_each_and_own_end_step_paragraphs_both_dispatch_when_eligible(
        request, actor, opponent_turn, foreign_count, ownership_first):
    text = CLAUSE + '\n' + EACH if ownership_first else EACH + '\n' + CLAUSE
    state, source = board(actor, opponent_turn, foreign_count, text)
    active = state.active_player
    state = end_step(state, source)
    assert state.active_player == active
    record(request, state, source, phase='each_and_own', actor=actor,
           opponent_turn=opponent_turn, foreign_count=foreign_count,
           ownership_first=ownership_first)
    assert all(item.controller == actor and item.source_card_id == source for item in state.stack)
    keys = [item.effect_key for item in state.stack]
    before = {pid: len(player.hand) for pid, player in state.players.items()}
    state = resolve_actual(state)
    eligible = not opponent_turn and foreign_count == 3
    assert len(state.players[actor].hand) == before[actor] + 1 + (3 if eligible else 0)
    assert len(state.players[3-actor].hand) == before[3-actor]
    assert keys.count('draw_cards') == 1
    assert keys.count('ownership_end_step_draw') == int(eligible)


@pytest.mark.parametrize('actor', [1, 2])
@pytest.mark.parametrize('opponent_turn', [False, True])
@pytest.mark.parametrize('ownership_first', [False, True])
def test_unknown_separate_ownership_tail_never_rewards_partial_draw(
        request, actor, opponent_turn, ownership_first):
    unknown = CLAUSE + ' Unknown instruction.'
    text = unknown + '\n' + EACH if ownership_first else EACH + '\n' + unknown
    state, source = board(actor, opponent_turn, 3, text)
    state = end_step(state, source)
    record(request, state, source, phase='unknown_ownership_separate', actor=actor,
           opponent_turn=opponent_turn, ownership_first=ownership_first)
    before = len(state.players[actor].hand)
    state = resolve_actual(state)
    assert len(state.players[actor].hand) == before + 1


@pytest.mark.parametrize('actor', [1, 2])
@pytest.mark.parametrize('opponent_turn', [False, True])
@pytest.mark.parametrize('ownership_first', [False, True])
def test_unknown_compound_each_own_paragraph_is_never_split_for_partial_reward(
        request, actor, opponent_turn, ownership_first):
    text = CLAUSE + ' ' + EACH if ownership_first else EACH + ' ' + CLAUSE
    state, source = board(actor, opponent_turn, 3, text)
    state = end_step(state, source)
    record(request, state, source, phase='compound_each_own_unsupported', actor=actor,
           opponent_turn=opponent_turn, ownership_first=ownership_first)
    before = {pid: len(player.hand) for pid, player in state.players.items()}
    state = resolve_actual(state)
    assert all(len(state.players[pid].hand) == count for pid, count in before.items())


@pytest.mark.parametrize('actor', [1, 2])
@pytest.mark.parametrize('opponent_turn', [False, True])
@pytest.mark.parametrize('ownership_first', [False, True])
def test_compound_unsupported_visibility_matches_its_actual_leading_event(
        actor, opponent_turn, ownership_first):
    text = CLAUSE + ' ' + EACH if ownership_first else EACH + ' ' + CLAUSE
    state, source = board(actor, opponent_turn, 3, text)
    state = end_step(state, source)
    triggers = [item for item in state.stack if item.source_card_id == source]
    if ownership_first and opponent_turn:
        assert not triggers, 'An own-first paragraph does not match the opponent end step'
    else:
        assert len(triggers) == 1
        assert triggers[0].controller == actor
        assert triggers[0].effect_key == 'noop'
        assert triggers[0].payload['__unsupported_trigger_instruction'] == text
