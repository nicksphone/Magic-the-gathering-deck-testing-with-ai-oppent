"""Pure regressions for ownership checks across a cold fixture restart."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from fastapi import HTTPException


class OwnedReloadTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name('suspend_composition_fixture.py')
        tree = ast.parse(source.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'owned')
        self.card = object()
        self.match = SimpleNamespace(state=SimpleNamespace(log=['owned'], cards={'source': self.card}))
        self.loads = []
        self.saved = self.match

        def load(match_id):
            self.loads.append(match_id)
            return self.saved

        self.main = SimpleNamespace(ACTIVE_MATCHES={}, _load_saved_match=load)
        namespace = {'main': self.main, 'CLAIM': 'owned', 'HTTPException': HTTPException,
                     'instruction': lambda card: {'supported': True}}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        self.owned, self.namespace = namespace['owned'], namespace

    def test_cold_match_is_loaded_before_ownership_is_checked(self):
        try:
            result = self.owned('cold-match', 'source')
        except HTTPException as error:
            self.fail(f'Cold fixture rejected the saved match: {error.status_code}')
        self.assertEqual(result, (self.match, self.card))
        self.assertEqual(self.loads, ['cold-match'])

    def test_hot_match_does_not_reload_persistence(self):
        self.main.ACTIVE_MATCHES['hot-match'] = self.match
        self.assertEqual(self.owned('hot-match', 'source'), (self.match, self.card))
        self.assertEqual(self.loads, [])

    def test_missing_saved_match_stays_not_found(self):
        self.saved = None
        with self.assertRaises(HTTPException) as caught:
            self.owned('missing', 'source')
        self.assertEqual(caught.exception.status_code, 404)

    def test_unowned_saved_match_is_not_appropriated(self):
        self.match.state.log = []
        with self.assertRaises(HTTPException) as caught:
            self.owned('other-match', 'source')
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.loads, ['other-match'])

    def test_unowned_cached_match_does_not_try_a_different_saved_match(self):
        self.main.ACTIVE_MATCHES['hot-match'] = SimpleNamespace(state=SimpleNamespace(log=[]))
        with self.assertRaises(HTTPException) as caught:
            self.owned('hot-match', 'source')
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.loads, [])

    def test_missing_card_after_reload_stays_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            self.owned('cold-match', 'absent')
        self.assertEqual(caught.exception.status_code, 422)

    def test_unsupported_card_after_reload_stays_rejected(self):
        self.namespace['instruction'] = lambda card: None
        with self.assertRaises(HTTPException) as caught:
            self.owned('cold-match', 'source')
        self.assertEqual(caught.exception.status_code, 422)


if __name__ == '__main__':
    unittest.main()
