"""Public canonical controls only; pure projections, not HTTP/SQL qualification."""
import ast
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import importlib.util
from pathlib import Path
import sys
import threading

import pytest

from game_state.serializers import serialize_match, serialize_match_snapshot
from game_state.series_policy import game_seed, next_play_draw_chooser
from game_state.state import Zone
from rules_engine.engine import RulesEngine
from rules_engine.optional_reveal import public_choice
from rules_engine.stack_engine import resolve_top_of_stack


BACKEND = Path(__file__).resolve().parents[1]
PUBLIC_FIELDS = {'kind', 'player_id', 'label', 'count', 'min_count'}
ACTOR_FIELDS = PUBLIC_FIELDS | {'type', 'options', 'option_labels', 'option_type_lines'}
INTERNAL_FIELDS = {'followup_effect', 'effect_controller', 'resolving_item'}


def canonical_controls():
    path = BACKEND / 'tests/test_canonical_daretti_full_body_contract.py'
    spec = importlib.util.spec_from_file_location('owned_public_daretti', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CANONICAL = canonical_controls()


def native_controller_projection():
    # Execute exact public definitions, avoiding application's storage import/lifespan.
    path = BACKEND / 'main.py'
    tree = ast.parse(path.read_text(), filename=str(path))
    names = {'MatchController', '_serialize_match_controller', '_next_play_draw_chooser'}
    nodes = [node for node in tree.body if getattr(node, 'name', None) in names]
    assert {node.name for node in nodes} == names
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    selected = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    namespace = {'__name__': 'owned_native_controller_projection', 'dataclass': dataclass,
                 'field': field, 'threading': threading, 'serialize_match': serialize_match,
                 'game_seed': game_seed, 'next_play_draw_chooser': next_play_draw_chooser}
    module = type(sys)('owned_native_controller_projection')
    module.__dict__.update(namespace)
    sys.modules[module.__name__] = module
    exec(compile(selected, str(path), 'exec'), module.__dict__)
    return module


CONTROLLER = native_controller_projection()


def main_prompt(state, actor_control='human'):
    controls = {1: 'human', 2: 'human'}
    controls[state.pending_mechanic_choice['player_id']] = actor_control
    match = CONTROLLER.MatchController(
        state=state, rules=RulesEngine(), controllers=controls, ai={}, mode='local',
        deck_ids=(None, None), mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=1)
    return CONTROLLER._serialize_match_controller(match)['pending_mechanic_choice']


def paused(seat, restore):
    state = CANONICAL.board(seat)
    hand = [CANONICAL.put(state, f'generated-private-hand-{seat}-{i}', Zone.HAND,
                          owner=seat, types=('Land',)).id for i in range(3)]
    state = CANONICAL.activate(state, seat, 0)
    popped = state.stack[-1]
    assert resolve_top_of_stack(state) is False
    pending = state.pending_mechanic_choice
    assert pending['resolving_item'] == asdict(popped)
    assert pending['followup_effect'] == {
        'effect_key': 'draw_cards', 'payload': {}, 'count_field': 'amount'}
    assert pending['effect_controller'] == seat
    assert pending['options'] == hand
    if restore:
        state = CANONICAL.restored(state)
    assert state.cards['daretti'].oracle_text == CANONICAL.RAW_BODY
    return state, hand


def prompt_expected(seat):
    return {'kind': 'discard', 'player_id': seat, 'label': 'Choose any number of cards to discard',
            'count': 2, 'min_count': 0}


def actor_expected(seat, hand):
    return {**prompt_expected(seat), 'type': 'choose_mechanic', 'options': list(hand),
            'option_labels': {cid: cid for cid in hand},
            'option_type_lines': {cid: 'Land' for cid in hand}}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('boundary', ['public-choice', 'spectator-serializer', 'main-controller'])
def test_public_discard_prompt_never_exposes_private_options_or_continuation(
        seat, count, restore, boundary):
    state, hand = paused(seat, restore)
    before = deepcopy(serialize_match_snapshot(state))
    if boundary == 'public-choice':
        view = public_choice(state.pending_mechanic_choice)
    elif boundary == 'spectator-serializer':
        view = serialize_match(state, look_players=())['pending_mechanic_choice']
    else:
        view = main_prompt(state)
    assert serialize_match_snapshot(state) == before
    assert set(view) == PUBLIC_FIELDS
    assert view == prompt_expected(seat)
    result = CANONICAL.choose(state, seat, hand[:count])
    assert result.discards_this_turn[seat] == result.draws_this_turn[seat] == count


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_actor_discard_hint_retains_authorized_options_but_no_engine_continuation(
        seat, count, restore):
    state, hand = paused(seat, restore)
    before = deepcopy(serialize_match_snapshot(state))
    assert RulesEngine().legal_moves(state, 3-seat) == []
    hints = RulesEngine().legal_moves(state, seat)
    assert len(hints) == 1
    view = hints[0]
    assert view['options'] == hand
    assert view['option_labels'] == {cid: cid for cid in hand}
    assert view['option_type_lines'] == {cid: 'Land' for cid in hand}
    assert serialize_match_snapshot(state) == before
    assert set(view) == ACTOR_FIELDS
    assert view == actor_expected(seat, hand)
    result = CANONICAL.choose(state, seat, hand[:count])
    assert result.discards_this_turn[seat] == result.draws_this_turn[seat] == count


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count', [0, 1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_all_current_projections_leave_real_pending_root_and_native_resolution_unchanged(
        seat, count, restore):
    state, hand = paused(seat, restore)
    before = deepcopy(serialize_match_snapshot(state))
    pending_object = state.pending_mechanic_choice
    frame_object = pending_object['resolving_item']
    followup_object = pending_object['followup_effect']
    options_object = pending_object['options']
    for _ in range(2):
        public_choice(pending_object)
        serialize_match(state, look_players=())
        main_prompt(state)
        RulesEngine().legal_moves(state, seat)
        assert serialize_match_snapshot(state) == before
        assert state.pending_mechanic_choice is pending_object
        assert pending_object['resolving_item'] is frame_object
        assert pending_object['followup_effect'] is followup_object
        assert pending_object['options'] is options_object
    result = CANONICAL.choose(state, seat, hand[:count])
    assert serialize_match_snapshot(state) == before
    assert result.cards['daretti'].oracle_text == CANONICAL.RAW_BODY
    assert result.cards['daretti'].loyalty == 5
    assert result.discards_this_turn[seat] == result.draws_this_turn[seat] == count
    assert result.players[seat].graveyard == hand[:count]
    assert len(result.players[seat].hand) == 3
    assert len(result.players[seat].library) == 8-count
    assert not result.pending_mechanic_choice and not result.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_ai_controller_summary_stays_bounded(seat):
    state, _ = paused(seat, False)
    before = deepcopy(serialize_match_snapshot(state))
    assert main_prompt(state, 'ai') == {
        'kind': 'discard', 'player_id': seat, 'label': 'AI is making a choice'}
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('optional', [False, True])
def test_discard_projection_protocol_omits_unknown_fields_and_preserves_absence(seat, optional):
    # Projection-only descriptor, not an injected gameplay choice.
    pending = {'kind': 'discard', 'player_id': seat, 'label': 'Discard', 'count': 1,
               'options': ['generated-private'], '__unknown_future_context': {'private': 'generated'}}
    expected = {'kind': 'discard', 'player_id': seat, 'label': 'Discard', 'count': 1}
    if optional:
        pending['min_count'] = expected['min_count'] = 0
    before = deepcopy(pending)
    assert public_choice(pending) == expected
    assert pending == before


@pytest.mark.parametrize('kind,fields', [
    ('search_library', ['kind', 'player_id', 'label', 'count', 'min_count']),
    ('optional_search', ['kind', 'player_id', 'label', 'count', 'min_count']),
    ('land_from_hand', ['kind', 'player_id', 'label', 'count', 'min_count']),
    ('optional_reveal', ['kind', 'player_id', 'label', 'count']),
    ('hand_top_order', ['kind', 'player_id', 'options', 'count', 'min_count', 'label',
                        'option_labels', 'option_type_lines']),
    ('entry_mode', ['kind', 'player_id', 'label', 'options', 'option_labels', 'count']),
    ('legend_rule', None), ('legacy_unknown', None),
])
def test_other_public_choice_protocol_families_remain_unchanged(kind, fields):
    pending = {'kind': kind, 'player_id': 1, 'label': 'Generated public prompt', 'count': 1,
               'min_count': 0, 'options': ['generated-option'],
               'option_labels': {'generated-option': 'Generated'},
               'option_type_lines': {'generated-option': 'Land'},
               'effect_payload': {'generated': True}}
    before = deepcopy(pending)
    expected = pending if fields is None else {key: pending[key] for key in fields}
    assert public_choice(pending) == expected
    assert pending == before


def test_no_pending_choice_remains_none():
    assert public_choice(None) is None
