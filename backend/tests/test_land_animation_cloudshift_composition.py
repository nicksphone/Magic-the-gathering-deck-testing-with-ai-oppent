"""Actual canonical response against a pending old-incarnation animation."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_card_view
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_canonical_land_animation_audit import FAMILIES, action, position, record, resolve, snapshot
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures/cloudshift_compound_audit'
for entry in (FIXTURES / 'SHA256SUMS').read_text().splitlines():
    digest, filename = entry.split()
    assert hashlib.sha256((FIXTURES / Path(filename).name).read_bytes()).hexdigest() == digest
CLOUDSHIFT = json.loads((FIXTURES / 'cloudshift.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_checked_cloudshift_reentry_invalidates_pending_animation_and_replays(request, seat, name):
    state, land = position(seat, name)
    spell = raw_card(state, CLOUDSHIFT, seat, Zone.HAND)
    assert CLOUDSHIFT['mana_cost'] == '{W}'
    state.players[seat].mana_pool = ({'C': 2, 'W': 1} if name == 'Mutavault'
                                    else {'C': 6, 'W': 3, 'U': 2})
    before = snapshot(state)
    results = []
    for root in (state, deserialize_match_snapshot(before)):
        candidate = resolve(checked_action(root, RulesEngine(), seat, action(root.cards[land.id])))
        assert 'Creature' in serialize_card_view(candidate, land.id)['types']
        candidate = checked_action(candidate, RulesEngine(), seat, action(candidate.cards[land.id]))
        pending = candidate.stack[-1]
        old = (object_incarnation(candidate.cards[land.id]), candidate.cards[land.id].zone_change_sequence)
        assert (pending.payload['source_incarnation'], pending.payload['source_zone_change_sequence']) == old
        candidate = checked_action(candidate, RulesEngine(), seat, {
            'type': 'cast_spell', 'card_id': spell.id, 'targets': {'target_card_id': land.id},
        })
        assert candidate.stack[-1].effect_key == 'exile_return_immediate'
        for _ in range(2):
            candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
        assert len(candidate.stack) == 1 and candidate.stack[0].id == pending.id
        returned = candidate.cards[land.id]
        assert returned.zone == Zone.BATTLEFIELD
        assert (object_incarnation(returned), returned.zone_change_sequence) != old
        assert returned.summoning_sick and returned.owner == returned.controller == seat
        assert returned.tapped == (name == 'Celestial Colonnade')
        assert not returned.type_effects
        assert 'Creature' not in serialize_card_view(candidate, land.id)['types']
        assert sum(candidate.players[seat].mana_pool.values()) == 0
        candidate = resolve(candidate)
        assert not candidate.cards[land.id].type_effects
        assert 'Creature' not in serialize_card_view(candidate, land.id)['types']
        assert snapshot(root) == before
        after = snapshot(candidate)
        assert snapshot(deserialize_match_snapshot(after)) == after
        results.append(after)
    assert results[0] == results[1]
    record(request, candidate, phase='canonical_cloudshift_pending_animation_replay', before=before)
