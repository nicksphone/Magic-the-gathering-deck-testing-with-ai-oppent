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
    assert hashlib.sha256(ast.get_source_segment(path.read_text(), node).encode()).hexdigest() == 'f2dc14a6efe794b7c0b1fef22ba030ef85866debff920961a2138baef13b66a1'
    node.decorator_list = []
    def publish(state, deck, *, capture_original_stock=True, mainboards=None):
        if type(capture_original_stock) is not bool:
            raise TypeError('capture_original_stock must be bool')
        if capture_original_stock is False:
            state.sideboard_facts = {}
        return state, deck

    namespace = {'__file__': str(path), 'Path': Path, 'MatchFactory': MatchFactory,
                 'Step': Step, 'Zone': Zone, 'CardInstance': CardInstance, 'StackItem': StackItem,
                 'RulesEngine': RulesEngine, 'publish': publish}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    state, _ = namespace['fixture'](modal=True, face_kind=face_kind)
    return state
