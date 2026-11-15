"""Synthetic checkpoint/inference protocols, never private rows or game weights."""
from copy import deepcopy
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from ai import learned_qv as codec
from tests.test_qv_life_context import contract, field, pack, payload as life_payload, state


ACTIVATION = 'relu-softsign-life-state-product'


def payload():
    raw = life_payload()
    raw['activation'] = ACTIVATION
    raw['weights']['q_interaction.weight'] = [[0.0] * 64]
    return raw


def test_explicit_activation_shape_and_checkpoint_roundtrip(tmp_path):
    raw = payload()
    assert codec.parameter_shapes(ACTIVATION) == {
        **codec.PARAMETERS, 'q_context.weight': (1, 192), 'q_interaction.weight': (1, 64)}
    made = codec.checkpoint(raw['weights'], contract(), raw['provenance'], activation=ACTIVATION)
    assert made == raw and made['version'] == 'mtg.qv.v2'
    policy = codec.QVPolicy(made, expected=contract())
    assert policy.payload() == raw
    path = tmp_path / 'synthetic.json'
    codec.save_checkpoint(path, raw)
    assert codec.load_checkpoint(path, expected=contract()).payload() == raw
    with pytest.raises(ValueError):
        codec.QVPolicy(raw, expected={**contract(), 'engine_hash': 'f' * 64})
    raw['weights']['q_interaction.weight'][0][0] = 5
    detached = policy.payload()
    detached['weights']['q_interaction.weight'][0][0] = 6
    assert made['weights']['q_interaction.weight'][0][0] == 0
    assert policy.payload()['weights']['q_interaction.weight'][0][0] == 0


@pytest.mark.parametrize('value', [[], [[]], [[0.] * 63], [[0.] * 65],
    [[0.] * 64] * 2, [0.] * 64, [[True] * 64], [['0'] * 64],
    [[float('nan')] * 64], [[float('inf')] * 64], [[101.] * 64]])
def test_malformed_interaction_shapes_and_numbers_rejected(value):
    raw = payload()
    raw['weights']['q_interaction.weight'] = value
    with pytest.raises(ValueError):
        codec.QVPolicy(raw, expected=contract())


@pytest.mark.parametrize('change', ['missing-interaction', 'missing-context', 'interaction-bias',
    'context-bias', 'extra', 'legacy-family', 'life-family', 'v1-version', 'future-version',
    'future-activation', 'non-string-activation', 'v1-contract', 'future-schema',
    'missing-provenance', 'extra-provenance', 'bad-provenance'])
def test_cross_family_parameters_and_provenance_fail_closed(change):
    raw = payload()
    if change.startswith('missing-') and change != 'missing-provenance':
        del raw['weights']['q_' + change.removeprefix('missing-') + '.weight']
    elif change in ('interaction-bias', 'context-bias'):
        raw['weights']['q_' + change.removesuffix('-bias') + '.bias'] = [0.]
    elif change == 'extra':
        raw['weights']['future.weight'] = [[0.]]
    elif change == 'legacy-family':
        raw.update(activation=codec.LEGACY_ACTIVATION, version=codec.VERSION)
    elif change == 'life-family':
        raw['activation'] = codec.LIFE_CONTEXT_ACTIVATION
    elif change == 'v1-version':
        raw['version'] = codec.VERSION
    elif change == 'future-version':
        raw['version'] = 'mtg.qv.v3'
    elif change == 'future-activation':
        raw['activation'] = 'relu-softsign-future'
    elif change == 'non-string-activation':
        raw['activation'] = [ACTIVATION]
    elif change == 'v1-contract':
        raw['contract'].update(feature_version=codec.FEATURE_VERSION,
            decision_version='mtg.decision.v1', feature_schema_sha256=codec.FEATURE_SCHEMA_SHA256)
    elif change == 'future-schema':
        raw['contract']['feature_schema_sha256'] = 'f' * 64
    elif change == 'missing-provenance':
        del raw['provenance']['dataset_sha256']
    elif change == 'extra-provenance':
        raw['provenance']['source'] = 'unverified'
    else:
        raw['provenance']['dataset_sha256'] = 'invalid'
    with pytest.raises(ValueError):
        codec.QVPolicy(raw, expected=raw['contract'])


@pytest.mark.parametrize('old', [False, True])
def test_no_implicit_old_checkpoint_migration(old):
    raw = life_payload(old)
    raw.update(activation=ACTIVATION, version='mtg.qv.v2')
    with pytest.raises(ValueError):
        codec.QVPolicy(raw, expected=contract())


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'bool', 'text', 'nonfinite'])
def test_new_activation_keeps_strict_authorized_life_context(change):
    policy = codec.QVPolicy(payload(), expected=contract())
    value = state()
    parent = field(value, 'observation', 'players', 'self')
    if change == 'missing':
        parent['items'].clear()
    elif change == 'duplicate':
        parent['items'].append(deepcopy(parent['items'][0]))
    else:
        parent['items'][0][1] = {'kind': 'bool' if change == 'bool' else
            'text' if change == 'text' else 'number', 'value': True if change == 'bool' else
            '20' if change == 'text' else float('inf')}
    with pytest.raises(ValueError):
        policy.prepare(value)


def test_product_is_added_to_existing_life_head_before_softsign_and_prepare_is_pure():
    raw = payload()
    weights = raw['weights']
    weights['kind.weight'][codec.KINDS.index('map')][0] = 3
    weights['kind.weight'][codec.KINDS.index('number')][0] = 2
    weights['q_out.bias'][0] = 1
    weights['v_out.bias'][0] = .5
    weights['q_context.weight'][0][0] = .5
    weights['q_context.weight'][0][64] = 1
    weights['q_context.weight'][0][128] = -.25
    weights['q_interaction.weight'][0][0] = .25
    policy = codec.QVPolicy(raw, expected=contract())
    value, action = state(10, 40), pack(7)
    before = deepcopy((value, action, raw))
    prepared = policy.prepare(value)
    cache = deepcopy(prepared._cache)
    # raw Q = 1 + 2*(.5 + .5 - .25*2) + .25*3*2 = 3.5.
    expected = {'q': 7 / 9, 'v': math.tanh(.5)}
    assert prepared.predict(action) == expected
    assert prepared.predict(action) == policy.predict(value, action)
    assert (value, action, raw) == before and prepared._cache == cache
    field(value, 'observation', 'players', 'self', 'life')['value'] = 99
    assert prepared.predict(action) == expected and prepared._cache == cache
    bad = deepcopy(action)
    bad['version'] = codec.FEATURE_VERSION
    with pytest.raises(ValueError):
        prepared.predict(bad)


def large_interaction_case(weight=0.):
    raw, value = payload(), state()
    raw['weights']['kind.weight'][codec.KINDS.index('list')][0] = 1
    raw['weights']['fold.weight'][0][0] = 100
    raw['weights']['fold.weight'][0][64] = 100
    raw['weights']['q_out.bias'][0] = 1
    raw['weights']['q_interaction.weight'][0][0] = weight
    action = {'version': codec.FEATURE_CONTEXT_VERSION, 'entities': [],
              'root': {'kind': 'list', 'items': [{'kind': 'null'} for _ in range(80)]}}
    value['root']['items'].append([pack('synthetic-large-list')['root'], deepcopy(action['root'])])
    return raw, value, action


@pytest.mark.parametrize('weight,expected', [(0., .5), (1e-160, 1.)])
def test_finite_large_embeddings_do_not_overflow_before_interaction_weight(weight, expected):
    raw, value, action = large_interaction_case(weight)
    before = deepcopy((raw, value, action))
    policy = codec.QVPolicy(raw, expected=contract())
    prepared = policy.prepare(value)
    a = policy._encode(action, {})
    assert all(math.isfinite(x) for x in [*prepared._state, *a])
    assert math.isinf(prepared._state[0] * a[0])
    cache = deepcopy(prepared._cache)
    assert prepared.predict(action) == {'q': expected, 'v': 0.}
    assert policy.predict(value, action) == {'q': expected, 'v': 0.}
    if weight == 0:
        old = deepcopy(raw)
        old['activation'] = codec.LIFE_CONTEXT_ACTIVATION
        del old['weights']['q_interaction.weight']
        assert codec.QVPolicy(old, expected=contract()).predict(value, action) == prepared.predict(action)
    assert (raw, value, action) == before and prepared._cache == cache


def test_truly_nonfinite_interaction_is_still_rejected():
    raw, value, action = large_interaction_case(1.)
    with pytest.raises(ValueError):
        codec.QVPolicy(raw, expected=contract()).predict(value, action)


def test_inference_and_new_checkpoint_do_not_import_torch():
    # A fresh interpreter catches imports hidden by the training test process.
    code = '''
import builtins, json, sys
original = builtins.__import__
def importing(name, *args, **kwargs):
    assert name.split('.')[0] != 'torch', 'Runtime inference imported Torch'
    return original(name, *args, **kwargs)
builtins.__import__ = importing
from ai.learned_qv import QVPolicy
raw, state, action = json.load(sys.stdin)
policy = QVPolicy(raw, expected=raw['contract'])
assert policy.predict(state, action) == {'q': 0., 'v': 0.}
assert policy.prepare(state).predict(action) == {'q': 0., 'v': 0.}
assert 'torch' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', code],
        input=json.dumps([payload(), state(), pack(1)]),
        cwd=Path(codec.__file__).resolve().parents[1], text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
