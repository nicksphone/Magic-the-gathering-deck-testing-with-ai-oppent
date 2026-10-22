"""Inspect real final exec operands without invoking a shell, setpriv or guest."""
from pathlib import Path
import shlex
from string import Template
import unittest


class HostedEntryOperandTests(unittest.TestCase):
    def test_env_i_forwards_both_admitted_ids_to_actual_guest_command(self):
        path = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean/entry.sh'
        text = path.read_text()
        self.assertIn('\nexec setpriv ', text)
        actual = shlex.split(text[text.index('\nexec setpriv '):].replace('\\\n', ' '))
        admitted = {'MTG_UID': '1001', 'MTG_GID': '1001',
                    'MTG_HEAD': 'a' * 40, 'ROOT': '/tmp/mtg-hosted-clean'}
        operands = [Template(value).substitute(admitted) for value in actual]
        env = operands.index('env')
        self.assertEqual(operands[env + 1], '-i')
        received = {}
        cursor = env + 2
        while cursor < len(operands) and '=' in operands[cursor]:
            key, value = operands[cursor].split('=', 1)
            self.assertTrue(key.isidentifier())
            self.assertNotIn(key, received)
            received[key] = value
            cursor += 1
        self.assertEqual(received.get('MTG_UID'), admitted['MTG_UID'])
        self.assertEqual(received.get('MTG_GID'), admitted['MTG_GID'])
        self.assertIn('--reuid=' + received['MTG_UID'], operands[:env])
        self.assertIn('--regid=' + received['MTG_GID'], operands[:env])
        self.assertEqual(received['MTG_HEAD'], admitted['MTG_HEAD'])
        self.assertEqual(set(received), {'PATH', 'HOME', 'TMPDIR', 'LANG',
                                        'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE',
                                        'MTG_HEAD', 'MTG_UID', 'MTG_GID'})
        self.assertEqual(operands[cursor:], ['/usr/bin/python3.12', '-B',
                                           '/public/ops/ci/hosted-clean/guest.py'])
