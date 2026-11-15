"""Default bounded proof and native copies must not confuse Battle metadata.

Positions are declared model/consumer inputs, not paid lifecycle witnesses.
"""
from copy import deepcopy
import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot, _card_snapshot, _card_from_snapshot
from rules_engine.graveyard_inventory import public_graveyard_inventory
from rules_engine.copiable_values import values, apply
from rules_engine.alternative_casts import restore_printed_characteristics
from ai.information import decision_view
from ai.pending_effects import planning_copy
from tests.test_empty_hand_attack_witness import ROWS, position
from tests.test_linked_damage_targets import raw_card
from tests.test_battle_characteristics import position as battle_position, mark, rejected


def ordinary_position(seat):
    state, _ = position(seat, 'Sheoldred, the Apocalypse', counter=True)
    card = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    return state, card


@pytest.mark.parametrize('seat', [1, 2])
def test_default_metadata_preserves_existing_positive_inventory_domain(seat):
    state, card = ordinary_position(seat)
    assert card.printed_defense is None and card.battle_protector is None
    mark('ordinary-default-metadata-positive-inventory-assertion-reached')
    assert public_graveyard_inventory(state, seat)['status'] == 'inert'


@pytest.mark.parametrize('seat', [1, 2])
def test_nondefault_defense_or_protector_cannot_certify_inertness(seat):
    state, card = ordinary_position(seat)
    assert public_graveyard_inventory(state, seat)['status'] == 'inert'
    for field, value in (('printed_defense', '3'), ('battle_protector', 3-seat)):
        setattr(card, field, value)
        assert public_graveyard_inventory(state, seat)['status'] == 'unknown'
        setattr(card, field, None)
        assert public_graveyard_inventory(state, seat)['status'] == 'inert'
    _, battle, _, _ = battle_position(seat)
    apply(card, values(battle))
    restore_printed_characteristics(card)
    assert card.name == 'Lightning Bolt' and card.printed_defense is None
    assert public_graveyard_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_planning_and_information_copies_preserve_only_visible_battle_metadata(seat):
    state, battle, _, _ = battle_position(seat)
    for player in state.players.values():
        for zone in ('library', 'hand', 'graveyard', 'battlefield', 'exile'):
            ids = getattr(player, zone)
            if battle.id in ids: ids.remove(battle.id)
    battle.move_to_zone(Zone.BATTLEFIELD)
    state.players[seat].battlefield.append(battle.id)
    battle.battle_protector = 3-seat
    battle.counters['defense'] = 2
    hidden = next(c for c in state.cards.values() if c.owner == 3-seat and 'Battle' in c.types)
    for zone in ('library', 'hand'):
        ids = getattr(state.players[3-seat], zone)
        if hidden.id in ids: ids.remove(hidden.id)
    hidden.move_to_zone(Zone.LIBRARY)
    state.players[3-seat].library.append(hidden.id)
    before = serialize_match_snapshot(state)
    plan = planning_copy(state)
    view, _ = decision_view(state, seat, [])
    for copied in (plan.cards[battle.id], view.cards[battle.id]):
        assert copied.printed_defense == '3' and copied.battle_protector == 3-seat
        assert copied.counters['defense'] == 2
        copied.counters['defense'] = 1
    assert view.cards[hidden.id].printed_defense is None
    assert view.cards[hidden.id].battle_protector is None and not view.cards[hidden.id].name
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_whole_match_snapshot_retains_known_battle_characteristics(seat):
    state, battle, _, _ = battle_position(seat)
    battle.battle_protector = 3-seat
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.cards[battle.id].printed_defense == '3'
    assert restored.cards[battle.id].battle_protector == 3-seat
    assert values(restored.cards[battle.id])['printed_defense'] == '3'


@pytest.mark.parametrize('seat', [1, 2])
def test_v3_current_defense_mismatch_is_rejected_on_restore(seat):
    state, battle, _, _ = battle_position(seat)
    raw = _card_snapshot(battle)
    raw['printed_defense'] = '4'
    mark('v3-current-defense-mismatch-restore-assertion-reached')
    rejected(lambda: _card_from_snapshot(deepcopy(raw), state.players))
    mark('Battle-metadata-consumer-whole-module-passed')
