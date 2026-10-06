"""Canonical normal-spell and independently queued cycling instructions."""
import hashlib
import json
from copy import copy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import spell_resolution_text
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_spell_trigger_surface_audit import (
    DIRECTORY, act, add, cards, install, offline_http, position, record, restore, settle,
)


SIBLINGS = {row['name']: row for row in map(
    json.loads, (DIRECTORY / 'sibling-families.jsonl').read_text().splitlines())}
cards.ROWS.update(SIBLINGS)
DELAYED = json.loads((DIRECTORY / 'delayed-control.jsonl').read_text())
cards.ROWS[DELAYED['name']] = DELAYED


def test_sibling_raw_fixture_hash():
    assert hashlib.sha256((DIRECTORY / 'sibling-families.jsonl').read_bytes()).hexdigest() == (
        '9bd7f14b101a44a490df36e3e54f1d8a15030ffe91019b1fef14ac67a43c3c75')


@pytest.mark.parametrize('name', ['Renewed Faith', 'Resounding Roar', 'Slice and Dice'])
def test_trigger_only_surface_is_not_stripped(name):
    state, source = position(1, name)
    trigger = copy(source)
    trigger.oracle_text = source.oracle_text.splitlines()[-1]
    with cards.unchanged_root(state):
        assert spell_resolution_text(trigger, trigger.oracle_text) == trigger.oracle_text


def test_delayed_trigger_creation_remains_an_ordinary_spell_instruction():
    state, source = position(1, 'Final Fortune')
    with cards.unchanged_root(state):
        assert spell_resolution_text(source, source.oracle_text) == source.oracle_text
    assert "At the beginning of that turn's end step" in source.oracle_text


@pytest.mark.parametrize('name', ['Resounding Roar', 'Slice and Dice'])
@pytest.mark.parametrize('seat', [1, 2])
def test_normal_spell_surface_excludes_its_independent_cycle_trigger(request, name, seat):
    state, source = position(seat, name)
    with cards.unchanged_root(state):
        surface = spell_resolution_text(source, source.oracle_text)
    record(request, {'oracle': source.oracle_text, 'surface': surface})
    assert 'When you cycle' not in surface
    assert surface.splitlines()[0] == source.oracle_text.splitlines()[0]


@pytest.mark.parametrize('seat', [1, 2])
def test_roar_actual_cast_only_grants_three_and_root_is_immutable(request, seat):
    state, source = position(seat, 'Resounding Roar')
    target = add(state, 'Krosan Tusker', seat)
    state.players[seat].mana_pool = {'C': 1, 'G': 1}
    with cards.unchanged_root(state):
        paid = checked_action(state, RulesEngine(), seat, cards.cast(source, targets={'target_card_id': target.id}))
    queued = serialize_match_snapshot(paid)
    assert resolve_top_of_stack(paid)
    record(request, {'queued': queued, 'resolved': serialize_match_snapshot(paid),
                     'power': effective_power(paid, target.id),
                     'toughness': effective_toughness(paid, target.id)})
    assert (effective_power(paid, target.id), effective_toughness(paid, target.id)) == (9, 8)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('cycling', [False, True])
def test_roar_actual_http_spell_and_legitimate_cycle_trigger_restart(request, offline_http, seat, cycling):
    state, source = position(seat, 'Resounding Roar')
    target = add(state, 'Krosan Tusker', seat)
    state.players[seat].mana_pool = {'C': 5, 'R': 1, 'G': 1, 'W': 1}
    match = install(state, seat, request)
    action = {'type': 'cycle_card' if cycling else 'cast_spell', 'card_id': source.id}
    if not cycling:
        action['targets'] = {'target_card_id': target.id}
    response = act(offline_http, match, seat, action)
    assert response.status_code == 200, response.text
    queued = serialize_match_snapshot(restore(state.id).state)
    match, choices = settle(offline_http, state.id, seat)
    record(request, {'queued': queued, 'choices': choices,
                     'resolved': serialize_match_snapshot(match.state),
                     'power': effective_power(match.state, target.id),
                     'toughness': effective_toughness(match.state, target.id)})
    assert not choices
    expected = (12, 11) if cycling else (9, 8)
    assert (effective_power(match.state, target.id), effective_toughness(match.state, target.id)) == expected
    assert match.state.draws_this_turn.get(seat, 0) == int(cycling)
