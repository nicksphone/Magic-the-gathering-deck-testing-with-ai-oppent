"""Post-exile Siege choice must already match its persisted/restored state."""
import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from tests.test_battle_combat import act, reach
from tests.test_battle_product_acceptance import battle_position, paid_front, resolve_until


@pytest.mark.parametrize("seat", [1, 2])
def test_defeated_siege_choice_preserves_live_combat_through_round_trip(seat):
    state, battle, attackers = battle_position(seat)
    state = paid_front(state, seat, battle)
    state = reach(state, Step.DECLARE_ATTACKERS)
    state = act(state, seat, {"type": "attack", "attackers": attackers,
                             "attack_targets": {cid: "battle:" + battle for cid in attackers}})
    state = reach(state, Step.DECLARE_BLOCKERS)
    state = act(state, 3-seat, {"type": "block", "blocks": {}})
    state = reach(state, Step.COMBAT_DAMAGE)
    state = resolve_until(state, lambda s: s.pending_mechanic_choice is not None)
    assert state.cards[battle].zone == Zone.EXILE
    assert state.pending_mechanic_choice["kind"] == "effect_cast"
    live = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(live)
    assert serialize_match_snapshot(restored) == live
    # CR 506.4: removing the attacked permanent does not remove its attackers.
    assert state.attackers == attackers
    assert state.attack_targets == {cid: "" for cid in attackers}
    assert all(state.combat_target_context[cid]["removed"] is True for cid in attackers)
    assert all(state.combat_target_context[cid]["target_card_id"] == battle for cid in attackers)
