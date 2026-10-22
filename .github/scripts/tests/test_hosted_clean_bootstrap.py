"""Evaluate the actual closed GitHub job expression, not a duplicate policy."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

REPO = 'nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent'
REF = 'refs/heads/codex/hosted-clean-install-20261022'
PATH = Path(__file__).resolve().parents[3] / '.github/workflows/hosted-clean-install.yml'


class HostedBootstrapTests(unittest.TestCase):
    def allowed(self, event, before, ref=REF, repo=REPO):
        lines = [line.strip()[4:] for line in PATH.read_text().splitlines() if line.startswith('    if: ')]
        self.assertEqual(len(lines), 1, 'Exactly one real top-level job admission expression')
        expression = lines[0].replace('&&', ' and ').replace('||', ' or ').strip()
        tree = ast.parse(expression, mode='eval')
        allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq,
                   ast.Attribute, ast.Name, ast.Load, ast.Constant)
        self.assertTrue(all(isinstance(node, allowed) for node in ast.walk(tree)))
        context = SimpleNamespace(repository=repo, event_name=event, ref=ref,
                                  event=SimpleNamespace(before=before))
        return eval(compile(tree, 'actual-workflow-expression', 'eval'), {'__builtins__': {}}, {'github': context})

    def test_first_exact_branch_creation_and_future_manual_only(self):
        self.assertTrue(self.allowed('push', '0' * 40))
        self.assertTrue(self.allowed('workflow_dispatch', None))
        for event, before, ref, repo in (
            ('push', 'a' * 40, REF, REPO), ('push', '0' * 40, 'refs/heads/main', REPO),
            ('pull_request', '0' * 40, REF, REPO), ('push', '0' * 40, REF, 'foreign/repo')):
            with self.subTest(event=event, before=before, ref=ref, repo=repo):
                self.assertFalse(self.allowed(event, before, ref, repo))

    def test_push_trigger_is_exact_not_main_or_wildcard(self):
        text = PATH.read_text()
        self.assertIn('  push:', text)
        self.assertIn('      - codex/hosted-clean-install-20261022', text)
        self.assertIn('      - .github/workflows/hosted-clean-install.yml', text)
        self.assertNotIn('branches: [main]', text)
