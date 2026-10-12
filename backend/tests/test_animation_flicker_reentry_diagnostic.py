"""Actual paid blink invalidates the earlier activation's source reference."""
import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, object_incarnation, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.type_effects import effective_types
from tests.test_canonical_global_flash_audit import ROWS as FLASH_ROWS
from tests.test_canonical_land_animation_audit import FAMILIES, ROWS, action, position, resolve, snapshot
from tests.test_linked_damage_targets import raw_card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_paid_flicker_returns_fresh_land_and_old_pending_animation_cannot_apply(seat, name):
    state, land = position(seat, name)
    grant = raw_card(state, FLASH_ROWS['Leyline of Anticipation'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, grant.id)
    spell = raw_card(state, ROWS['Flicker'], seat, Zone.HAND)
    assert spell.oracle_text == "Exile target nontoken permanent, then return it to the battlefield under its owner's control."
    state.players[seat].mana_pool = ({'C': 3, 'W': 1} if name == 'Mutavault'
                                    else {'C': 7, 'W': 3, 'U': 2})
    before = snapshot(state)
    candidate = resolve(checked_action(state, RulesEngine(), seat, action(land)))
    assert 'Creature' in effective_types(candidate, land.id)
    reference = (object_incarnation(candidate.cards[land.id]), candidate.cards[land.id].zone_change_sequence)
    candidate = checked_action(candidate, RulesEngine(), seat, action(candidate.cards[land.id]))
    pending = candidate.stack[-1]
    assert pending.payload['source_incarnation'] == reference[0]
    assert pending.payload['source_zone_change_sequence'] == reference[1]
    candidate = checked_action(candidate, RulesEngine(), seat,
                               {'type': 'cast_spell', 'card_id': spell.id,
                                'targets': {'target_card_id': land.id}})
    assert candidate.stack[-1].payload['mana_spent'] == 2
    for _ in range(2):
        candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
    assert len(candidate.stack) == 1 and candidate.stack[0].id == pending.id
    returned = candidate.cards[land.id]
    assert returned.zone == Zone.BATTLEFIELD and returned.controller == returned.owner == seat
    assert land.id in candidate.players[seat].battlefield and land.id not in candidate.players[seat].exile
    assert object_incarnation(returned) > reference[0]
    assert returned.zone_change_sequence == reference[1] + 2
    assert 'Creature' not in effective_types(candidate, land.id)
    assert sum(candidate.players[seat].mana_pool.values()) == 0
    restored = deserialize_match_snapshot(snapshot(candidate))
    assert snapshot(restored) == snapshot(candidate)
    assert restored.stack[0].payload == candidate.stack[0].payload
    candidate = resolve(restored)
    returned = candidate.cards[land.id]
    assert returned.zone == Zone.BATTLEFIELD
    assert returned.controller == returned.owner == seat
    assert 'Creature' not in effective_types(candidate, land.id)
    assert not returned.type_effects
    assert not returned.base_stat_effects
    assert not returned.keyword_effects
    assert not candidate.stack
    assert snapshot(state) == before
