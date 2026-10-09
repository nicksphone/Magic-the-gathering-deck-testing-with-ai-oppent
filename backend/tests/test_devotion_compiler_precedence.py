"""Exact devotion instructions must precede the general closed X-buff guard."""
from copy import copy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_devotion import ROWS, add, fixture


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_aspect_uses_live_devotion_after_snapshot(seat):
    state = fixture()
    state.active_player = state.priority_player = seat
    recipient = add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    spell = add(state, 'Aspect of Hydra', seat, Zone.HAND, cards=ROWS)
    state.players[seat].mana_pool = {'G': 1}
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {
        'type': 'cast_spell', 'card_id': spell.id,
        'targets': {'target_card_id': recipient.id},
    })
    assert state.players[seat].mana_pool.get('G', 0) == 0
    assert state.stack[-1].effect_key == 'devotion_effect'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    for _ in range(4):
        if not state.stack:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert not state.stack
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert effective_combat_stats(state, recipient.id) == (6, 6)


@pytest.mark.parametrize('tail', [
    ' Draw a card.',
    ' Then gain 2 life.',
    ' If you control a Forest, draw a card.',
    ' Until your next turn.',
])
def test_unknown_devotion_suffix_does_not_compile_a_partial_reward(tail):
    state = fixture()
    recipient = add(state, 'Burning-Tree Emissary', cards=ROWS)
    spell = copy(add(state, 'Aspect of Hydra', zone=Zone.HAND, cards=ROWS))
    spell.oracle_text += tail
    before = serialize_match_snapshot(state)
    key, payload = infer_effect_from_oracle(
        state, spell, 1, {'target_card_id': recipient.id}, report_unsupported=False)
    assert key == 'noop'
    assert payload.get('__unsupported_instruction')
    assert serialize_match_snapshot(state) == before
