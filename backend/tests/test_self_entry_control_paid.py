"""NEW paid self-entry controls; no whole-card or end-step certification."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.agent_control_facts import ROWS
from tests.test_source_linked_exile import (
    FACTS, BOOMERANG, position, cast, next_main, raw_card, action,
    reference, snap, deserialize_match_snapshot, resolve_top_of_stack, Zone,
)
from rules_engine.engine import RulesEngine

ROOT = Path(__file__).resolve().parents[2]
CLOUDSHIFT = json.loads((ROOT / 'backend/tests/fixtures/favor_target_lifecycle/cloudshift.json').read_text())
PLAINS = json.loads((ROOT / 'backend/tests/fixtures/activated_top_selection/plains.json').read_text())


def paid_targeted_entry(seat):
    state, _ = position(seat)
    # Declared physical white source survives the intervening turn transition.
    raw_card(state, PLAINS, seat, Zone.BATTLEFIELD)
    target = raw_card(state, FACTS['Elvish Mystic'], seat, Zone.HAND)
    state = cast(state, seat, target.id)
    actor = 3 - seat
    state = next_main(state, actor)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    source = raw_card(state, ROWS['Agent of Treachery'], actor, Zone.HAND)
    state = cast(state, actor, source.id)
    assert state.pending_trigger_order and state.pending_trigger_order['phase'] == 'targets'
    before = snap(state)
    moves = RulesEngine().legal_moves(state, actor)
    assert snap(state) == before
    move = next(m for m in moves if m['type'] == 'choose_trigger_target'
                and m.get('target_card_id') == target.id)
    state = action(state, actor, deepcopy(move))
    assert state.stack[-1].effect_key == 'change_control'
    assert state.stack[-1].controller == actor
    assert state.stack[-1].payload['target_card_id'] == target.id
    assert 'new_controller' not in state.stack[-1].payload
    return state, source.id, target.id, actor


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['ordinary_restore', 'source_departure', 'target_blink'])
def test_actual_paid_self_entry_control(seat, case):
    state, source, target, actor = paid_targeted_entry(seat)
    old_reference = reference(state.cards[target])
    if case == 'source_departure':
        spell = raw_card(state, BOOMERANG, actor, Zone.HAND)
        state = cast(state, actor, spell.id, {'target_card_id': source})
        assert state.cards[source].zone == Zone.HAND
    elif case == 'target_blink':
        spell = raw_card(state, CLOUDSHIFT, seat, Zone.HAND)
        state = cast(state, seat, spell.id, {'target_card_id': target})
        assert state.cards[target].zone == Zone.BATTLEFIELD
        assert reference(state.cards[target]) != old_reference
        assert state.cards[target].controller == seat
    state = deserialize_match_snapshot(snap(state))
    assert resolve_top_of_stack(state)
    expected = seat if case == 'target_blink' else actor
    assert state.cards[target].controller == expected
    assert state.cards[target].owner == seat
    assert target in state.players[expected].battlefield
    assert target not in state.players[3 - expected].battlefield
    state = deserialize_match_snapshot(snap(state))
    assert state.cards[target].controller == expected
