"""Workflow wiring controls only; no application, browser, SQL or network."""
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


WORKFLOW = Path(__file__).resolve().parents[3] / '.github/workflows/browser-recovery-localization.yml'


class LocalizationWorkflowTests(unittest.TestCase):
    def test_focused_diagnostic_has_explicit_service_origins(self):
        source = WORKFLOW.read_text()
        for key, value in (
            ('MTG_FRONTEND_ORIGIN', 'http://127.0.0.1:15173'),
            ('MTG_BACKEND_ORIGIN', 'http://127.0.0.1:10199'),
        ):
            self.assertIn(f'{key}: {value}', source)

    def test_actual_shell_preserves_primary_failure_and_fails_closed_on_port_checks(self):
        source = WORKFLOW.read_text()
        body = textwrap.dedent(source.split('Focused transport and start recovery, not the full UI suite', 1)[1]
                               .split('run: |\n', 1)[1])
        self.assertIn('browser-cors-transport-diagnostic.mjs browser-start-recovery.mjs', body)
        mocks = '''
timeout() { return "$PROGRAM_STATUS"; }
ss() { printf '%s' "$PORT_OUTPUT"; return "$QUERY_STATUS"; }
'''
        for program, query, ports, expected in (
            (0, 0, '', 0), (0, 0, 'LISTEN fixture', 1),
            (0, 2, '', 1), (23, 0, '', 23),
            (124, 0, 'LISTEN fixture', 124), (23, 2, '', 23),
        ):
            with self.subTest(program=program, query=query, ports=ports):
                with tempfile.TemporaryDirectory(prefix='mtg-localization-shell-') as root:
                    result = subprocess.run(['/usr/bin/bash', '--noprofile', '--norc', '-c', mocks + body],
                        cwd=root, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': root,
                                       'PROGRAM_STATUS': str(program), 'QUERY_STATUS': str(query),
                                       'PORT_OUTPUT': ports}, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
