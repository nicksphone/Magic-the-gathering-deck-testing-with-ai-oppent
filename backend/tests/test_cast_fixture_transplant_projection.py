"""Pure original setup-prefix projection, not HTTP/SQLite acceptance."""
import ast
from copy import deepcopy
import importlib
import inspect
from pathlib import Path

import pytest
import main
from card_data.seed_cards import seed_card_payload
from game_state.state import MatchFactory
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests import test_api_input_contracts as api
from tests import fixture_state_support as fixture_support

CASES = [
    ('tests.test_bestow', 'test_http_bestow_cost_target_and_snapshot_resume'),
    ('tests.test_cast_payment_choices', 'test_http_selection_is_strict_and_rejections_preserve_database'),
    ('tests.test_effect_cast_admission', 'test_api_cannot_forge_effect_permission'),
    ('tests.test_effect_cast_choices', 'test_http_saved_cast_permission_and_duplicate_rejection'),
]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('module_name,function_name', CASES)
def test_real_factory_setup_prefix_can_serialize_without_capture_repair(monkeypatch, seat, module_name, function_name):
    module = importlib.import_module(module_name)
    function = getattr(module, function_name)
    path = Path(inspect.getsourcefile(function))
    tree = ast.parse(path.read_text())
    original = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name)
    prefix = deepcopy(original)
    boundary = next(i for i, statement in enumerate(prefix.body)
                    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name) and statement.value.func.id == 'persist')
    prefix.body = prefix.body[:boundary + 1]
    prefix.decorator_list = []
    namespace = dict(function.__globals__)
    snapshots = []
    def serialize_only(controller):
        snapshots.append(serialize_match_snapshot(controller.state))
    monkeypatch.setattr(api, 'persist', serialize_only)
    namespace['persist'] = serialize_only
    exec(compile(ast.Module(body=[prefix], type_ignores=[]), str(path), 'exec'), namespace)
    deck = [{**seed_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=4)
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={}, mode='human_vs_human',
        deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=3, root_seed=4)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {state.id: controller})
    monkeypatch.setattr(main, '_persist_active_match', lambda repo, current: serialize_match_snapshot(current.state))
    original_adopt = fixture_support.adopt_fixture_state
    class ProjectionRepository:
        def delete_active_match(self, identifier):
            assert identifier == state.id
    def adopt_without_sql(current, replacement):
        return original_adopt(current, replacement, repo=ProjectionRepository())
    monkeypatch.setattr(fixture_support, 'adopt_fixture_state', adopt_without_sql)
    # No client operation exists in the projected prefix; the original actions remain outside this proof.
    namespace[function_name]((None, controller), seat)
    assert len(snapshots) == 1
    assert snapshots[0]['id'] == controller.state.id
