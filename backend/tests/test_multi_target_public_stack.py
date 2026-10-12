"""Public announcements survive a paid real copy and snapshot restoration."""
import pytest

from game_state.serializers import serialize_match, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_multi_target_immediate_return import case, cast, resolve, restored, canonical, raw_card, ISLAND


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_twincast_keeps_both_public_permanent_targets(seat):
    state, targets, spell = case(seat)
    state.mechanic_choice_required = True
    state.mechanic_choice_players = {seat}
    raw_card(state, ISLAND, seat, Zone.BATTLEFIELD)
    targets.reverse()
    copy = raw_card(state, canonical('coupled_targets/twincast.json'), seat, Zone.HAND)
    state.players[seat].mana_pool['U'] += 2
    state = cast(state, seat, spell, {'target_card_ids': targets})
    original_id = state.stack[-1].id
    state = cast(state, seat, copy.id, {'target_stack_id': original_id})
    state = resolve(state)
    for _ in range(2):
        assert state.pending_mechanic_choice['kind'] == 'copy_target'
        state = checked_action(restored(state), RulesEngine(), seat,
                               {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert state.pending_mechanic_choice is None
    state = restored(state)
    before = serialize_match_snapshot(state)
    frames = serialize_match(state)['stack']
    assert len(frames) == 2
    assert len({frame['id'] for frame in frames}) == 2
    assert all(frame['effect_key'] == 'exile_return_batch' and frame['targets'] == targets
               and 'payload' not in frame for frame in frames)
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.cards[copy.id].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before
