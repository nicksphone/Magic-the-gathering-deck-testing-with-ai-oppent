"""Public synthetic numerical contracts; no archived features or fitted weights."""
from copy import deepcopy
import math
import struct

import pytest

from ai import learned_qv as codec
from tests.test_qv_life_context import payload, state, pack, field


class OriginalDotPolicy(codec.QVPolicy):
    """Frozen original _linear from base 23a; independent numerical reference."""
    def _linear(self, name, values, relu=True):
        weights = self._payload['weights']
        bias = weights.get(name + '.bias', [0.0] * len(weights[name + '.weight']))
        result = [sum(a * b for a, b in zip(row, values)) + offset
                  for row, offset in zip(weights[name + '.weight'], bias)]
        if any(not math.isfinite(value) for value in result):
            raise ValueError('Nonfinite Q/V activation')
        return [max(0.0, value) for value in result] if relu else result


def populated(context=True):
    raw = payload(context)
    for name, rows in raw['weights'].items():
        for i, row in enumerate(rows):
            if isinstance(row, list):
                rows[i] = [((17*i + 13*j + len(name)) % 29 - 14) / 300
                           for j in range(len(row))]
            else:
                rows[i] = ((17*i + len(name)) % 29 - 14) / 300
    return raw


def policy(raw, cls=codec.QVPolicy):
    return cls(raw, expected=raw['contract'])


def bits(result):
    return {key: struct.pack('!d', value) for key, value in result.items()}


def no_native(*args):
    pytest.fail('Legacy or rejected input reached native sumprod')


@pytest.mark.parametrize('relu', [False, True])
def test_context_affine_dispatches_native_sumprod(monkeypatch, relu):
    raw = populated()
    subject = policy(raw)
    native, calls = math.sumprod, []

    def spy(left, right):
        calls.append((list(left), list(right)))
        return native(left, right)

    monkeypatch.setattr(codec.math, 'sumprod', spy)
    values = [i / 100 for i in range(64)]
    expected = native(raw['weights']['q_out.weight'][0], values) + raw['weights']['q_out.bias'][0]
    assert subject._linear('q_out', values, relu) == [max(0.0, expected) if relu else expected]
    assert calls == [(raw['weights']['q_out.weight'][0], values)]


@pytest.mark.parametrize('feature_version', [codec.FEATURE_VERSION, codec.FEATURE_CONTEXT_VERSION])
def test_legacy_has_zero_native_calls_and_original_bits(monkeypatch, feature_version):
    raw = populated(False)
    decision, schema = codec.FEATURE_CONTRACTS[feature_version]
    raw['contract'].update(feature_version=feature_version, decision_version=decision,
                           feature_schema_sha256=schema)
    sample, action = pack({'unit': 17}), pack({'action': 'public-unit'})
    sample['version'] = action['version'] = feature_version
    subject, original = policy(raw), policy(raw, OriginalDotPolicy)
    monkeypatch.setattr(codec.math, 'sumprod', no_native)
    assert bits(subject.predict(sample, action)) == bits(original.predict(sample, action))
    assert bits(subject.prepare(sample).predict(action)) == bits(original.prepare(sample).predict(action))


@pytest.mark.parametrize('feature_version', [codec.FEATURE_VERSION, codec.FEATURE_CONTEXT_VERSION])
def test_default_checkpoint_and_predictions_stay_exact(monkeypatch, feature_version):
    raw = payload(False)
    decision, schema = codec.FEATURE_CONTRACTS[feature_version]
    raw['contract'].update(feature_version=feature_version, decision_version=decision,
                           feature_schema_sha256=schema)
    raw['weights']['q_out.bias'][0], raw['weights']['v_out.bias'][0] = 22, -.7
    sample = pack(1)
    sample['version'] = feature_version
    monkeypatch.setattr(codec.math, 'sumprod', no_native)
    subject = policy(raw)
    expected = {'q': math.tanh(22), 'v': math.tanh(-.7)}
    assert raw['version'] == codec.VERSION and raw['activation'] == codec.LEGACY_ACTIVATION
    assert bits(subject.predict(sample, sample)) == bits(expected)
    assert subject.payload() == raw


@pytest.mark.parametrize('context', [False, True])
@pytest.mark.parametrize('length', [63, 65])
def test_native_length_is_strict_and_legacy_truncation_is_preserved(context, length):
    raw = populated(context)
    subject, original = policy(raw), policy(raw, OriginalDotPolicy)
    values = [.125] * length
    if context:
        with pytest.raises(ValueError):
            subject._linear('q_out', values, False)
    else:
        assert bits({'x': subject._linear('q_out', values, False)[0]}) == bits(
            {'x': original._linear('q_out', values, False)[0]})


@pytest.mark.parametrize('own,opponent', [(20, 20), (3, 18), (37, 2)])
def test_context_direct_and_prepared_match_original_surrogate_with_bounded_error(own, opponent):
    raw, sample = populated(), state(own, opponent)
    sample['entities'] = [{'kind': 'text', 'value': 'synthetic-public'},
                          {'kind': 'ref', 'index': 0}]
    sample['root']['items'].append([{'kind': 'text', 'value': 'synthetic-ref'},
                                    {'kind': 'ref', 'index': 1}])
    actions = [pack({'unit_action': value, 'label': 'ascii-\u00e9'}) for value in (-3, 1/7, 20)]
    for action in actions:
        action['entities'] = deepcopy(sample['entities'])
    before = deepcopy((raw, sample, actions))
    subject, original = policy(raw), policy(raw, OriginalDotPolicy)
    prepared, reference = subject.prepare(sample), original.prepare(sample)
    cache_before = deepcopy(prepared._cache)
    actual, expected = [], []
    for action in actions:
        predicted, old = prepared.predict(action), reference.predict(action)
        assert predicted == subject.predict(sample, action)
        assert all(math.isfinite(v) and -1 <= v <= 1 for v in predicted.values())
        assert predicted == pytest.approx(old, rel=0, abs=1e-12)
        actual.append(predicted['q'])
        expected.append(old['q'])
    assert max(range(3), key=actual.__getitem__) == max(range(3), key=expected.__getitem__)
    assert [i for i,v in enumerate(actual) if v == max(actual)] == [i for i,v in enumerate(expected) if v == max(expected)]
    assert prepared._cache == cache_before and (raw, sample, actions) == before


def test_exact_context_ties_remain_exact_without_tolerance_ranking():
    raw, sample = payload(), state()
    actions = [pack({'action': 'first'}), pack({'action': 'second'})]
    for cls in (codec.QVPolicy, OriginalDotPolicy):
        prepared = policy(raw, cls).prepare(sample)
        scores = [prepared.predict(action)['q'] for action in actions]
        assert scores == [0.0, 0.0]
        assert [i for i,value in enumerate(scores) if value == max(scores)] == [0, 1]
        assert max(range(2), key=scores.__getitem__) == 0


@pytest.mark.parametrize('entry', ['direct', 'prepared'])
@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'bool', 'nan', 'inf',
                                     'wrong_kind', 'forward_ref', 'unknown_kind'])
def test_bad_context_state_rejected_before_native_math(monkeypatch, entry, mutation):
    sample, action = state(), pack({'unit': 1})
    own = field(sample, 'observation', 'players', 'self')
    life = field(sample, 'observation', 'players', 'self', 'life')
    if mutation == 'missing':
        own['items'].clear()
    elif mutation == 'duplicate':
        own['items'].append(deepcopy(own['items'][0]))
    elif mutation in {'bool', 'nan', 'inf'}:
        life['value'] = {'bool': True, 'nan': float('nan'), 'inf': float('inf')}[mutation]
    elif mutation == 'wrong_kind':
        life.update(kind='text', value='20')
    elif mutation == 'forward_ref':
        sample['entities'] = [{'kind': 'ref', 'index': 0}]
    else:
        sample['root']['kind'] = 'unknown'
    subject = policy(payload())
    monkeypatch.setattr(codec.math, 'sumprod', no_native)
    with pytest.raises(ValueError):
        subject.predict(sample, action) if entry == 'direct' else subject.prepare(sample)


@pytest.mark.parametrize('entry', ['direct', 'prepared'])
@pytest.mark.parametrize('mutation', ['nan', 'unknown_kind', 'forward_ref'])
def test_bad_action_rejected_on_direct_and_prepared_paths(entry, mutation):
    sample, action = state(), pack(1)
    if mutation == 'nan':
        action['root']['value'] = float('nan')
    elif mutation == 'unknown_kind':
        action['root']['kind'] = 'unknown'
    else:
        action['root'] = {'kind': 'ref', 'index': 0}
    subject = policy(payload())
    with pytest.raises(ValueError):
        subject.predict(sample, action) if entry == 'direct' else subject.prepare(sample).predict(action)


@pytest.mark.parametrize('context', [False, True])
@pytest.mark.parametrize('mutation', ['nan_weight', 'short_row', 'mixed_activation'])
def test_closed_checkpoint_validation_still_rejects_before_native(monkeypatch, context, mutation):
    raw = payload(context)
    if mutation == 'nan_weight':
        raw['weights']['q_out.weight'][0][0] = float('nan')
    elif mutation == 'short_row':
        raw['weights']['q_out.weight'][0].pop()
    else:
        raw['activation'] = codec.LEGACY_ACTIVATION if context else codec.LIFE_CONTEXT_ACTIVATION
    monkeypatch.setattr(codec.math, 'sumprod', no_native)
    with pytest.raises(ValueError):
        policy(raw)
