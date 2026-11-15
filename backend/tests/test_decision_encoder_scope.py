"""Decision-local deterministic embedding reuse; synthetic protocol weights only."""
from collections import Counter
from contextlib import nullcontext
from contextvars import Context, copy_context
from copy import deepcopy
import random
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from ai import agent as a, learned_policy as lp, learned_qv as qv
from tests.test_learned_qv import blank_checkpoint, contract


def policy(seed=7, life=False):
    raw = blank_checkpoint(qv)
    rng = random.Random(seed)
    weights = {}
    for name, shape in qv.parameter_shapes(qv.LIFE_CONTEXT_ACTIVATION if life else qv.LEGACY_ACTIVATION).items():
        weights[name] = ([[rng.uniform(-.001, .001) for _ in range(shape[1])] for _ in range(shape[0])]
                         if len(shape) == 2 else [rng.uniform(-.001, .001) for _ in range(shape[0])])
    expected = contract()
    if life:
        expected.update(decision_version='mtg.decision.v2', feature_version=qv.FEATURE_CONTEXT_VERSION,
                        feature_schema_sha256=qv.FEATURE_CONTEXT_SCHEMA_SHA256)
    raw = qv.checkpoint(weights, expected, raw['provenance'],
                        activation=qv.LIFE_CONTEXT_ACTIVATION if life else qv.LEGACY_ACTIVATION)
    return qv.QVPolicy(raw, expected=expected)


def text(value):
    return {'kind': 'text', 'value': value}


def number(value):
    return {'kind': 'number', 'value': value}


def mapping(**fields):
    return {'kind': 'map', 'items': [[text(k), v] for k, v in fields.items()]}


def pack(root_value=1, entity='public entity', *, life=False):
    entities = [mapping(name=text(entity), values={'kind': 'list', 'items': [number(2), text('stable text')]}),
                {'kind': 'list', 'items': [{'kind': 'ref', 'index': 0}, text('second entity')]}]
    root = {'kind': 'list', 'items': [{'kind': 'ref', 'index': 1}, number(root_value)]}
    if life:
        root = mapping(observation=mapping(players=mapping(self=mapping(life=number(13)),
                       opponent=mapping(life=number(17)))), payload=root)
    return {'version': qv.FEATURE_CONTEXT_VERSION if life else qv.FEATURE_VERSION,
            'entities': entities, 'root': root}


def scope(owner, agent=None, actor=None):
    # Makes the original implementation reach the causal RED assertion.
    return getattr(qv, '_decision_encoder_scope', lambda *_: nullcontext())(owner, agent, actor)


def entry():
    assert hasattr(qv, '_encoder_state'), 'Missing private encoder scope'
    return qv._encoder_state.get()


def bits(result):
    return struct.pack('!dd', result['q'], result['v'])


def counted(function):
    calls = Counter()
    code = qv.QVPolicy._linear.__code__
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            calls[frame.f_locals['name']] += 1
    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        result = function()
    finally:
        sys.setprofile(previous)
    return result, calls


@pytest.mark.parametrize('life', [False, True])
def test_repeated_entities_reduce_native_linear_calls_with_bit_exact_qv(life):
    owner = policy(life=life)
    state, action = pack(life=life), pack(4, life=life)
    baseline, _ = counted(lambda: owner.prepare(state).predict(action))
    with scope(owner):
        first, first_calls = counted(lambda: owner.prepare(state).predict(action))
        second, second_calls = counted(lambda: owner.prepare(deepcopy(state)).predict(deepcopy(action)))
    assert bits(first) == bits(second) == bits(baseline)
    assert second_calls['text'] + second_calls['fold'] < first_calls['text'] + first_calls['fold']
    assert second_calls['v_hidden'] == second_calls['v_out'] == 1


def test_changed_entity_root_and_references_match_uncached_results():
    owner = policy()
    states = [pack(), pack(9), pack(3, 'different entity')]
    states.append(deepcopy(states[0])); states[-1]['root']['items'][0]['index'] = 0
    expected = [bits(owner.prepare(state).predict(pack(6))) for state in states]
    with scope(owner):
        actual = [bits(owner.prepare(state).predict(pack(6))) for state in states]
    assert actual == expected


@pytest.mark.parametrize('bad', ['state-ref', 'entity-ref', 'action-ref', 'version'])
def test_cache_hit_never_bypasses_feature_validation(bad):
    owner = policy()
    state = pack()
    with scope(owner):
        prepared = owner.prepare(state)
        invalid = deepcopy(state)
        if bad == 'entity-ref':
            invalid['entities'][0] = {'kind': 'ref', 'index': 0}
        elif bad == 'version':
            invalid['version'] = 'invalid'
        else:
            invalid['root'] = {'kind': 'ref', 'index': 99}
        with pytest.raises(ValueError):
            prepared.predict(invalid) if bad == 'action-ref' else owner.prepare(invalid)


def test_other_policy_identity_never_uses_active_cache():
    first, other = policy(1), policy(2)
    expected = bits(other.prepare(pack()).predict(pack(5)))
    with scope(first):
        cached = first.prepare(pack())
        separate = other.prepare(pack())
        assert separate._cache is not cached._cache
        assert bits(separate.predict(pack(5))) == expected
        with scope(other):
            assert other.prepare(pack())._cache is not cached._cache
        assert first.prepare(pack())._cache is cached._cache


def test_nested_foreign_and_exception_scopes_restore_without_public_call_leak():
    owner = policy()
    assert entry() is None
    with scope(owner):
        first = owner.prepare(pack())
        with scope(owner):
            assert owner.prepare(pack())._cache is not first._cache
        try:
            with scope(None):
                assert entry() is None
                assert owner.prepare(pack())._cache is not first._cache
                raise LookupError('same exception')
        except LookupError:
            pass
        assert owner.prepare(pack())._cache is first._cache
    assert entry() is None
    with scope(owner):
        assert owner.prepare(pack())._cache is not first._cache


def test_retired_copied_context_cannot_reuse_completed_decision_cache():
    owner = policy()
    with scope(owner):
        prepared = owner.prepare(pack())
        copied = copy_context()
    outside = copied.run(lambda: owner.prepare(pack()))
    assert outside._cache is not prepared._cache


def test_concurrent_inherited_contexts_have_independent_caches():
    owner = policy()
    barrier = Barrier(2)
    with scope(owner):
        parent = owner.prepare(pack())
        contexts = [copy_context(), copy_context()]
        def worker(context):
            def run():
                with scope(owner):
                    local = owner.prepare(pack())
                    barrier.wait(timeout=10)
                    return local._cache
            return context.run(run)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, contexts))
        assert results[0] is not results[1]
        assert all(cache is not parent._cache for cache in results)
    assert entry() is None


def test_eviction_bounds_preserve_recomputed_results():
    owner = policy()
    expected = bits(owner.prepare(pack()).predict(pack(7)))
    with scope(owner):
        for index in range(7):
            prepared = owner.prepare(pack(index, f'bank-{index}'))
            assert len(prepared._cache.get('banks', {})) <= 4
            assert len(prepared._cache.get('texts', {})) <= 1024
        assert bits(owner.prepare(pack()).predict(pack(7))) == expected
    assert entry() is None


def test_large_single_pack_text_cache_is_bounded_between_prepares():
    owner = policy()
    state = {'version': qv.FEATURE_VERSION, 'entities': [
        {'kind': 'list', 'items': [text(f'unique text {i}') for i in range(1030)]}],
        'root': {'kind': 'ref', 'index': 0}}
    expected = bits(owner.prepare(state).predict(pack()))
    with scope(owner):
        prepared = owner.prepare(state)
        assert len(prepared._cache.get('texts', {})) <= 1024
        assert len(prepared._cache.get('banks', {})) <= 4
        assert bits(prepared.predict(pack())) == expected


def test_payload_export_mutation_does_not_change_trusted_policy_or_cache():
    owner = policy()
    with scope(owner):
        expected = bits(owner.prepare(pack()).predict(pack(3)))
        exported = owner.payload()
        exported['weights']['text.bias'][0] += .5
        assert bits(owner.prepare(pack()).predict(pack(3))) == expected


@pytest.mark.parametrize('foreign', ['native', 'subclass', 'provider-override'])
def test_agent_boundary_shares_only_native_provider_and_masks_foreign(monkeypatch, foreign):
    from tests.test_ai_information_boundary import bare_state
    provider = policy()
    binding = lp.LivePolicyBinding(provider, '0' * 64, ())
    cls = a.AIAgent
    if foreign == 'subclass':
        class Child(a.AIAgent):
            pass
        cls = Child
    if foreign == 'provider-override':
        provider.prepare = lambda state: qv.QVDecision(provider, state)
    owner = cls('master', learned_binding=binding)
    seen = []
    def choice(bound, agent, view, supplied, seat, *, admit, _terminal_win=None):
        active = entry()
        seen.append(active is not None)
        one, two = provider.prepare(pack()), provider.prepare(pack())
        assert (one._cache is two._cache) is (foreign == 'native')
        _terminal_win.append(True)
        return {'type': 'pass_priority'}
    monkeypatch.setattr(lp, 'choose_learned_action', choice)
    with scope(provider):
        outer = entry()
        owner.choose_action(bare_state(1), [{'type': 'pass_priority'}], 1)
        assert entry() is outer
    assert seen == [foreign == 'native']
    assert entry() is None


def test_only_registered_native_forecasts_join_same_actor_scope(monkeypatch):
    from tests.test_ai_information_boundary import bare_state
    provider = policy()
    binding = lp.LivePolicyBinding(provider, '0' * 64, ())
    root, unrelated = a.AIAgent('master', learned_binding=binding), a.AIAgent('master', learned_binding=binding)
    phase, observed = [], []
    def invoke(owner, actor, label):
        phase.append(label)
        try:
            owner.choose_action(bare_state(actor), [{'type': 'pass_priority'}], actor)
        finally:
            phase.pop()
    root_cache = []
    def choice(bound, owner, view, supplied, actor, *, admit, _terminal_win=None):
        cache = provider.prepare(pack())._cache
        if not phase:
            root_cache.append(cache)
            child = a._native_planner_snapshot(root)()
            invoke(child, 1, 'approved')
            invoke(child, 1, 'sequential approved')
            invoke(unrelated, 1, 'unrelated')
            invoke(root, 1, 'reentrant root')
            invoke(child, 2, 'other actor')
            assert provider.prepare(pack())._cache is cache
        else:
            observed.append((phase[-1], cache is root_cache[0]))
        _terminal_win.append(True)
        return {'type': 'pass_priority'}
    monkeypatch.setattr(lp, 'choose_learned_action', choice)
    root.choose_action(bare_state(1), [{'type': 'pass_priority'}], 1)
    assert observed == [('approved', True), ('sequential approved', True),
                        ('unrelated', False), ('reentrant root', False), ('other actor', False)]
    assert entry() is None


def test_foreign_agent_masks_encoder_before_decision_view(monkeypatch):
    from ai import information
    from tests.test_ai_information_boundary import bare_state
    provider = policy()
    class Foreign(a.AIAgent):
        pass
    owner = Foreign('master', learned_binding=lp.LivePolicyBinding(provider, '0' * 64, ()))
    original_view = information.decision_view
    seen = []
    def view(*args):
        seen.append(entry())
        assert entry() is None
        return original_view(*args)
    def choice(*args, _terminal_win=None, **kwargs):
        _terminal_win.append(True)
        return {'type': 'pass_priority'}
    monkeypatch.setattr(information, 'decision_view', view)
    monkeypatch.setattr(lp, 'choose_learned_action', choice)
    with scope(provider):
        outer = entry()
        owner.choose_action(bare_state(1), [{'type': 'pass_priority'}], 1)
        assert entry() is outer
    assert seen == [None]


def test_foreign_and_retired_factory_registration_cannot_admit_children():
    provider = policy()
    owner = a.AIAgent('master', learned_binding=lp.LivePolicyBinding(provider, '0' * 64, ()))
    with scope(provider, owner, 1):
        root_cache = provider.prepare(pack())._cache
        factory = a._native_planner_snapshot(owner)
        with scope(None):
            foreign_child = factory()
        with scope(provider, foreign_child, 1):
            assert provider.prepare(pack())._cache is not root_cache
    retired_child = factory()
    with scope(provider, owner, 1):
        current = provider.prepare(pack())._cache
        with scope(provider, retired_child, 1):
            assert provider.prepare(pack())._cache is not current


def test_inherited_thread_cannot_register_child_into_parent_scope():
    provider = policy()
    owner = a.AIAgent('master', learned_binding=lp.LivePolicyBinding(provider, '0' * 64, ()))
    with scope(provider, owner, 1):
        root_cache = provider.prepare(pack())._cache
        factory, context = a._native_planner_snapshot(owner), copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            child = pool.submit(context.run, factory).result(timeout=10)
        assert id(child) not in entry()['approved']
        with scope(provider, child, 1):
            assert provider.prepare(pack())._cache is not root_cache


@pytest.mark.parametrize('nested', ['unrelated', 'opposite-actor'])
def test_projection_deepcopy_callback_cannot_receive_parent_cache(nested, monkeypatch):
    from tests.test_ai_information_boundary import bare_state
    provider = policy()
    binding = lp.LivePolicyBinding(provider, '0' * 64, ())
    parent = a.AIAgent('master', learned_binding=binding)
    observed = []
    class ProjectionProbe:
        def __deepcopy__(self, memo):
            observed.append(provider.prepare(pack())._cache)
            return 'projection probe copied'
    def choice(*args, _terminal_win=None, **kwargs):
        _terminal_win.append(True)
        return {'type': 'pass_priority'}
    monkeypatch.setattr(lp, 'choose_learned_action', choice)
    with scope(provider, parent, 1):
        parent_cache = provider.prepare(pack())._cache
        owner = (a.AIAgent('master', learned_binding=binding) if nested == 'unrelated'
                 else a._native_planner_snapshot(parent)())
        actor = 1 if nested == 'unrelated' else 2
        state = bare_state(actor)
        state.starting_decks = {actor: [{'probe': ProjectionProbe()}]}
        owner.choose_action(state, [{'type': 'pass_priority'}], actor)
        assert len(observed) == 1 and observed[0] is not parent_cache
        assert provider.prepare(pack())._cache is parent_cache
    assert entry() is None
