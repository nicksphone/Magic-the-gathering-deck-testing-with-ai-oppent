"""Stdlib-only collection-order contracts; never import the gameplay module."""
import ast
from collections import Counter
import json
from pathlib import Path
import unittest


HERE = Path(__file__).parent
PUBLIC_ROWS = (
    ('blood-artist.json', 'Blood Artist'),
    ('darksteel-colossus.json', 'Darksteel Colossus'),
    ('descend-upon-the-sinful.json', 'Descend upon the Sinful'),
    ('final-judgment.json', 'Final Judgment'),
    ('glorious-anthem.json', 'Glorious Anthem'),
    ('humility.json', 'Humility'),
    ('island.json', 'Island'),
    ('llanowar-elves.json', 'Llanowar Elves'),
    ('plains.json', 'Plains'),
    ('raise-the-alarm.json', 'Raise the Alarm'),
    ('ray-of-command.json', 'Ray of Command'),
    ('sunfall.json', 'Sunfall'),
)


class MassExileCollectionOrderTests(unittest.TestCase):
    def _fixture_rows(self):
        directory = HERE / 'fixtures' / 'mass_exile_audit'
        return [json.loads((directory / filename).read_text(encoding='utf-8'))
                for filename, _ in PUBLIC_ROWS]

    def _actual_orders(self):
        path = HERE / 'test_mass_exile_lifecycle_audit.py'
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'test_official_full_raw_receipt']
        self.assertEqual(len(functions), 1)
        decorators = [node for node in functions[0].decorator_list
                      if isinstance(node, ast.Call)
                      and ast.unparse(node.func) == 'pytest.mark.parametrize'
                      and node.args and isinstance(node.args[0], ast.Constant)
                      and node.args[0].value == 'name']
        self.assertEqual(len(decorators), 1)
        self.assertEqual(len(decorators[0].args), 2)
        argument = decorators[0].args[1]
        # Evaluate only this finite real decorator argument, never module code.
        self.assertIsInstance(argument, ast.Call)
        self.assertIsInstance(argument.func, ast.Name)
        self.assertIn(argument.func.id, ('list', 'sorted'))
        self.assertEqual(len(argument.args), 1)
        self.assertIsInstance(argument.args[0], ast.Name)
        self.assertEqual(argument.args[0].id, 'ROWS')
        self.assertEqual(argument.keywords, [])
        code = compile(ast.Expression(argument), str(path), 'eval')
        rows = self._fixture_rows()
        results = []
        for sequence in (rows, list(reversed(rows))):
            namespace = {'ROWS': {row['name']: row for row in sequence}}
            result = eval(code, {'__builtins__': {}, 'list': list, 'sorted': sorted}, namespace)
            self.assertIs(type(result), list)
            self.assertTrue(all(type(name) is str for name in result))
            results.append(result)
        return results

    def test_exact_twelve_public_fixture_names(self):
        names = [row['name'] for row in self._fixture_rows()]
        self.assertEqual(names, [name for _, name in PUBLIC_ROWS])
        self.assertEqual(len(names), 12)
        self.assertEqual(len(set(names)), 12)

    def test_actual_decorator_order_is_independent_of_row_insertion(self):
        forward, reverse = self._actual_orders()
        self.assertEqual(forward, reverse)

    def test_actual_decorator_conserves_every_public_row_once(self):
        expected = Counter(name for _, name in PUBLIC_ROWS)
        for order in self._actual_orders():
            self.assertEqual(len(order), 12)
            self.assertEqual(Counter(order), expected)
