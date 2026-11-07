"""Synthetic typed-tree protocols only, not archived game rows or policy evidence."""
from copy import deepcopy
import inspect
import math

import pytest

from ai import learned_qv as codec
from scripts import train_qv, train_qv_preferences


ACTIVATION = 'relu-softsign-life-context'


def contract():
    return {'decision_version': 'mtg.decision.v2',
            'feature_version': codec.FEATURE_CONTEXT_VERSION,
            'feature_schema_sha256': codec.FEATURE_CONTEXT_SCHEMA_SHA256,
            'dataset_version': 'mtg.dataset.v2', 'action_version': 'mtg.action.v1:',
            'engine_hash': 'a' * 64}


def node(value):
    if type(value) is dict:
        return {'kind': 'map', 'items': [[node(k), node(v)] for k, v in value.items()]}
    return {'kind': 'text' if type(value) is str else 'number', 'value': value}


def pack(value):
    return {'version': codec.FEATURE_CONTEXT_VERSION, 'entities': [], 'root': node(value)}


def state(own=20, opposing=20):
    return pack({'observation': {'players': {'self': {'life': own},
                                           'opponent': {'life': opposing}}}})


def field(value, *keys):
    result = value['root']
    for key in keys:
        result = next(v for k, v in result['items'] if k['value'] == key)
    return result


def weights(context=False):
    result = {key: ([[0.0] * shape[1] for _ in range(shape[0])]
                    if len(shape) == 2 else [0.0] * shape[0])
              for key, shape in codec.PARAMETERS.items()}
    if context:
        result['q_context.weight'] = [[0.0] * 192]
    return result


def payload(context=True):
    kwargs = {'activation': ACTIVATION} if context else {}
    return codec.checkpoint(weights(context), contract(), {
        'dataset_sha256': 'b' * 64, 'split_sha256': 'c' * 64,
        'trainer_sha256': 'd' * 64, 'torch_version': '0+synthetic',
        'trainer_seed': 17, 'updates': 0, 'samples': 0}, **kwargs)


def test_defaults_remain_legacy_and_legacy_v1_v2_roundtrip(tmp_path):
    for fn in (codec.checkpoint,):
        assert inspect.signature(fn).parameters['activation'].default == 'relu-tanh'
    for fn in (train_qv.torch_model, train_qv.train_samples,
               train_qv_preferences.train_preferences):
        assert inspect.signature(fn).parameters['q_activation'].default == 'relu-tanh'
    assert inspect.signature(train_qv_preferences.train_preferences).parameters['batch_size'].default == 1
    for version in (codec.FEATURE_VERSION, codec.FEATURE_CONTEXT_VERSION):
        raw = payload(False)
        decision, schema = codec.FEATURE_CONTRACTS[version]
        raw['contract'].update(feature_version=version, decision_version=decision,
                               feature_schema_sha256=schema)
        raw['weights']['q_out.bias'][0] = 22
        raw['weights']['v_out.bias'][0] = -.7
        policy = codec.QVPolicy(raw, expected=raw['contract'])
        tree = {**pack(1), 'version': version}
        assert policy.predict(tree, tree) == {'q': math.tanh(22), 'v': math.tanh(-.7)}
        assert policy.payload() == raw and raw['version'] == 'mtg.qv.v1'
        path = tmp_path / (version + '.json')
        codec.save_checkpoint(path, raw)
        assert codec.load_checkpoint(path, expected=raw['contract']).payload() == raw


def test_new_closed_discriminator_shape_roundtrip_and_expected_engine(tmp_path):
    raw = payload()
    assert (raw['version'], raw['activation']) == ('mtg.qv.v2', ACTIVATION)
    assert set(raw['weights']) == {*codec.PARAMETERS, 'q_context.weight'}
    assert len(raw['weights']['q_context.weight'][0]) == 192
    policy = codec.QVPolicy(raw, expected=contract())
    assert policy.payload() == raw  # Constructor must not silently retag to v1.
    path = tmp_path / 'synthetic.json'
    codec.save_checkpoint(path, raw)
    assert codec.load_checkpoint(path, expected=contract()).payload() == raw
    with pytest.raises(ValueError):
        codec.QVPolicy(raw, expected={**contract(), 'engine_hash': 'f' * 64})


@pytest.mark.parametrize('change', ['old-version', 'old-activation', 'unknown-version',
    'unknown-activation', 'missing-context', 'context-bias', 'shape', 'extra',
    'legacy-retag', 'legacy-extra', 'context-bool', 'context-nonfinite', 'feature-v1'])
def test_mixed_old_retag_and_wrong_parameter_sets_fail_closed(change):
    raw = payload()
    if change == 'old-version':
        raw['version'] = 'mtg.qv.v1'
    elif change == 'old-activation':
        raw['activation'] = 'relu-tanh'
    elif change == 'unknown-version':
        raw['version'] = 'mtg.qv.future'
    elif change == 'unknown-activation':
        raw['activation'] = 'softsign'
    elif change == 'missing-context':
        del raw['weights']['q_context.weight']
    elif change == 'context-bias':
        raw['weights']['q_context.bias'] = [0.0]
    elif change == 'shape':
        raw['weights']['q_context.weight'][0].pop()
    elif change == 'extra':
        raw['weights']['product.weight'] = [[0.0]]
    elif change == 'legacy-retag':
        raw = payload(False)
        raw.update(version='mtg.qv.v2', activation=ACTIVATION)
    elif change == 'legacy-extra':
        raw.update(version='mtg.qv.v1', activation='relu-tanh')
    elif change in ('context-bool', 'context-nonfinite'):
        raw['weights']['q_context.weight'][0][0] = True if change == 'context-bool' else float('inf')
    else:
        raw['contract'].update(feature_version=codec.FEATURE_VERSION,
                              decision_version='mtg.decision.v1',
                              feature_schema_sha256=codec.FEATURE_SCHEMA_SHA256)
    with pytest.raises(ValueError):
        codec.QVPolicy(raw, expected=raw['contract'])


@pytest.mark.parametrize('path', [(), ('observation',), ('observation', 'players'),
    ('observation', 'players', 'self'), ('observation', 'players', 'opponent')])
@pytest.mark.parametrize('change', ['duplicate', 'missing', 'non-text-key'])
def test_each_authorized_life_path_key_must_be_unique_and_present(path, change):
    value = state()
    parent = field(value, *path)
    if change == 'duplicate':
        parent['items'].append(deepcopy(parent['items'][0]))
    elif change == 'missing':
        parent['items'].pop(0)
    else:
        parent['items'][0][0] = node(42)
    policy = codec.QVPolicy(payload(), expected=contract())
    with pytest.raises(ValueError):
        policy.prepare(value)


@pytest.mark.parametrize('bad', [True, False, float('inf'), float('-inf'), float('nan'),
                                '20', None, 10**400])
def test_life_must_be_an_explicit_finite_number_without_zero_fallback(bad):
    value = state()
    life = field(value, 'observation', 'players', 'self', 'life')
    life['value'] = bad
    policy = codec.QVPolicy(payload(), expected=contract())
    with pytest.raises(ValueError):
        policy.prepare(value)


def test_context_formula_and_prepared_cache_are_detached_and_read_only():
    raw = payload()
    raw['weights']['kind.weight'][codec.KINDS.index('number')][0] = 2
    raw['weights']['q_out.bias'][0] = 1
    raw['weights']['v_out.bias'][0] = .5
    raw['weights']['q_context.weight'][0][0] = .5
    raw['weights']['q_context.weight'][0][64] = 1
    raw['weights']['q_context.weight'][0][128] = -.25
    policy = codec.QVPolicy(raw, expected=contract())
    value, action = state(10, 40), pack(7)
    before = deepcopy((value, action, raw))
    prepared = policy.prepare(value)
    cache = deepcopy(prepared._cache)
    # old rawQ 1 + 2 * (.5 + 10/20 - .25 * 40/20) = 2
    expected = {'q': 2 / 3, 'v': math.tanh(.5)}
    assert prepared.predict(action) == expected
    assert prepared.predict(action) == policy.predict(value, action)
    assert (value, action, raw) == before and prepared._cache == cache
    field(value, 'observation', 'players', 'self', 'life')['value'] = 99
    assert prepared.predict(action) == expected
    assert prepared._cache == cache


def test_life_extraction_ignores_decoys_and_requires_number_node_kind():
    value = state(-10, 0)
    value['root']['items'].append([node('life'), node(999)])
    before = deepcopy(value)
    assert codec.life_context(value) == (1.0, -.5, 0.0)
    assert value == before
    for kind, raw in [('bool', True), ('text', '20'), ('null', None)]:
        bad = deepcopy(value)
        target = field(bad, 'observation', 'players', 'opponent', 'life')
        target.clear()
        target['kind'] = kind
        if kind != 'null':
            target['value'] = raw
        with pytest.raises(ValueError):
            codec.life_context(bad)
    players = field(value, 'observation', 'players')
    players['items'].append(deepcopy(players['items'][1]))
    with pytest.raises(ValueError):
        codec.life_context(value)


def test_new_policy_payload_and_checkpoint_factory_detach_weights():
    raw = payload()
    policy = codec.QVPolicy(raw, expected=contract())
    raw['weights']['q_context.weight'][0][0] = 5
    copy = policy.payload()
    copy['weights']['q_context.weight'][0][0] = 6
    assert policy.payload()['weights']['q_context.weight'][0][0] == 0


def test_real_binary64_saturation_fixture_softsign_keeps_bounded_margin():
    def scores(context, bias):
        raw = payload(context)
        raw['weights']['q_out.bias'][0] = bias
        return codec.QVPolicy(raw, expected=contract()).predict(state(), pack(1))['q']
    # libm tanh(19) may be one ULP below 1; do not require a platform-specific tie.
    assert abs(scores(False, 22) - scores(False, 19)) <= math.ulp(1.0)
    assert scores(True, 22) == 22 / 23
    assert scores(True, 19) == 19 / 20
    assert scores(True, 22) - scores(True, 19) > .006
