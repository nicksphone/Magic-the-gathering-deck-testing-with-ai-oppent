"""Pure callback-admission controls; Torch remains an optional lazy import."""
import builtins
import inspect
import unittest
from unittest.mock import patch

from scripts import train_qv
from tests.test_learned_qv import contract, number


class ProgressAdmissionTests(unittest.TestCase):
    def test_progress_is_optional_keyword_with_inert_default(self):
        parameter = inspect.signature(train_qv.train_samples).parameters.get('progress')
        self.assertIsNotNone(parameter, 'Missing optional training progress callback')
        self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(parameter.default)

    def test_invalid_progress_fails_before_any_torch_import(self):
        self.assertIn('progress', inspect.signature(train_qv.train_samples).parameters,
                      'Missing optional training progress callback')
        original_import = builtins.__import__

        def importing(name, *args, **kwargs):
            if name.split('.')[0] == 'torch':
                self.fail('Invalid callback must fail before Torch import')
            return original_import(name, *args, **kwargs)

        samples = [{'state': number(1), 'action': number(0), 'return': 1.0}]
        with patch('builtins.__import__', side_effect=importing):
            for invalid in (False, 0, [], {}, 'not callable'):
                with self.subTest(kind=type(invalid).__name__):
                    with self.assertRaisesRegex(ValueError, 'progress.*callable'):
                        train_qv.train_samples(samples, contract=contract(),
                            dataset_sha256='b' * 64, split_sha256='c' * 64,
                            seed=17, epochs=1, seconds=30, progress=invalid)
