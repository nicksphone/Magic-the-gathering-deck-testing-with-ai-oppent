"""Optional cached-CPU synthetic-unit learning, never real-game qualification."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import random

import pytest

from ai import learned_qv as codec
from scripts import train_qv, train_qv_preferences as trainer
from tests.test_qv_life_context import ACTIVATION, contract, field, pack, payload, state


def options(**kwargs):
    return dict(contract=contract(), dataset_sha256='b' * 64, split_sha256='c' * 64,
                seed=17, epochs=1, seconds=60, **kwargs)


def rows():
    # Deliberately synthetic protocol features, not game observations/actions.
    return [{'state': state(4, 20), 'preferred': pack(1), 'alternatives': [pack(-1)]},
            {'state': state(20, 4), 'preferred': pack(-1), 'alternatives': [pack(1)]}]


@pytest.mark.parametrize('key,bad', [('batch_size', True), ('batch_size', 0),
    ('batch_size', 257), ('batch_size', 1.5), ('q_activation', 'softsign'),
    ('q_activation', None)])
def test_bad_options_rejected_before_torch(key, bad, monkeypatch):
    import builtins
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        assert name.split('.')[0] != 'torch', 'Bad options imported Torch'
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', importing)
    with pytest.raises(ValueError):
        trainer.train_preferences(rows(), **options(**{key: bad}))


def test_new_mode_bad_life_rejected_before_torch(monkeypatch):
    import builtins
    data = rows()
    field(data[0]['state'], 'observation', 'players', 'self')['items'] = []
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        assert name.split('.')[0] != 'torch', 'Bad life imported Torch'
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', importing)
    with pytest.raises(ValueError):
        trainer.train_preferences(data, **options(q_activation=ACTIVATION))


def cpu():
    return pytest.importorskip('torch', reason='Optional already-cached CPU runtime')


def test_seed_preserves_all_old_weights_zero_context_and_external_rng():
    torch = cpu()
    before = torch.random.get_rng_state().clone()
    python_before = random.getstate()
    old = train_qv.torch_model(seed=17)
    new = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    assert torch.equal(before, torch.random.get_rng_state())
    assert random.getstate() == python_before
    a, b = train_qv.export_weights(old), train_qv.export_weights(new)
    assert set(a) == set(codec.PARAMETERS)
    assert set(b) == {*a, 'q_context.weight'}
    assert b['q_context.weight'] == [[0.0] * 192]
    assert all(a[key] == b[key] for key in a)
    new.q_activation = 'relu-tanh'
    with pytest.raises(ValueError):
        train_qv.export_weights(new)


def test_context_raw_scores_forward_and_stdlib_qv_parity(tmp_path):
    torch = cpu()
    saturated = torch.tensor([22., 20.], dtype=torch.float64).tanh()
    assert saturated.tolist() == [1., 1.]
    model = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    with torch.no_grad():
        model.q_context.weight.copy_(torch.arange(192, dtype=torch.float64).reshape(1, -1) / 10000)
        model.q_out.bias.fill_(22)
        row = rows()[0]
        before = deepcopy(row)
        logits, value = trainer._scores(model, row, torch)
        s = model.encode(row['state'], {})
        ctx = s.new_tensor([1, 4/20, 20/20])
        expected = []
        for action in [row['preferred'], *row['alternatives']]:
            a = model.encode(action, {})
            base = model.q_out(model.q_hidden(torch.cat((s, a))).relu()).squeeze()
            expected.append(base + model.q_context(torch.outer(ctx, a).flatten()).squeeze())
        assert torch.equal(logits, torch.stack(expected))
        raw = codec.checkpoint(train_qv.export_weights(model), contract(), {
            'dataset_sha256': 'b'*64, 'split_sha256': 'c'*64, 'trainer_sha256': 'd'*64,
            'torch_version': str(torch.__version__), 'trainer_seed': 17,
            'updates': 0, 'samples': 0}, activation=ACTIVATION)
        path = tmp_path / 'synthetic.json'
        codec.save_checkpoint(path, raw)
        prepared = codec.load_checkpoint(path, expected=contract()).prepare(row['state'])
        cache = deepcopy(prepared._cache)
        for logit, action in zip(logits, [row['preferred'], *row['alternatives']]):
            q, v = model(row['state'], action)
            assert float(q) == pytest.approx(float(logit / (1 + logit.abs())), abs=1e-12)
            assert float(v) == pytest.approx(float(value), abs=1e-12)
            assert prepared.predict(action) == pytest.approx({'q': float(q), 'v': float(v)}, abs=1e-9)
        assert row == before and prepared._cache == cache


def test_actual_synthetic_joint_fit_and_q_only_value_head_preservation():
    torch = cpu()
    data = rows()
    before = deepcopy(data)
    initial = train_qv.export_weights(train_qv.torch_model(seed=17, q_activation=ACTIVATION))
    payload, report = trainer.train_preferences(data, **{
        **options(q_activation=ACTIVATION, batch_size=2), 'epochs': 100,
        'learning_rate': .003, 'temperature': .25})
    assert data == before and report['final']['strict_top1'] == 1
    assert report['final']['mean_preferred_margin'] > 0
    assert report['updates'] == report['optimizer_updates'] == 100
    assert report['row_exposures'] == 200
    assert report['value_samples'] == 0 and report['final']['v_mse'] is None
    assert report['final']['max_parity_error'] <= 1e-9
    for name in ('v_hidden.weight', 'v_hidden.bias', 'v_out.weight', 'v_out.bias'):
        assert payload['weights'][name] == initial[name]
    policy = codec.QVPolicy(payload, expected=contract())
    for row in data:
        assert policy.predict(row['state'], row['preferred'])['q'] > policy.predict(
            row['state'], row['alternatives'][0])['q']


@pytest.mark.parametrize('batch_size', [1, 2, 256])
def test_batch_partial_observed_value_mask_and_accounting(batch_size, monkeypatch):
    torch = cpu()

    def gradients(model):
        return {name: None if value.grad is None else value.grad.detach().clone()
                for name, value in model.named_parameters()}

    for size in (2, 3):
        data = rows() + ([deepcopy(rows()[0])] if size == 3 else [])
        data[-1]['alternatives'].append(pack(0))  # Per-row CE, not pooled candidates.
        order = list(range(size))
        random.Random(17).shuffle(order)
        # One observed row, last in shuffled order: with size=3/batch=2 this
        # also checks an observed final partial batch uses denominator 1, not 2.
        data[order[-1]]['return'] = .8
        before, initial_threads = deepcopy(data), torch.get_num_threads()
        reference = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
        optimizer = torch.optim.Adam(reference.parameters(), lr=.001)
        expected_losses, expected_gradients = [], []
        for start in range(0, size, batch_size):
            optimizer.zero_grad(set_to_none=True)
            per_row = []
            for index in order[start:start + batch_size]:
                row = data[index]
                logits, value = trainer._scores(reference, row, torch)
                loss = torch.nn.functional.cross_entropy(
                    (logits/.25).unsqueeze(0), torch.zeros(1, dtype=torch.long))
                if 'return' in row:
                    loss = loss + .25 * (value - row['return']).square()
                per_row.append(loss)
            # Independent masked PER-ROW objective, not a second implementation
            # of the trainer's separately aggregated Q and V terms.
            loss = torch.stack(per_row).mean()
            expected_losses.append(float(loss.detach()))
            loss.backward()
            expected_gradients.append(gradients(reference))
            torch.nn.utils.clip_grad_norm_(reference.parameters(), 10, error_if_nonfinite=True)
            optimizer.step()

        actual_losses, actual_gradients, events, models = [], [], [], []
        original_factory, original_backward = trainer.torch_model, torch.Tensor.backward

        def factory(**kwargs):
            model = original_factory(**kwargs)
            models.append(model)
            return model

        def backward(loss, *args, **kwargs):
            actual_losses.append(float(loss.detach()))
            result = original_backward(loss, *args, **kwargs)
            actual_gradients.append(gradients(models[0]))
            return result

        # Observe the real loss and every parameter gradient BEFORE clipping.
        with monkeypatch.context() as observing:
            observing.setattr(trainer, 'torch_model', factory)
            observing.setattr(torch.Tensor, 'backward', backward)
            payload, report = trainer.train_preferences(data, **options(
                q_activation=ACTIVATION, batch_size=batch_size, progress=events.append))
        assert len(actual_losses) == len(expected_losses)
        objective_error = max(abs(a - b) for a, b in zip(actual_losses, expected_losses))
        assert len(actual_gradients) == len(expected_gradients)
        gradient_error = 0.0
        for actual, expected in zip(actual_gradients, expected_gradients):
            for name in expected:
                if expected[name] is None:
                    assert actual[name] is None, name
                else:
                    assert actual[name] is not None, name
                    error = float((actual[name] - expected[name]).abs().max())
                    gradient_error = max(gradient_error, error)
        diagnostic = {'rows': size, 'batch_size': batch_size,
                      'max_objective_error': objective_error,
                      'max_preclip_gradient_error': gradient_error}
        print('synthetic masked-per-row objective/gradient:', diagnostic)
        assert objective_error < 1e-12 and gradient_error < 1e-12, diagnostic
        for name, expected in reference.state_dict().items():
            actual = expected.new_tensor(payload['weights'][name])
            assert float((actual - expected).abs().max()) < 1e-12, name
        count = math.ceil(size / batch_size)
        assert report['updates'] == report['optimizer_updates'] == count
        assert payload['provenance']['updates'] == count
        assert report['row_exposures'] == size and report['batch_size'] == batch_size
        assert report['value_samples'] == 1 and report['preference_only_samples'] == size - 1
        event = [e for e in events if e['phase'] == 'updates' and e['event'] == 'end'][0]
        assert event['processed'] == event['total'] == event['row_exposures'] == size
        assert event['updates'] == count and torch.get_num_threads() == initial_threads
        assert data == before


def test_default_one_row_order_weights_match_pinned_legacy_trainer():
    cpu()
    # The handoff runner supplies the exact archived baseline outside source.
    path = Path(__file__).resolve().parents[3] / 'baseline/backend/scripts/train_qv_preferences.py'
    if not path.is_file():
        pytest.skip('Exact pre-change archive reference is optional outside handoff')
    spec = importlib.util.spec_from_file_location('legacy_preference_reference', path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    train_spec = importlib.util.spec_from_file_location('scripts._legacy_qv_reference', path.with_name('train_qv.py'))
    old_train = importlib.util.module_from_spec(train_spec)
    train_spec.loader.exec_module(old_train)
    old.torch_model = old_train.torch_model
    old.export_weights = old_train.export_weights
    assert train_qv.export_weights(train_qv.torch_model(seed=17)) == old_train.export_weights(
        old_train.torch_model(seed=17))
    data = rows()
    data[0]['return'] = .8
    args = {**options(), 'epochs': 2}
    reference, reference_report = old.train_preferences(data, **args)
    actual, report = trainer.train_preferences(data, **args)
    assert actual['weights'] == reference['weights']
    assert actual['version'] == reference['version'] == 'mtg.qv.v1'
    assert actual['activation'] == reference['activation'] == 'relu-tanh'
    for key in ('initial', 'final', 'updates', 'samples'):
        assert report[key] == reference_report[key]


def test_return_trainer_opt_in_and_row_exposure_bound():
    cpu()
    samples = [{'state': state(), 'action': pack(1), 'return': 1.0}]
    payload, report = train_qv.train_samples(samples, **options(q_activation=ACTIVATION))
    assert payload['activation'] == ACTIVATION and payload['version'] == 'mtg.qv.v2'
    assert report['updates'] == 1
    with pytest.raises(ValueError):
        trainer.train_preferences(rows() * 51, **{**options(batch_size=256), 'epochs': 1000})


def test_existing_return_cli_exposes_only_explicit_activation_opt_in(tmp_path, monkeypatch):
    sample = {'state': state(), 'action': pack(1), 'return': 1.0}
    captured = []

    def loading(*args, **kwargs):
        return {'train': [sample], 'eval': [sample]}, contract(), 'b'*64, 'c'*64

    def fitting(*args, **kwargs):
        captured.append(kwargs['q_activation'])
        return payload(kwargs['q_activation'] == ACTIVATION), {'updates': 0, 'weights_changed': False}

    monkeypatch.setattr(train_qv, 'load_samples', loading)
    monkeypatch.setattr(train_qv, 'train_samples', fitting)
    for index, extra in enumerate(([], ['--q-activation', ACTIVATION])):
        assert train_qv.main(['--dataset', str(tmp_path / 'sealed'), '--split', 'synthetic',
            '--out', str(tmp_path / f'model-{index}.json'), '--seed', '17',
            '--engine-hash', 'a'*64, *extra]) == 0
    assert captured == ['relu-tanh', ACTIVATION]
    with pytest.raises(SystemExit) as error:
        train_qv.main(['--dataset', 'synthetic', '--engine-hash', 'a'*64,
                       '--q-activation', 'unknown'])
    assert error.value.code == 2
