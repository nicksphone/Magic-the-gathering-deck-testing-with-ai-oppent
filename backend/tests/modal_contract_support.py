"""Bind the actual CI fixture's pure state factory without its SQL/server module."""
import ast
import hashlib
from pathlib import Path
from game_state.state import MatchFactory, Step, Zone, CardInstance, StackItem
from rules_engine.engine import RulesEngine

def canonical_fixture(face_kind=''):
    path = Path(__file__).with_name('browser_fixture_server.py')
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'fixture')
    assert hashlib.sha256(ast.get_source_segment(path.read_text(), node).encode()).hexdigest() == '4a5f59f073fec8958da4f57ef4a9f83ead9c94e110f9e383a75c83262da2a2bd'
    node.decorator_list = []
    namespace = {'__file__': str(path), 'Path': Path, 'MatchFactory': MatchFactory,
                 'Step': Step, 'Zone': Zone, 'CardInstance': CardInstance, 'StackItem': StackItem,
                 'RulesEngine': RulesEngine, 'publish': lambda state, deck: (state, deck)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    state, _ = namespace['fixture'](modal=True, face_kind=face_kind)
    return state
