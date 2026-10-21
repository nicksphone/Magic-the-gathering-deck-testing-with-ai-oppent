"""Execute the workflow's real report projector using synthetic public XML only."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


WORKFLOW = Path(__file__).resolve().parents[3] / '.github/workflows/browser-recovery-localization.yml'
PREFIX = '::notice title=Recovery unit compatibility result::'


class RecoveryUnitReportTests(unittest.TestCase):
    def project(self, count=212, *, skipped=False, runner_exit=0):
        source = WORKFLOW.read_text()
        marker = "<<'PYTHON' || summary_status=$?\n"
        self.assertEqual(source.count(marker), 1)
        body = textwrap.dedent(source.split(marker, 1)[1].split('          PYTHON\n', 1)[0])
        self.assertIn('ET.parse(report)', body)
        suite = ET.Element('testsuite')
        for index in range(count):
            case = ET.SubElement(suite, 'testcase', name=f'public-protocol-{index}')
            if skipped and index == 0:
                ET.SubElement(case, 'skipped')
        output = io.StringIO()
        code = None
        with tempfile.TemporaryDirectory(prefix='mtg-recovery-report-') as root:
            report = Path(root) / 'public.xml'
            ET.ElementTree(suite).write(report, encoding='utf-8')
            with patch.object(sys, 'argv', ['-', str(report), str(runner_exit)]), redirect_stdout(output):
                try:
                    exec(compile(body, str(WORKFLOW), 'exec'), {'__name__': '__main__'})
                except SystemExit as error:
                    code = error.code
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith(PREFIX))
        return code, json.loads(lines[0][len(PREFIX):])

    def test_actual_projector_accepts_current_ordinary_cohort(self):
        code, summary = self.project()
        self.assertIsNone(code)
        self.assertEqual(summary, {'schema': 1, 'cases': 212, 'runner_exit': 0,
                                   'failures': 0, 'errors': 0, 'skipped': 0})

    def test_actual_projector_rejects_stale_partial_extra_skipped_or_invalid_status(self):
        for options in ({'count': 183}, {'count': 200}, {'count': 201}, {'count': 202},
                        {'count': 211}, {'count': 213},
                        {'skipped': True}, {'runner_exit': -1}, {'runner_exit': 256}):
            with self.subTest(options=options):
                code, _ = self.project(**options)
                self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
