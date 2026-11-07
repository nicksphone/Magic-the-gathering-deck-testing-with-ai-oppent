"""Bounded CPU synthetic diagnostics, not game labels or accepted model weights."""
import builtins
from copy import deepcopy
import random

import pytest

from ai import learned_qv as codec
from scripts import train_qv, train_qv_preferences as trainer
from tests.test_qv_life_context import contract, field, pack, state
from tests.test_qv_state_interaction import ACTIVATION, large_interaction_case


def cpu():
    return pytest.importorskip('torch', reason='Optional already-cached CPU runtime')


def options(**kwargs):
    return {**dict(contract=contract(), dataset_sha256='b' * 64, split_sha256='c' * 64,
                   seed=17, epochs=1, seconds=60, q_activation=ACTIVATION), **kwargs}


def test_zero_initial_head_preserves_all_seeded_weights_raw_outputs_and_rng():
    torch = cpu()
    before, python_before = torch.random.get_rng_state().clone(), random.getstate()
    old = train_qv.torch_model(seed=17)
    life = train_qv.torch_model(seed=17, q_activation=codec.LIFE_CONTEXT_ACTIVATION)
    model = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    assert torch.equal(before, torch.random.get_rng_state()) and random.getstate() == python_before
    weights, old_weights, life_weights = map(train_qv.export_weights, (model, old, life))
    assert set(weights) == {*life_weights, 'q_interaction.weight'}
    assert all(weights[key] == old_weights[key] for key in old_weights)
    assert all(weights[key] == life_weights[key] for key in life_weights)
    assert weights['q_interaction.weight'] == [[0.] * 64]
    assert weights['q_context.weight'] == [[0.] * 192]
    assert sum(p.numel() for p in model.parameters()) - sum(p.numel() for p in life.parameters()) == 64
    with torch.no_grad():
        for value, action in [(state(4, 20), pack(-1)), (state(20, 4), pack(1))]:
            s, a = model.encode(value, {}), model.encode(action, {})
            assert torch.equal(model.raw_q(s, a, codec.life_context(value)), old.raw_q(s, a))
            assert all(torch.equal(x, y) for x, y in zip(model(value, action), life(value, action)))
    for activation in (codec.LEGACY_ACTIVATION, codec.LIFE_CONTEXT_ACTIVATION):
        model.q_activation = activation
        with pytest.raises(ValueError):
            train_qv.export_weights(model)


def test_nonzero_interaction_forward_preference_and_prepared_stdlib_parity(tmp_path):
    torch = cpu()
    model = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    value = state(10, 40)
    value['entities'] = [pack('synthetic-entity')['root'], {'kind': 'ref', 'index': 0}]
    value['root']['items'].append([pack('synthetic-ref')['root'], {'kind': 'ref', 'index': 1}])
    actions = [pack(3), pack(-2)]
    for action in actions:
        action['entities'] = deepcopy(value['entities'])
    actions[1]['root'] = {'kind': 'ref', 'index': 1}
    row = {'state': value, 'preferred': actions[0], 'alternatives': actions[1:]}
    before = deepcopy(row)
    with torch.no_grad():
        model.q_context.weight.copy_(torch.arange(192, dtype=torch.float64).reshape(1, -1) / 1000)
        model.q_interaction.weight.copy_((torch.arange(64, dtype=torch.float64) - 31.5).reshape(1, -1) / 100)
        logits, v = trainer._scores(model, row, torch)
        s = model.encode(value, {})
        expected = []
        for action in actions:
            a = model.encode(action, {})
            base = model.q_out(model.q_hidden(torch.cat((s, a))).relu()).squeeze()
            context = (model.q_context.weight.reshape(3, 64) * a * s.new_tensor([1., .5, 2.])[:, None]).sum()
            interaction = (model.q_interaction.weight[0] * s * a).sum()
            expected.append(base + context + interaction)
        assert torch.allclose(logits, torch.stack(expected), atol=1e-12, rtol=0)
        raw = codec.checkpoint(train_qv.export_weights(model), contract(), {
            'dataset_sha256': 'b' * 64, 'split_sha256': 'c' * 64, 'trainer_sha256': 'd' * 64,
            'torch_version': str(torch.__version__), 'trainer_seed': 17, 'updates': 0, 'samples': 0},
            activation=ACTIVATION)
        path = tmp_path / 'synthetic.json'
        codec.save_checkpoint(path, raw)
        policy = codec.load_checkpoint(path, expected=contract())
        prepared = policy.prepare(value)
        cache, retained_payload = deepcopy(prepared._cache), policy.payload()
        for logit, action in zip(logits, actions):
            q, actual_v = model(value, action)
            assert float(q) == pytest.approx(float(logit / (1 + logit.abs())), abs=1e-12)
            assert float(actual_v) == pytest.approx(float(v), abs=1e-12)
            expected = {'q': float(q), 'v': float(actual_v)}
            assert prepared.predict(action) == pytest.approx(expected, abs=1e-9)
            assert policy.predict(value, action) == prepared.predict(action)
        assert row == before and prepared._cache == cache and policy.payload() == retained_payload
        field(value, 'observation', 'players', 'self', 'life')['value'] = 99
        assert prepared.predict(actions[0])['q'] == pytest.approx(float(model.bounded_q(logits[0])), abs=1e-9)


def test_product_supplies_state_ranking_gradient_in_a_flat_relu_region():
    torch = cpu()
    model = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.q_hidden.bias.fill_(1)
        model.q_out.weight.fill_(1)
    s = torch.ones(64, dtype=torch.float64, requires_grad=True)
    a, b = torch.zeros_like(s), torch.zeros_like(s)
    a[0], a[1], b[0], b[1] = 5, 7, 1, 2
    context = (1., 1., 1.)

    def gradient():
        margin = model.raw_q(s, a, context) - model.raw_q(s, b, context)
        return torch.autograd.grad(margin, s)[0]

    assert gradient().tolist() == [0.] * 64
    with torch.no_grad():
        model.q_interaction.weight[0, 0] = 2
        model.q_interaction.weight[0, 1] = -3
    assert gradient().tolist() == [8., -15.] + [0.] * 62


@pytest.mark.parametrize('weight,expected_q', [(0., .5), (1e-160, 1.)])
def test_large_finite_embeddings_zero_and_small_heads_match_stdlib(weight, expected_q):
    torch = cpu()
    raw, value, action = large_interaction_case(weight)
    model = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    model.load_state_dict({name: torch.tensor(v, dtype=torch.float64) for name, v in raw['weights'].items()})
    with torch.no_grad():
        s, a = model.encode(value, {}), model.encode(action, {})
        assert bool(torch.isfinite(s).all() and torch.isfinite(a).all())
        assert bool(torch.isinf(s * a).any())
        logit = model.raw_q(s, a, codec.life_context(value))
        assert float(logit) == pytest.approx(1. if weight == 0 else 1e162, rel=1e-12)
        q, v = model(value, action)
        assert (float(q), float(v)) == (expected_q, 0.)
        alternative = deepcopy(action)
        alternative['root']['items'].pop()
        row = {'state': value, 'preferred': action, 'alternatives': [alternative]}
        logits, _ = trainer._scores(model, row, torch)
        assert bool(torch.isfinite(logits).all())
        assert float(logits[0]) == float(logit)
        policy = codec.QVPolicy(raw, expected=contract())
        assert policy.predict(value, action) == {'q': float(q), 'v': float(v)}


def test_zero_head_keeps_trainable_gradient_and_nonfinite_gradients_fail_closed():
    torch = cpu()
    model = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
    # Large but representable dQ/dw; skipping the zero head would erase this.
    s = torch.full((64,), 1e150, dtype=torch.float64)
    a = torch.full_like(s, 1e150)
    model.raw_q(s, a, (1., 1., 1.)).backward()
    assert model.q_interaction.weight.grad.tolist()[0] == pytest.approx([1e300] * 64, rel=1e-15)
    model.zero_grad(set_to_none=True)
    raw, value, action = large_interaction_case()
    model.load_state_dict({name: torch.tensor(v, dtype=torch.float64) for name, v in raw['weights'].items()})
    model(value, action)[0].backward()
    assert not bool(torch.isfinite(model.q_interaction.weight.grad).all())
    with pytest.raises(RuntimeError):
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10., error_if_nonfinite=True)


def test_torch_truly_nonfinite_interaction_is_rejected_not_clipped_or_squashed():
    torch = cpu()
    raw, value, action = large_interaction_case(1.)
    model = train_qv.torch_model(seed=17, q_activation=ACTIVATION)
    model.load_state_dict({name: torch.tensor(v, dtype=torch.float64) for name, v in raw['weights'].items()})
    with pytest.raises(ValueError):
        model(value, action)


@pytest.mark.parametrize('entry', ['return', 'preference'])
@pytest.mark.parametrize('change', ['missing-life', 'duplicate-life', 'bool-life', 'v1-contract'])
def test_conditioned_training_validates_context_before_torch_import(entry, change, monkeypatch):
    value = state()
    args = options()
    life = field(value, 'observation', 'players', 'self')
    if change == 'missing-life':
        life['items'].clear()
    elif change == 'duplicate-life':
        life['items'].append(deepcopy(life['items'][0]))
    elif change == 'bool-life':
        life['items'][0][1] = {'kind': 'bool', 'value': True}
    else:
        args['contract'] = {**contract(), 'feature_version': codec.FEATURE_VERSION,
            'decision_version': 'mtg.decision.v1', 'feature_schema_sha256': codec.FEATURE_SCHEMA_SHA256}
    row = {'state': value, 'action': pack(1), 'return': 1.}
    fn = train_qv.train_samples
    if entry == 'preference':
        row = {'state': value, 'preferred': pack(1), 'alternatives': [pack(-1)]}
        fn = trainer.train_preferences
    original = builtins.__import__

    def importing(name, *a, **kw):
        assert name.split('.')[0] != 'torch', 'Invalid input imported Torch'
        return original(name, *a, **kw)

    monkeypatch.setattr(builtins, '__import__', importing)
    with pytest.raises(ValueError):
        fn([row], **args)


def test_return_trainer_and_existing_cli_explicit_opt_in(tmp_path, monkeypatch):
    cpu()
    samples = [{'state': state(), 'action': pack(1), 'return': 1.}]
    raw, report = train_qv.train_samples(samples, **options())
    assert raw['activation'] == ACTIVATION and report['updates'] == 1
    assert any(x != 0 for x in raw['weights']['q_interaction.weight'][0])

    def load(*args, **kwargs):
        return {'train': samples, 'eval': samples}, contract(), 'b' * 64, 'c' * 64

    monkeypatch.setattr(train_qv, 'load_samples', load)
    path = tmp_path / 'synthetic-cli.json'
    assert train_qv.main(['--dataset', str(tmp_path / 'sealed'), '--split', 'synthetic',
        '--out', str(path), '--seed', '17', '--engine-hash', 'a' * 64,
        '--epochs', '1', '--seconds', '60', '--q-activation', ACTIVATION]) == 0
    assert codec.load_checkpoint(path, expected=contract()).payload()['activation'] == ACTIVATION


def synthetic_rows():
    rows = []
    for group in range(8):
        for sign in (-1, 1):
            value = {'observation': {'players': {'self': {'life': 20}, 'opponent': {'life': 20}}},
                     'synthetic_context': sign,
                     'irrelevant_backdrop': {'n' + str(j): group + j for j in range(8)}}
            rows.append({'state': pack(value), 'preferred': pack(sign), 'alternatives': [pack(-sign)]})
    return rows


def test_matched_synthetic_latent_conditioning_at_fixed_seed_and_480_updates():
    torch = cpu()
    rows = synthetic_rows()
    before = deepcopy(rows)
    outcomes = {}
    for activation in (codec.LEGACY_ACTIVATION, codec.LIFE_CONTEXT_ACTIVATION, ACTIVATION):
        initial = train_qv.export_weights(train_qv.torch_model(seed=17, q_activation=activation))
        raw, report = trainer.train_preferences(rows, **options(q_activation=activation,
            epochs=60, seconds=90, learning_rate=.003, temperature=.25, value_weight=0,
            batch_size=2, batch_pairs=[[i, i + 1] for i in range(0, 16, 2)]))
        policy = codec.QVPolicy(raw, expected=contract())
        margins = [policy.predict(r['state'], r['preferred'])['q'] -
                   policy.predict(r['state'], r['alternatives'][0])['q'] for r in rows]
        flags = [m > 0 for m in margins]
        correct, pairs = sum(flags), sum(all(flags[i:i + 2]) for i in range(0, 16, 2))
        outcomes[activation] = (correct, pairs)
        print('synthetic conditioning only:', activation, correct, pairs, min(margins))
        assert report['updates'] == report['optimizer_updates'] == raw['provenance']['updates'] == 480
        assert report['row_exposures'] == 960 and report['samples'] == 16
        assert report['value_samples'] == 0 and report['final']['v_mse'] is None
        assert report['final']['parity_actions'] == 32 and report['final']['max_parity_error'] < 1e-9
        assert report['ranking_loss_input'] == 'unbounded_q_logits'
        for name in ('v_hidden.weight', 'v_hidden.bias', 'v_out.weight', 'v_out.bias'):
            assert raw['weights'][name] == initial[name]
        if activation == ACTIVATION:
            assert min(margins) > .9
            assert any(x != 0 for x in raw['weights']['q_interaction.weight'][0])
        assert rows == before
    assert outcomes == {codec.LEGACY_ACTIVATION: (8, 0), codec.LIFE_CONTEXT_ACTIVATION: (8, 0),
                        ACTIVATION: (16, 8)}
