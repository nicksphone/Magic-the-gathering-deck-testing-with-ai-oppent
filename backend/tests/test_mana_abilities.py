"""Canonical devotion and land-output parity, without changing card text."""
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_card_view, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.mana import mana_source_outputs, can_pay_with_pool_and_lands
from tests.test_variable_mana import clean
from tests.test_ai_recurring_engines import add as add_card

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures' / 'mana_abilities.json').read_text())}


def add(state, name, seat=1, zone=Zone.BATTLEFIELD):
    card = add_card(state, name, seat, zone, cards=ROWS)
    card.summoning_sick = False
    return card


@pytest.mark.parametrize('seat', [1, 2])
def test_devotion_source_uses_live_symbols_in_outputs_and_public_view(seat):
    state = clean()
    source = add(state, "Karametra's Acolyte", seat)
    elves = [add(state, 'Llanowar Elves', seat) for _ in range(2)]
    before = serialize_match_snapshot(state)
    assert mana_source_outputs(state, seat, source.id) == {'G': 3}
    assert serialize_card_view(state, source.id)['mana_source_amounts'] == {'G': 3}
    assert serialize_match_snapshot(state) == before
    state.players[seat].battlefield.remove(elves[0].id)
    elves[0].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(elves[0].id)
    assert mana_source_outputs(state, seat, source.id) == {'G': 2}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', [("Gaea's Cradle", 'G'), ("Serra's Sanctum", 'W')])
def test_counted_land_outputs_and_zero_resources(name, color, seat):
    state = clean()
    source = add(state, name, seat)
    if color == 'G':
        add(state, 'Soul Warden', seat)
        add(state, 'Llanowar Elves', seat)
    else:
        from tests.test_conditional_creature_types import CARDS
        for god_name in ['Nylea, God of the Hunt', 'Xenagos, God of Revels']:
            add_card(state, god_name, seat, cards=CARDS)
    assert mana_source_outputs(state, seat, source.id) == {color: 2}
    assert serialize_card_view(state, source.id)['mana_source_amounts'] == {color: 2}
    for cid in list(state.players[seat].battlefield):
        if cid != source.id:
            state.players[seat].battlefield.remove(cid)
            state.cards[cid].move_to_zone(Zone.EXILE)
            state.players[seat].exile.append(cid)
    assert mana_source_outputs(state, seat, source.id) == {}


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_land_can_bootstrap_a_colored_spell_without_using_itself_twice(seat):
    state = clean()
    source = add(state, 'Nykthos, Shrine to Nyx', seat)
    add(state, 'Steel Leaf Champion', seat)
    forests = [add(state, 'Forest', seat) for _ in range(2)]
    before = serialize_match_snapshot(state)
    assert can_pay_with_pool_and_lands(state, seat, '{G}{G}{G}')
    assert serialize_match_snapshot(state) == before
    state.players[seat].battlefield.remove(forests[0].id)
    forests[0].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(forests[0].id)
    assert not can_pay_with_pool_and_lands(state, seat, '{G}{G}{G}')
    assert not state.cards[source.id].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_autopayment_activates_paid_land_and_resolves_spell(seat):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from tests.test_ai_recurring_engines import resolve
    state = paid_position(seat)
    source = next(card for card in state.cards.values() if card.name.startswith('Nykthos'))
    spell = add(state, 'Steel Leaf Champion', seat, Zone.HAND)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': spell.id, 'targets': {}})
    assert state.cards[source.id].tapped
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = resolve(state)
    assert state.cards[spell.id].zone == Zone.BATTLEFIELD


def paid_position(seat):
    from game_state.state import Step
    state = clean()
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    add(state, 'Nykthos, Shrine to Nyx', seat)
    add(state, 'Steel Leaf Champion', seat)
    for _ in range(2):
        add(state, 'Forest', seat)
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,cost,index,expected', [('Cabal Coffers', 2, 0, 6), ('Cabal Stronghold', 3, 1, 5)])
def test_paid_swamp_counts_distinguish_basic_subtypes_and_real_costs(seat, name, cost, index, expected):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, name, seat)
    lands = [add(state, 'Swamp', seat) for _ in range(5)]
    lands.append(add(state, 'Overgrown Tomb', seat))
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_mana_ability',
        'card_id': source.id, 'ability_index': index, 'color': 'B'})
    assert state.cards[source.id].tapped
    assert sum(state.cards[land.id].tapped for land in lands) == cost
    assert state.players[seat].mana_pool['B'] == expected
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,expected', [('Mana Reflection', 2), ('Nyxbloom Ancient', 3)])
def test_mana_multipliers_share_actual_pool_public_values_and_payment(seat, name, expected):
    from rules_engine.mana import auto_pay_cost, land_mana_amount
    state = clean()
    source = add(state, 'Forest', seat)
    add(state, name, seat)
    add(state, name, 3-seat)
    before = serialize_match_snapshot(state)
    assert mana_source_outputs(state, seat, source.id) == {'G': expected}
    assert land_mana_amount(state, seat, source.id) == expected
    assert serialize_card_view(state, source.id)['mana_source_amounts'] == {'G': expected}
    assert serialize_match_snapshot(state) == before
    assert auto_pay_cost(state, seat, '{G}')
    assert source.tapped
    assert state.players[seat].mana_pool['G'] == expected-1


@pytest.mark.parametrize('seat', [1, 2])
def test_independent_multiplier_instances_apply_once_each(seat):
    state = clean()
    source = add(state, 'Forest', seat)
    add(state, 'Mana Reflection', seat)
    add(state, 'Nyxbloom Ancient', seat)
    assert mana_source_outputs(state, seat, source.id) == {'G': 6}


@pytest.mark.parametrize('seat', [1, 2])
def test_zero_output_is_a_legal_explicit_mana_activation_not_an_ai_resource(seat):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, "Gaea's Cradle", seat)
    assert mana_source_outputs(state, seat, source.id) == {}
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_mana_ability',
        'card_id': source.id, 'ability_index': 0, 'color': 'G'})
    assert state.cards[source.id].tapped
    assert state.players[seat].mana_pool.get('G', 0) == 0
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['Casual', 'Strong', 'Master'])
def test_ai_casts_with_paid_resources_without_proactive_mana_floating(seat, difficulty):
    from ai.agent import AIAgent
    from rules_engine.move_generator import legal_moves
    state = paid_position(seat)
    spell = add(state, 'Steel Leaf Champion', seat, Zone.HAND)
    agent = AIAgent(difficulty, 'Ramp')
    moves = legal_moves(state, seat)
    assert any(move['type'] == 'activate_mana_ability' for move in moves)
    decision = agent.choose_action(state, moves, seat)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == spell.id


from tests.test_api_input_contracts import game, persist


@pytest.mark.parametrize('seat', [1, 2])
def test_http_paid_choice_validation_and_sqlite_resume(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, controller = game
    match_id = controller.state.id
    controller.state = state = paid_position(seat)
    state.id = match_id
    persist(controller)
    source = next(card for card in state.cards.values() if card.name.startswith('Nykthos'))
    url = f'/matches/{state.id}'
    moves = client.get(url+'/legal-moves', params={'player_id': seat}).json()['moves']
    assert any(move['type'] == 'activate_mana_ability' and move['card_id'] == source.id
               and move['ability_index'] == 1 and move['outputs']['G'] == 3 for move in moves)
    before = client.get(url).json()
    for index, color in [(99, 'G'), (1, 'C')]:
        response = client.post(url+'/action', json={'player_id': seat, 'action': {
            'type': 'activate_mana_ability', 'card_id': source.id, 'ability_index': index, 'color': color}})
        assert response.status_code == 422, response.text
        assert client.get(url).json() == before
    response = client.post(url+'/action', json={'player_id': seat, 'action': {
        'type': 'activate_mana_ability', 'card_id': source.id, 'ability_index': 1, 'color': 'G'}})
    assert response.status_code == 200, response.text
    expected = client.get(url).json()
    assert expected['players'][str(seat)]['mana_pool']['G'] == 3
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(url).json() == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_artifact_counted_land_tracks_friendly_current_permanents(seat):
    state = clean()
    source = add(state, 'Tolarian Academy', seat)
    for _ in range(2):
        add(state, 'Sol Ring', seat)
    add(state, 'Sol Ring', 3-seat)
    assert mana_source_outputs(state, seat, source.id) == {'U': 2}


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_counted_paid_land_uses_owner_zone_color_and_card_type(seat):
    from tests.test_conditional_creature_types import CARDS
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, 'Crypt of Agadeem', seat)
    for _ in range(2):
        add(state, 'Swamp', seat)
        add_card(state, 'Blood Artist', seat, Zone.GRAVEYARD, cards=CARDS)
    add_card(state, 'Blood Artist', 3-seat, Zone.GRAVEYARD, cards=CARDS)
    add(state, 'Llanowar Elves', seat, Zone.GRAVEYARD)
    state = checked_action(state, RulesEngine(), seat, {'type': 'activate_mana_ability',
        'card_id': source.id, 'ability_index': 1, 'color': 'B'})
    assert state.players[seat].mana_pool['B'] == 2
    assert not state.stack


def test_library_moving_activation_is_not_classified_as_a_mana_ability():
    from rules_engine.mana_abilities import mana_ability_specs
    from rules_engine.oracle_effects import extract_activated_abilities
    from rules_engine.mana import repeatable_nonland_mana_outputs
    state = clean()
    source = add(state, 'Chromatic Sphere')
    assert mana_ability_specs(source, state) == ()
    assert extract_activated_abilities(source)
    assert mana_source_outputs(state, 1, source.id) == {}
    assert repeatable_nonland_mana_outputs(source, state=state) == {}


@pytest.mark.parametrize('seat', [1, 2])
def test_devotion_mana_clauses_have_no_obsolete_coverage_warning(seat):
    from rules_engine.coverage import known_unsupported_mechanics
    state = paid_position(seat)
    for name in ["Karametra's Acolyte", 'Nykthos, Shrine to Nyx']:
        row = ROWS[name]
        assert 'unsupported devotion instruction' not in known_unsupported_mechanics(row['oracle_text'], card_name=name)


@pytest.mark.parametrize('seat', [1, 2])
def test_land_names_do_not_grant_basic_land_subtype_mana(seat):
    from rules_engine.mana import land_mana_colors
    state = clean()
    source = add(state, 'Island of Wak-Wak', seat)
    assert mana_source_outputs(state, seat, source.id) == {}
    assert land_mana_colors(source) == set()


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_payment_preserves_resources_for_another_colored_spell(seat):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from tests.test_ai_recurring_engines import resolve
    state = paid_position(seat)
    add(state, 'Forest', seat)
    first = add(state, 'Steel Leaf Champion', seat, Zone.HAND)
    second = add(state, 'Llanowar Elves', seat, Zone.HAND)
    state = resolve(checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': first.id, 'targets': {}}))
    assert can_pay_with_pool_and_lands(state, seat, state.cards[second.id].mana_cost)
    state = resolve(checked_action(state, RulesEngine(), seat,
        {'type': 'cast_spell', 'card_id': second.id, 'targets': {}}))
    assert state.cards[second.id].zone == Zone.BATTLEFIELD
