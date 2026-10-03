"""Crew, canonical land animation and copiable-characteristic boundaries."""
import json
from copy import copy
from pathlib import Path

import pytest

from effects.handlers import crew_vehicle, destroy_permanent, exile_permanent, return_permanent_to_hand, create_token_copy
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone, object_incarnation, assign_static_order_on_battlefield_entry, MatchFactory
from rules_engine.continuous import effective_combat_stats, effective_keywords
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_ai_recurring_engines import fixture
from tests.test_api_input_contracts import game, persist

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/type_effect_lifecycle.json').read_text())}


def permanent(state, name, seat=1):
    sample = MatchFactory.from_decks([{**ROWS[name], 'card_name': name, 'quantity': 1}], [], seed=7)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.BATTLEFIELD)
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def animate(state, land, seat):
    source = permanent(state, 'Nissa, Who Shakes the World', seat)
    surface = copy(source)
    surface.oracle_text = next(line.split(':', 1)[1].strip() for line in source.oracle_text.splitlines()
                              if line.startswith('+1:'))
    surface.types = []
    key, payload = infer_effect_from_oracle(state, surface, seat, {'target_card_id': land.id})
    assert key == 'add_counters' and payload['animate_land']
    resolve_effect(state, seat, key, {**payload, '__source_card_id': source.id})
    return source


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['crew', 'land'])
@pytest.mark.parametrize('destination,handler', [
    (Zone.HAND, return_permanent_to_hand), (Zone.EXILE, exile_permanent), (Zone.GRAVEYARD, destroy_permanent),
])
def test_resolution_types_and_stats_do_not_leak_into_new_zones(seat, family, destination, handler):
    state = fixture()
    card = permanent(state, "Smuggler's Copter" if family == 'crew' else 'Forest', seat)
    printed = (list(card.types), card.power, card.toughness, list(card.keywords))
    if family == 'crew':
        crew_vehicle(state, seat, {'card_id': card.id, 'effect_timestamp': object_incarnation(card)})
    else:
        animate(state, card, seat)
    assert 'Creature' in card.types
    assert effective_combat_stats(state, card.id) == (3, 3)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    card = state.cards[card.id]
    handler(state, seat, {'target_card_id': card.id})
    assert card.zone == destination
    assert (card.types, card.power, card.toughness, card.keywords) == printed
    assert 'Creature' in card.last_known_battlefield['types']
    assert card.last_known_battlefield['power'] == 3
    assert card.last_known_battlefield['toughness'] == 3
    assert card.base_stat_effects == [] and card.keyword_effects == []


@pytest.mark.parametrize('seat', [1, 2])
def test_land_animation_is_indefinite_and_not_an_intrinsic_characteristic(seat):
    state = fixture()
    card = permanent(state, 'Forest', seat)
    source = animate(state, card, seat)
    assert (card.power, card.toughness) == (None, None)
    assert card.keywords == []
    assert {'vigilance', 'haste'} <= set(effective_keywords(state, card.id))
    assert all(effect['source_card_id'] == source.id for effect in card.keyword_effects)
    RulesEngine()._clear_marked_damage(state)
    RulesEngine()._revert_crew_vehicles(state)
    assert effective_combat_stats(state, card.id) == (3, 3)
    assert 'Creature' in card.types
    assert {'vigilance', 'haste'} <= set(effective_keywords(state, card.id))


@pytest.mark.parametrize('seat', [1, 2])
def test_reentry_does_not_inherit_the_old_animation(seat):
    state = fixture()
    card = permanent(state, 'Forest', seat)
    animate(state, card, seat)
    exile_permanent(state, seat, {'target_card_id': card.id})
    state.players[seat].exile.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    assert card.types == ['Land']
    assert effective_combat_stats(state, card.id) == (None, None)
    assert 'haste' not in effective_keywords(state, card.id)
    assert not card.counters


@pytest.mark.parametrize('seat', [1, 2])
def test_token_copy_does_not_inherit_crew_but_can_be_crewed_itself(seat):
    state = fixture()
    card = permanent(state, "Smuggler's Copter", seat)
    crew_vehicle(state, seat, {'card_id': card.id})
    create_token_copy(state, seat, {'target_card_id': card.id})
    token = next(state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token)
    assert 'Creature' not in token.types and 'Artifact' in token.types
    assert token.type_effects == []
    crew_vehicle(state, seat, {'card_id': token.id})
    assert effective_combat_stats(state, token.id) == (3, 3)


@pytest.mark.parametrize('seat', [1, 2])
def test_token_copy_of_animated_land_is_not_an_elemental(seat):
    state = fixture()
    card = permanent(state, 'Forest', seat)
    animate(state, card, seat)
    create_token_copy(state, seat, {'target_card_id': card.id})
    token = next(state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token)
    assert set(token.types) == {'Land', 'Token'}
    assert (token.power, token.toughness) == (None, None)
    assert 'haste' not in effective_keywords(state, token.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('order', ['crew-first', 'persistent-first'])
def test_cleanup_does_not_erase_an_independent_type_addition(seat, order):
    from rules_engine.type_effects import add_type_effect
    state = fixture()
    card = permanent(state, "Smuggler's Copter", seat)
    # Effect-composition primitive, not an invented Oracle card or cast.
    if order == 'crew-first':
        crew_vehicle(state, seat, {'card_id': card.id})
    add_type_effect(state, card.id, ['Creature'])
    if order == 'persistent-first':
        crew_vehicle(state, seat, {'card_id': card.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    card = state.cards[card.id]
    before = serialize_match_snapshot(state)
    from rules_engine.continuous import continuous_layer_trace
    trace = continuous_layer_trace(state, card.id)
    assert len([row for row in trace['applied_layers'] if row['layer'].startswith('type-add:')]) == 2
    assert serialize_match_snapshot(state) == before
    RulesEngine()._revert_crew_vehicles(state)
    assert 'Creature' in card.types
    assert len(card.type_effects) == 1 and not card.type_effects[0]['until_end_of_turn']
    exile_permanent(state, seat, {'target_card_id': card.id})
    assert card.types == ['Artifact']


@pytest.mark.parametrize('seat', [1, 2])
def test_face_rebase_and_front_restoration_do_not_conflict_with_later_effects(seat):
    from rules_engine.type_effects import add_type_effect
    from rules_engine.card_faces import apply_transform_face
    state = fixture()
    card = permanent(state, 'Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun', seat)
    add_type_effect(state, card.id, ['Artifact'], until_end_of_turn=True)
    apply_transform_face(card, 1)
    assert set(card.types) == {'Land', 'Artifact'}
    RulesEngine()._revert_crew_vehicles(state)
    assert card.types == ['Land']
    add_type_effect(state, card.id, ['Creature'])
    return_permanent_to_hand(state, seat, {'target_card_id': card.id})
    assert card.types == ['Enchantment']
    assert not card.type_effects and card.type_effect_base is None
    assert card.selected_face_index in (None, 0)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('humility_first', [False, True])
def test_animation_keyword_and_stat_setters_follow_resolution_timestamps(seat, humility_first):
    state = fixture()
    card = permanent(state, 'Forest', seat)
    if humility_first:
        permanent(state, 'Humility', 3 - seat)
    animate(state, card, seat)
    if not humility_first:
        permanent(state, 'Humility', 3 - seat)
    assert effective_combat_stats(state, card.id) == ((3, 3) if humility_first else (4, 4))
    assert ('haste' in effective_keywords(state, card.id)) is humility_first
    assert ('vigilance' in effective_keywords(state, card.id)) is humility_first


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_crew_snapshot_keeps_printed_types_after_departure(seat):
    state = fixture()
    card = permanent(state, "Smuggler's Copter", seat)
    card.types.append('Creature')
    card.counters.update({'__crew_added_creature': 1, '__crew_until_turn': state.turn})
    old = serialize_match_snapshot(state)
    for raw in old['cards'].values():
        raw.pop('type_effects', None)
        raw.pop('type_effect_base', None)
    state = deserialize_match_snapshot(old)
    card = state.cards[card.id]
    return_permanent_to_hand(state, seat, {'target_card_id': card.id})
    assert card.types == ['Artifact'] and not card.counters


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('new_effect', ['crew', 'persistent'])
def test_legacy_crew_composes_with_new_effects_without_polluting_copiable_types(seat, new_effect):
    from rules_engine.type_effects import add_type_effect, copiable_types
    state = fixture()
    card = permanent(state, "Smuggler's Copter", seat)
    card.types.append('Creature')
    card.counters.update({'__crew_added_creature': 1, '__crew_until_turn': state.turn})
    if new_effect == 'crew':
        crew_vehicle(state, seat, {'card_id': card.id})
    else:
        add_type_effect(state, card.id, ['Creature'])
    assert copiable_types(card) == ['Artifact']
    assert any(effect['timestamp_origin'] == 'legacy_inferred' for effect in card.type_effects)
    RulesEngine()._revert_crew_vehicles(state)
    assert ('Creature' in card.types) is (new_effect == 'persistent')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['crew', 'land'])
def test_http_announcement_resolution_and_sqlite_restore_preserve_animation(game, seat, family):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, controller = game
    state = controller.state
    state.active_player = state.priority_player = seat
    card = permanent(state, "Smuggler's Copter" if family == 'crew' else 'Forest', seat)
    if family == 'crew':
        helper = permanent(state, 'Grizzly Bears', seat)
        action = {'type': 'crew', 'card_id': card.id, 'crew_card_ids': [helper.id]}
    else:
        source = permanent(state, 'Nissa, Who Shakes the World', seat)
        action = {'type': 'activate_loyalty', 'card_id': source.id, 'ability_index': 0,
                  'targets': {'target_card_id': card.id}}
    persist(controller)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert 'Creature' not in card.types
    for _ in range(8):
        current = main.ACTIVE_MATCHES[state.id].state
        if not current.stack:
            break
        response = client.post(f'/matches/{state.id}/action', json={
            'player_id': current.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    assert not current.stack
    assert 'Creature' in current.cards[card.id].types
    expected = client.get(f'/matches/{state.id}').json()
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(f'/matches/{state.id}').json() == expected
    restored = main.ACTIVE_MATCHES[state.id].state
    assert restored.cards[card.id].type_effects
    assert effective_combat_stats(restored, card.id) == (3, 3)
    exile_permanent(restored, seat, {'target_card_id': card.id})
    assert 'Creature' not in restored.cards[card.id].types


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['crew', 'land'])
@pytest.mark.parametrize('bulk', [False, True])
def test_animated_departure_preserves_actual_creature_death_triggers(seat, family, bulk):
    from effects.handlers import destroy_all_creatures
    from rules_engine.stack_engine import resolve_top_of_stack
    state = fixture()
    card = permanent(state, "Smuggler's Copter" if family == 'crew' else 'Forest', seat)
    payoff = permanent(state, 'Zulaport Cutthroat', seat)
    if family == 'crew':
        crew_vehicle(state, seat, {'card_id': card.id})
    else:
        animate(state, card, seat)
    if bulk:
        destroy_all_creatures(state, seat, {})
    else:
        destroy_permanent(state, seat, {'target_card_id': card.id})
    triggers = [item for item in state.stack if item.source_card_id == payoff.id]
    assert len(triggers) == (2 if bulk else 1)
    assert card.zone == Zone.GRAVEYARD and 'Creature' not in card.types
    for _ in range(12):
        if not state.stack:
            break
        resolve_top_of_stack(state)
    assert not state.stack
    assert state.players[3 - seat].life == 20 - (2 if bulk else 1)
    assert state.players[seat].life == 20 + (2 if bulk else 1)
