"""Paid original legend episodes with explicit offered choices, not automatic keepers."""
import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_sba_graveyard_entry_audit import legend_position, observed, target_events
from tests.test_kozilek_graveyard_trigger_audit import passes
from tests.test_self_graveyard_replacement_audit import act, restart, snap


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('replacements', [False, True])
def test_paid_legend_requires_offered_keeper_then_committed_departure(seat, replacements, tmp_path, observed):
    state, keeper, cid, sources = legend_position(seat, replacements)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid})
    assert state.stack[0].payload['mana_spent'] == 10
    assert state.stack[0].payload['__announced_stack_kind'] == 'spell'
    state = passes(state)
    assert len(state.stack) == 1 and state.cards[cid].zone == Zone.STACK
    state = restart(state, tmp_path, 'diagnostic-paid-legend-before-entry')
    state = passes(state)
    pending = state.pending_mechanic_choice
    assert pending and pending['kind'] == 'legend_keeper' and pending['player_id'] == seat
    assert set(pending['options']) == {keeper, cid}
    assert state.pending_replacement_choice is None
    assert state.cards[keeper].zone == state.cards[cid].zone == Zone.BATTLEFIELD
    assert not any(row['event'] == 'enters_graveyard' for row in target_events(observed, state, cid))
    offer = next(action for action in RulesEngine().legal_moves(state, seat)
                 if action['type'] == 'choose_mechanic' and action.get('kind') == 'legend_keeper')
    assert offer['count'] == 1 and set(offer['options']) == {keeper, cid}
    choice = {'type': offer['type'], 'card_ids': [keeper]}
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, choice)
    assert snap(state) == before
    state = act(state, seat, choice)
    assert state.pending_mechanic_choice is None
    assert state.cards[keeper].zone == Zone.BATTLEFIELD
    if replacements:
        pending = state.pending_replacement_choice
        assert pending and pending['resume_kind'] == 'legend_keeper_die'
        assert pending['target_card_id'] == cid
        assert {row['source_id'] for row in pending['options']} == set(sources)
        choice = next(action for action in RulesEngine().legal_moves(state, seat)
                      if action['type'] == 'choose_replacement' and action['replacement_source_id'] == sources[0])
        before = snap(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 3-seat, choice)
        assert snap(state) == before
        state = act(state, seat, choice)
        assert state.cards[cid].zone == Zone.EXILE
        assert cid not in state.players[seat].graveyard
        assert not any(row['event'] == 'enters_graveyard' for row in target_events(observed, state, cid))
        assert not any(item.source_card_id == cid for item in state.stack)
    else:
        rows = target_events(observed, state, cid)
        leave = next(row for row in rows if row['event'] == 'leaves_battlefield')
        assert state.cards[cid].zone == Zone.GRAVEYARD and cid in state.players[seat].graveyard
        assert state.cards[cid].zone_change_sequence == leave['source_sequence'] + 1
        assert len([row for row in rows if row['event'] == 'enters_graveyard']) == 1
        items = [item for item in state.stack if item.source_card_id == cid]
        assert len(items) == 1 and items[0].controller == seat
        assert items[0].payload['__trigger_event'] == 'enters_graveyard'
    restart(state, tmp_path, 'diagnostic-explicit-keeper-and-departure')
