"""Explicitly collected RED desired contracts, not a default release gate.

Run this module by path. No xfail, injection of an effect, or Oracle shortening.
The first genuine admission/scheduling failure blocks later desired checks.
"""
import pickle

import pytest
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.extra_sequence_support import add, position, resume, submit


def next_upkeep(state):
    turn = state.turn
    for _ in range(24):
        RulesEngine().next_step(state)
        if state.turn > turn and state.step == Step.UPKEEP:
            return
    raise AssertionError('No next turn upkeep within bounded ordinary progression')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_relation', ['self', 'opponent'])
def test_desired_target_extra_turn_then_resume_normal_order(seat, target_relation):
    target = seat if target_relation == 'self' else 3 - seat
    original = position(seat)
    source = add(original, 'Time Warp', seat, Zone.HAND)
    creature = add(original, 'Grizzly Bears', target)
    land = add(original, 'Island', target)
    creature.tapped = land.tapped = True
    before = pickle.dumps(original)
    state = submit(original, source, target)
    assert pickle.dumps(original) == before
    assert state.stack[-1].controller == seat and state.stack[-1].payload['target_player'] == target
    saved = serialize_match_snapshot(state)
    state = resume(state)
    assert serialize_match_snapshot(state) == saved
    assert resolve_top_of_stack(state)
    actors = []
    for expected in [target, 3 - seat]:
        next_upkeep(state)
        actors.append(state.active_player)
        if state.active_player == target:
            assert not state.cards[creature.id].tapped and not state.cards[land.id].tapped
            assert not state.cards[creature.id].summoning_sick
        hand = len(state.players[state.active_player].hand)
        RulesEngine().next_step(state)
        assert state.step == Step.DRAW and len(state.players[state.active_player].hand) == hand + 1
    assert actors == [target, 3 - seat], 'Extra turn before next normal turn: CR 500.7'
    assert state.turn == 7


@pytest.mark.parametrize('seat', [1, 2])
def test_desired_most_recently_resolved_turn_first_and_restore(seat):
    state = position(seat)
    for target in [3 - seat, seat]:
        source = add(state, 'Time Warp', seat, Zone.HAND)
        state = submit(state, source, target)
        assert resolve_top_of_stack(state)
        state.priority_player = seat
    saved = serialize_match_snapshot(state)
    state = resume(state)
    assert serialize_match_snapshot(state) == saved
    actors = []
    for _ in range(3):
        next_upkeep(state)
        actors.append(state.active_player)
    assert actors == [seat, 3 - seat, 3 - seat], 'Latest extra turn first, then normal order: CR 500.7'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('step', [Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN])
def test_desired_activated_untap_then_extra_combat_main_not_extra_turn(seat, step):
    original = position(seat, step)
    source = add(original, 'Aggravated Assault', seat)
    own = add(original, 'Grizzly Bears', seat)
    other = add(original, 'Grizzly Bears', 3 - seat)
    land = add(original, 'Island', seat)
    own.tapped = other.tapped = land.tapped = True
    before = pickle.dumps(original)
    mana = sum(original.players[seat].mana_pool.values())
    state = submit(original, source)
    assert pickle.dumps(original) == before
    assert sum(state.players[seat].mana_pool.values()) == mana - 5
    assert state.stack[-1].controller == seat and state.stack[-1].source_card_id == source.id
    saved = serialize_match_snapshot(state)
    state = resume(state)
    assert serialize_match_snapshot(state) == saved
    assert resolve_top_of_stack(state)
    assert not state.cards[own.id].tapped
    assert state.cards[other.id].tapped and state.cards[land.id].tapped
    assert state.cards[own.id].summoning_sick, 'Untap is not a new turn: CR 302.6'
    hand = len(state.players[seat].hand)
    seen = []
    for _ in range(6):
        RulesEngine().next_step(state)
        seen.append(state.step)
        assert state.turn == 5 and state.active_player == seat
    assert seen == [Step.BEGIN_COMBAT, Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS,
                    Step.COMBAT_DAMAGE, Step.END_COMBAT, Step.POSTCOMBAT_MAIN]
    assert len(state.players[seat].hand) == hand, 'Extra combat/main has no beginning/draw phase'
    assert state.cards[own.id].summoning_sick
    assert not state.attackers and not state.blocks
