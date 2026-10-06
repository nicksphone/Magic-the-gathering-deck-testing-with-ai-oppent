"""Canonical type-quality regression for nested retained-source target hints."""
from copy import copy, deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.attachments import attach_if_legal
from rules_engine.protection import source_matches_quality
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.targeting import validate_protection_targets
from rules_engine.type_effects import effective_types
from tests.test_color_consumer_goldens import no_database_or_network, checked, position, restart, resolve_copy
from tests.test_basic_land_hooks import add, attach_song_fixture


SOURCE = Path(__file__).parent / 'fixtures/aura_costs.json'
SOURCE_SHA = 'c6861515e20337ec3c32763a6ca89332e0ed665aad54f8bb520261c4e5a9d17c'


def attach_mantle_fixture(state, target, seat):
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    row = next(card for card in json.loads(raw) if card['name'] == 'Spirit Mantle')
    assert row['oracle_id']
    sample = MatchFactory.from_decks([{**row, 'card_name': row['name'], 'quantity': 1}], [], seed=71)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.BATTLEFIELD)
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    # Controlled attachment with the stack occupied, not a sorcery-speed cast.
    assert attach_if_legal(state, card.id, target)


def animate_fixture(state, target, seat):
    raw = (Path(__file__).parent / 'fixtures/type_effect_lifecycle.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '057372efdfa60d499a94a39f6771831beece600ee0fff0819b47a39e6337e486'
    row = next(card for card in json.loads(raw) if card['name'] == 'Nissa, Who Shakes the World')
    assert row['oracle_id']
    sample = MatchFactory.from_decks([{**row, 'card_name': row['name'], 'quantity': 1}], [], seed=71)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.BATTLEFIELD)
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    surface = copy(card)
    surface.oracle_text = next(line.split(':', 1)[1].strip() for line in card.oracle_text.splitlines()
                              if line.startswith('+1:'))
    surface.types = []
    key, payload = infer_effect_from_oracle(state, surface, seat, {'target_card_id': target})
    assert key == 'add_counters' and payload['animate_land']
    # Controlled canonical ability effect, not a sorcery-timing loyalty activation.
    resolve_effect(state, seat, key, {**payload, '__source_card_id': card.id})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('converted_at_departure', [False, True])
def test_old_source_type_not_same_id_reentry_controls_nested_target_hints(seat, converted_at_departure):
    state = position(seat)
    source = add(state, 'Royal Assassin', seat)
    target = add(state, 'Dryad Arbor', 3-seat)
    target.tapped = True
    state = checked(state, seat, {'type': 'activate_ability', 'card_id': source.id,
        'ability_index': 0, 'targets': {'target_card_id': target.id}})
    stack_id = state.stack[-1].id
    if converted_at_departure:
        state = attach_song_fixture(state, source.id, seat)
        # Controlled effect primitive; no illegal Unsummon on a noncreature land.
        resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source.id})
    else:
        # This departure is an actual legal instant response and resolution.
        rows = json.loads((Path(__file__).parent / 'fixtures/defensive_responses.json').read_text())
        row = next(card for card in rows if card['name'] == 'Unsummon')
        sample = MatchFactory.from_decks([{**row, 'card_name': row['name'], 'quantity': 1}], [], seed=71)
        bounce = next(iter(sample.cards.values()))
        bounce.id = state.allocate_object_id()
        bounce.owner = bounce.controller = seat
        bounce.move_to_zone(Zone.HAND)
        state.cards[bounce.id] = bounce
        state.players[seat].hand.append(bounce.id)
        state = checked(state, seat, {'type': 'cast_spell', 'card_id': bounce.id,
            'targets': {'target_card_id': source.id}})
        for _ in range(8):
            if state.cards[bounce.id].zone != Zone.STACK:
                break
            state = checked(state, state.priority_player, {'type': 'pass_priority'})
        assert state.cards[bounce.id].zone == Zone.GRAVEYARD
    assert state.cards[source.id].zone == Zone.HAND
    receipt = deepcopy(state.stack[-1].payload['__source_lki'])
    assert ('Creature' in receipt['types']) == (not converted_at_departure)
    # Controlled same-ID reentry as the opposite type, not a played episode.
    card = state.cards[source.id]
    state.players[seat].hand.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    state = attach_song_fixture(state, card.id, seat)
    if converted_at_departure:
        animate_fixture(state, card.id, seat)
        assert {'Land', 'Creature'} <= set(effective_types(state, card.id))
    attach_mantle_fixture(state, target.id, 3-seat)
    state = restart(state)
    card = state.cards[source.id]
    assert object_incarnation(card) != receipt['battlefield_incarnation']
    assert state.stack[-1].id == stack_id and state.stack[-1].controller == seat
    assert state.stack[-1].payload['__source_lki'] == receipt
    before = serialize_match_snapshot(state)
    assert source_matches_quality(card, 'creature', state=state, source_lki=receipt) == (not converted_at_departure)
    assert source_matches_quality(card, 'land', state=state, source_lki=receipt) == converted_at_departure
    assert validate_protection_targets(state, card, {'target_card_id': target.id}, source_lki=receipt)[0] == converted_at_departure
    assert serialize_match_snapshot(state) == before
    result = resolve_copy(state)
    assert result.cards[target.id].zone == (Zone.GRAVEYARD if converted_at_departure else Zone.BATTLEFIELD)
    assert '_retained_source_lki' not in vars(state.cards[source.id])
