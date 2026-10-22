"""Read real root-stage PATH operands; never run the provisioning script."""
from pathlib import Path
import shlex
import unittest


class HostedProvisionPathTests(unittest.TestCase):
    def test_final_root_path_retains_system_sbin_for_real_account_commands(self):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/provision.sh'
        lines = path.read_text().replace('\\\n', ' ').splitlines()
        exports = []
        for line_number, line in enumerate(lines):
            operands = shlex.split(line, comments=True)
            if operands[:1] == ['export']:
                exports.extend((line_number, value.split('=', 1)[1])
                               for value in operands[1:] if value.startswith('PATH='))
        self.assertEqual(len(exports), 1, 'One explicit root toolchain PATH')
        declaration_line, value = exports[0]
        self.assertEqual(value.split(':'), ['/opt/go/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin'])
        for command in ('groupadd', 'useradd'):
            calls = [line_number for line_number, line in enumerate(lines)
                     if command in shlex.split(line, comments=True)]
            self.assertEqual(len(calls), 1, 'Keep the actual account-creation fallback')
            self.assertLess(declaration_line, calls[0])
