"""Synthetic sampler/gradient units, not game outcomes or policy qualification."""
import builtins
from copy import deepcopy
import random

import pytest
import torch

from scripts import train_qv, train_qv_preferences as trainer
from tests.test_qv_preference_training import preference, options


@pytest.mark.parametrize('pairs,batch_size', [([], 2), ([[0, 0]], 2),
    ([[0, 2]], 2), ([[-1, 1]], 2), ([[True, 1]], 2), ([[0]], 2),
    ([(0, 1)], 2), (((0, 1),), 2), ([[0, 1], [0, 1]], 2), ([[0, 1]], 1)])
def test_invalid_batch_pairs_rejected_before_torch(pairs, batch_size, monkeypatch):
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        assert name.split('.')[0] != 'torch', 'Invalid sampler imported Torch'
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', importing)
    with pytest.raises(ValueError):
        trainer.train_preferences([preference(), preference()], **options(),
                                  batch_size=batch_size, batch_pairs=pairs)


def test_paired_optimizer_matches_independent_per_pair_mean_and_order(monkeypatch):
    rows = [preference() for _ in range(4)]
    for i, row in enumerate(rows):
        row['state']['root']['value'] = i+1
        row['preferred']['root']['value'] = (-1 if i % 2 else 1)
        row['alternatives'][0]['root']['value'] = -row['preferred']['root']['value']
    del rows[1]['return']
    del rows[3]['return']
    pairs = [[0, 1], [2, 3]]
    before = deepcopy((rows, pairs))
    reference = train_qv.torch_model(seed=17)
    optimizer = torch.optim.Adam(reference.parameters(), lr=.001)
    rng, order = random.Random(17), list(range(2))
    expected_gradients = []
    for _ in range(2):
        rng.shuffle(order)
        for pair in order:
            optimizer.zero_grad(set_to_none=True)
            losses = []
            for index in pairs[pair]:
                row = rows[index]
                logits, value = trainer._scores(reference, row, torch)
                loss = torch.nn.functional.cross_entropy(
                    (logits/.25).unsqueeze(0), torch.zeros(1, dtype=torch.long))
                if 'return' in row:
                    loss = loss + .25*(value-row['return']).square()
                losses.append(loss)
            torch.stack(losses).mean().backward()
            expected_gradients.append({k: None if p.grad is None else p.grad.detach().clone()
                                       for k, p in reference.named_parameters()})
            torch.nn.utils.clip_grad_norm_(reference.parameters(), 10, error_if_nonfinite=True)
            optimizer.step()

    factory, backward = trainer.torch_model, torch.Tensor.backward
    actual_gradients, models = [], []

    def observe_factory(**kwargs):
        result = factory(**kwargs)
        models.append(result)
        return result

    def observe_backward(loss, *args, **kwargs):
        result = backward(loss, *args, **kwargs)
        actual_gradients.append({k: None if p.grad is None else p.grad.detach().clone()
                                 for k, p in models[0].named_parameters()})
        return result

    monkeypatch.setattr(trainer, 'torch_model', observe_factory)
    monkeypatch.setattr(torch.Tensor, 'backward', observe_backward)
    args = {**options(), 'epochs': 2, 'batch_size': 2, 'batch_pairs': pairs}
    payload, report = trainer.train_preferences(rows, **args)
    assert (rows, pairs) == before
    assert len(actual_gradients) == len(expected_gradients) == 4
    for actual, expected in zip(actual_gradients, expected_gradients):
        for name, value in expected.items():
            if value is None:
                assert actual[name] is None
            else:
                assert float((actual[name]-value).abs().max()) < 1e-12
    for name, value in reference.state_dict().items():
        assert float((value-value.new_tensor(payload['weights'][name])).abs().max()) < 1e-12
    assert report['row_exposures'] == 8 and report['optimizer_updates'] == 4
    assert report['batch_pairing']['version'] == 1
    assert report['value_samples'] == 2 and report['final']['max_parity_error'] <= 1e-9
