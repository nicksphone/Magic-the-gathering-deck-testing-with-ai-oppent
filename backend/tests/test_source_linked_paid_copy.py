"""Paid canonical permanent-copy and post-entry suppression, not entry suppression."""
import json

import pytest

from tests.test_source_linked_exile import (
    ROOT, position, cast, action, activate, raw_card, BOOMERANG,
    FACE, reference, exile_permission, Zone, resolve_top_of_stack,
    snap, deserialize_match_snapshot,
)
from rules_engine.continuous import printed_abilities_suppressed
from rules_engine.engine import RulesEngine

ENGINE = json.loads((ROOT/'backend/tests/fixtures/creature_observer_fix/lithoform-engine.json').read_bytes())
SONG = next(r for r in json.loads((ROOT/'backend/tests/fixtures/aura_costs.json').read_bytes()) if r['name'] == 'Song of the Dryads')
NEGATE = next(r for r in json.loads((ROOT/'backend/tests/fixtures/copy_counters.json').read_bytes()) if r['name'] == 'Negate')


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_copy_survives_original_and_has_independent_entry_link(seat):
    state, source = position(seat)
    engine = raw_card(state, ENGINE, seat, Zone.HAND)
    state = cast(state, seat, engine.id)
    bounce = raw_card(state, BOOMERANG, seat, Zone.HAND)
    state = cast(state, seat, bounce.id, {'target_card_id': source})
    state = action(state, seat, {'type': 'cast_spell', 'card_id': source,
                                'selected_face_index': 1, 'targets': {}})
    original = state.stack[-1].id
    before = sum(state.players[seat].mana_pool.values())
    state = action(state, seat, {'type': 'activate_ability', 'card_id': engine.id,
                                'ability_index': 2, 'targets': {'target_stack_id': original}})
    assert state.cards[engine.id].tapped
    assert sum(state.players[seat].mana_pool.values()) == before - 4
    assert resolve_top_of_stack(state)
    assert len(state.stack) == 2
    copied = state.stack[-1].id
    assert copied != original
    counter = raw_card(state, NEGATE, 3-seat, Zone.HAND)
    state = cast(state, 3-seat, counter.id, {'target_stack_id': original})
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.stack[-1].id == copied
    state = deserialize_match_snapshot(snap(state))
    assert resolve_top_of_stack(state)
    token, = [c for c in state.cards.values() if c.zone == Zone.BATTLEFIELD and c.is_token and c.name == FACE['name']]
    assert token.loyalty == 5 and token.oracle_text == FACE['oracle_text']
    assert len(state.emblems) == 2
    assert state.loyalty_permissions[1]['source'] == reference(token)
    assert state.loyalty_permissions[1]['source'] != state.loyalty_permissions[0]['source']
    state = activate(state, seat, token.id, 0)
    assert not state.loyalty_permissions[0]['cards']
    assert len(state.loyalty_permissions[1]['cards']) == 2
    assert all(exile_permission(state, seat, ref['id']) for ref in state.loyalty_permissions[1]['cards'])


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_source_ability_loss_does_not_remove_existing_emblem(seat):
    state, source = position(seat)
    state = activate(state, seat, source, 0)
    refs = list(state.loyalty_permissions[0]['cards'])
    song = raw_card(state, SONG, 3-seat, Zone.HAND)
    # Opponent must have the real sorcery-speed Aura window.
    from tests.test_source_linked_exile import next_main
    state = next_main(state, 3-seat)
    state = cast(state, 3-seat, song.id, {'target_card_id': source})
    assert printed_abilities_suppressed(state, source)
    assert not any(m['type'] == 'activate_loyalty' and m.get('card_id') == source for m in RulesEngine().legal_moves(state, seat))
    before = snap(state)
    assert all(exile_permission(state, seat, ref['id']) for ref in refs)
    assert snap(state) == before
    state = deserialize_match_snapshot(before)
    assert all(exile_permission(state, seat, ref['id']) for ref in refs)
