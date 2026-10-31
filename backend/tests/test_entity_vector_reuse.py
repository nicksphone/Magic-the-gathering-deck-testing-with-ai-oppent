"""Exact entity embeddings only; synthetic weights, no native decisions."""
from contextlib import contextmanager
from copy import deepcopy
import random
import struct
import sys

import pytest

from ai import learned_qv as qv
from tests.test_learned_qv import blank_checkpoint, contract


def policy(life=False):
    rng = random.Random(81)
    activation = qv.LIFE_CONTEXT_ACTIVATION if life else qv.LEGACY_ACTIVATION
    weights = {name: ([[rng.uniform(-.003, .003) for _ in range(shape[1])]
                      for _ in range(shape[0])] if len(shape) == 2 else
                     [rng.uniform(-.003, .003) for _ in range(shape[0])])
               for name, shape in qv.parameter_shapes(activation).items()}
    expected = contract()
    if life:
        expected.update(decision_version='mtg.decision.v2', feature_version=qv.FEATURE_CONTEXT_VERSION,
                        feature_schema_sha256=qv.FEATURE_CONTEXT_SCHEMA_SHA256)
    raw = qv.checkpoint(weights, expected, blank_checkpoint(qv)['provenance'], activation=activation)
    return qv.QVPolicy(raw, expected=expected)


def text(value):
    return dict(kind='text', value=value)


def number(value):
    return dict(kind='number', value=value)


def ref(index):
    return dict(kind='ref', index=index)


def seq(*items):
    return dict(kind='list', items=list(items))


def mapping(**items):
    return dict(kind='map', items=[[text(k), v] for k, v in items.items()])


def pack(entities=None, *, life=False, root=None):
    if entities is None:
        entities = [seq(text('stable'), number(4)), seq(ref(0), text('dependent'))]
    payload = root if root is not None else seq(ref(len(entities)-1), number(11))
    if life:
        payload = mapping(observation=mapping(players=mapping(self=mapping(life=number(13)),
                          opponent=mapping(life=number(17)))), payload=payload)
    return dict(version=qv.FEATURE_CONTEXT_VERSION if life else qv.FEATURE_VERSION,
                entities=entities, root=payload)


def bits(result):
    return struct.pack('!dd', result['q'], result['v'])


@contextmanager
def fold_count():
    count = [0]
    previous = sys.getprofile()
    code = qv.QVPolicy._linear.__code__
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code is code and frame.f_locals['name'] == 'fold':
            count[0] += 1
    sys.setprofile(profile)
    try:
        yield count
    finally:
        sys.setprofile(previous)


@pytest.mark.parametrize('life', [False, True])
def test_changed_banks_renumbered_refs_reuse_entities_with_bit_exact_qv(life):
    owner = policy(life)
    first = pack(life=life)
    second = pack([number(83), deepcopy(first['entities'][0]), seq(ref(1), text('dependent'))], life=life)
    original = deepcopy([first, second])
    action = pack(life=life, root=number(19))
    expected = [bits(owner.prepare(state).predict(action)) for state in (first, second)]
    with qv._decision_encoder_scope(owner):
        owner.prepare(first)
        with fold_count() as warm:
            prepared = owner.prepare(second)
        actual = prepared.predict(action)
    with fold_count() as cold:
        owner.prepare(second)
    assert bits(actual) == expected[1]
    assert warm[0] < cold[0], 'No entity-vector reuse across different whole banks'
    assert [first, second] == original


@pytest.mark.parametrize('life', [False, True])
def test_changed_dependencies_and_order_never_false_hit(life):
    owner = policy(life)
    states = [pack(life=life)]
    states.append(pack([seq(text('changed'), number(-6)), seq(ref(0), text('dependent'))], life=life))
    states.append(pack([seq(number(4), text('stable')), seq(ref(0), text('dependent'))], life=life))
    states.append(pack([mapping(a=number(1), b=number(2)), seq(ref(0))], life=life))
    states.append(pack([mapping(b=number(2), a=number(1)), seq(ref(0))], life=life))
    expected = [bits(owner.prepare(state).predict(state)) for state in states]
    with qv._decision_encoder_scope(owner):
        actual = [bits(owner.prepare(state).predict(state)) for state in states]
    assert actual == expected
    assert len(set(expected)) > 1, 'Synthetic weights must expose changed dependencies'


def test_signed_zero_and_numeric_types_have_distinct_exact_structural_keys():
    owner = policy()
    with qv._decision_encoder_scope(owner):
        prepared = owner.prepare(pack([number(0.0), number(-0.0), number(0), number(1), number(1.0)]))
        nodes = prepared._cache.get('entity_nodes', {})
        numeric = [key for key in nodes if key[0] == 'number']
        assert len(numeric) == 5, 'Scalar keys must preserve type and float sign bits'


@pytest.mark.parametrize('bad', ['forward', 'root', 'number', 'extra', 'action'])
def test_warm_entity_hit_still_validates_every_feature(bad):
    owner = policy()
    state = pack()
    with qv._decision_encoder_scope(owner):
        prepared = owner.prepare(state)
        invalid = deepcopy(state)
        if bad == 'forward':
            invalid['entities'][0] = ref(1)
        elif bad == 'root':
            invalid['root'] = ref(99)
        elif bad == 'number':
            invalid['entities'][0] = number(float('nan'))
        elif bad == 'extra':
            invalid['entities'][0]['ignored'] = True
        else:
            invalid['entities'][1] = ref(1)
        before = deepcopy(prepared._cache)
        with pytest.raises(ValueError):
            prepared.predict(invalid) if bad == 'action' else owner.prepare(invalid)
        assert prepared._cache == before


def test_predict_copies_all_maps_and_does_not_leak_ids_or_embeddings():
    owner = policy()
    with qv._decision_encoder_scope(owner):
        prepared = owner.prepare(pack())
        assert 'entity_serial' in prepared._cache, 'No structural interner state'
        before = deepcopy(prepared._cache)
        action = pack([seq(text('action-only'), number(76)), seq(ref(0))])
        first = prepared.predict(action)
        second = prepared.predict(action)
        assert bits(first) == bits(second)
        assert prepared._cache == before
        assert all(type(value) is dict for value in prepared._cache.values())


def test_eviction_bounds_and_monotonic_ids_never_recycle(monkeypatch):
    owner = policy()
    monkeypatch.setattr(qv, '_ENTITY_KEY_LIMIT', 6, raising=False)
    monkeypatch.setattr(qv, '_ENTITY_VECTOR_LIMIT', 2, raising=False)
    with qv._decision_encoder_scope(owner):
        previous = 0
        old_ids = set()
        for i in range(5):
            state = pack([seq(text('new-' + str(i)), number(i)), seq(ref(0))])
            prepared = owner.prepare(state)
            cache = prepared._cache
            assert 'entity_serial' in cache, 'No monotonic ID state'
            assert len(cache['entity_nodes']) <= 6 and len(cache['entity_vectors']) <= 2
            assert cache['entity_serial']['next'] > previous
            current = set(cache['entity_nodes'].values())
            assert not (current - old_ids) or min(current - old_ids) > previous
            previous = cache['entity_serial']['next']
            old_ids |= current
        cache['entity_nodes'].clear()
        cache['entity_vectors'].clear()
        before = previous
        reused = owner.prepare(pack())
        assert min(reused._cache['entity_nodes'].values()) > before


def test_scope_none_and_other_policy_do_not_create_entity_cache():
    owner, other = policy(), policy()
    plain = owner.prepare(pack())
    assert set(plain._cache) == {'texts', 'banks'}
    with qv._decision_encoder_scope(owner):
        assert set(other.prepare(pack())._cache) == {'texts', 'banks'}
        scoped = owner.prepare(pack())
        assert 'entity_vectors' in scoped._cache
    later = owner.prepare(pack())
    assert set(later._cache) == {'texts', 'banks'}


def test_one_pack_may_exceed_retention_bound_and_still_compute_exactly(monkeypatch):
    owner = policy()
    monkeypatch.setattr(qv, '_ENTITY_KEY_LIMIT', 5, raising=False)
    monkeypatch.setattr(qv, '_ENTITY_VECTOR_LIMIT', 2, raising=False)
    state = pack([number(i) for i in range(12)])
    expected = bits(owner.prepare(state).predict(state))
    with qv._decision_encoder_scope(owner):
        prepared = owner.prepare(state)
        assert len(prepared._cache.get('entity_vectors', {})) <= 2
        assert len(prepared._cache.get('entity_nodes', {})) <= 5
        assert bits(prepared.predict(state)) == expected
