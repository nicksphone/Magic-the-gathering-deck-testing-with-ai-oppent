"""Canonical devotion transitions through public views and combat consumers."""
import json
from pathlib import Path

import pytest

from game_state.serializers import (
    serialize_card_view, serialize_match_snapshot, deserialize_match_snapshot,
)
from game_state.state import Step, Zone
from rules_engine.move_generator import legal_moves
from rules_engine.type_effects import effective_types, add_type_effect, copiable_types, devotion_type_condition
from rules_engine.continuous import printed_abilities_suppressed, effective_combat_stats, continuous_layer_trace
from game_state.state import assign_static_order_on_battlefield_entry
from tests.test_ai_recurring_engines import fixture, add
from tests.test_api_input_contracts import game, persist

FIXTURES = Path(__file__).parent / 'fixtures'
CARDS = {row['name']: row for filename in ('devotion.json', 'static_admission.json', 'conditional_types.json')
         for row in json.loads((FIXTURES / filename).read_text())}

GODS = [('Heliod, God of the Sun', 'W', 5), ('Thassa, God of the Sea', 'U', 5),
        ('Erebos, God of the Dead', 'B', 5), ('Purphoros, God of the Forge', 'R', 5),
        ('Nylea, God of the Hunt', 'G', 5), ('Ephara, God of the Polis', 'WU', 7),
        ('Karametra, God of Harvests', 'GW', 7), ('Xenagos, God of Revels', 'RG', 7),
        ('Iroas, God of Victory', 'RW', 7), ('Mogis, God of Slaughter', 'BR', 7),
        ('Athreos, God of Passage', 'WB', 7), ('Keranos, God of Storms', 'UR', 7),
        ('Kruphix, God of Horizons', 'GU', 7), ('Phenax, God of Deception', 'UB', 7),
        ('Pharika, God of Affliction', 'BG', 7)]

DEVOTION_SOURCES = {'W': 'Soul Warden', 'U': 'Cloudfin Raptor', 'B': 'Blood Artist',
                    'R': 'Fanatic of Mogis', 'G': 'Elvish Mystic'}


def position(name, seat):
    state = fixture()
    state.active_player = state.priority_player = seat
    state.step = Step.DECLARE_ATTACKERS
    god = add(state, name, seat, cards=CARDS)
    god.summoning_sick = False
    return state, god


def fund_devotion(state, name, seat):
    count = 2 if name.startswith('Nylea') else 3
    return [add(state, 'Burning-Tree Emissary', seat, cards=CARDS) for _ in range(count)]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_low_devotion_public_view_is_enchantment_not_creature(seat, name):
    state, god = position(name, seat)
    before = serialize_match_snapshot(state)
    view = serialize_card_view(state, god.id)
    assert 'Enchantment' in view['types']
    assert 'Creature' not in view['types']
    assert (view['power'], view['toughness']) == (None, None)
    assert 'Creature' in god.types, 'Continuous queries must not rewrite copiable types'
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_low_devotion_is_not_an_attack_candidate(seat, name):
    state, god = position(name, seat)
    assert not any(god.id in move.get('options', [])
                   for move in legal_moves(state, seat) if move['type'] == 'attack')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,count', [('Nylea, God of the Hunt', 2),
                                      ('Xenagos, God of Revels', 3)])
def test_live_threshold_and_reentry_survive_snapshot_without_losing_printed_types(seat, name, count):
    state, god = position(name, seat)
    payoffs = [add(state, 'Burning-Tree Emissary', seat, cards=CARDS) for _ in range(count)]
    assert 'Creature' in serialize_card_view(state, god.id)['types']
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    removed = restored.cards[payoffs[0].id]
    restored.players[seat].battlefield.remove(removed.id)
    restored.players[seat].exile.append(removed.id)
    removed.move_to_zone(Zone.EXILE)
    assert 'Creature' not in serialize_card_view(restored, god.id)['types']
    restored.players[seat].exile.remove(removed.id)
    restored.players[seat].battlefield.append(removed.id)
    removed.move_to_zone(Zone.BATTLEFIELD)
    assert 'Creature' in serialize_card_view(restored, god.id)['types']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_condition_does_not_remove_creature_type_outside_battlefield(seat, name):
    state = fixture()
    god = add(state, name, seat, Zone.HAND, cards=CARDS)
    view = serialize_card_view(state, god.id)
    assert 'Creature' in view['types']
    assert view['power'] == god.power


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
@pytest.mark.parametrize('funded', [False, True])
def test_type_layer_precedes_humility_and_retains_ability_when_not_creature(seat, name, funded):
    from tests.test_static_ability_suppression import add as suppressed_add
    state, god = position(name, seat)
    if funded:
        fund_devotion(state, name, seat)
    suppressed_add(state, 'Humility', 3-seat)
    before = serialize_match_snapshot(state)
    assert ('Creature' in effective_types(state, god)) == funded
    assert printed_abilities_suppressed(state, god.id) == funded
    view = serialize_card_view(state, god.id)
    assert ('indestructible' in view['keywords']) != funded
    assert (view['power'], view['toughness']) == ((1, 1) if funded else (None, None))
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_later_animation_layer_timestamp_overrides_removal_but_preserves_copiable_types(seat, name):
    state, god = position(name, seat)
    assign_static_order_on_battlefield_entry(state, god.id)
    base = copiable_types(god)
    add_type_effect(state, god.id, ['Creature'], until_end_of_turn=True)
    assert 'Creature' in effective_types(state, god)
    assert copiable_types(god) == base
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    from rules_engine.engine import RulesEngine
    RulesEngine()._revert_crew_vehicles(state)
    assert 'Creature' not in effective_types(state, god.id)
    assert copiable_types(state.cards[god.id]) == base


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_becoming_noncreature_removes_attacker_and_return_does_not_rejoin(seat, name):
    from rules_engine.combat import declare_attackers
    from rules_engine.state_based_actions import apply_state_based_actions
    from rules_engine.zone_actions import sacrifice_selected
    state, god = position(name, seat)
    resources = fund_devotion(state, name, seat)
    declare_attackers(state, [god.id])
    assert god.id in state.attackers
    assert sacrifice_selected(state, seat, [resources[0].id])
    apply_state_based_actions(state)
    assert god.id not in state.attackers
    assert god.id not in state.attack_targets
    add(state, 'Burning-Tree Emissary', seat, cards=CARDS)
    apply_state_based_actions(state)
    assert 'Creature' in effective_types(state, god)
    assert god.id not in state.attackers
    assert god.tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
@pytest.mark.parametrize('funded', [False, True])
def test_simultaneous_sacrifice_captures_types_before_all_devotion_sources_leave(seat, name, funded):
    from rules_engine.zone_actions import sacrifice_selected
    state, god = position(name, seat)
    artist = add(state, 'Blood Artist', seat)
    resources = fund_devotion(state, name, seat) if funded else []
    assert sacrifice_selected(state, seat, [god.id, *[card.id for card in resources]])
    assert ('Creature' in god.last_known_battlefield['types']) == funded
    rewards = [item for item in state.stack if item.source_card_id == artist.id]
    assert len(rewards) == (len(resources) + 1 if funded else 0)
    assert 'Creature' in effective_types(state, god), 'Graveyard characteristics are printed'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_layer_trace_and_target_hints_use_same_type_view(seat, name):
    from rules_engine.oracle_effects import inspect_target_hints
    state, god = position(name, seat)
    pump = add(state, 'Aspect of Hydra', seat, Zone.HAND, cards=CARDS)
    assert god.id not in [row['id'] for row in inspect_target_hints(state, pump, seat)['creature_targets']]
    trace = continuous_layer_trace(state, god.id)
    assert any(row['layer'] == 'type-remove:Creature' for row in trace['applied_layers'])
    fund_devotion(state, name, seat)
    assert god.id in [row['id'] for row in inspect_target_hints(state, pump, seat)['creature_targets']]
    assert not any(row['layer'] == 'type-remove:Creature' for row in continuous_layer_trace(state, god.id)['applied_layers'])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_opposing_devotion_does_not_change_type_or_creature_board_value(seat, name):
    from ai.heuristics import _board_value
    state, god = position(name, seat)
    before = _board_value(state, seat)
    fund_devotion(state, name, 3-seat)
    assert 'Creature' not in effective_types(state, god)
    assert _board_value(state, seat) == before
    fund_devotion(state, name, seat)
    assert 'Creature' in effective_types(state, god)
    assert _board_value(state, seat) > before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_reanimated_noncreature_remains_sick_when_threshold_is_reached(seat, name):
    from effects.handlers import return_permanent_from_graveyard_to_battlefield
    state = fixture()
    state.active_player = state.priority_player = seat
    state.step = Step.DECLARE_ATTACKERS
    god = add(state, name, seat, Zone.GRAVEYARD, cards=CARDS)
    god.summoning_sick = False
    return_permanent_from_graveyard_to_battlefield(state, seat, {'target_card_id': god.id})
    assert god.zone == Zone.BATTLEFIELD
    assert 'Creature' not in effective_types(state, god)
    assert god.summoning_sick
    fund_devotion(state, name, seat)
    assert 'Creature' in effective_types(state, god)
    assert not any(god.id in move.get('options', [])
                   for move in legal_moves(state, seat) if move['type'] == 'attack')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_control_change_uses_new_controller_devotion_and_resets_creature_readiness(seat, name):
    from effects.handlers import change_control
    state, god = position(name, seat)
    fund_devotion(state, name, seat)
    change_control(state, 3-seat, {'target_card_id': god.id})
    assert 'Creature' not in effective_types(state, god)
    assert god.summoning_sick
    fund_devotion(state, name, 3-seat)
    assert 'Creature' in effective_types(state, god)
    assert god.summoning_sick


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_http_types_targets_and_sqlite_restart_track_threshold(game, seat, name):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, controller = game
    state = controller.state
    state.active_player = state.priority_player = seat
    state.step = Step.DECLARE_ATTACKERS
    god = add(state, name, seat, cards=CARDS)
    god.summoning_sick = False
    persist(controller)
    moves = client.get(f'/matches/{state.id}/legal-moves', params={'player_id': seat})
    assert moves.status_code == 200, moves.text
    assert not any(god.id in move.get('options', []) for move in moves.json()['moves'] if move['type'] == 'attack')
    # The HTTP response is tested through the production serializer after restart.
    fund_devotion(state, name, seat)
    persist(controller)
    expected = client.get(f'/matches/{state.id}').json()
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(f'/matches/{state.id}').json() == expected
    restored = main.ACTIVE_MATCHES[state.id].state
    assert 'Creature' in serialize_card_view(restored, god.id)['types']
    assert 'Creature' in restored.cards[god.id].types


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,colors,threshold', GODS)
def test_all_fifteen_canonical_gods_transition_at_exact_threshold(seat, name, colors, threshold):
    from rules_engine.devotion import devotion_count
    state, god = position(name, seat)
    instruction = devotion_type_condition(god.oracle_text, god.name)
    assert instruction is not None
    assert set(instruction[0]) == set(colors)
    assert instruction[1] == threshold
    while devotion_count(state, seat, colors) < threshold - 1:
        add(state, DEVOTION_SOURCES[colors[0]], seat, cards=CARDS)
    assert 'Creature' not in effective_types(state, god)
    last = add(state, DEVOTION_SOURCES[colors[-1]], seat, cards=CARDS)
    assert devotion_count(state, seat, colors) == threshold
    assert 'Creature' in effective_types(state, god)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert 'Creature' in effective_types(restored, god.id)
    restored.players[seat].battlefield.remove(last.id)
    restored.players[seat].exile.append(last.id)
    restored.cards[last.id].move_to_zone(Zone.EXILE)
    assert 'Creature' not in effective_types(restored, god.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_correlated_subtype_absent_only_while_creature_type_is_absent(seat, name):
    from rules_engine.continuous import _has_subtype
    state, god = position(name, seat)
    assert not _has_subtype(god, 'god', state=state)
    assign_static_order_on_battlefield_entry(state, god.id)
    add_type_effect(state, god.id, ['Creature'], until_end_of_turn=True)
    assert _has_subtype(god, 'god', state=state)
    from rules_engine.engine import RulesEngine
    RulesEngine()._revert_crew_vehicles(state)
    assert not _has_subtype(god, 'god', state=state)


@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_supported_type_clause_has_no_stale_static_or_devotion_gap(name):
    from rules_engine.coverage import static_coverage_details, known_unsupported_mechanics
    row = CARDS[name]
    assert static_coverage_details(row['oracle_text'], card_name=name) == []
    assert 'unsupported devotion instruction' not in known_unsupported_mechanics(row['oracle_text'], card_name=name)


@pytest.mark.parametrize('seat', [1, 2])
def test_type_departure_preserves_remaining_members_of_announced_band(seat):
    from rules_engine.combat import declare_attackers, declare_blockers
    from rules_engine.state_based_actions import apply_state_based_actions
    from rules_engine.zone_actions import sacrifice_selected
    rows = {row['name']: row for row in json.loads(
        (FIXTURES / 'combat_ability_provenance.json').read_text())}
    state, god = position('Heliod, God of the Sun', seat)
    heroes = [add(state, 'Benalish Hero', seat, cards=rows) for _ in range(2)]
    for hero in heroes:
        hero.summoning_sick = False
    resources = [add(state, 'Soul Warden', seat, cards=CARDS) for _ in range(2)]
    blocker = add(state, 'Grizzly Bears', 3-seat)
    members = [god.id, *[hero.id for hero in heroes]]
    declare_attackers(state, members, bands=[members])
    assert sacrifice_selected(state, seat, [resources[0].id])
    apply_state_based_actions(state)
    assert god.id not in state.attackers
    assert all(hero.id in state.attackers for hero in heroes)
    declare_blockers(state, {heroes[0].id: [blocker.id]})
    assert all(state.blocks.get(hero.id) == [blocker.id] for hero in heroes)
    assert god.id not in state.blocks


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Nylea, God of the Hunt', 'Xenagos, God of Revels'])
def test_counted_life_loss_uses_current_types_and_correlated_subtypes(seat, name):
    from effects.handlers import _count_controlled_type, lose_life
    state, god = position(name, seat)
    assert _count_controlled_type(state, seat, 'creatures') == 0
    assert _count_controlled_type(state, seat, 'gods') == 0
    assert _count_controlled_type(state, seat, 'enchantments') == 1
    before = state.players[3-seat].life
    lose_life(state, seat, {'target_player': 3-seat, 'count_type': 'creatures'})
    assert state.players[3-seat].life == before
    resources = fund_devotion(state, name, seat)
    assert _count_controlled_type(state, seat, 'creatures') == len(resources) + 1
    assert _count_controlled_type(state, seat, 'gods') == 1
