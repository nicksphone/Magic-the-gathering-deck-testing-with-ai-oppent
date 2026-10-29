"""Offline CPU Torch Q/V fitting; never imports Torch for checkpoint inference."""
try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

import argparse
from copy import deepcopy
import fcntl
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import stat
import time

from ai.learned_qv import (FEATURE_SCHEMA_SHA256, KINDS, QVPolicy,
                          LEGACY_ACTIVATION, LIFE_CONTEXT_ACTIVATION, life_context,
                          parameter_shapes, validate_q_activation,
                          WIDTH, checkpoint, read_bytes, read_json, save_checkpoint,
                          normalized_number, strict_json, text_moments,
                          validate_contract, validate_features)


def torch_model(*, seed, q_activation=LEGACY_ACTIVATION):
    parameter_shapes(q_activation)
    import torch
    from torch import nn

    if type(seed) is not int or not 0 <= seed < 2**63:
        raise ValueError('Explicit bounded trainer seed required')

    class TreeQV(nn.Module):
        def __init__(self):
            super().__init__()
            self.q_activation = q_activation
            self.kind = nn.Embedding(8, WIDTH)
            self.byte = nn.Embedding(256, WIDTH)
            self.text = nn.Linear(3 * WIDTH + 1, WIDTH)
            self.scalar = nn.Linear(1, WIDTH, bias=False)
            self.fold = nn.Linear(2 * WIDTH, WIDTH)
            self.q_hidden = nn.Linear(2 * WIDTH, WIDTH)
            self.q_out = nn.Linear(WIDTH, 1)
            self.v_hidden = nn.Linear(WIDTH, WIDTH)
            self.v_out = nn.Linear(WIDTH, 1)
            if q_activation == LIFE_CONTEXT_ACTIVATION:
                # Added after every legacy module: seeded legacy weights stay identical.
                self.q_context = nn.Linear(3 * WIDTH, 1, bias=False)
                nn.init.zeros_(self.q_context.weight)

        def encode(self, pack, cache):
            validate_features(pack)
            bank, texts = [], cache.setdefault('texts', {})

            def node(value):
                kind = value['kind']
                base = self.kind.weight[KINDS.index(kind)]
                if kind == 'ref':
                    result = base + bank[value['index']]
                elif kind in ('number', 'bool'):
                    scalar = float(value['value'])
                    if kind == 'number':
                        scalar = normalized_number(value['value'])
                    result = base + self.scalar(base.new_tensor([scalar]))
                elif kind == 'text':
                    text = value['value']
                    if text in texts:
                        return texts[text]
                    moments, length = text_moments(text)
                    pooled = (base.new_tensor(moments) @ self.byte.weight).flatten()
                    texts[text] = self.text(torch.cat((pooled, base.new_tensor([length])))).relu()
                    return texts[text]
                elif kind == 'list':
                    result = base
                    for item in value['items']:
                        result = self.fold(torch.cat((result, node(item)))).relu()
                elif kind in ('map', 'set'):
                    rows = ([self.fold(torch.cat((node(a), node(b)))).relu()
                             for a, b in value['items']] if kind == 'map'
                            else [node(item) for item in value['items']])
                    # Sorting affects summation order, not feature values or gradients.
                    rows.sort(key=lambda row: tuple(row.detach().tolist()))
                    result = base + (torch.stack(rows).sum(0) if rows else torch.zeros_like(base))
                else:
                    result = base
                return result.relu()

            bank_key = json.dumps(pack['entities'], sort_keys=True, separators=(',', ':'), allow_nan=False)
            banks = cache.setdefault('banks', {})
            if bank_key in banks:
                bank = banks[bank_key]
            else:
                for entity in pack['entities']:
                    bank.append(node(entity))
                banks[bank_key] = bank
            return node(pack['root'])

        def raw_q(self, state, action, context=None):
            q = self.q_out(self.q_hidden(torch.cat((state, action))).relu()).squeeze()
            if self.q_activation == LIFE_CONTEXT_ACTIVATION:
                q = q + self.q_context(torch.outer(action.new_tensor(context), action).flatten()).squeeze()
            return q

        def bounded_q(self, q):
            return q / (1 + q.abs()) if self.q_activation == LIFE_CONTEXT_ACTIVATION else q.tanh()

        def forward(self, state, action):
            if state.get('version') != action.get('version'):
                raise ValueError('State/action feature epochs differ')
            cache = {}
            context = life_context(state) if self.q_activation == LIFE_CONTEXT_ACTIVATION else None
            s, a = self.encode(state, cache), self.encode(action, cache)
            q = self.bounded_q(self.raw_q(s, a, context))
            v = self.v_out(self.v_hidden(s).relu()).tanh().squeeze()
            return q, v

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = TreeQV().double().cpu()
    return model


def export_weights(model):
    values = model.state_dict()
    parameters = parameter_shapes(model.q_activation)
    if (set(values) != set(parameters)
            or any(tuple(values[key].shape) != shape for key, shape in parameters.items())):
        raise ValueError('Unexpected Torch model parameters')
    return {key: value.detach().cpu().tolist() for key, value in values.items()}


def terminal_targets(transitions, end):
    if type(end.get('complete')) is not bool:
        raise ValueError('Explicit completion label required')
    rewards = end.get('terminal_rewards')
    if not end['complete']:
        if type(end.get('reason')) is not str or end['reason'] == 'terminal' or rewards is not None:
            raise ValueError('Incomplete episodes cannot have terminal rewards')
        return None
    if (end.get('reason') != 'terminal' or type(rewards) is not dict or set(rewards) != {'1', '2'}
            or any(type(value) is not int or value not in (-1, 0, 1) for value in rewards.values())
            or sum(rewards.values()) != 0):
        raise ValueError('Actual zero-sum terminal reward pair required')
    result = []
    for row in transitions:
        seat = row['input']['observation']['seat']
        if type(seat) is not int or seat not in (1, 2):
            raise ValueError('Actual acting seat required')
        result.append(float(rewards[str(seat)]))
    return result


def validate_split(episodes, split):
    if (type(split) is not dict or set(split) != {'schema', 'train', 'eval'}
            or type(split['schema']) is not int or split['schema'] not in (1, 2)):
        raise ValueError('Explicit split schema required')
    pattern = r'episode-\d{4}' if split['schema'] == 1 else r'[0-9a-f]{64}/episode-\d{4}'
    for key in ('train', 'eval'):
        if (type(split[key]) is not list or not split[key]
                or any(type(name) is not str or not re.fullmatch(pattern, name)
                       for name in split[key]) or len(set(split[key])) != len(split[key])):
            raise ValueError('Nonempty unique train/eval episode lists required')
    train, heldout = set(split['train']), set(split['eval'])
    names = [row['episode'] for row in episodes]
    if train & heldout or len(set(names)) != len(names) or train | heldout != set(names):
        raise ValueError('Split must partition every episode exactly once')
    groups = {key: set() for key in ('train', 'eval')}
    fingerprints = {key: set() for key in groups}
    for episode in episodes:
        if (type(episode['groups']) is not list or not episode['groups']
                or any(type(group) is not str or not re.fullmatch(
                    r'(?:seed|family|deck|position):[0-9a-f]{64}', group) for group in episode['groups'])
                or type(episode['fingerprint']) is not str
                or not re.fullmatch('[0-9a-f]{64}', episode['fingerprint'])):
            raise ValueError('Explicit group and trajectory fingerprint required')
        side = 'train' if episode['episode'] in train else 'eval'
        groups[side].update(episode['groups'])
        fingerprints[side].add(episode['fingerprint'])
    if groups['train'] & groups['eval'] or fingerprints['train'] & fingerprints['eval']:
        raise ValueError('Shared component or duplicate trajectory crosses train/eval')
    return deepcopy(split)


def _samples(samples, *, feature_version=None):
    if type(samples) is not list or not 1 <= len(samples) <= 4096:
        raise ValueError('Use 1..4096 bounded training samples')
    for row in samples:
        if type(row) is not dict or set(row) != {'state', 'action', 'return'}:
            raise ValueError('Only semantic state/action and actual return are samples')
        target = row['return']
        if type(target) not in (int, float) or not math.isfinite(target) or not -1 <= target <= 1:
            raise ValueError('Finite actor-relative return required')
        validate_features(row['state'], expected_version=feature_version)
        validate_features(row['action'], expected_version=feature_version)
        if row['state']['version'] != row['action']['version']:
            raise ValueError('State/action feature epochs differ')


def train_samples(samples, *, contract, dataset_sha256, split_sha256,
                  seed, epochs=20, learning_rate=0.01, seconds=300, progress=None,
                  q_activation=LEGACY_ACTIVATION):
    validate_contract(contract)
    _samples(samples, feature_version=contract['feature_version'])
    validate_q_activation(q_activation, contract)
    if q_activation == LIFE_CONTEXT_ACTIVATION:
        for row in samples:
            life_context(row['state'])
    if progress is not None and not callable(progress):
        raise ValueError('Optional progress callback must be callable')
    if (type(epochs) is not int or not 1 <= epochs <= 1000 or epochs * len(samples) > 100000
            or type(seconds) is not int or not 1 <= seconds <= 3600
            or type(learning_rate) not in (int, float) or not math.isfinite(learning_rate)
            or not 0 < learning_rate <= 1):
        raise ValueError('Explicit finite CPU training budget required')
    import torch

    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    started = time.monotonic()
    try:
        model = (torch_model(seed=seed) if q_activation == LEGACY_ACTIVATION
                 else torch_model(seed=seed, q_activation=q_activation))
        initial = export_weights(model)
        optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)

        def budget():
            if time.monotonic() - started >= seconds:
                raise ValueError('CPU training deadline reached; no checkpoint published')

        def notify(phase, event, processed, updates):
            if progress is not None:
                progress({'phase': phase, 'event': event, 'processed': processed,
                          'total': epochs * len(samples) if phase == 'updates' else len(samples),
                          'updates': updates, 'elapsed_seconds': time.monotonic() - started})

        def mse(phase, updates=0):
            notify(phase, 'start', 0, updates)
            with torch.no_grad():
                errors = []
                for row in samples:
                    budget()
                    errors.append(float((model(row['state'], row['action'])[0] - row['return']) ** 2))
                    if progress is not None and len(errors) % 64 == 0:
                        notify(phase, 'progress', len(errors), updates)
            value = math.fsum(errors) / len(errors)
            notify(phase, 'end', len(errors), updates)
            return value

        initial_loss = mse('initial_mse')
        updates = 0
        notify('updates', 'start', 0, updates)
        for _ in range(epochs):
            for row in samples:
                budget()
                optimizer.zero_grad(set_to_none=True)
                q, v = model(row['state'], row['action'])
                target = q.new_tensor(row['return'])
                loss = (q - target).square() + (v - target).square()
                if not torch.isfinite(loss).item():
                    raise ValueError('Nonfinite training loss')
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0, error_if_nonfinite=True)
                optimizer.step()
                updates += 1
                if progress is not None and updates % 64 == 0:
                    notify('updates', 'progress', updates, updates)
        notify('updates', 'end', updates, updates)
        # Final MSE and parity share the same read-only final-weight forward pass.
        notify('final_mse', 'start', 0, updates)
        notify('export_parity', 'start', 0, updates)
        payload = checkpoint(export_weights(model), contract, {
            'dataset_sha256': dataset_sha256, 'split_sha256': split_sha256,
            'trainer_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'torch_version': str(torch.__version__),
            'trainer_seed': seed, 'updates': updates, 'samples': len(samples)},
            activation=q_activation)
        policy = QVPolicy(payload, expected=contract)
        verified = 0
        final_errors = []
        with torch.no_grad():
            for row in samples:
                budget()
                q, v = model(row['state'], row['action'])
                final_errors.append(float((q - row['return']) ** 2))
                result = policy.predict(row['state'], row['action'])
                if max(abs(result['q'] - q.item()), abs(result['v'] - v.item())) > 1e-9:
                    raise ValueError('Actual trained Torch/stdlib export parity failed')
                verified += 1
                if progress is not None and verified % 64 == 0:
                    notify('final_mse', 'progress', verified, updates)
                    notify('export_parity', 'progress', verified, updates)
        final_loss = math.fsum(final_errors) / len(final_errors)
        notify('final_mse', 'end', verified, updates)
        notify('export_parity', 'end', verified, updates)
        return payload, {'updates': updates, 'samples': len(samples),
                         'weights_changed': export_weights(model) != initial,
                         'initial_q_mse': initial_loss, 'final_q_mse': final_loss}
    finally:
        torch.set_num_threads(old_threads)


def _read_run(root, expected_engine_hash):
    from training.dataset import MAX_BYTES, MAX_EPISODES, validate_teacher_config, validate_episode
    from training.decision_frame import feature_contract

    root = Path(root)
    if root.is_symlink() or root.resolve(strict=True) != root.absolute():
        raise ValueError('Canonical existing closed dataset directory required')
    lock = os.open(root / 'run.lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_size != 0 or info.st_nlink != 1:
            raise ValueError('Original dataset read-only lock required')
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        manifest, raw_manifest = read_json(root / 'manifest.json', 65536)
        if type(manifest) is not dict:
            raise ValueError('Versioned manifest object required')
        fields = {'version', 'max_bytes', 'configuration_hash', 'engine_hash', 'deck_hashes', 'policy_hash', 'origin'}
        if manifest.get('origin') == 'heuristic':
            fields.add('teacher_config')
        if (set(manifest) != fields or manifest['version'] != 'mtg.dataset.v2'
                or manifest['engine_hash'] != expected_engine_hash
                or manifest['origin'] not in ('heuristic', 'scripted', 'unverified')
                or type(manifest['max_bytes']) is not int or not 4096 <= manifest['max_bytes'] <= MAX_BYTES):
            raise ValueError('Exact versioned dataset and caller engine binding required')
        hashes = [manifest[key] for key in ('configuration_hash', 'engine_hash', 'policy_hash')]
        if type(manifest['deck_hashes']) is not list or len(manifest['deck_hashes']) != 2:
            raise ValueError('Original two-deck provenance required')
        if any(type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value)
               for value in hashes + manifest['deck_hashes']):
            raise ValueError('Dataset provenance hashes required')
        if manifest['origin'] == 'heuristic':
            validate_teacher_config(manifest.get('teacher_config'))
        entries = list(root.iterdir())
        shards = sorted(p for p in entries if re.fullmatch(r'episode-\d{4}\.jsonl', p.name))
        if (not 1 <= len(shards) <= MAX_EPISODES
                or {p.name for p in entries} != {'manifest.json', 'run.lock', *(p.name for p in shards)}):
            raise ValueError('Closed original dataset members required')
        digest = sha256(raw_manifest)
        episodes, used, contract = [], len(raw_manifest), None
        for index, path in enumerate(shards):
            episode = f'episode-{index:04d}'
            if path.stem != episode:
                raise ValueError('Original contiguous episodes required')
            end = validate_episode(path, episode, dataset_version='mtg.dataset.v2')
            raw = read_bytes(path, MAX_BYTES)
            used += len(raw)
            if used > manifest['max_bytes']:
                raise ValueError('Dataset byte bound exceeded')
            lines = raw.splitlines(keepends=True)
            if not lines:
                raise ValueError('Original nonempty episode required')
            rows = [strict_json(line) for line in lines]
            if (rows[-1] != end or not all(line.endswith(b'\n') for line in lines)
                    or sha256(b''.join(lines[:-1])).hexdigest() != end['content_sha256']):
                raise ValueError('Episode changed between validation and intake')
            if rows[0]['origin'] != manifest['origin']:
                raise ValueError('Episode/manifest teacher provenance differs')
            groups = rows[0]['groups']
            if (not any(group.startswith('seed:') for group in groups)
                    or not any(group.startswith('family:') for group in groups)
                    or not {'deck:' + value for value in manifest['deck_hashes']}.issubset(groups)):
                raise ValueError('Original seed/family/deck grouping required')
            transitions = rows[1:-1]
            for row in transitions:
                current = {**feature_contract(row['input']), 'dataset_version': 'mtg.dataset.v2',
                           'action_version': 'mtg.action.v1:', 'engine_hash': expected_engine_hash}
                validate_contract(current)
                if contract is not None and current != contract:
                    raise ValueError('Mixed decision/feature epochs in a run')
                contract = current
            fingerprint = sha256(json.dumps([
                {key: row[key] for key in ('input', 'action', 'action_id')}
                for row in transitions], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            episodes.append({'episode': episode, 'groups': groups, 'fingerprint': fingerprint,
                             'transitions': transitions, 'end': end})
            digest.update(path.name.encode() + b'\0' + raw)
        return digest.hexdigest(), episodes, contract, used
    finally:
        os.close(lock)


def collect_corpus(roots, *, expected_engine_hash, max_corpus_bytes=50 * 1024 * 1024):
    """Read existing sealed runs; scoped IDs are addressing, never model features."""
    from training.dataset import MAX_EPISODES
    if type(max_corpus_bytes) is not int or not 4096 <= max_corpus_bytes <= 100 * 1024 * 1024:
        raise ValueError('Explicit integer corpus budget within 4096..100 MiB required')
    if type(roots) not in (list, tuple) or not 1 <= len(roots) <= MAX_EPISODES:
        raise ValueError('Use bounded original sealed run roots')
    runs, episodes, contract, used = {}, [], None, 0
    for root in roots:
        identity, rows, current, size = _read_run(root, expected_engine_hash)
        if identity in runs:
            raise ValueError('Duplicate run bytes or run root')
        used += size
        if used > max_corpus_bytes or len(episodes) + len(rows) > MAX_EPISODES:
            raise ValueError('Aggregate original dataset budget exceeded')
        if current is not None:
            if contract is not None and current != contract:
                raise ValueError('Mixed decision/feature epochs across runs')
            contract = current
        runs[identity] = rows
        for row in rows:
            episodes.append({**row, 'episode': identity + '/' + row['episode']})
    identities = sorted(runs)
    digest = identities[0] if len(identities) == 1 else sha256(
        ('mtg.qv.corpus.v1\0' + '\0'.join(identities)).encode('ascii')).hexdigest()
    return {'contract': contract, 'sha256': digest, 'runs': identities,
            'episodes': sorted(episodes, key=lambda row: row['episode'])}


def _selected_samples(corpus, split):
    from training.decision_frame import encode_action, encode_state
    if type(split) is not dict:
        raise ValueError('Explicit split schema required')
    episodes = corpus['episodes']
    if split.get('schema') == 1:
        if len(corpus['runs']) != 1:
            raise ValueError('Legacy unscoped split requires exactly one run')
        episodes = [{**row, 'episode': row['episode'].split('/', 1)[1]} for row in episodes]
    validate_split(episodes, split)
    if corpus['contract'] is None:
        raise ValueError('No accepted actor decision contract')
    records = {row['episode']: row for row in episodes}
    samples = {'train': [], 'eval': []}
    for side in samples:
        for name in split[side]:
            episode = records[name]
            targets = terminal_targets(episode['transitions'], episode['end'])
            if targets is None:
                continue
            for row, target in zip(episode['transitions'], targets):
                samples[side].append({'state': encode_state(row['input']),
                                     'action': encode_action(row['input'], row['action']),
                                     'return': target})
        _samples(samples[side], feature_version=corpus['contract']['feature_version'])
    return samples


def load_samples(root, split_path, *, expected_engine_hash, max_corpus_bytes=50 * 1024 * 1024):
    roots = list(root) if type(root) in (list, tuple) else [root]
    corpus = collect_corpus(roots, expected_engine_hash=expected_engine_hash,
                            max_corpus_bytes=max_corpus_bytes)
    split, split_bytes = read_json(split_path, 65536)
    return (_selected_samples(corpus, split), corpus['contract'], corpus['sha256'],
            sha256(split_bytes).hexdigest())


def _output_path(value, roots):
    path = Path(value).absolute()
    parent = path.parent.resolve(strict=True)
    backend = Path(__file__).resolve().parents[1]
    excluded = [Path(root).resolve() for root in roots]
    excluded.extend(backend / name for name in ('rules_engine', 'effects', 'game_state', 'ai', 'card_data', 'training'))
    if any(parent == root or root in parent.parents for root in excluded):
        raise ValueError('Outputs must stay outside sealed datasets and hashed source')
    if path.is_symlink():
        raise ValueError('Fresh regular output path required')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, action='append',
                        help='Repeat for original independently sealed runs')
    parser.add_argument('--split')
    parser.add_argument('--engine-hash', required=True)
    parser.add_argument('--max-corpus-bytes', type=int, default=50 * 1024 * 1024,
                        help='Explicit aggregate capacity, at most 100 MiB; each sealed run stays bounded')
    parser.add_argument('--out')
    parser.add_argument('--seed', type=int)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--split-out')
    parser.add_argument('--eval-fraction', type=float, default=0.2)
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--learning-rate', type=float, default=0.01)
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--q-activation', choices=(LEGACY_ACTIVATION, LIFE_CONTEXT_ACTIVATION),
                        default=LEGACY_ACTIVATION, help='Explicit checkpoint architecture opt-in')
    args = parser.parse_args(argv)
    if args.collect_only:
        if not args.split_out or args.out or args.split or args.seed is not None:
            parser.error('Collection requires --split-out, not training/output arguments')
    elif not args.split or not args.out or args.seed is None or args.split_out:
        parser.error('Training requires explicit --split, --out and --seed')
    try:
        if args.collect_only:
            from training.dataset import grouped_split_report
            if not math.isfinite(args.eval_fraction) or not 0 < args.eval_fraction < 1:
                raise ValueError('Finite interior evaluation fraction required')
            path = _output_path(args.split_out, args.dataset)
            corpus = collect_corpus(args.dataset, expected_engine_hash=args.engine_hash,
                                    max_corpus_bytes=args.max_corpus_bytes)
            report = grouped_split_report(corpus['episodes'], eval_fraction=args.eval_fraction)
            split = {'schema': 2, 'train': report['train'], 'eval': report['eval']}
            ready = report['partition_ready']
            reasons = [] if ready else ['empty_training_or_heldout_partition']
            if ready:
                try:
                    _selected_samples(corpus, split)
                except ValueError:
                    ready = False
                    reasons = ['unusable_training_or_heldout_samples']
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(split, output, sort_keys=True, allow_nan=False)
                output.write('\n')
            completed = sum(row['end']['complete'] for row in corpus['episodes'])
            print(json.dumps({'status': 'corpus_collected_not_policy_qualified',
                'runs': len(corpus['runs']), 'episodes': len(corpus['episodes']),
                'complete_episodes': completed,
                'incomplete_episodes': len(corpus['episodes']) - completed,
                'partition_ready': ready, 'reasons': reasons,
                'corpus_sha256': corpus['sha256']}, allow_nan=False))
            return 0 if ready else 2
        path = _output_path(args.out, args.dataset)
        samples, contract, dataset_hash, split_hash = load_samples(
            args.dataset, args.split, expected_engine_hash=args.engine_hash,
            max_corpus_bytes=args.max_corpus_bytes)
        payload, report = train_samples(samples['train'], contract=contract,
            dataset_sha256=dataset_hash, split_sha256=split_hash, seed=args.seed,
            epochs=args.epochs, learning_rate=args.learning_rate, seconds=args.seconds,
            q_activation=args.q_activation)
        policy = QVPolicy(payload, expected=contract)
        errors = [((result['q'] - row['return']) ** 2, (result['v'] - row['return']) ** 2)
                  for row in samples['eval']
                  for result in [policy.predict(row['state'], row['action'])]]
        report['heldout_samples'] = len(errors)
        report['heldout_q_mse'] = math.fsum(row[0] for row in errors) / len(errors)
        report['heldout_v_mse'] = math.fsum(row[1] for row in errors) / len(errors)
        fitted = report.get('updates', 0) > 0 and report.get('weights_changed') is True
        save_checkpoint(path, payload)
        print(json.dumps({'status': ('fitted_offline_not_policy_qualified' if fitted
                                   else 'untrained_protocol_not_policy_qualified'),
                          'fitted': fitted, **report}, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, ImportError):
        print(json.dumps({'status': 'unavailable', 'reason': 'training_or_input_not_qualified'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
