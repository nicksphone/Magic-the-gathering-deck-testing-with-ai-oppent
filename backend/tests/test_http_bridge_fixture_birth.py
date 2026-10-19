"""Real builder/setup-prefix projections only: no bridge import/auth/HTTP/SQL certificate."""
import ast
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from game_state.serializers import serialize_match_snapshot
from tests import test_private_choice_intent_boundary as private
from tests import test_optional_land_from_hand_audit as land

ROOT = Path(land.__file__).parent
# Exact public f1 setup body retained only as a default/RNG compatibility reference.
LEGACY_SETUP = "def setup(name, seat, *, eligible=True, drawn_land=False, shock=False):\n    state = position('Ramp', 'Tempo', seat)\n    state.mechanic_choice_players = {1, 2}\n    state.trigger_order_choice_players = {1, 2}\n    source = take(state, name, seat, Zone.HAND)\n    # Real paid casts use their exact canonical costs, never injected stack items.\n    take(state, 'Forest', seat, Zone.BATTLEFIELD)\n    take(state, 'Tropical Island', seat, Zone.BATTLEFIELD)\n    land = None\n    if eligible:\n        if shock:\n            from tests.test_contextual_cost_prohibitions import canonical\n            land = canonical(state, 'sacred-foundry', seat, Zone.HAND)\n        else:\n            land = take(state, 'Forest', seat, Zone.HAND)\n    take(state, 'Delver of Secrets', 3-seat, Zone.HAND)\n    # This is a rules fixture's predetermined draw, NOT an AI policy input.\n    draw = next(cid for cid in state.players[seat].library\n                if state.cards[cid].name == ('Forest' if drawn_land else 'Ugin, the Spirit Dragon'))\n    state.players[seat].library.remove(draw)\n    state.players[seat].library.append(draw)\n    player = state.players[seat]\n    player.lands_played_this_turn = player.land_plays_recorded_on_turn = 1\n    player.last_land_play_turn = state.turn\n    return state, source, land, draw\n"


def setup_prefix(kind, family, seat):
    name = 'private_choice_boundary_fixture_server.py' if kind == 'private' else 'optional_land_choice_http_fixture_server.py'
    tree = ast.parse((ROOT / name).read_text())
    function = deepcopy(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'fixture'))
    boundary = next(i for i, s in enumerate(function.body) if isinstance(s, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'controller' for t in s.targets))
    function.body = function.body[:boundary] + [ast.copy_location(ast.Return(ast.Name(id='state', ctx=ast.Load())), function.body[boundary])]
    function.decorator_list = []
    labels = tree if kind == 'private' else ast.parse((ROOT / 'cold_restart_http_fixture.py').read_text())
    key = 'LABEL' if kind == 'private' else 'LAND_LABEL'
    label = next(n.value.value for n in labels.body if isinstance(n, ast.Assign)
                 and isinstance(n.value, ast.Constant) and any(isinstance(t, ast.Name) and t.id == key for t in n.targets))
    namespace = dict(Request=Request, HTTPException=HTTPException, authorize=lambda request: None,
                     uuid4=uuid4, position=private.position, setup=land.setup, LABEL=label)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(ROOT / name), 'exec'), namespace)
    return namespace['fixture'](None, family, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind,family', [('private', 'delver'), ('private', 'officer'),
                                        ('optional', 'Growth Spiral'), ('optional', 'Arboreal Grazer')])
def test_bridge_setup_prefix_is_serializable_and_fresh(kind, family, seat):
    first = setup_prefix(kind, family, seat)
    snapshot = serialize_match_snapshot(first)
    second = setup_prefix(kind, family, seat)
    assert serialize_match_snapshot(second)
    assert first.id != second.id
    assert snapshot['id'] == first.id
    if first.sideboard_facts:
        assert first.sideboard_facts['game_id'] == first.id
    if family == 'officer':
        assert not first.sideboard_facts


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Growth Spiral', 'Arboreal Grazer'])
def test_optional_default_snapshot_retains_exact_old_setup(family, seat):
    tree = ast.parse(LEGACY_SETUP)
    old = deepcopy(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'setup'))
    old.name = 'legacy_setup'
    namespace = dict(land.setup.__globals__)
    exec(compile(ast.Module(body=[old], type_ignores=[]), 'unchanged-old-setup', 'exec'), namespace)
    before = namespace['legacy_setup'](family, seat)
    after = land.setup(family, seat)
    assert serialize_match_snapshot(before[0]) == serialize_match_snapshot(after[0])
    assert tuple(card.id if hasattr(card, 'id') else card for card in before[1:]) == tuple(card.id if hasattr(card, 'id') else card for card in after[1:])
    assert before[0].rng.getstate() == after[0].rng.getstate()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Growth Spiral', 'Arboreal Grazer'])
def test_optional_explicit_identity_is_captured_at_birth(family, seat):
    identifier = str(uuid4())
    state, source, selected, drawn = land.setup(family, seat, game_id=identifier)
    assert state.id == state.sideboard_facts['game_id'] == identifier
    assert serialize_match_snapshot(state)['id'] == identifier


@pytest.mark.parametrize('identifier', [True, 1, '', ' '])
def test_optional_birth_id_preserves_factory_validation(identifier):
    with pytest.raises(ValueError):
        land.setup('Growth Spiral', 1, game_id=identifier)
