"""Synthetic protocol offers test choice transport, not land legality or AI strength."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.action_contract import complete_action
from rules_engine.action_validation import ActionRejected


def land_guard():
    path = Path(__file__).resolve().parents[1] / 'main.py'
    tree = ast.parse(path.read_bytes())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'_force_ai_land_action', '_step_key'}]
    assert len(functions) == 2
    namespace = dict(compute_max_land_plays_this_turn=lambda state, seat: 1,
                     complete_action=complete_action, ActionRejected=ActionRejected)
    module = ast.Module(body=[ast.ImportFrom(module='__future__',
        names=[ast.alias(name='annotations')], level=0), *functions], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace['_force_ai_land_action']


def match_for(seat, picked):
    state = SimpleNamespace(pregame_pending=False, stack=[], active_player=seat,
                            step='precombat_main', turn=1,
                            players={seat: SimpleNamespace(last_land_play_turn=0)})
    chooser = SimpleNamespace(choose_action=lambda *_: SimpleNamespace(action=picked))
    return SimpleNamespace(state=state, ai={seat: chooser})


def offers():
    # Opaque protocol permission keys and display metadata are deliberate, not real cards.
    base = dict(type='play_land', card_id='protocol-land', from_graveyard=True,
                selected_face_index=1, card_name='Synthetic land-choice protocol')
    return [dict(base, entry_choice='tapped'),
            dict(base, entry_choice='tapped', graveyard_permission_key='protocol-grant-1'),
            dict(base, entry_choice='pay_two_life', graveyard_permission_key='protocol-grant-2')]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('typed', [False, True])
@pytest.mark.parametrize('selected', [0, 1, 2])
def test_complete_selected_offer_survives(seat, typed, selected):
    moves = offers()
    before = deepcopy(moves)
    picked = complete_action(moves[selected]) if typed else deepcopy(moves[selected])
    result = land_guard()(match_for(seat, picked), seat, moves)
    assert result is moves[selected]
    assert complete_action(result) == complete_action(picked)
    assert moves == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('typed', [False, True])
def test_entry_choice_is_preserved_independently(seat, typed):
    base = dict(type='play_land', card_id='protocol-land', from_graveyard=True,
                graveyard_permission_key='protocol-grant', selected_face_index=1)
    moves = [dict(base, entry_choice='tapped'), dict(base, entry_choice='pay_two_life')]
    before = deepcopy(moves)
    picked = complete_action(moves[1]) if typed else deepcopy(moves[1])
    result = land_guard()(match_for(seat, picked), seat, moves)
    assert result is moves[1]
    assert complete_action(result) == complete_action(picked)
    assert moves == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('picked', [dict(type='pass_priority'),
    dict(type='play_land', card_id='not-offered'),
    dict(type='play_land', card_id='protocol-land', selected_face_index=1, entry_choice='invalid')])
def test_invalid_or_unoffered_choice_keeps_offered_fallback(seat, picked):
    moves = offers()
    assert land_guard()(match_for(seat, picked), seat, moves) is moves[0]
