"""Bounded JSON Q/V weights and stdlib inference; no training framework import."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import stat


VERSION = 'mtg.qv.v1'
LEGACY_ACTIVATION = 'relu-tanh'
LIFE_CONTEXT_VERSION = 'mtg.qv.v2'
LIFE_CONTEXT_ACTIVATION = 'relu-softsign-life-context'
FEATURE_VERSION = 'mtg.features.v1'
FEATURE_SCHEMA_SHA256 = '0b3aadfead9f66999c8b6c3ddc13699ad7dc5dd1c76179e95585042ba0339ed5'
FEATURE_CONTEXT_VERSION = 'mtg.features.v2'
FEATURE_CONTEXT_SCHEMA_SHA256 = '9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06'
FEATURE_CONTRACTS = {
    FEATURE_VERSION: ('mtg.decision.v1', FEATURE_SCHEMA_SHA256),
    FEATURE_CONTEXT_VERSION: ('mtg.decision.v2', FEATURE_CONTEXT_SCHEMA_SHA256),
}
WIDTH = 64
MAX_CHECKPOINT_BYTES = 2 * 1024 * 1024
MAX_NODES = 262144
MAX_ENTITIES = 4096
MAX_TEXT_BYTES = 65536
MAX_TOTAL_TEXT_BYTES = 1048576
KINDS = ('null', 'bool', 'number', 'text', 'list', 'map', 'set', 'ref')
PARAMETERS = {
    'kind.weight': (8, WIDTH), 'byte.weight': (256, WIDTH),
    'text.weight': (WIDTH, 3 * WIDTH + 1), 'text.bias': (WIDTH,),
    'scalar.weight': (WIDTH, 1), 'fold.weight': (WIDTH, 2 * WIDTH),
    'fold.bias': (WIDTH,), 'q_hidden.weight': (WIDTH, 2 * WIDTH),
    'q_hidden.bias': (WIDTH,), 'q_out.weight': (1, WIDTH), 'q_out.bias': (1,),
    'v_hidden.weight': (WIDTH, WIDTH), 'v_hidden.bias': (WIDTH,),
    'v_out.weight': (1, WIDTH), 'v_out.bias': (1,),
}


def parameter_shapes(activation):
    if type(activation) is str and activation == LEGACY_ACTIVATION:
        return PARAMETERS
    if type(activation) is str and activation == LIFE_CONTEXT_ACTIVATION:
        return {**PARAMETERS, 'q_context.weight': (1, 3 * WIDTH)}
    raise ValueError('Unsupported Q/V activation')


def validate_q_activation(activation, contract):
    parameter_shapes(activation)
    if (activation == LIFE_CONTEXT_ACTIVATION
            and contract['feature_version'] != FEATURE_CONTEXT_VERSION):
        raise ValueError('Life-context Q requires the registered v2 feature contract')


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('Unexpected Q/V schema')


def _numeric(value, limit):
    if type(value) not in (int, float) or abs(value) > limit or not math.isfinite(value):
        raise ValueError('Finite bounded numeric value required')
    return float(value)


def _hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Exact SHA256 required')


def normalized_number(value):
    if type(value) not in (int, float):
        raise ValueError('Finite scalar semantic value required')
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError('Finite binary64 scalar required') from exc
    if not math.isfinite(number):
        raise ValueError('Finite binary64 scalar required')
    return number / (1 + abs(number))


def text_moments(text):
    if type(text) is not str or len(text) > MAX_TEXT_BYTES:
        raise ValueError('Bounded semantic text required')
    encoded = text.encode('utf-8')
    if len(encoded) > MAX_TEXT_BYTES:
        raise ValueError('Bounded semantic text required')
    moments = [[0.0] * 256 for _ in range(3)]
    count = len(encoded)
    for index, byte in enumerate(encoded):
        position = 0.0 if count == 1 else 2 * index / (count - 1) - 1
        for row, value in zip(moments, (1.0, position, position * position)):
            row[byte] += value / count
    return moments, count / (1 + count)


def validate_contract(value):
    fixed = {'dataset_version': 'mtg.dataset.v2', 'action_version': 'mtg.action.v1:'}
    _keys(value, {*fixed, 'decision_version', 'feature_version',
                  'feature_schema_sha256', 'engine_hash'})
    if any(type(value[key]) is not str or value[key] != expected for key, expected in fixed.items()):
        raise ValueError('Incompatible Q/V feature or action version')
    version = value['feature_version']
    if (type(version) is not str or version not in FEATURE_CONTRACTS
            or (value['decision_version'], value['feature_schema_sha256']) != FEATURE_CONTRACTS[version]):
        raise ValueError('Incompatible closed Q/V decision/feature contract')
    _hash(value['engine_hash'])


def validate_features(pack, *, expected_version=None):
    _keys(pack, ('version', 'root', 'entities'))
    if (type(pack['version']) is not str or pack['version'] not in FEATURE_CONTRACTS
            or expected_version is not None and pack['version'] != expected_version
            or type(pack['entities']) is not list
            or len(pack['entities']) > MAX_ENTITIES):
        raise ValueError('Incompatible semantic feature tree')
    used, text_bytes = 0, 0

    def node(value, refs, depth=0):
        nonlocal used, text_bytes
        used += 1
        if used > MAX_NODES or depth > 64 or type(value) is not dict:
            raise ValueError('Semantic feature tree bound exceeded')
        kind = value.get('kind')
        if type(kind) is not str or kind not in KINDS:
            raise ValueError('Unknown semantic node kind')
        fields = ('kind',) if kind == 'null' else ('kind', 'index' if kind == 'ref' else
                   'items' if kind in ('map', 'set', 'list') else 'value')
        _keys(value, fields)
        if kind == 'ref':
            if type(value['index']) is not int or not 0 <= value['index'] < refs:
                raise ValueError('Reference must gather an earlier authorized entity')
        elif kind == 'bool':
            if type(value['value']) is not bool:
                raise ValueError('Boolean semantic node required')
        elif kind == 'number':
            normalized_number(value['value'])
        elif kind == 'text':
            if type(value['value']) is not str or len(value['value']) > MAX_TEXT_BYTES:
                raise ValueError('Text semantic node required')
            size = len(value['value'].encode('utf-8'))
            text_bytes += size
            if size > MAX_TEXT_BYTES or text_bytes > MAX_TOTAL_TEXT_BYTES:
                raise ValueError('Semantic text byte bound exceeded')
        elif kind in ('list', 'set', 'map'):
            if type(value['items']) is not list:
                raise ValueError('Semantic items must be a list')
            for item in value['items']:
                if kind == 'map':
                    if type(item) is not list or len(item) != 2:
                        raise ValueError('Semantic map pair required')
                    node(item[0], refs, depth + 1)
                    node(item[1], refs, depth + 1)
                else:
                    node(item, refs, depth + 1)

    for index, entity in enumerate(pack['entities']):
        node(entity, index)
    node(pack['root'], len(pack['entities']))


def life_context(state):
    """Read only the unique authorized actor-relative numeric life paths."""
    validate_features(state, expected_version=FEATURE_CONTEXT_VERSION)

    def field(value, key):
        if value['kind'] != 'map':
            raise ValueError('Explicit life-context map required')
        matches = [item for name, item in value['items']
                   if name['kind'] == 'text' and name['value'] == key]
        if len(matches) != 1:
            raise ValueError('Unique life-context key required')
        return matches[0]

    players = field(field(state['root'], 'observation'), 'players')
    values = [1.0]
    for role in ('self', 'opponent'):
        life = field(field(players, role), 'life')
        if life['kind'] != 'number':
            raise ValueError('Explicit finite life number required')
        # validate_features already rejects booleans, overflow and nonfinite numbers.
        values.append(float(life['value']) / 20)
    return tuple(values)


def _validate(payload, expected):
    _keys(payload, ('version', 'width', 'activation', 'contract', 'provenance', 'weights'))
    parameters = parameter_shapes(payload['activation'])
    version = VERSION if payload['activation'] == LEGACY_ACTIVATION else LIFE_CONTEXT_VERSION
    if (type(payload['version']) is not str or payload['version'] != version
            or type(payload['width']) is not int or payload['width'] != WIDTH):
        raise ValueError('Unsupported Q/V architecture')
    validate_contract(payload['contract'])
    validate_q_activation(payload['activation'], payload['contract'])
    validate_contract(expected)
    if payload['contract'] != expected:
        raise ValueError('Q/V engine or feature contract mismatch')
    p = payload['provenance']
    _keys(p, ('dataset_sha256', 'split_sha256', 'trainer_sha256', 'torch_version',
              'trainer_seed', 'updates', 'samples'))
    _hash(p['dataset_sha256'])
    _hash(p['split_sha256'])
    _hash(p['trainer_sha256'])
    if (type(p['torch_version']) is not str or not 1 <= len(p['torch_version']) <= 64
            or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.+-'
                   for c in p['torch_version'])):
        raise ValueError('Bounded trainer version required')
    for key in ('trainer_seed', 'updates', 'samples'):
        limit = 2**63 - 1 if key == 'trainer_seed' else 100000
        if type(p[key]) is not int or not 0 <= p[key] <= limit:
            raise ValueError('Invalid bounded training provenance')
    _keys(payload['weights'], parameters)
    for name, shape in parameters.items():
        rows = payload['weights'][name]
        if type(rows) is not list or len(rows) != shape[0]:
            raise ValueError('Q/V tensor shape mismatch')
        if len(shape) == 2:
            if any(type(row) is not list or len(row) != shape[1] for row in rows):
                raise ValueError('Q/V tensor shape mismatch')
            values = (value for row in rows for value in row)
        else:
            values = iter(rows)
        for value in values:
            _numeric(value, 100)


def checkpoint(weights, contract, provenance, *, activation=LEGACY_ACTIVATION):
    parameter_shapes(activation)
    version = VERSION if activation == LEGACY_ACTIVATION else LIFE_CONTEXT_VERSION
    payload = {'version': version, 'width': WIDTH, 'activation': activation,
               'contract': contract, 'provenance': provenance, 'weights': weights}
    _validate(payload, contract)
    if len(json.dumps(payload, separators=(',', ':'), allow_nan=False).encode()) > MAX_CHECKPOINT_BYTES:
        raise ValueError('Q/V checkpoint exceeds byte bound')
    return deepcopy(payload)


class QVPolicy:
    def __init__(self, payload, *, expected):
        _validate(payload, expected)
        self._payload = checkpoint(payload['weights'], payload['contract'], payload['provenance'],
                                   activation=payload['activation'])

    def payload(self):
        return deepcopy(self._payload)

    def _linear(self, name, values, relu=True):
        weights = self._payload['weights']
        bias = weights.get(name + '.bias', [0.0] * len(weights[name + '.weight']))
        if self._payload['activation'] == LIFE_CONTEXT_ACTIVATION:
            result = [math.sumprod(row, values) + offset
                      for row, offset in zip(weights[name + '.weight'], bias)]
        else:
            result = [sum(a * b for a, b in zip(row, values)) + offset
                      for row, offset in zip(weights[name + '.weight'], bias)]
        if any(not math.isfinite(value) for value in result):
            raise ValueError('Nonfinite Q/V activation')
        return [max(0.0, value) for value in result] if relu else result

    def _encode(self, pack, cache):
        validate_features(pack, expected_version=self._payload['contract']['feature_version'])
        weights, bank, texts = self._payload['weights'], [], cache.setdefault('texts', {})

        def node(value):
            kind = value['kind']
            base = weights['kind.weight'][KINDS.index(kind)]
            if kind == 'ref':
                result = [a + b for a, b in zip(base, bank[value['index']])]
            elif kind in ('number', 'bool'):
                scalar = float(value['value'])
                if kind == 'number':
                    scalar = normalized_number(value['value'])
                result = [a + b * scalar for a, (b,) in zip(base, weights['scalar.weight'])]
            elif kind == 'text':
                text = value['value']
                if text in texts:
                    return texts[text]
                moments, length = text_moments(text)
                pooled = [math.fsum(coefficient * weights['byte.weight'][byte][index]
                                   for byte, coefficient in enumerate(row) if coefficient)
                          for row in moments for index in range(WIDTH)]
                texts[text] = self._linear('text', pooled + [length])
                return texts[text]
            elif kind == 'list':
                result = list(base)
                for item in value['items']:
                    result = self._linear('fold', result + node(item))
            elif kind in ('map', 'set'):
                items = ([self._linear('fold', node(a) + node(b)) for a, b in value['items']]
                         if kind == 'map' else [node(item) for item in value['items']])
                result = [offset + math.fsum(row[i] for row in items) for i, offset in enumerate(base)]
            else:
                result = list(base)
            if any(not math.isfinite(item) for item in result):
                raise ValueError('Nonfinite semantic encoding')
            return [max(0.0, item) for item in result]

        # A memo key is never an embedding or model feature. Reuse only within this decision.
        bank_key = json.dumps(pack['entities'], sort_keys=True, separators=(',', ':'), allow_nan=False)
        banks = cache.setdefault('banks', {})
        if bank_key in banks:
            bank = banks[bank_key]
        else:
            for entity in pack['entities']:
                bank.append(node(entity))
            banks[bank_key] = bank
        return node(pack['root'])

    def predict(self, state, action):
        return self.prepare(state).predict(action)

    def prepare(self, state):
        return QVDecision(self, state)


class QVDecision:
    """One fixed-checkpoint decision, retaining no engine or raw-reference objects."""

    def __init__(self, policy, state):
        self._policy, self._cache = policy, {}
        self._context = (life_context(state)
                         if policy._payload['activation'] == LIFE_CONTEXT_ACTIVATION else None)
        self._state = policy._encode(state, self._cache)
        self._value = math.tanh(policy._linear('v_out', policy._linear('v_hidden', self._state), False)[0])

    def predict(self, action):
        # New action-only entries cannot accumulate across arbitrarily many proposals.
        cache = {key: dict(value) for key, value in self._cache.items()}
        vector = self._policy._encode(action, cache)
        q = self._policy._linear('q_out', self._policy._linear('q_hidden', self._state + vector), False)[0]
        if self._context is not None:
            q += self._policy._linear('q_context',
                [scale * item for scale in self._context for item in vector], False)[0]
            return {'q': normalized_number(q), 'v': self._value}
        return {'q': math.tanh(q), 'v': self._value}


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    def nonfinite(_value):
        raise ValueError('Nonfinite JSON number')

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError('Invalid bounded JSON') from exc


def read_bytes(path, limit):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError('Bounded regular JSON file required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if len(data) > limit or any(getattr(before, key) != getattr(after, key) for key in fields):
            raise ValueError('JSON file changed during intake')
        return data
    finally:
        os.close(fd)


def read_json(path, limit):
    data = read_bytes(path, limit)
    return strict_json(data), data


def load_checkpoint(path, *, expected):
    value, _ = read_json(path, MAX_CHECKPOINT_BYTES)
    return QVPolicy(value, expected=expected)


def save_checkpoint(path, payload):
    _validate(payload, payload['contract'])
    data = (json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if len(data) > MAX_CHECKPOINT_BYTES:
        raise ValueError('Q/V checkpoint exceeds byte bound')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
