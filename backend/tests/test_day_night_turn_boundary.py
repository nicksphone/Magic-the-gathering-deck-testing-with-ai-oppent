"""Canonical two-seat designation and untap/upkeep boundary, no Oracle edits."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone, object_incarnation
from rules_engine.engine import RulesEngine
from rules_engine import named_counters
from tests.test_cathar_day_night_linked_exile import setup, cast
from tests.test_optional_reveal_transform import position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('designation,count,expected', [
    ('none', 0, 'none'), ('none', 1, 'none'), ('none', 2, 'none'),
    ('day', 0, 'night'), ('day', 1, 'day'), ('day', 2, 'day'),
    ('night', 0, 'night'), ('night', 1, 'night'), ('night', 2, 'day'),
])
def test_natural_turn_uses_previous_active_player_only_and_restores(seat, designation, count, expected):
    state, _, _ = position(seat)
    state.day_night = designation
    state.step = Step.CLEANUP
    state.spells_cast_this_turn = {seat: count, 3-seat: 9}
    before = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(before)
    RulesEngine().next_step(result)
    assert serialize_match_snapshot(state) == before
    assert result.active_player == 3-seat and result.step == Step.UPKEEP
    assert result.spells_cast_last_turn == count
    assert result.day_night == expected
    assert result.spells_cast_this_turn[3-seat] == 0
    assert not result.trigger_staging and not result.stack
    assert deserialize_match_snapshot(serialize_match_snapshot(result)).day_night == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('designation,count,face,expected', [
    ('day', 0, 1, 'night'), ('night', 2, 0, 'day'),
])
def test_transform_precedes_untap_triggers_wait_for_upkeep_and_restart(
        seat, designation, count, face, expected, monkeypatch):
    state, source, targets, _ = setup(seat, designation)
    cast(state, source)
    # Front entry normally has an exile trigger; this explicit timing position
    # starts after that trigger, with its original canonical permanent retained.
    state.stack.clear()
    state.pending_trigger_order = None
    state.trigger_staging = False
    state.staged_triggers.clear()
    state.step = Step.UNTAP
    state.turn = 3
    state.spells_cast_last_turn = count
    source.tapped = True
    incarnation = object_incarnation(source)
    observations = []
    original = named_counters.untap_permanent

    def observe(game, card_id, **kwargs):
        observations.append((game.day_night, game.cards[source.id].selected_face_index,
                             len(game.stack), game.pending_trigger_order))
        return original(game, card_id, **kwargs)

    monkeypatch.setattr(named_counters, 'untap_permanent', observe)
    RulesEngine()._apply_step_start_actions(state)
    assert observations and all(row == (expected, face, 0, None) for row in observations)
    assert not source.tapped and object_incarnation(source) == incarnation
    assert state.trigger_staging and state.trigger_staging_event == 'untap'
    assert not state.stack and state.pending_trigger_order is None
    assert bool(state.staged_triggers) == (face == 0)
    saved = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(saved)
    observed_count = len(observations)
    assert RulesEngine().advance_no_priority_step(restored)
    assert len(observations) == observed_count  # Entry actions never repeat.
    assert restored.step == Step.UPKEEP and restored.day_night == expected
    assert not restored.trigger_staging
    assert serialize_match_snapshot(state) == saved
    if face == 0:
        assert len(restored.stack) == 1
        assert restored.pending_trigger_order['phase'] == 'targets'
        offered = RulesEngine().legal_moves(restored, seat)
        assert {move['target_card_id'] for move in offered} == {card.id for card in targets}
        assert RulesEngine().legal_moves(restored, 3-seat) == []
    else:
        assert not restored.stack and not restored.pending_trigger_order
    assert sum(line == f'The game becomes {expected}.' for line in restored.log) == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_entry_establishes_day_and_designation_persists_without_source(seat):
    state, source, _, _ = setup(seat, 'none')
    cast(state, source)
    assert state.day_night == 'day'
    # Removal is an explicit empty-battlefield timing position, not a claimed
    # played departure event. The game designation is independent of its source.
    state = deepcopy(state)
    for player in state.players.values():
        for cid in player.battlefield:
            state.cards[cid].move_to_zone(Zone.GRAVEYARD)
            state.players[state.cards[cid].owner].graveyard.append(cid)
        player.battlefield.clear()
    state.stack.clear()
    state.pending_trigger_order = None
    state.trigger_staging = False
    state.staged_triggers.clear()
    state.step = Step.UNTAP
    state.turn = 2
    state.spells_cast_last_turn = 0
    RulesEngine()._apply_step_start_actions(state)
    assert state.day_night == 'night'
    RulesEngine().advance_no_priority_step(state)
    assert state.day_night == 'night'


@pytest.mark.parametrize('seat', [1, 2])
def test_upkeep_never_rechecks_previous_turn_and_delver_stays_upkeep(seat):
    state, source, _ = position(seat)
    state.turn = 3
    state.day_night = 'day'
    state.spells_cast_last_turn = 0
    state.step = Step.UPKEEP
    RulesEngine()._apply_step_start_actions(state)
    assert state.day_night == 'day'
    assert len(state.stack) == 1 and state.stack[0].source_card_id == source
