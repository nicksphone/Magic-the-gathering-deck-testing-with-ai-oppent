"""NEW actual paid opposite-controller trigger copies, never injected frames."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_self_entry_control_paid import paid_targeted_entry
from tests.test_source_linked_exile import (
    raw_card, cast, action, snap, deserialize_match_snapshot,
    resolve_top_of_stack, Zone,
)
from rules_engine.engine import RulesEngine
from rules_engine.spree import parse

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'audit/gate2-spree-http/fixtures/spree_http'
FACTS = json.loads((FIXTURES / 'canonical.json').read_bytes())
PROVENANCE = json.loads((FIXTURES / 'provenance.json').read_bytes())
FAVOR = FACTS['Return the Favor']
assert hashlib.sha256(json.dumps(FAVOR, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False).encode()).hexdigest() == PROVENANCE['cards'][FAVOR['name']]['canonical_fullrowSHA']
STIFLE_BYTES = (ROOT / 'backend/tests/fixtures/agent_self_entry/stifle.json').read_bytes()
assert hashlib.sha256(STIFLE_BYTES).hexdigest() == '6bb0888de9ca032e119d301db6381d0351ed76932d8ef4f8158a47ec50e5301f'
STIFLE = json.loads(STIFLE_BYTES)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('counter_original', [False, True])
def test_paid_opposite_controller_copy_uses_resolving_controller(seat, counter_original):
    state, source, target, original_actor = paid_targeted_entry(seat)
    original = state.stack[-1].id
    assert original_actor == 3 - seat
    favor = raw_card(state, FAVOR, seat, Zone.HAND)
    mode = parse(FAVOR['oracle_text'])[0]
    before_pool = sum(state.players[seat].mana_pool.values())
    untapped = {cid for cid in state.players[seat].battlefield if not state.cards[cid].tapped}
    state = action(state, seat, {'type': 'cast_spell', 'card_id': favor.id,
        'cost_choice': {'id': 'base'}, 'targets': {
            'mode_texts': [mode.text],
            'mode_targets': {mode.text: {'target_stack_id': original}},
        }})
    assert state.cards[favor.id].zone == Zone.STACK
    assert state.stack[-1].payload['mana_spent'] == 3
    assert sum(state.players[seat].mana_pool.values()) < before_pool or any(state.cards[cid].tapped for cid in untapped)
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending and pending['kind'] == 'copy_target' and pending['player_id'] == seat
    copied_id = pending['stack_id']
    assert copied_id != original
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.controller == seat and copied.effect_key == 'change_control'
    assert copied.source_card_id == source
    assert next(item for item in state.stack if item.id == original).controller == original_actor
    token = f'target_card_id:{source}'
    assert token in pending['options']
    before = snap(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert snap(state) == before
    assert any(move['type'] == 'choose_mechanic' for move in moves)
    state = action(state, seat, {'type': 'choose_mechanic', 'card_ids': [token]})
    copied = next(item for item in state.stack if item.id == copied_id)
    assert copied.payload['target_card_id'] == source
    assert next(item for item in state.stack if item.id == original).payload['target_card_id'] == target
    if counter_original:
        spell = raw_card(state, STIFLE, seat, Zone.HAND)
        state = cast(state, seat, spell.id, {'target_stack_id': original})
        assert all(item.id != original for item in state.stack)
        assert any(item.id == copied_id for item in state.stack)
    state = deserialize_match_snapshot(snap(state))
    assert state.stack[-1].id == copied_id
    assert resolve_top_of_stack(state)
    assert state.cards[source].controller == seat
    assert state.cards[source].owner == original_actor
    if not counter_original:
        assert state.stack[-1].id == original
        assert resolve_top_of_stack(state)
        assert state.cards[target].controller == original_actor
    else:
        assert state.cards[target].controller == seat
    state = deserialize_match_snapshot(snap(state))
    assert state.cards[source].controller == seat
    assert state.cards[source].owner == original_actor
