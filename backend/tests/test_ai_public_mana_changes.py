"""Canonical resource changes, actual AI decisions and private-zone boundaries."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.mana_resource_policy import resource_delta, resource_change_plan
from ai.pending_effects import planning_copy
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands
from tests.test_variable_mana import clean
from tests.test_ai_recurring_engines import add as add_card, resolve
from tests.test_api_input_contracts import game, persist

CARDS = {}
for name in ('land_types', 'ward', 'attached_scaling', 'aura_costs', 'variable_mana', 'public_foretell', 'quoted_entry'):
    CARDS.update({card['name']: card for card in json.loads(
        (Path(__file__).parent / 'fixtures' / (name + '.json')).read_text())})
STYLES = ['Aggro', 'Burn', 'Midrange', 'Control', 'Tempo', 'Ramp', 'Drain',
          'Aristocrats', 'Reanimator', 'Tokens', 'Tribal', 'Combo-lite',
          'Counter-heavy', 'Removal-heavy']


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, seat, zone, cards=CARDS)
    card.summoning_sick = False
    return card


def setup(case, seat):
    state = clean()
    state.active_player = state.priority_player = seat
    state.turn = 4
    for _ in range(2):
        add(state, 'Hallowed Fountain', seat)
    source = add(state, 'Blood Moon' if case == 'harmful' else 'Prismatic Omen', seat, Zone.HAND)
    held = add(state, 'Lightning Bolt' if case == 'useful' else 'Counterspell', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2, 'G': 1}
    if case == 'harmful':
        state.players[seat].mana_pool['R'] = 1
    return state, source, held


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('case', ['harmful', 'useful', 'redundant'])
def test_actual_decisions_fix_access_or_hold_unhelpful_changes(case, difficulty, style, seat):
    state, source, held = setup(case, seat)
    before = serialize_match_snapshot(state)
    rules = RulesEngine()
    agent = AIAgent(difficulty=difficulty, archetype=style)
    action = agent.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert serialize_match_snapshot(state) == before
    if case == 'useful':
        assert action['type'] == 'cast_spell' and action['card_id'] == source.id
        state = checked_action(state, rules, seat, action)
        state = resolve(state)
        assert state.cards[source.id].zone == Zone.BATTLEFIELD
        assert can_pay_with_pool_and_lands(state, seat, held.mana_cost,
                                         card_name=held.name, spell_types=set(held.types), oracle_text=held.oracle_text)
    else:
        assert action['type'] == 'pass_priority'
        assert source.zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
def test_known_fixing_is_dynamic_and_restores_after_source_departure(seat):
    state, source, held = setup('redundant', seat)
    rules = RulesEngine()
    agent = AIAgent()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    before = serialize_match_snapshot(state)
    assert resource_change_plan(agent, state, move, seat)['defer']
    add(state, 'Lightning Bolt', seat, Zone.HAND)
    plan = resource_change_plan(agent, state, move, seat)
    assert not plan['defer'] and plan['score'] > 3
    projected = planning_copy(state)
    projected = checked_action(projected, rules, seat, plan['action'])
    projected = resolve(projected)
    restored = deserialize_match_snapshot(serialize_match_snapshot(projected))
    assert resource_delta(state, restored, seat, excluded_card_ids={source.id}) == plan['score']
    restored.players[seat].battlefield.remove(source.id)
    restored.cards[source.id].move_to_zone(Zone.GRAVEYARD)
    restored.players[seat].graveyard.append(source.id)
    assert resource_delta(state, restored, seat, excluded_card_ids={source.id}) == 0
    assert before != serialize_match_snapshot(state)  # only the deliberate new hand card


@pytest.mark.parametrize('seat', [1, 2])
def test_public_control_history_raises_disruption_value_without_hidden_hand(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    for _ in range(3):
        add(state, 'Forest', seat)
        add(state, 'Hallowed Fountain', 3-seat)
    source = add(state, 'Blood Moon', seat, Zone.HAND)
    add(state, 'Counterspell', 3-seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool = {'C': 2, 'R': 1}
    agent = AIAgent(archetype='Control')
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    plan = resource_change_plan(agent, state, move, seat)
    assert plan['score'] >= 2 and not plan['defer']
    assert agent.choose_action(state, rules.legal_moves(state, seat), seat).action['card_id'] == source.id
    for name in ['Counterspell', 'Lightning Bolt', 'Prismatic Omen']:
        hidden = add(state, name, 3-seat, Zone.HAND)
        assert resource_change_plan(agent, state, move, seat) == plan
        state.players[3-seat].hand.remove(hidden.id)
        hidden.move_to_zone(Zone.LIBRARY)
        state.players[3-seat].library.append(hidden.id)
        assert resource_change_plan(agent, state, move, seat) == plan


@pytest.mark.parametrize('seat', [1, 2])
def test_intrinsic_fixing_does_not_treat_restricted_printed_output_as_free(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    land = add(state, 'Ancient Ziggurat', seat)
    source = add(state, 'Prismatic Omen', seat, Zone.HAND)
    add(state, 'Lightning Bolt', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'G': 1}
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    plan = resource_change_plan(AIAgent(), state, move, seat)
    assert plan['score'] > 3 and not plan['defer']
    assert not land.tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_aura_targets_are_selected_by_actual_resource_gain(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    friendly = add(state, 'Hallowed Fountain', seat)
    enemy = add(state, 'Hallowed Fountain', 3-seat)
    add(state, 'Lightning Bolt', seat, Zone.HAND)
    source = add(state, 'Lush Growth', seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1}
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    agent = AIAgent()
    plan = resource_change_plan(agent, state, move, seat)
    assert plan and not plan['defer']
    assert plan['action']['targets']['target_card_id'] == friendly.id
    before = serialize_match_snapshot(state)
    action = agent.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert action['card_id'] == source.id and action['targets']['target_card_id'] == friendly.id
    assert serialize_match_snapshot(state) == before
    assert not enemy.tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_draw_aura_keeps_resource_outcome_unknown(seat):
    state, source, held = setup('harmful', seat)
    aura = add(state, 'Spreading Seas', seat, Zone.HAND)
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == aura.id)
    assert resource_change_plan(AIAgent(), state, move, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Spreading Seas', "Giant's Amulet", 'Ossification', 'Chained to the Rocks'])
def test_canonical_aura_and_equipment_self_entry_matches_original_object_only(name, seat):
    from rules_engine.events import _matches_enters_battlefield_trigger
    state = clean()
    source = add(state, name, seat)
    unrelated = add(state, 'Hallowed Fountain', seat)
    assert _matches_enters_battlefield_trigger(state, source, source.oracle_text.lower(), {'card_id': source.id})
    assert not _matches_enters_battlefield_trigger(state, source, source.oracle_text.lower(), {'card_id': unrelated.id})


@pytest.mark.parametrize('seat', [1, 2])
def test_spreading_seas_actual_cast_emits_and_resolves_draw(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    target = add(state, 'Hallowed Fountain', seat)
    source = add(state, 'Spreading Seas', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'U': 1}
    before = len(state.players[seat].library)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_card_id': target.id}})
    state = resolve(state)
    assert state.cards[source.id].zone == Zone.BATTLEFIELD
    assert len(state.players[seat].library) == before - 1
    assert len(state.players[seat].hand) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_normal_land_wins_when_both_fix_us_but_only_one_fixes_opponent(seat, style, difficulty):
    state = clean()
    state.active_player = state.priority_player = seat
    for _ in range(2):
        add(state, 'Hallowed Fountain', seat)
        add(state, 'Hallowed Fountain', 3-seat)
    add(state, 'Elvish Archdruid', 3-seat, Zone.GRAVEYARD)
    add(state, 'Lush Growth', seat, Zone.HAND)
    add(state, 'Yavimaya, Cradle of Growth', seat, Zone.HAND)
    basic = add(state, 'Forest', seat, Zone.HAND)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty=difficulty, archetype=style)
    rules = RulesEngine()
    action = agent.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert action['type'] == 'play_land' and action['card_id'] == basic.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, rules, seat, action)
    assert state.cards[basic.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_fixing_value_tracks_source_controller_without_snapshot_mutation(seat):
    state, source, held = setup('useful', seat)
    add(state, 'Hallowed Fountain', 3-seat)
    rules = RulesEngine()
    agent = AIAgent()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    plan = resource_change_plan(agent, state, move, seat)
    projected = resolve(checked_action(state, rules, seat, plan['action']))
    assert resource_delta(state, projected, seat, excluded_card_ids={source.id}) > 3
    projected.players[seat].battlefield.remove(source.id)
    projected.players[3-seat].battlefield.append(source.id)
    projected.cards[source.id].controller = 3-seat
    before = serialize_match_snapshot(projected)
    assert resource_delta(state, projected, seat, excluded_card_ids={source.id}) < 0
    assert serialize_match_snapshot(projected) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['harmful', 'useful', 'redundant'])
def test_live_autoplay_decisions_and_sqlite_resume(game, case, seat):
    import main
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session
    client, controller = game
    match_id = controller.state.id
    state, source, held = setup(case, seat)
    state.id = match_id
    controller.state = state
    controller.controllers = {seat: 'ai', 3-seat: 'human'}
    controller.ai[seat] = AIAgent(difficulty='master', archetype='Control')
    persist(controller)
    url = f'/matches/{match_id}'
    response = client.post(url+'/autoplay', params={'ticks': 1})
    assert response.status_code == 200, response.text
    assert controller.state.cards[source.id].zone == (Zone.STACK if case == 'useful' else Zone.HAND)
    if case == 'useful':
        for _ in range(2):
            pid = controller.state.priority_player
            if controller.controllers[pid] == 'human':
                response = client.post(url+'/action', json={'player_id': pid, 'action': {'type': 'pass_priority'}})
            else:
                response = client.post(url+'/autoplay', params={'ticks': 1})
            assert response.status_code == 200, response.text
        assert controller.state.cards[source.id].zone == Zone.BATTLEFIELD
    expected = client.get(url).json()
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    assert client.get(url).json() == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Saw It Coming', 'Behold the Multiverse'])
def test_face_down_opponent_exile_never_becomes_public_color_demand(seat, name):
    # A canonical hidden-exile snapshot fixture, not an implemented Foretell action.
    state = clean()
    state.active_player = state.priority_player = seat
    for _ in range(3):
        add(state, 'Forest', seat)
        add(state, 'Hallowed Fountain', 3-seat)
    source = add(state, 'Blood Moon', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2, 'R': 1}
    rules = RulesEngine()
    agent = AIAgent()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    public_plan = resource_change_plan(agent, state, move, seat)
    hidden = add(state, name, 3-seat, Zone.EXILE)
    hidden.exile_face_down = True
    before = serialize_match_snapshot(state)
    assert resource_change_plan(agent, state, move, seat) == public_plan
    restored = deserialize_match_snapshot(before)
    assert resource_change_plan(agent, restored, move, seat) == public_plan
    assert serialize_match_snapshot(state) == before
    hidden.exile_face_down = False
    assert resource_change_plan(agent, state, move, seat)['score'] > public_plan['score']


@pytest.mark.parametrize('name', ['Saw It Coming', 'Behold the Multiverse'])
def test_foretell_is_explicitly_unsupported_not_implied_by_exile_views(name):
    from rules_engine.coverage import known_unsupported_mechanics
    assert 'foretell' in known_unsupported_mechanics(CARDS[name]['oracle_text'])


@pytest.mark.parametrize('seat', [1, 2])
def test_unattributed_face_down_exile_is_unknown_even_to_owner(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    for _ in range(2):
        add(state, 'Hallowed Fountain', seat)
    source = add(state, 'Blood Moon', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2, 'R': 1}
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, seat) if move.get('card_id') == source.id)
    agent = AIAgent()
    plan = resource_change_plan(agent, state, move, seat)
    hidden = add(state, 'Saw It Coming', seat, Zone.EXILE)
    hidden.exile_face_down = True
    assert resource_change_plan(agent, state, move, seat) == plan
    hidden.exile_face_down = False
    assert resource_change_plan(agent, state, move, seat)['score'] < plan['score']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ["Dragonbroods' Relic", "Outlaws' Merriment"])
def test_quoted_token_entry_never_triggers_on_creator_entry(seat, name):
    from rules_engine.events import _matches_enters_battlefield_trigger, emit_event
    state = clean()
    source = add(state, name, seat)
    assert not _matches_enters_battlefield_trigger(state, source, source.oracle_text.lower(), {'card_id': source.id})
    emit_event(state, 'enters_battlefield', {'card_id': source.id})
    assert not state.stack and not state.staged_triggers and not state.pending_trigger_order


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_artifact_cast_does_not_run_quoted_token_entry_ability(seat):
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, "Dragonbroods' Relic", seat, Zone.HAND)
    from rules_engine.mana import parse_mana_cost
    cost = parse_mana_cost(source.mana_cost)
    state.players[seat].mana_pool = {color: cost[color] for color in 'WUBRGC'}
    state.players[seat].mana_pool['C'] += cost['generic']
    state = resolve(checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source.id}))
    assert state.cards[source.id].zone == Zone.BATTLEFIELD
    assert all(player.life == 20 for player in state.players.values())
    assert not state.stack and sum(state.players[seat].mana_pool.values()) == 0
