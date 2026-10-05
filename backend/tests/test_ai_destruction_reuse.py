"""Decision-local reuse invariants; canonical decisions are checked separately."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pickle
from threading import Barrier
from unittest.mock import patch

import pytest

from ai import pending_effects as projections
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.test_ai_search_prefix import bare_state
from tests.test_pending_removal import fixture, add_card
from tests.test_ai_recurring_engines import add as add_canonical
from tests.regression_agent_wave2.support import add as add_golden


def announced(state):
    return {'type': 'cast_spell', 'card_id': state.players[1].library[0],
            'targets': {'target_card_id': state.players[2].library[0]},
            'cost_choice': {'id': 'base'}}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('result', [True, False, None])
def test_scalar_results_cache_without_conflating_unknown(seat, result):
    state = bare_state(seat)
    action = announced(state)
    with patch.object(projections, '_friendly_destruction_profit', return_value=result) as compute:
        with projections.decision_projection_scope(state, seat):
            assert projections.friendly_destruction_profit(state, seat, action) is result
            assert projections.friendly_destruction_profit(state, seat, deepcopy(action)) is result
        assert compute.call_count == 1
        projections.friendly_destruction_profit(state, seat, action)
        assert compute.call_count == 2


@pytest.mark.parametrize('field', ['targets', 'cost_choice', 'selected_face_index', 'modes',
                                  'x_value', 'additional_costs', 'mana_cost', 'source_card_id'])
def test_complete_announced_actions_have_separate_entries(field):
    state = bare_state()
    action = announced(state)
    changed = deepcopy(action)
    changed[field] = {'selected': 'other'} if field in {'targets', 'cost_choice', 'additional_costs'} else 2
    with patch.object(projections, '_friendly_destruction_profit', return_value=False) as compute:
        with projections.decision_projection_scope(state, 1):
            projections.friendly_destruction_profit(state, 1, action)
            projections.friendly_destruction_profit(state, 1, changed)
        assert compute.call_count == 2


@pytest.mark.parametrize('change', ['turn', 'controller', 'zone', 'reentry', 'alias', 'counter', 'mana', 'rng',
                                   'pending', 'extra', 'library_order', 'restricted_mana'])
def test_mutations_of_the_same_root_invalidate_dynamic_results(change):
    state = bare_state()
    action = announced(state)
    card = state.cards[action['card_id']]
    with patch.object(projections, '_friendly_destruction_profit', return_value=False) as compute:
        with projections.decision_projection_scope(state, 1):
            projections.friendly_destruction_profit(state, 1, action)
            if change == 'turn': state.turn += 1
            elif change == 'controller': card.controller = 2
            elif change == 'zone': card.move_to_zone(Zone.EXILE)
            elif change == 'reentry':
                card.move_to_zone(Zone.EXILE)
                card.move_to_zone(Zone.LIBRARY)
            elif change == 'alias': state.cards[state.players[2].library[0]].keywords = card.keywords
            elif change == 'counter': card.counters['+1/+1'] = 1
            elif change == 'mana': state.players[1].mana_pool['U'] += 1
            elif change == 'rng': state.rng.random()
            elif change == 'pending': state.pending_mechanic_choice = {'player_id': 2, 'kind': 'scry'}
            elif change == 'extra': state.test_gameplay_field = ['changed']
            elif change == 'library_order': state.players[1].library.reverse()
            elif change == 'restricted_mana': state.players[1].restricted_mana_pool.append({'color': 'U', 'amount': 1})
            projections.friendly_destruction_profit(state, 1, action)
        assert compute.call_count == 2


def test_reordered_dictionary_keys_hit_but_actor_and_projected_state_do_not():
    state = bare_state()
    action = announced(state)
    with patch.object(projections, '_friendly_destruction_profit', return_value=False) as compute:
        with projections.decision_projection_scope(state, 1):
            projections.friendly_destruction_profit(state, 1, action)
            projections.friendly_destruction_profit(state, 1, dict(reversed(list(action.items()))))
            projections.friendly_destruction_profit(state, 2, action)
            projections.friendly_destruction_profit(deepcopy(state), 1, action)
        assert compute.call_count == 3


@pytest.mark.parametrize('result', [True, False, None])
def test_callback_execution_bypasses_reuse_even_for_same_callable(result):
    state = bare_state()
    action = announced(state)
    history = []
    def policy(*args):
        history.append(len(history))
        return {'type': 'pass_priority'}
    def resolve(*args, own_choice_action=None):
        own_choice_action(state, [], 1)
        return result
    with patch.object(projections, '_friendly_destruction_profit', side_effect=resolve) as compute:
        with projections.decision_projection_scope(state, 1):
            for _ in range(2):
                assert projections.friendly_destruction_profit(state, 1, action, own_choice_action=policy) is result
        assert compute.call_count == 2 and history == [0, 1]


def test_unused_distinct_opaque_policies_are_never_called_or_assumed_pure():
    state = bare_state()
    action = announced(state)
    def forbidden(*args):
        raise AssertionError('This projection has no choice')
    with patch.object(projections, '_friendly_destruction_profit', return_value=False) as compute:
        with projections.decision_projection_scope(state, 1):
            projections.friendly_destruction_profit(state, 1, action, own_choice_action=forbidden)
            projections.friendly_destruction_profit(state, 1, action, own_choice_action=lambda *args: forbidden(*args))
        assert compute.call_count == 1


def test_nonserializable_state_or_action_bypasses_without_losing_forecast():
    state = bare_state()
    action = announced(state)
    with patch.object(projections, '_friendly_destruction_profit', return_value=True) as compute:
        with projections.decision_projection_scope(state, 1):
            action['opaque'] = object()
            for _ in range(2): assert projections.friendly_destruction_profit(state, 1, action) is True
            del action['opaque']
            state.opaque = lambda: None
            for _ in range(2): assert projections.friendly_destruction_profit(state, 1, action) is True
        assert compute.call_count == 4


def test_mutating_compute_cannot_install_a_stale_entry():
    state = bare_state()
    def change(*args, **kwargs):
        state.turn += 1
        return False
    with patch.object(projections, '_friendly_destruction_profit', side_effect=change) as compute:
        with projections.decision_projection_scope(state, 1):
            for _ in range(2): projections.friendly_destruction_profit(state, 1, announced(state))
        assert compute.call_count == 2


def test_nested_exception_restores_outer_memo_without_caching_failure():
    state = bare_state()
    other = deepcopy(state)
    with patch.object(projections, '_friendly_destruction_profit', return_value=False) as compute:
        with projections.decision_projection_scope(state, 1):
            projections.friendly_destruction_profit(state, 1, announced(state))
            with pytest.raises(RuntimeError):
                with projections.decision_projection_scope(other, 1):
                    raise RuntimeError('interrupted')
            projections.friendly_destruction_profit(state, 1, announced(state))
        assert compute.call_count == 1


def test_failed_computation_is_not_cached_or_swallowed():
    state = bare_state()
    with patch.object(projections, '_friendly_destruction_profit', side_effect=[RuntimeError('interrupted'), False]) as compute:
        with projections.decision_projection_scope(state, 1):
            with pytest.raises(RuntimeError):
                projections.friendly_destruction_profit(state, 1, announced(state))
            assert projections.friendly_destruction_profit(state, 1, announced(state)) is False
            assert projections.friendly_destruction_profit(state, 1, announced(state)) is False
        assert compute.call_count == 2


def test_distinct_actions_retain_one_root_snapshot_not_one_per_target():
    state = bare_state()
    state.log.append('long-session trace ' * 10000)
    expected = pickle.dumps(state, protocol=5)
    with patch.object(projections, '_friendly_destruction_profit', return_value=False):
        with projections.decision_projection_scope(state, 1):
            for value in range(10):
                projections.friendly_destruction_profit(state, 1, {**announced(state), 'x_value': value})
            retained = set()
            def inspect(value):
                if isinstance(value, bytes) and value == expected: retained.add(id(value))
                elif isinstance(value, dict):
                    for k, v in value.items(): inspect(k); inspect(v)
                elif isinstance(value, (tuple, list)):
                    for part in value: inspect(part)
            inspect(projections._decision_projection.get()[2])
            assert len(retained) == 1


def test_parallel_decisions_cannot_share_the_memo():
    state = bare_state()
    barrier = Barrier(2)
    def run(_):
        with projections.decision_projection_scope(state, 1):
            barrier.wait()
            for _ in range(2): projections.friendly_destruction_profit(state, 1, announced(state))
    with patch.object(projections, '_friendly_destruction_profit', return_value=False) as compute:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(run, range(2)))
        assert compute.call_count == 2


@pytest.mark.parametrize('profitable', [False, True])
def test_real_paid_projections_reuse_baseline_and_keep_source_unchanged(profitable):
    state, _, held = fixture()
    friend = add_card(state, 'Sprite Dragon', Zone.BATTLEFIELD, 1)
    if profitable:
        add_canonical(state, 'Zulaport Cutthroat', 1)
        state.players[2].life = 1
    action = {'type': 'cast_spell', 'card_id': held, 'targets': {'target_card_id': friend.id}}
    before = serialize_match_snapshot(state)
    with patch.object(projections, '_friendly_destruction_profit', wraps=projections._friendly_destruction_profit) as compute:
        with projections.decision_projection_scope(state, 1):
            actual = projections.friendly_destruction_profit(state, 1, action)
            assert actual is profitable
            assert projections.friendly_destruction_profit(state, 1, action) is actual
        assert compute.call_count == 1
    assert serialize_match_snapshot(state) == before


def test_baseline_reuse_is_scalar_and_does_not_merge_candidate_actions():
    state, _, held = fixture()
    friends = [add_golden(state, 'Grizzly Bears', 1, Zone.BATTLEFIELD) for _ in range(2)]
    with patch.object(projections, '_destruction_baseline', wraps=projections._destruction_baseline) as baseline:
        with patch.object(projections, '_friendly_destruction_profit', wraps=projections._friendly_destruction_profit) as compute:
            with projections.decision_projection_scope(state, 1):
                for friend in friends:
                    assert projections.friendly_destruction_profit(state, 1,
                        {'type': 'cast_spell', 'card_id': held, 'targets': {'target_card_id': friend.id}}) is False
            assert compute.call_count == 2 and baseline.call_count == 1


def test_real_unresolved_order_stays_unknown_and_owned_choices_bypass_reuse():
    from ai.agent import AIAgent
    state, _, held = fixture()
    friends = [add_card(state, 'Sprite Dragon', Zone.BATTLEFIELD, 1) for _ in range(2)]
    action = {'type': 'cast_spell', 'card_id': held, 'targets': {'target_card_id': friends[0].id}}
    before = serialize_match_snapshot(state)
    with patch.object(projections, '_friendly_destruction_profit', wraps=projections._friendly_destruction_profit) as compute:
        with projections.decision_projection_scope(state, 1):
            assert projections.friendly_destruction_profit(state, 1, action) is None
            assert projections.friendly_destruction_profit(state, 1, action) is None
        assert compute.call_count == 1
    agent = AIAgent('master', 'Control')
    calls = []
    def choose(projected, moves, actor):
        calls.append(actor)
        return agent.choose_action(projected, moves, actor).action
    reference = projections.friendly_destruction_profit(state, 1, action, own_choice_action=choose)
    assert reference is not None
    calls.clear()
    with patch.object(projections, '_friendly_destruction_profit', wraps=projections._friendly_destruction_profit) as compute:
        with projections.decision_projection_scope(state, 1):
            for _ in range(2):
                assert projections.friendly_destruction_profit(state, 1, action, own_choice_action=choose) is reference
        assert compute.call_count == 2 and len(calls) >= 2
    assert serialize_match_snapshot(state) == before


def test_missing_policy_unknown_does_not_hide_a_later_owned_continuation():
    from ai.agent import AIAgent
    state, _, held = fixture()
    friends = [add_card(state, 'Sprite Dragon', Zone.BATTLEFIELD, 1) for _ in range(2)]
    action = {'type': 'cast_spell', 'card_id': held, 'targets': {'target_card_id': friends[0].id}}
    agent = AIAgent('master', 'Control')
    choose = lambda projected, moves, actor: agent.choose_action(projected, moves, actor).action
    reference = projections.friendly_destruction_profit(state, 1, action, own_choice_action=choose)
    assert reference is not None
    with projections.decision_projection_scope(state, 1):
        assert projections.friendly_destruction_profit(state, 1, action) is None
        assert projections.friendly_destruction_profit(state, 1, action, own_choice_action=choose) is reference
