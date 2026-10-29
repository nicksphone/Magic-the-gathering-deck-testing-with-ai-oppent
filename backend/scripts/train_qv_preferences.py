"""Offline heuristic-preference ranking, not invented counterfactual returns.

Q becomes a bounded preference utility. V fits only supplied, observed
actor-relative terminal returns; a preference-only row omits that target.
The existing feature/checkpoint/inference contracts are reused;
neither successful fitting nor teacher agreement authorizes live activation.
"""
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import re
import time

from ai.learned_qv import (QVPolicy, checkpoint, normalized_number,
                          LEGACY_ACTIVATION, LIFE_CONTEXT_ACTIVATION,
                          life_context, validate_q_activation,
                          validate_contract, validate_features)
from scripts.train_qv import export_weights, torch_model


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def semantic_action_key(pack):
    """Recognize guaranteed feature-equivalence, not guessed equal game outcomes."""
    validate_features(pack)
    bank = []

    def node(value):
        kind = value['kind']
        content = None
        if kind == 'ref':
            content = bank[value['index']]
        elif kind == 'map':
            content = sorted([node(key), node(item)] for key, item in value['items'])
        elif kind in {'set', 'list'}:
            content = [node(item) for item in value['items']]
            if kind == 'set':
                content.sort()
        elif kind == 'number':
            content = normalized_number(value['value']) or 0.0
        elif kind != 'null':
            content = value['value']
        return sha256(_canonical([kind, content]).encode()).hexdigest()

    for entity in pack['entities']:
        bank.append(node(entity))
    return sha256(_canonical([pack['version'], node(pack['root'])]).encode()).hexdigest()


def validate_preferences(rows, *, contract):
    validate_contract(contract)
    if type(rows) is not list or not 1 <= len(rows) <= 4096:
        raise ValueError('Use 1..4096 bounded preference decisions')
    for row in rows:
        if type(row) is not dict or set(row) not in (
                {'state', 'preferred', 'alternatives'},
                {'state', 'preferred', 'alternatives', 'return'}):
            raise ValueError('Only semantic preferences and optional observed returns are accepted')
        if 'return' in row:
            target = row['return']
            if type(target) not in (int, float) or not math.isfinite(target) or not -1 <= target <= 1:
                raise ValueError('Finite actor-relative terminal return required')
        alternatives = row['alternatives']
        if type(alternatives) is not list or not 1 <= len(alternatives) <= 8:
            raise ValueError('Use 1..8 distinct same-state alternatives')
        packs = [row['state'], row['preferred'], *alternatives]
        for pack in packs:
            validate_features(pack, expected_version=contract['feature_version'])
        bank = _canonical(row['state']['entities'])
        if any(_canonical(pack['entities']) != bank for pack in packs[1:]):
            raise ValueError('All candidates must share the same authorized entity bank')
        candidates = [semantic_action_key(pack) for pack in packs[1:]]
        if len(set(candidates)) != len(candidates):
            raise ValueError('Preferred and alternative actions must be semantically distinct')


def _scores(model, row, torch):
    # Optimize raw logits: squashing can hide a wrong ranking by saturating both
    # choices. Runtime scores and ranking/parity diagnostics remain bounded.
    cache = {}
    state = model.encode(row['state'], cache)
    context = life_context(row['state']) if model.q_activation == LIFE_CONTEXT_ACTIVATION else None
    scores = []
    for action in [row['preferred'], *row['alternatives']]:
        encoded = model.encode(action, cache)
        scores.append(model.raw_q(state, encoded, context))
    value = model.v_out(model.v_hidden(state).relu()).tanh().squeeze()
    return torch.stack(scores), value


def train_preferences(rows, *, contract, dataset_sha256, split_sha256, seed,
                      epochs=8, learning_rate=.001, seconds=1800,
                      temperature=.25, value_weight=.25, progress=None,
                      q_activation=LEGACY_ACTIVATION, batch_size=1):
    """Fit checked preferences against admitted same-position alternatives.

    The caller must validate original dataset provenance and grouped partitions.
    This API never reads evaluation rows or assigns outcomes to unchosen actions.
    No checkpoint is returned if validation, budget, finiteness or parity fails.
    """
    validate_preferences(rows, contract=contract)
    validate_q_activation(q_activation, contract)
    if q_activation == LIFE_CONTEXT_ACTIVATION:
        for row in rows:
            life_context(row['state'])
    if (type(seed) is not int or not 0 <= seed < 2**63
            or type(epochs) is not int or not 1 <= epochs <= 1000
            or epochs * len(rows) > 100000
            or type(seconds) is not int or not 1 <= seconds <= 3600
            or type(batch_size) is not int or not 1 <= batch_size <= 256):
        raise ValueError('Explicit finite seed, epoch, update and time budgets required')
    for name, value, allow_zero in [('learning_rate', learning_rate, False),
                                   ('temperature', temperature, False),
                                   ('value_weight', value_weight, True)]:
        if (type(value) not in (int, float) or not math.isfinite(value)
                or value > 1 or value < 0 or not allow_zero and value == 0):
            raise ValueError('Invalid bounded ' + name)
    if progress is not None and not callable(progress):
        raise ValueError('Optional progress callback must be callable')
    if any(type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value)
           for value in (dataset_sha256, split_sha256)):
        raise ValueError('Exact dataset and split provenance hashes required')

    import torch
    from torch.nn import functional as functional

    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    started = time.monotonic()
    updates = row_exposures = 0
    try:
        model = (torch_model(seed=seed) if q_activation == LEGACY_ACTIVATION
                 else torch_model(seed=seed, q_activation=q_activation))
        initial_weights = export_weights(model)
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        zero = torch.zeros(1, dtype=torch.long)

        def budget():
            if time.monotonic() - started >= seconds:
                raise ValueError('Preference training deadline reached; no checkpoint published')

        def notify(phase, event, processed):
            if progress is not None:
                progress({'phase': phase, 'event': event, 'processed': processed,
                          'total': epochs * len(rows) if phase == 'updates' else len(rows),
                          'updates': updates, 'row_exposures': row_exposures,
                          'elapsed_seconds': time.monotonic() - started})

        def measure(phase, policy=None):
            notify(phase, 'start', 0)
            losses, logit_losses, margins, values = [], [], [], []
            correct = parity_actions = 0
            max_error = 0.0
            with torch.no_grad():
                for index, row in enumerate(rows):
                    budget()
                    logits, value = _scores(model, row, torch)
                    scores = model.bounded_q(logits)
                    loss = functional.cross_entropy((scores / temperature).unsqueeze(0), zero)
                    logit_loss = functional.cross_entropy((logits / temperature).unsqueeze(0), zero)
                    margin = float(scores[0] - scores[1:].max())
                    losses.append(float(loss))
                    logit_losses.append(float(logit_loss))
                    margins.append(margin)
                    if 'return' in row:
                        values.append(float((value - row['return']).square()))
                    correct += margin > 0
                    if policy is not None:
                        prepared = policy.prepare(row['state'])
                        for score, action in zip(scores, [row['preferred'], *row['alternatives']]):
                            predicted = prepared.predict(action)
                            error = max(abs(predicted['q'] - float(score)),
                                        abs(predicted['v'] - float(value)))
                            if not math.isfinite(error) or error > 1e-9:
                                raise ValueError('Preference Torch/stdlib export parity failed')
                            max_error = max(max_error, error)
                            parity_actions += 1
                    if (index + 1) % 32 == 0:
                        notify(phase, 'progress', index + 1)
            notify(phase, 'end', len(rows))
            return {'preference_loss': math.fsum(losses) / len(rows),
                    'ranking_logit_loss': math.fsum(logit_losses) / len(rows),
                    'strict_top1': correct / len(rows),
                    'mean_preferred_margin': math.fsum(margins) / len(rows),
                    'v_mse': math.fsum(values) / len(values) if values else None,
                    'parity_actions': parity_actions, 'max_parity_error': max_error}

        initial = measure('initial_preferences')
        order = list(range(len(rows)))
        rng = random.Random(seed)
        notify('updates', 'start', 0)
        for _ in range(epochs):
            rng.shuffle(order)
            for start in range(0, len(order), batch_size):
                budget()
                optimizer.zero_grad(set_to_none=True)
                batch = order[start:start + batch_size]
                rankings, observed_values = [], []
                for index in batch:
                    budget()
                    row = rows[index]
                    logits, value = _scores(model, row, torch)
                    rankings.append(functional.cross_entropy((logits / temperature).unsqueeze(0), zero))
                    if 'return' in row:
                        observed_values.append((value - row['return']).square())
                loss = torch.stack(rankings).mean()
                if observed_values:
                    loss = loss + value_weight * torch.stack(observed_values).sum() / len(batch)
                if not torch.isfinite(loss).item():
                    raise ValueError('Nonfinite preference loss')
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0, error_if_nonfinite=True)
                optimizer.step()
                updates += 1
                row_exposures += len(batch)
                if updates % 32 == 0:
                    notify('updates', 'progress', row_exposures)
        notify('updates', 'end', row_exposures)
        payload = checkpoint(export_weights(model), contract, {
            'dataset_sha256': dataset_sha256, 'split_sha256': split_sha256,
            'trainer_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'torch_version': str(torch.__version__), 'trainer_seed': seed,
            'updates': updates, 'samples': len(rows)}, activation=q_activation)
        final = measure('final_preferences_and_parity', QVPolicy(payload, expected=contract))
        budget()
        value_samples = sum('return' in row for row in rows)
        objective = ('heuristic_listwise_preferences_plus_actual_return_V'
                     if value_samples == len(rows)
                     else 'listwise_preferences_plus_available_actual_return_V')
        return payload, {'objective': objective,
                         'ranking_loss_input': 'unbounded_q_logits',
                         'q_semantics': 'preference_utility_not_calibrated_return',
                         'samples': len(rows), 'updates': updates,
                         'optimizer_updates': updates, 'row_exposures': row_exposures,
                         'batch_size': batch_size, 'q_activation': q_activation,
                         'value_samples': value_samples,
                         'preference_only_samples': len(rows) - value_samples,
                         'temperature': temperature, 'value_weight': value_weight,
                         'initial': initial, 'final': final,
                         'weights_changed': export_weights(model) != initial_weights,
                         'elapsed_seconds': time.monotonic() - started}
    finally:
        torch.set_num_threads(old_threads)
