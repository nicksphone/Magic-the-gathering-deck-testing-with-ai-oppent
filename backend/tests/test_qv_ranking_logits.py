"""Synthetic numerical regressions, not game outcomes or trained-policy evidence."""
from copy import deepcopy
import math

import pytest

from ai.learned_qv import QVPolicy, WIDTH
from scripts import train_qv_preferences as trainer
from tests.test_learned_qv import contract, number


@pytest.mark.parametrize('bias', [0.0, 20.0, -20.0])
@pytest.mark.parametrize('observed_return', [False, True])
def test_common_score_offset_cannot_hide_wrong_preference(bias, observed_return, monkeypatch):
    torch = pytest.importorskip('torch', reason='Actual CPU trainer needs optional Torch')
    from scripts.train_qv import torch_model

    model = torch_model(seed=17)
    # Real model, with a deliberately wrong raw margin of -0.5. Large common
    # offsets saturate runtime tanh but must not erase the training gradient.
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.scalar.weight[0, 0] = 1
        model.q_hidden.weight[0, WIDTH] = 1
        model.q_hidden.bias[0] = 1
        model.q_out.weight[0, 0] = -1
        model.q_out.bias[0] = bias
    monkeypatch.setattr(trainer, 'torch_model', lambda *, seed: model)
    row = {'state': number(0), 'preferred': number(1), 'alternatives': [number(0)]}
    if observed_return:
        row['return'] = 1.0
    original, threads = deepcopy(row), torch.get_num_threads()
    payload, report = trainer.train_preferences([row], contract=contract(),
        dataset_sha256='b' * 64, split_sha256='c' * 64, seed=17, epochs=1,
        learning_rate=.01, seconds=30, temperature=.25)

    assert payload['weights']['q_out.weight'][0][0] > -.999
    assert 'ranking_logit_loss' in report['initial']
    assert report['initial']['ranking_logit_loss'] == pytest.approx(math.log1p(math.exp(2)))
    bounded_gap = math.tanh(bias - 1) - math.tanh(bias - 1.5)
    assert report['initial']['preference_loss'] == pytest.approx(
        math.log1p(math.exp(bounded_gap / .25)))
    assert report['ranking_loss_input'] == 'unbounded_q_logits'
    assert report['value_samples'] == int(observed_return)
    assert report['preference_only_samples'] == int(not observed_return)
    assert row == original and torch.get_num_threads() == threads
    # Rank/margin diagnostics and exported inference remain bounded, even though
    # the optimization objective uses the unsquashed head values.
    policy = QVPolicy(payload, expected=contract())
    scores = [policy.predict(row['state'], action)['q']
              for action in [row['preferred'], *row['alternatives']]]
    assert all(math.isfinite(score) and -1 <= score <= 1 for score in scores)
    assert report['final']['strict_top1'] == int(scores[0] > scores[1])
    assert report['final']['mean_preferred_margin'] == pytest.approx(scores[0] - scores[1])
    assert report['final']['max_parity_error'] <= 1e-9
    assert report['final']['parity_actions'] == 2
