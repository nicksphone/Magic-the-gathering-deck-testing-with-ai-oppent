"""Real paid activation; controlled transition seam, NOT a lawful blink episode.

This independent reader test never edits shared fixtures or injects shuffle events.
Lagrange owns the separate real paid source-lifecycle episode audit.
"""
from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import capture_last_known_battlefield
from tests.test_batch_graveyard_publication_audit import assert_private
from tests.test_paid_counter_family_audit import board
from tests.test_self_graveyard_replacement_audit import snap


def take(state, actor, action):
    before = snap(state)
    result = checked_action(state, RulesEngine(), actor, action)
    assert snap(state) == before
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('transition', ['unchanged', 'departed', 'reentered'])
@pytest.mark.parametrize('restore', [False, True])
def test_paid_activation_shuffle_retains_original_reference_at_reader(
        seat, transition, restore, monkeypatch, tmp_path):
    state, source, _ = board(seat, 'Fertilid')
    original = {'incarnation': object_incarnation(state.cards[source]),
                'zone_change_sequence': state.cards[source].zone_change_sequence}
    state = take(state, seat, {'type': 'activate_ability', 'card_id': source,
                              'ability_index': 0, 'targets': {'target_player': 3-seat}})
    assert state.cards[source].counters['+1/+1'] == 1
    assert sum(state.players[seat].mana_pool.values()) == 0
    item_id = state.stack[-1].id
    assert state.stack[-1].controller == seat and state.stack[-1].source_card_id == source
    activation_frame = asdict(state.stack[-1])
    if transition != 'unchanged':
        # Controlled source transition, not cast/entry/reanimation certification.
        capture_last_known_battlefield(state, source)
        state.players[seat].battlefield.remove(source)
        state.cards[source].move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(source)
        if transition == 'reentered':
            state.players[seat].graveyard.remove(source)
            state.cards[source].move_to_zone(Zone.BATTLEFIELD)
            state.players[seat].battlefield.append(source)
            assign_static_order_on_battlefield_entry(state, source)
            # Explicit retained-board setup matching the canonical printed two counters.
            # No enters event or partial ETB execution is injected.
            state.cards[source].counters['+1/+1'] = 2
        assert state.stack[-1].payload['__source_lki']['battlefield_incarnation'] == original['incarnation']
        assert state.cards[source].zone_change_sequence > original['zone_change_sequence']
    if restore:
        before = snap(state)
        state = deserialize_match_snapshot(before)
        assert snap(state) == before
    receipts = []
    import rules_engine.events as events
    emit = events.emit_event

    def spy(current, event, payload):
        if event == 'shuffle':
            receipts.append(deepcopy(payload))
        return emit(current, event, payload)

    monkeypatch.setattr(events, 'emit_event', spy)
    assert_private(state)
    for _ in range(2):
        state = take(state, state.priority_player, {'type': 'pass_priority'})
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'search_library' and pending['player_id'] == 3-seat
    assert pending['resolving_item']['id'] == item_id
    assert pending['resolving_item']['source_card_id'] == source
    pending_frame = deepcopy(pending['resolving_item'])
    state = take(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': []})
    assert state.pending_mechanic_choice is None and len(receipts) == 1
    assert_private(state)
    cause = receipts[0]['cause']
    assert cause['stack_id'] == item_id and cause['controller'] == seat
    assert cause['source_card_id'] == source and cause['kind'] == 'activated'
    current = {'incarnation': object_incarnation(state.cards[source]),
               'zone_change_sequence': state.cards[source].zone_change_sequence}
    evidence = {'scene': 'real paid activation + controlled transition seam',
                'transition': transition, 'restore': restore, 'activation_frame': activation_frame,
                'retained_pending_frame': pending_frame, 'original_reference': original,
                'current_reference': current, 'actual_shuffle_receipt': receipts[0],
                'final_snapshot': snap(state)}
    (tmp_path / 'reader-receipt.json').write_text(json.dumps(evidence, indent=2, sort_keys=True))
    assert cause['source_reference'] == original
