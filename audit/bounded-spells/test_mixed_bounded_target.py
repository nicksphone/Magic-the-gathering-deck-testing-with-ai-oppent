import pytest
from test_paid_preflight import facts, setup, cast
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected


@pytest.mark.parametrize('seat', [1, 2])
def test_mixed_bounded_target_announcements_are_atomic(facts, seat):
    state, source, targets, _, ids = setup(facts, seat, 'Force of Vigor', 1)
    targets['target_card_id'] = ids[1]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, source, targets)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_singular_bounded_target_uses_native_single_target_frame(facts, seat):
    import domain_paid_support as paid
    from game_state.state import Zone
    state, source, _, _, ids = setup(facts, seat, 'Force of Vigor', 1)
    state = cast(state, seat, source, {'target_card_id': ids[0]})
    assert state.stack[-1].effect_key == 'destroy_permanent'
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = paid.restore(state)
    state = paid.resolve(state)
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[ids[0]].zone == Zone.GRAVEYARD
    assert state.cards[ids[1]].zone == Zone.BATTLEFIELD
