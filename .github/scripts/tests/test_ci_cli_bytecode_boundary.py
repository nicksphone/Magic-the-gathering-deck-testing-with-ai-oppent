"""Actual ancestor-CLI argv and owned-import bytecode controls; no application."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_ci_backend_metadata_symlink_ancestors as ancestor


class MetadataCliBytecodeTests(unittest.TestCase):
    def subject(self, root):
        subject = ancestor.AncestorSymlinkTests('runTest')
        subject.root = root
        subject.fixture = SimpleNamespace(repo=root / 'source')
        return subject

    def test_actual_cli_passes_explicit_no_bytecode_with_isolation(self):
        with tempfile.TemporaryDirectory(prefix='cli-bytecode-argv-') as directory:
            root = Path(directory)
            subject = self.subject(root)
            with patch.object(ancestor.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=0, stdout='', stderr='')) as run:
                subject.cli(root / 'evidence', root / 'output.json')
            run.assert_called_once()
            argv = run.call_args.args[0]
            self.assertEqual(argv[:4], [sys.executable, '-I', '-B', '-c'])
            self.assertEqual(argv[5:], [str(ancestor.fixtures.SCRIPTS / 'ci_backend_metadata.py'),
                                       str(root / 'evidence'), str(root / 'source'),
                                       str(root / 'output.json')])
            self.assertEqual(run.call_args.kwargs['env'], {'PATH': ancestor.os.defpath,
                                                          'HOME': str(root)})

    def test_actual_cli_owned_import_does_not_create_bytecode(self):
        with tempfile.TemporaryDirectory(prefix='cli-bytecode-native-') as directory:
            root = Path(directory)
            scripts = root / 'scripts'
            scripts.mkdir()
            (scripts / 'owned_import.py').write_text('VALUE = 7\n')
            (scripts / 'ci_backend_metadata.py').write_text(
                'import importlib.util, json, sys\n'
                'from pathlib import Path\n'
                'path = Path(__file__).with_name("owned_import.py")\n'
                'spec = importlib.util.spec_from_file_location("owned_import", path)\n'
                'module = importlib.util.module_from_spec(spec)\n'
                'spec.loader.exec_module(module)\n'
                'Path(sys.argv[3]).write_text(json.dumps({"value": module.VALUE,\n'
                '    "dont_write_bytecode": sys.dont_write_bytecode}))\n')
            subject = self.subject(root)
            output = root / 'output.json'
            with patch.object(ancestor.fixtures, 'SCRIPTS', scripts):
                result = subject.cli(root / 'evidence', output)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, '')
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(output.read_text()),
                             {'value': 7, 'dont_write_bytecode': True})
            self.assertEqual(list(root.rglob('*.pyc')), [])
            self.assertEqual(list(root.rglob('__pycache__')), [])


if __name__ == '__main__':
    unittest.main()
