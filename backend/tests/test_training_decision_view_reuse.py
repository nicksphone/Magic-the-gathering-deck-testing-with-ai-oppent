"""Collector equivalence and real view counts on existing canonical roots."""
from copy import deepcopy
import socket
import sqlite3

import pytest

from rules_engine.action_validation import ActionRejected
from game_state.state import Zone
from tests.test_training_environment import cast, env, position, resolve
from training import TrainingEnvironment
from training import environment as adapter
from training.dataset import canonical, episode_records


class LegacyProxy:
    """Exercise the supported public-method path without replacing its outputs."""

    def __init__(self, environment):
        self.environment = environment

    def __getattr__(self, name):
        return getattr(self.environment, name)


@pytest.fixture(autouse=True)
def no_sql_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('SQL/network is forbidden in collector regressions')

    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)


def root(kind, seat):
    if kind in {'pregame', 'mulligan'}:
        environment = env()
        if kind == 'mulligan':
            environment.step({'type': 'mulligan'})
            environment.step({'type': 'mulligan'})
            if seat == 2:
                options = environment.prompts()[0]['hint']['options']
                environment.step({'type': 'choose_mechanic', 'card_ids': options[-1:]})
            options = environment.prompts()[0]['hint']['options']
            action = {'type': 'choose_mechanic', 'card_ids': options[-1:]}
        else:
            if seat == 2:
                environment.step({'type': 'keep_hand'})
            action = {'type': 'keep_hand'}
    else:
        environment, cid = position(seat, 'Consider' if kind == 'surveil' else 'Lightning Bolt')
        action = cast(environment, cid, **({} if kind == 'surveil' else {'target_player': 3-seat}))
        if kind in {'stack', 'surveil'}:
            environment.step(action)
            if kind == 'surveil':
                resolve(environment)
                options = environment.prompts()[0]['hint']['options']
                action = {'type': 'choose_mechanic', 'card_ids': options}
            else:
                action = {'type': 'pass_priority'}
    assert environment.acting_seat == seat
    environment.lookup(action, seat)
    return environment, action


def collect(environment, teacher, **kwargs):
    return list(episode_records(environment, teacher, episode='episode-0000',
                               groups=['family:' + 'a' * 64], tick_budget=1, **kwargs))


def jsonl(rows):
    return ''.join(canonical(row) + '\n' for row in rows).encode('ascii')


@pytest.mark.parametrize('kind', ['pregame', 'mulligan', 'cast', 'stack', 'surveil'])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize(('decision_frame', 'public_context'), [(False, False), (True, False), (True, True)])
def test_real_views_and_root_clones_reduced_with_exact_legacy_bytes(
        monkeypatch, kind, seat, decision_frame, public_context):
    environment, action = root(kind, seat)
    before = environment.snapshot()
    legacy = TrainingEnvironment()
    legacy.restore(before)
    flags = dict(decision_frame=decision_frame, public_context=public_context)
    expected = collect(LegacyProxy(legacy), lambda current: deepcopy(action), **flags)
    counts = {'views': 0, 'root_clones': 0}
    original_view, original_copy = adapter.decision_view, adapter.deepcopy

    def counted_view(*args, **kwargs):
        counts['views'] += 1
        return original_view(*args, **kwargs)

    def counted_copy(value, *args, **kwargs):
        if value is environment._state:
            counts['root_clones'] += 1
        return original_copy(value, *args, **kwargs)

    monkeypatch.setattr(adapter, 'decision_view', counted_view)
    monkeypatch.setattr(adapter, 'deepcopy', counted_copy)
    at_teacher = []

    def choose(current):
        assert current is environment
        assert current.snapshot() == before
        at_teacher.append(dict(counts))
        return deepcopy(action)

    actual = collect(environment, choose, **flags)
    assert len(actual) == 3 and actual[1]['kind'] == 'transition'
    assert actual == expected
    assert jsonl(actual) == jsonl(expected)
    assert environment.snapshot() == legacy.snapshot()
    assert at_teacher == [{'views': 1, 'root_clones': 1}]


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_identity_and_private_pending_choices_do_not_cross_frames(seat):
    environment, action = root('surveil', seat)
    changed = TrainingEnvironment()
    changed.restore(environment.snapshot())
    state = changed._state
    visible = set(environment.observe(seat)['known_cards'])
    opponent = state.players[3-seat]
    a, b = opponent.hand[0], opponent.library[-1]
    opponent.hand[0], opponent.library[-1] = b, a
    state.cards[a].move_to_zone(Zone.LIBRARY)
    state.cards[b].move_to_zone(Zone.HAND)
    for ids in (opponent.hand, state.players[1].library, state.players[2].library):
        hidden = [cid for cid in ids if cid not in visible]
        assert len(hidden) >= 2
        a, b = hidden[:2]
        # Keep the actor's explicitly inspected top card in its actual position.
        ia, ib = ids.index(a), ids.index(b)
        ids[ia], ids[ib] = ids[ib], ids[ia]
    state.rng.random()
    state.log.append('PRIVATE replay detail')
    options = environment.prompts()[0]['hint']['options']
    other = environment.observe(3-seat)
    assert not set(options).intersection(other['known_cards'])
    assert not other['pending_choice'] or 'prompts' not in other['pending_choice']
    before = [current.snapshot() for current in (environment, changed)]

    def choose(current):
        assert current.snapshot() == before[0 if current is environment else 1]
        return deepcopy(action)

    first = collect(environment, choose, decision_frame=True, public_context=True)
    second = collect(changed, choose, decision_frame=True, public_context=True)
    assert first[1]['kind'] == second[1]['kind'] == 'transition'
    assert jsonl(first) == jsonl(second)
    assert 'PRIVATE' not in canonical(first)


@pytest.mark.parametrize('wrapper', ['subclass', 'proxy', 'instance'])
@pytest.mark.parametrize('method', ['observe', 'prompts', 'decision_context'])
def test_custom_public_methods_are_not_bypassed(wrapper, method):
    original, action = root('pregame', 1)
    calls = []
    base = getattr(TrainingEnvironment, method)

    def customized(self, seat):
        calls.append(method)
        value = base(self, seat)
        if method == 'observe':
            value['turn'] += 1000
        return value

    if wrapper == 'subclass':
        class CustomEnvironment(TrainingEnvironment):
            pass
        setattr(CustomEnvironment, method, customized)
        environment = CustomEnvironment()
        environment.restore(original.snapshot())
    elif wrapper == 'proxy':
        class CustomProxy(LegacyProxy):
            pass
        setattr(CustomProxy, method, lambda self, seat: customized(self.environment, seat))
        environment = CustomProxy(original)
    else:
        environment = original
        setattr(environment, method, lambda seat: customized(environment, seat))
    calls.clear()
    rows = collect(environment, lambda current: deepcopy(action), decision_frame=True, public_context=True)
    assert rows[1]['kind'] == 'transition'
    assert method in calls
    if method == 'observe':
        assert rows[1]['input']['observation']['turn'] == 1001


@pytest.mark.parametrize('public_context', [False, True])
@pytest.mark.parametrize('outcome', ['error', 'interrupt', 'reject', 'cancel_before', 'cancel_teacher', 'cancel_lookup'])
def test_teacher_failures_and_cancellation_retain_legacy_bytes(public_context, outcome):
    original, action = root('pregame', 1)
    before = original.snapshot()

    def run(use_proxy):
        environment = TrainingEnvironment()
        environment.restore(before)
        stopped = outcome == 'cancel_before'

        def choose(current):
            nonlocal stopped
            if outcome == 'error':
                raise RuntimeError('PRIVATE teacher failure')
            if outcome == 'interrupt':
                raise KeyboardInterrupt()
            if outcome == 'reject':
                raise ActionRejected('PRIVATE rejected proposal')
            stopped = outcome == 'cancel_teacher'
            return deepcopy(action)

        if outcome == 'cancel_lookup':
            original_lookup = environment.lookup

            def lookup(*args, **kwargs):
                nonlocal stopped
                result = original_lookup(*args, **kwargs)
                stopped = True
                return result

            environment.lookup = lookup
        rows = collect(LegacyProxy(environment) if use_proxy else environment, choose,
                       decision_frame=True, public_context=public_context, cancelled=lambda: stopped)
        assert environment.snapshot() == before
        assert len(rows) == 2 and rows[-1]['steps'] == 0
        expected = {'error': 'teacher_or_engine_error', 'interrupt': 'interrupted', 'reject': 'rejected_action'}
        assert rows[-1]['reason'] == expected.get(outcome, 'cancelled')
        assert 'PRIVATE' not in canonical(rows)
        return rows

    assert jsonl(run(False)) == jsonl(run(True))
