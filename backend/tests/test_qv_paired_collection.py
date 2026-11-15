"""Pure optional-dependency boundary; no fitting or gameplay quality claim."""
import builtins
import importlib.util
from pathlib import Path


def test_paired_sampler_module_imports_without_loading_optional_torch(monkeypatch):
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        assert name.split('.')[0] != 'torch', 'Collection imported optional Torch'
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', importing)
    path = Path(__file__).with_name('test_qv_paired_batches.py')
    spec = importlib.util.spec_from_file_location('paired_sampler_without_torch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.test_invalid_batch_pairs_rejected_before_torch)
    assert callable(module.test_paired_optimizer_matches_independent_per_pair_mean_and_order)
