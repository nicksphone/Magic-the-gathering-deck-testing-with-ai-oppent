"""Strict actual response/reentry requirement, separate from departure control."""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_card_view
from game_state.state import Step, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_canonical_land_animation_audit import FAMILIES, ROWS, action, position, record, resolve, snapshot
from tests.test_canonical_global_flash_audit import ROWS as FLASH_ROWS
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_flash_response_reentry_must_not_receive_old_pending_animation(request, seat, name):
    state, land = position(seat, name)
    grant = raw_card(state, FLASH_ROWS['Leyline of Anticipation'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, grant.id)
    spell = raw_card(state, ROWS['Flicker'], seat, Zone.HAND)
    assert ROWS['Flicker']['mana_cost'] == '{1}{W}'
    state.players[seat].mana_pool = ({'C': 3, 'W': 1} if name == 'Mutavault'
                                    else {'C': 7, 'W': 3, 'U': 2})
    before = snapshot(state)
    candidate = resolve(checked_action(state, RulesEngine(), seat, action(land)))
    candidate = checked_action(candidate, RulesEngine(), seat, action(candidate.cards[land.id]))
    pending = candidate.stack[-1]
    old = (object_incarnation(candidate.cards[land.id]), candidate.cards[land.id].zone_change_sequence)
    assert pending.payload['source_incarnation'] == old[0]
    assert pending.payload['source_zone_change_sequence'] == old[1]
    candidate = checked_action(candidate, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': land.id},
    })
    for _ in range(2):
        candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
    assert len(candidate.stack) == 1 and candidate.stack[0].id == pending.id
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    assert snapshot(state) == before
    record(request, candidate, phase='actual_pending_reentry_requirement', before=before,
           old_incarnation=old, pending_payload=pending.payload)
    returned = candidate.cards[land.id]
    assert returned.zone == Zone.BATTLEFIELD, 'Canonical immediate blink return is an external prerequisite'
    assert (object_incarnation(returned), returned.zone_change_sequence) != old
    assert returned.summoning_sick and returned.owner == returned.controller == seat
    candidate = resolve(candidate)
    assert 'Creature' not in serialize_card_view(candidate, land.id)['types']
    assert not candidate.cards[land.id].type_effects
    assert snapshot(deserialize_match_snapshot(snapshot(candidate))) == snapshot(candidate)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_offturn_priority_activation_and_deterministic_snapshot_replay(request, seat, name):
    state, land = position(seat, name)
    state.active_player = 3-seat
    state.step = Step.UPKEEP
    before = snapshot(state)
    assert any(move['type'] == 'activate_ability' and move.get('card_id') == land.id
               for move in RulesEngine().legal_moves(state, seat))
    results = []
    for root in (state, deserialize_match_snapshot(before)):
        candidate = resolve(checked_action(root, RulesEngine(), seat, action(root.cards[land.id])))
        assert snapshot(root) == before
        assert sum(candidate.players[seat].mana_pool.values()) == 0
        assert 'Creature' in serialize_card_view(candidate, land.id)['types']
        results.append(snapshot(candidate))
    assert results[0] == results[1]
    record(request, candidate, phase='offturn_checked_deterministic_replay', before=before)
