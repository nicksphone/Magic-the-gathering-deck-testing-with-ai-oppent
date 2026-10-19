"""Real paid canonical and whole-intent controls; no inferred selection or SQL."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from training.environment import TrainingEnvironment
from test_discard_continuation_projection import CANONICAL, paused


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 2])
def test_paid_complete_canonical_body_uses_safe_hint_then_explicit_native_choice(seat, count):
    state = CANONICAL.board(seat)
    source = state.cards['daretti']
    state.players[seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source.id)
    state.players[seat].mana_pool = {'R': 1, 'C': 3}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': source.id})
    assert resolve_top_of_stack(state) is True
    assert state.cards[source.id].zone == Zone.BATTLEFIELD
    assert state.cards[source.id].loyalty == 3
    assert not any(state.players[seat].mana_pool.values())
    hand = [CANONICAL.put(state, f'paid-generated-hand-{seat}-{i}', Zone.HAND,
                          owner=seat, types=('Land',)).id for i in range(3)]
    state = CANONICAL.activate(state, seat, 0)
    assert resolve_top_of_stack(state) is False
    before = deepcopy(serialize_match_snapshot(state))
    hint = RulesEngine().legal_moves(state, seat)[0]
    assert hint['options'] == hand and hint['min_count'] == 0 and hint['count'] == 2
    assert not {'followup_effect', 'resolving_item', 'effect_controller'} & hint.keys()
    result = CANONICAL.choose(state, seat, hand[:count])
    assert serialize_match_snapshot(state) == before
    assert result.discards_this_turn[seat] == result.draws_this_turn[seat] == count
    assert result.players[seat].graveyard == hand[:count]
    assert result.cards['daretti'].oracle_text == CANONICAL.RAW_BODY
    assert result.cards['daretti'].loyalty == 5
    assert not result.stack and not result.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_memory_whole_actor_intent_requires_explicit_selection_and_replays_exactly(
        seat, count, restore):
    state, hand = paused(seat, restore)
    env = TrainingEnvironment()
    env._state = deepcopy(state)
    before = deepcopy(env.snapshot())
    hint = env._rules.legal_moves(env._state, seat)[0]
    action = {'type': 'choose_mechanic', 'card_ids': hand[:count]}
    intent = {**deepcopy(hint), **deepcopy(action)}
    untouched = deepcopy(intent)
    normalized = env.lookup_intent(intent, seat)
    assert normalized == env.lookup(action, seat)
    assert normalized['action'] == action
    assert env.snapshot() == before and intent == untouched
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint, seat)
    with pytest.raises(ActionRejected):
        env.lookup_intent(intent, 3-seat)
    assert env.snapshot() == before
    fork, replay = TrainingEnvironment(), TrainingEnvironment()
    # These retained synthetic boards are not built-in-deck training episodes.
    fork._state = deserialize_match_snapshot(before['state'])
    replay._state = deserialize_match_snapshot(before['state'])
    assert fork.step(normalized['action'], seat) == replay.step(action, seat)
    assert fork.snapshot() == replay.snapshot()
    assert fork._state.discards_this_turn[seat] == fork._state.draws_this_turn[seat] == count
    assert not fork._state.pending_mechanic_choice and not fork._state.stack
