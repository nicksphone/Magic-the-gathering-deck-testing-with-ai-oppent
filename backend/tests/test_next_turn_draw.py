"""Canonical Aura and instant delayed draws use the ordinary durable stack."""
import json
from pathlib import Path

import pytest
from sqlmodel import Session

import main
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, serialize_card_view
from game_state.state import Step, Zone
from persistence.db import engine
from persistence.repository import Repository
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from rules_engine.mana import parse_mana_cost
from tests.test_ai_recurring_engines import add as raw_add, resolve
from tests.test_variable_mana import clean
from tests.test_combat_keyword_triggers import CARDS as COMBAT
from tests.test_api_input_contracts import game, persist

CARDS = dict(COMBAT)
for fixture in ('attached_scaling', 'delayed_draw'):
    CARDS.update({row['name']: row for row in json.loads(
        (Path(__file__).parent / 'fixtures' / (fixture + '.json')).read_text())})


def setup(name, seat):
    state = clean()
    state.active_player = state.priority_player = seat
    creature = raw_add(state, 'Grizzly Bears', seat, cards=CARDS)
    source = raw_add(state, name, seat, Zone.HAND, cards=CARDS)
    cost = parse_mana_cost(source.mana_cost)
    state.players[seat].mana_pool = {color: cost[color] for color in 'WUBRGC'}
    state.players[seat].mana_pool['C'] += cost['generic']
    action = {'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_card_id': creature.id}}
    return state, source.id, creature.id, action


def upkeep(state, turn, player):
    state.turn, state.active_player, state.priority_player = turn, player, player
    state.step = Step.UPKEEP
    RulesEngine()._apply_step_start_actions(state)


@pytest.mark.parametrize('name', ['Vampirism', 'Fevered Strength'])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('resume', [False, True])
def test_actual_cast_delays_draw_until_next_turn_upkeep(name, seat, resume):
    state, source, creature, action = setup(name, seat)
    state = checked_action(state, RulesEngine(), seat, action)
    before = len(state.players[seat].hand)
    state = resolve(state)
    assert len(state.players[seat].hand) == before
    assert len(state.delayed_triggers) == 1
    assert state.delayed_triggers[0]['earliest_turn'] == state.turn + 1
    assert effective_power(state, creature) == (4 if name == 'Fevered Strength' else 2)
    if resume:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    upkeep(state, state.turn, seat)
    assert not state.stack and len(state.delayed_triggers) == 1
    upkeep(state, state.turn + 1, 3 - seat)
    assert len(state.stack) == 1 and state.stack[0].controller == seat
    assert not state.delayed_triggers and len(state.players[seat].hand) == before
    state = resolve(state)
    assert len(state.players[seat].hand) == before + 1
    upkeep(state, state.turn + 1, seat)
    assert not state.stack and not state.delayed_triggers


@pytest.mark.parametrize('name', ['Vampirism', 'Fevered Strength'])
@pytest.mark.parametrize('seat', [1, 2])
def test_source_departure_does_not_cancel_saved_delayed_draw(name, seat):
    state, source, _, action = setup(name, seat)
    state = resolve(checked_action(state, RulesEngine(), seat, action))
    card = state.cards[source]
    if card.zone == Zone.BATTLEFIELD:
        state.players[seat].battlefield.remove(source)
        card.move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(source)
    before = len(state.players[seat].hand)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    upkeep(state, state.turn + 1, 3 - seat)
    state = resolve(state)
    assert len(state.players[seat].hand) == before + 1


@pytest.mark.parametrize('seat', [1, 2])
def test_copied_instant_creates_independent_next_turn_draws(seat):
    state, _, _, action = setup('Fevered Strength', seat)
    state = checked_action(state, RulesEngine(), seat, action)
    resolve_effect(state, seat, 'copy_spell', {'target_stack_id': state.stack[-1].id})
    state = resolve(state)
    assert len(state.delayed_triggers) == 2
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = len(state.players[seat].hand)
    upkeep(state, state.turn + 1, 3 - seat)
    assert len(state.stack) == 2 and not state.delayed_triggers
    state = resolve(state)
    assert len(state.players[seat].hand) == before + 2


@pytest.mark.parametrize('name', ['Vampirism', 'Fevered Strength'])
@pytest.mark.parametrize('seat', [1, 2])
def test_real_stifle_counters_next_upkeep_trigger_without_another_draw(name, seat):
    state, _, _, action = setup(name, seat)
    state = resolve(checked_action(state, RulesEngine(), seat, action))
    upkeep(state, state.turn + 1, 3 - seat)
    stifle = raw_add(state, 'Stifle', 3 - seat, Zone.HAND, cards=CARDS)
    state.players[3 - seat].mana_pool = {'U': 1}
    before = len(state.players[seat].hand)
    state = checked_action(state, RulesEngine(), 3 - seat, {
        'type': 'cast_spell', 'card_id': stifle.id, 'targets': {'target_stack_id': state.stack[-1].id}})
    state = resolve(state)
    assert len(state.players[seat].hand) == before and not state.delayed_triggers
    upkeep(state, state.turn + 1, seat)
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_other_creature_penalty_and_attached_bonus_use_distinct_recipients(seat):
    state, _, creature, action = setup('Vampirism', seat)
    other = raw_add(state, 'Grizzly Bears', seat, cards=CARDS)
    state = resolve(checked_action(state, RulesEngine(), seat, action))
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert effective_power(state, creature) == 3
    assert effective_power(state, other.id) == 1
    assert serialize_card_view(state, creature)['power'] == 3
    assert serialize_card_view(state, other.id)['power'] == 1


@pytest.mark.parametrize('name', ['Vampirism', 'Fevered Strength'])
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stage', ['spell', 'delayed'])
def test_countered_spell_never_schedules_or_countered_delayed_trigger_never_repeats(name, seat, stage):
    state, _, _, action = setup(name, seat)
    state = checked_action(state, RulesEngine(), seat, action)
    if stage == 'delayed':
        state = resolve(state)
        upkeep(state, state.turn + 1, 3 - seat)
    before = len(state.players[seat].hand)
    resolve_effect(state, 3 - seat, 'counter_spell' if stage == 'spell' else 'counter_ability',
                   {'target_stack_id': state.stack[-1].id})
    state = resolve(state)
    assert not state.delayed_triggers
    upkeep(state, state.turn + 1, seat)
    assert not state.stack and len(state.players[seat].hand) == before


@pytest.mark.parametrize('name', ['Vampirism', 'Fevered Strength'])
@pytest.mark.parametrize('seat', [1, 2])
def test_http_cast_and_database_restart_preserve_delayed_draw(game, name, seat):
    client, match = game
    state, source, _, action = setup(name, seat)
    state.id = match.state.id
    match.state = state
    persist(match)
    path = f'/matches/{state.id}/action'

    def post(player, move):
        response = client.post(path, json={'player_id': player, 'action': move})
        assert response.status_code == 200, response.text

    def settle():
        for _ in range(12):
            if not match.state.stack:
                return
            post(match.state.priority_player, {'type': 'pass_priority'})
        raise AssertionError('HTTP stack did not settle')

    post(seat, action)
    before = len(match.state.players[seat].hand)
    settle()
    assert len(match.state.players[seat].hand) == before
    assert len(match.state.delayed_triggers) == 1
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    match = main.ACTIVE_MATCHES[state.id]
    assert match.state.delayed_triggers[0]['source_card_id'] == source
    # Advance from untap through the actual HTTP priority/next-step path.
    match.state.turn += 1
    match.state.step = Step.UNTAP
    match.state.active_player = match.state.priority_player = 3 - seat
    persist(match)
    response = client.post(f'/matches/{state.id}/autoplay?ticks=1')
    assert response.status_code == 200, response.text
    assert match.state.step == Step.UPKEEP and len(match.state.stack) == 1
    settle()
    assert len(match.state.players[seat].hand) == before + 1
