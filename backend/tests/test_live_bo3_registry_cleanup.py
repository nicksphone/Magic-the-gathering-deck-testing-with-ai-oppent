"""Original function with inert callbacks: registry scope, not HTTP/SQL proof."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


def exercise(fault=None):
    path = Path(__file__).with_name('test_live_bo3_policy.py')
    node = next(n for n in ast.parse(path.read_bytes()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'test_http_choice_and_restored_seed_provenance')
    original = {'existing-a': object(), 'existing-b': object()}
    registry = dict(original)
    events = []
    persisted = {'unrelated-row': object(), 'training-row': object()}
    before_rows = dict(persisted)
    match = SimpleNamespace(state=SimpleNamespace(id='inert-current', hands=(1, 2)))

    class Client:
        def __init__(self, _app):
            pass

        def __enter__(self):
            events.append('enter')
            registry['enter-only'] = object()
            if fault == 'enter':
                raise RuntimeError('inert enter failure')
            return self

        def __exit__(self, *_args):
            events.append('context-closed')
            registry['exit-only'] = object()
            if fault == 'exit':
                raise RuntimeError('inert exit failure')

        def post(self, path, json):
            if path.endswith('/sideboard'):
                return SimpleNamespace(raise_for_status=lambda: None)
            if json['player_id'] == 1:
                return SimpleNamespace(status_code=422)
            return SimpleNamespace(status_code=200, text='inert', json=lambda: {
                'active_player': 1, 'game_seed': None})

    class Session:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    def restore(_repo):
        registry['training-row'] = object()
        registry[match.state.id] = SimpleNamespace(state=match.state, root_seed=91)
        if fault == 'restore':
            raise RuntimeError('inert restore failure')

    namespace = dict(ACTIVE_MATCHES=registry, _match=lambda: match, TestClient=Client,
        app=object(), Session=Session, engine=object(), Repository=lambda session: session,
        _restore_active_matches=restore, _serialize_match_controller=lambda value: {'game_seed': None},
        _controller_snapshot=lambda value: {'root_seed': 91}, _hands=lambda state: state.hands)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    error = None
    try:
        namespace[node.name]()
    except RuntimeError as caught:
        error = caught
    return registry, original, namespace['ACTIVE_MATCHES'], events, persisted, before_rows, error


class RegistryCleanupControls(unittest.TestCase):
    def verify(self, fault):
        registry, original, exported, events, persisted, rows, error = exercise(fault)
        self.assertIs(registry, exported)
        self.assertEqual(set(registry), set(original))
        for key, value in original.items():
            self.assertIs(registry[key], value)
        self.assertEqual(persisted, rows)
        if fault:
            self.assertIsInstance(error, RuntimeError)
        else:
            self.assertIsNone(error)
        if fault != 'enter':
            self.assertIn('context-closed', events)

    def test_seeded_controllers_normal_scope(self):
        self.verify(None)

    def test_seeded_controllers_restore_error(self):
        self.verify('restore')

    def test_seeded_controllers_context_exit_error(self):
        self.verify('exit')

    def test_seeded_controllers_context_enter_error(self):
        self.verify('enter')


if __name__ == '__main__':
    unittest.main()
