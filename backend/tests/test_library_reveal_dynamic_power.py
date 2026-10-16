"""Real printed CDA selection and explicitly noncanonical unknown-stat protocols."""
import json

import pytest

from card_data.seed_cards import seed_card_payload
from effects.handlers import topdeck_reveal_creature_to_hand
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from tests.damage_life_printed_79 import canonical_card


ADELINE = 'Adeline, Resplendent Cathar'


def position(seat):
    island = {**seed_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}
    state = MatchFactory.from_decks([island], [island], seed=83)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    state.mechanic_choice_players = {seat}
    return state


def add(state, name, seat, zone, *, controller=None):
    cid = state.allocate_object_id()
    if name == ADELINE:
        raw = seed_card_payload(name)
        sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=83)
        card = next(iter(sample.cards.values()))
        card.id = cid
        card.owner = seat
        card.controller = seat if controller is None else controller
        card.move_to_zone(zone)
        assert card.oracle_text == raw['oracle_text']
        assert card.printed_power == '*' and card.power is None
    else:
        card = canonical_card(name, id=cid, owner=seat,
                              controller=seat if controller is None else controller, zone=zone)
    state.cards[cid] = card
    getattr(state.players[seat], zone.value).append(cid)
    return card


def reveal(state, seat):
    topdeck_reveal_creature_to_hand(state, seat, {
        'top_n': 1, 'power_max': 2, 'optional': True, 'bottom_random': False,
    })


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creatures', [0, 2, 3])
@pytest.mark.parametrize('stale_controller', [False, True])
def test_real_star_eligibility_uses_library_owner_not_stale_controller(seat, creatures, stale_controller):
    state = position(seat)
    for _ in range(creatures):
        add(state, 'Centaur Courser', seat, Zone.BATTLEFIELD)
    for _ in range(4):
        add(state, 'Centaur Courser', 3-seat, Zone.BATTLEFIELD)
    card = add(state, ADELINE, seat, Zone.LIBRARY,
               controller=3-seat if stale_controller else seat)
    assert effective_combat_stats(state, card.id)[0] == creatures
    reveal(state, seat)
    assert (card.id in state.pending_mechanic_choice['options']) == (creatures <= 2)
    assert card.power is None and card.printed_power == '*'
    assert card.zone == Zone.LIBRARY


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('power,eligible', [(None, False), ('unsupported', False), ('2', True)])
def test_unknown_power_is_not_zero_and_legacy_numeric_protocol_is_retained(seat, power, eligible):
    state = position(seat)
    # Deliberate internal metadata protocol, not a named official card fixture.
    card = CardInstance(id=state.allocate_object_id(), name='UNKNOWN STAT PROTOCOL',
        owner=seat, controller=seat, zone=Zone.LIBRARY, types=['Creature'],
        power=power, toughness=2)
    state.cards[card.id] = card
    state.players[seat].library.append(card.id)
    reveal(state, seat)
    assert (card.id in state.pending_mechanic_choice['options']) is eligible
    assert card.power == power


@pytest.mark.parametrize('seat', [1, 2])
def test_real_dynamic_selection_resumes_from_snapshot_without_replacing_printed_power(seat):
    state = position(seat)
    for _ in range(2):
        add(state, 'Centaur Courser', seat, Zone.BATTLEFIELD)
    card = add(state, ADELINE, seat, Zone.LIBRARY, controller=3-seat)
    reveal(state, seat)
    assert card.id in state.pending_mechanic_choice['options']
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(before)))
    assert serialize_match_snapshot(restored) == before
    selected = checked_action(restored, RulesEngine(), seat,
                              {'type': 'choose_mechanic', 'card_ids': [card.id]})
    assert selected.cards[card.id].zone == Zone.HAND
    assert card.id in selected.players[seat].hand
    assert selected.pending_mechanic_choice is None
    assert selected.cards[card.id].power is None
    assert selected.cards[card.id].printed_power == '*'


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_mana_value_tie_uses_real_characteristic_power(seat):
    state = position(seat)
    state.mechanic_choice_players = set()
    for _ in range(4):
        add(state, 'Centaur Courser', seat, Zone.BATTLEFIELD)
    dynamic = add(state, ADELINE, seat, Zone.LIBRARY)
    fixed = add(state, 'Centaur Courser', seat, Zone.LIBRARY)
    assert dynamic.mana_cost == '{1}{W}{W}' and fixed.mana_cost == '{2}{G}'
    assert effective_combat_stats(state, dynamic.id)[0] == 4
    topdeck_reveal_creature_to_hand(state, seat,
        {'top_n': 2, 'mv_max': 3, 'bottom_random': False})
    assert dynamic.id in state.players[seat].hand
    assert fixed.id in state.players[seat].library
