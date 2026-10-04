"""Canonical basic-land type additions, replacement and dependency ordering."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_card_view, serialize_match_snapshot
from rules_engine.mana import mana_source_outputs
from tests.test_variable_mana import clean
from tests.test_ai_recurring_engines import add as add_card

CARDS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures' / 'land_types.json').read_text())}


def add(state, name, seat=1):
    card = add_card(state, name, seat, cards=CARDS)
    card.summoning_sick = False
    return card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,color', [('Urborg, Tomb of Yawgmoth', 'B'), ('Yavimaya, Cradle of Growth', 'G')])
def test_global_addition_grants_mana_to_both_players_without_mutation(seat, name, color):
    state = clean()
    source = add(state, name, seat)
    land = add(state, 'Hallowed Fountain', 3-seat)
    before = serialize_match_snapshot(state)
    assert mana_source_outputs(state, seat, source.id) == {color: 1}
    assert mana_source_outputs(state, 3-seat, land.id) == dict.fromkeys({'W', 'U', color}, 1)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Dryad of the Ilysian Grove', 'Prismatic Omen'])
def test_controller_scoped_addition_does_not_fix_opponent_mana(seat, name):
    state = clean()
    add(state, name, seat)
    friendly = add(state, 'Hallowed Fountain', seat)
    enemy = add(state, 'Hallowed Fountain', 3-seat)
    assert mana_source_outputs(state, seat, friendly.id) == dict.fromkeys('WUBRG', 1)
    assert mana_source_outputs(state, 3-seat, enemy.id) == {'U': 1, 'W': 1}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Blood Moon', 'Magus of the Moon'])
def test_replacement_removes_old_mana_but_not_creature_types(seat, name):
    state = clean()
    add(state, name, seat)
    fountain = add(state, 'Hallowed Fountain', 3-seat)
    arbor = add(state, 'Dryad Arbor', 3-seat)
    assert mana_source_outputs(state, 3-seat, fountain.id) == {'R': 1}
    assert mana_source_outputs(state, 3-seat, arbor.id) == {'R': 1}
    view = serialize_card_view(state, arbor.id)
    assert view['types'] == arbor.types
    assert 'Dryad' in view['type_line'] and 'Forest' not in view['type_line']
    assert 'Mountain' in view['type_line']
    assert 'Forest' in arbor.type_line


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('order', [0, 1])
def test_dependency_removes_land_sourced_effect_before_it_applies(seat, order):
    state = clean()
    names = ['Urborg, Tomb of Yawgmoth', 'Blood Moon']
    if order:
        names.reverse()
    for name in names:
        add(state, name, seat)
    land = add(state, 'Hallowed Fountain', 3-seat)
    assert mana_source_outputs(state, 3-seat, land.id) == {'R': 1}
    urborg = next(card for card in state.cards.values() if card.name.startswith('Urborg'))
    assert mana_source_outputs(state, seat, urborg.id) == {'R': 1}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('order', [0, 1])
def test_independent_addition_and_replacement_follow_timestamps(seat, order):
    state = clean()
    names = ['Blood Moon', 'Prismatic Omen']
    if order:
        names.reverse()
    for stamp, name in enumerate(names, start=1):
        card = add(state, name, seat)
        card.effect_timestamp = stamp
    land = add(state, 'Hallowed Fountain', seat)
    expected = dict.fromkeys('WUBRG', 1) if not order else {'R': 1}
    assert mana_source_outputs(state, seat, land.id) == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_basic_land_replacement_does_not_make_basic_forest_nonbasic(seat):
    state = clean()
    add(state, 'Blood Moon', seat)
    from tests.test_mana_abilities import add as add_mana
    forest = add_mana(state, 'Forest', 3-seat)
    assert mana_source_outputs(state, 3-seat, forest.id) == {'G': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_land_entry_projected_types_remove_optional_payment_before_entry(seat):
    from rules_engine.entry import land_entry_options, apply_entry_choice
    state = clean()
    add(state, 'Blood Moon', 3-seat)
    land = add_card(state, 'Hallowed Fountain', seat, Zone.HAND, cards=CARDS)
    before = serialize_match_snapshot(state)
    assert land_entry_options(state, seat, land) == []
    assert serialize_match_snapshot(state) == before
    apply_entry_choice(state, seat, land)
    assert not land.tapped and state.players[seat].life == 20
    apply_entry_choice(state, seat, land, effect_tapped=True)
    assert land.tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,colors', [('Spreading Seas', 'U'), ('Lush Growth', 'WGR')])
def test_attached_replacement_changes_only_its_target_and_removes_printed_mana(seat, name, colors):
    state = clean()
    land = add(state, 'Hallowed Fountain', 3-seat)
    other = add(state, 'Hallowed Fountain', 3-seat)
    aura = add(state, name, seat)
    aura.attached_to = land.id
    assert mana_source_outputs(state, 3-seat, land.id) == dict.fromkeys(colors, 1)
    assert mana_source_outputs(state, 3-seat, other.id) == {'U': 1, 'W': 1}


@pytest.mark.parametrize('seat', [1, 2])
def test_live_swamp_counts_follow_global_addition_and_source_removal(seat):
    from rules_engine.mana_abilities import ability_outputs, mana_ability_specs
    from rules_engine.static_conditions import _land_count
    state = clean()
    coffers = add(state, 'Cabal Coffers', seat)
    add(state, 'Hallowed Fountain', seat)
    source = add(state, 'Urborg, Tomb of Yawgmoth', seat)
    assert _land_count(state, [seat], 'swamp') == 3
    assert ability_outputs(state, coffers, mana_ability_specs(coffers, state)[0]) == {'B': 3}
    state.players[seat].battlefield.remove(source.id)
    source.move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(source.id)
    assert _land_count(state, [seat], 'swamp') == 0
    assert ability_outputs(state, coffers, mana_ability_specs(coffers, state)[0]) == {'B': 0}


@pytest.mark.parametrize('seat', [1, 2])
def test_landwalk_uses_effective_land_subtype_not_printed_name(seat):
    from rules_engine.combat import _attacker_has_active_landwalk_with_state
    state = clean()
    attacker = add(state, 'River Boa', seat)
    land = add(state, 'Hallowed Fountain', 3-seat)
    assert _attacker_has_active_landwalk_with_state(state, attacker, 3-seat)
    moon = add(state, 'Blood Moon', 3-seat)
    assert not _attacker_has_active_landwalk_with_state(state, attacker, 3-seat)
    state.players[3-seat].battlefield.remove(moon.id)
    moon.move_to_zone(Zone.GRAVEYARD)
    assert _attacker_has_active_landwalk_with_state(state, attacker, 3-seat)
    assert 'Island' in land.type_line


@pytest.mark.parametrize('seat', [1, 2])
def test_snapshot_restores_effective_view_without_changing_printed_data(seat):
    from game_state.serializers import deserialize_match_snapshot
    from rules_engine.mana_abilities import mana_ability_specs
    state = clean()
    add(state, 'Prismatic Omen', seat)
    land = add(state, 'Hallowed Fountain', seat)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert serialize_card_view(restored, land.id) == serialize_card_view(state, land.id)
    assert restored.cards[land.id].type_line == CARDS['Hallowed Fountain']['type_line']
    specs = mana_ability_specs(restored.cards[land.id], restored)
    assert len(specs) == 5
    from rules_engine.mana_abilities import ability_outputs
    assert {tuple(ability_outputs(restored, restored.cards[land.id], row)) for row in specs} == {(color,) for color in 'WUBRG'}


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_group_tap_produces_replaced_mana_for_each_selected_land(seat):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    state = clean()
    state.active_player = state.priority_player = seat
    add(state, 'Blood Moon', seat)
    lands = [add(state, 'Hallowed Fountain', seat) for _ in range(2)]
    state = checked_action(state, RulesEngine(), seat, {'type': 'tap_lands_bulk',
        'land_name': 'Hallowed Fountain', 'count': 2, 'color': 'R'})
    assert state.players[seat].mana_pool['R'] == 2
    assert all(state.cards[land.id].tapped for land in lands)


@pytest.mark.parametrize('seat', [1, 2])
def test_ai_current_and_entering_land_colors_use_public_layers(seat):
    from ai.agent import AIAgent
    state = clean()
    add(state, 'Blood Moon', seat)
    land = add(state, 'Hallowed Fountain', seat)
    entering = add_card(state, 'Hallowed Fountain', seat, Zone.HAND, cards=CARDS)
    before = serialize_match_snapshot(state)
    agent = AIAgent('Master', 'Control')
    assert agent._land_colors(land, state) == {'R'}
    assert agent._land_colors(entering, state) == {'R'}
    assert serialize_match_snapshot(state) == before


from tests.test_api_input_contracts import game, persist, rejected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Hallowed Fountain', 'Unclaimed Territory', 'Cavern of Souls'])
def test_http_land_entry_removed_abilities_and_sqlite_restore(game, seat, name):
    import main
    from persistence.db import engine
    from persistence.repository import Repository
    from sqlmodel import Session
    client, controller = game
    match_id = controller.state.id
    controller.state = state = clean()
    state.id = match_id
    state.active_player = state.priority_player = seat
    add(state, 'Blood Moon', seat)
    land = add_card(state, name, seat, Zone.HAND, cards=CARDS)
    persist(controller)
    url = f'/matches/{state.id}'
    response = client.post(url+'/action', json={'player_id': seat, 'action': {
        'type': 'play_land', 'card_id': land.id}})
    assert response.status_code == 200, response.text
    current = controller.state
    assert current.pending_mechanic_choice is None
    assert current.players[seat].life == 20
    assert not current.cards[land.id].tapped
    rejected(client, controller, {'type': 'tap_land_for_mana', 'card_id': land.id, 'color': 'U'}, seat)
    moves = client.get(url+'/legal-moves', params={'player_id': seat}).json()['moves']
    mana = next(move for move in moves if move['type'] == 'activate_mana_ability' and move['card_id'] == land.id)
    assert mana['outputs'] == {'R': 1}
    response = client.post(url+'/action', json={'player_id': seat, 'action': {
        'type': 'activate_mana_ability', 'card_id': land.id,
        'ability_index': mana['ability_index'], 'color': 'R'}})
    assert response.status_code == 200, response.text
    expected = client.get(url).json()
    view = next(card for card in expected['players'][str(seat)]['battlefield'] if card['id'] == land.id)
    assert 'Mountain' in view['type_line']
    assert view['base_type_line'] == CARDS[name]['type_line']
    assert expected['players'][str(seat)]['mana_pool']['R'] == 1
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(url).json() == expected


@pytest.mark.parametrize('seat', [1, 2])
def test_controller_change_and_attachment_changes_invalidate_live_view(seat):
    from rules_engine.land_types import effective_type_line
    state = clean()
    source = add(state, 'Prismatic Omen', seat)
    lands = [add(state, 'Hallowed Fountain', pid) for pid in [seat, 3-seat]]
    assert mana_source_outputs(state, seat, lands[0].id) == dict.fromkeys('WUBRG', 1)
    state.players[seat].battlefield.remove(source.id)
    state.players[3-seat].battlefield.append(source.id)
    source.controller = 3-seat
    assert mana_source_outputs(state, seat, lands[0].id) == {'U': 1, 'W': 1}
    assert mana_source_outputs(state, 3-seat, lands[1].id) == dict.fromkeys('WUBRG', 1)
    aura = add(state, 'Spreading Seas', seat)
    aura.attached_to = lands[0].id
    assert mana_source_outputs(state, seat, lands[0].id) == {'U': 1}
    aura.attached_to = lands[1].id
    assert mana_source_outputs(state, seat, lands[0].id) == {'U': 1, 'W': 1}
    assert 'Island' in effective_type_line(state, lands[1])


@pytest.mark.parametrize('seat', [1, 2])
def test_set_land_types_preserves_nonland_subtypes_and_colors(seat):
    from rules_engine.land_types import effective_type_line
    state = clean()
    add(state, 'Blood Moon', seat)
    saga = add(state, "Urza's Saga", seat)
    arbor = add(state, 'Dryad Arbor', seat)
    assert 'Saga' in effective_type_line(state, saga)
    assert 'Enchantment' in effective_type_line(state, saga)
    assert "Urza's" not in effective_type_line(state, saga)
    assert 'Dryad' in effective_type_line(state, arbor)
    assert arbor.colors == CARDS['Dryad Arbor']['colors'] == ['G']


@pytest.mark.parametrize('seat', [1, 2])
def test_later_ability_loss_does_not_undo_magus_type_layer(seat):
    from tests.test_ability_suppression import add as suppressed_add
    state = clean()
    magus = add(state, 'Magus of the Moon', seat)
    suppressed_add(state, 'Humility', 3-seat)
    land = add(state, 'Hallowed Fountain', seat)
    arbor = add(state, 'Dryad Arbor', seat)
    from rules_engine.continuous import printed_abilities_suppressed
    assert printed_abilities_suppressed(state, magus.id)
    assert mana_source_outputs(state, seat, land.id) == {'R': 1}
    assert mana_source_outputs(state, seat, arbor.id) == {}


@pytest.mark.parametrize('seat', [1, 2])
def test_keyword_counter_grant_survives_printed_land_ability_loss(seat):
    from rules_engine.continuous import has_keyword
    state = clean()
    add(state, 'Blood Moon', seat)
    arbor = add(state, 'Dryad Arbor', seat)
    arbor.counters['flying'] = 1
    assert has_keyword(state, arbor.id, 'flying')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Ancient Ziggurat', 'Unclaimed Territory', 'Cavern of Souls'])
def test_lost_printed_spending_restriction_does_not_restrict_intrinsic_mana(seat, name):
    from rules_engine.mana import can_pay_with_pool_and_lands
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from rules_engine.mana_restrictions import available_pool
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, name, seat)
    add(state, 'Blood Moon', seat)
    assert mana_source_outputs(state, seat, source.id) == {'R': 1}
    assert can_pay_with_pool_and_lands(state, seat, '{R}', spell_types={'Instant'})
    state = checked_action(state, RulesEngine(), seat, {'type': 'tap_land_for_mana',
        'card_id': source.id, 'color': 'R'})
    assert available_pool(state.players[seat], ('spell', {'Instant'}))[0]['R'] == 1
    assert state.players[seat].restricted_mana_pool == []


@pytest.mark.parametrize('seat', [1, 2])
def test_already_produced_mana_preserves_original_restriction_after_type_change(seat):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from rules_engine.mana_restrictions import available_pool
    from game_state.serializers import deserialize_match_snapshot
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, 'Ancient Ziggurat', seat)
    action = {'type': 'tap_land_for_mana', 'card_id': source.id, 'color': 'R'}
    state = checked_action(state, RulesEngine(), seat, action)
    assert available_pool(state.players[seat], ('spell', {'Instant'}))[0]['R'] == 0
    add(state, 'Blood Moon', seat)
    state.cards[source.id].tapped = False
    state = checked_action(state, RulesEngine(), seat, action)
    assert state.players[seat].mana_pool['R'] == 2
    assert available_pool(state.players[seat], ('spell', {'Instant'}))[0]['R'] == 1
    assert available_pool(state.players[seat], ('spell', {'Creature'}))[0]['R'] == 2
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert available_pool(restored.players[seat], ('spell', {'Instant'}))[0]['R'] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Ancient Ziggurat', 'Unclaimed Territory', 'Cavern of Souls'])
@pytest.mark.parametrize('effect', ['Blood Moon', 'Prismatic Omen'])
def test_intrinsic_mana_pays_actual_instant_cast_without_printed_restrictions(seat, name, effect):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, name, seat)
    add(state, effect, seat)
    spell = add_card(state, 'Lightning Bolt', seat, Zone.HAND, cards=CARDS)
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {'type': 'cast_spell', 'card_id': spell.id,
        'targets': {'target_player': 3-seat}})
    assert len(state.stack) == 1 and state.cards[source.id].tapped
    assert state.players[seat].restricted_mana_pool == []
    for _ in range(2):
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack and state.players[3-seat].life == 17


@pytest.mark.parametrize('seat', [1, 2])
def test_addition_keeps_printed_and_intrinsic_mana_restrictions_distinct(seat):
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from rules_engine.mana_abilities import mana_ability_specs
    from rules_engine.mana_restrictions import available_pool
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, 'Ancient Ziggurat', seat)
    add(state, 'Prismatic Omen', seat)
    specs = mana_ability_specs(source, state)
    restricted = next(spec for spec in specs if 'Spend this mana' in spec[2])
    intrinsic = next(spec for spec in specs if spec[2] == 'Add {R}.')
    action = {'type': 'activate_mana_ability', 'card_id': source.id, 'color': 'R',
              'ability_index': restricted[0]}
    state = checked_action(state, RulesEngine(), seat, action)
    assert available_pool(state.players[seat], ('spell', {'Instant'}))[0]['R'] == 0
    state.cards[source.id].tapped = False
    state = checked_action(state, RulesEngine(), seat, {**action, 'ability_index': intrinsic[0]})
    assert available_pool(state.players[seat], ('spell', {'Instant'}))[0]['R'] == 1
    assert available_pool(state.players[seat], ('spell', {'Creature'}))[0]['R'] == 2
