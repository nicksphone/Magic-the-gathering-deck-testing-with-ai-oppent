"""Observe real executor commits; never inject entry events or trigger items."""
from copy import deepcopy

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.replacement import select_graveyard_entry_plan
from rules_engine.zone_actions import execute_graveyard_entry
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import position, restart, snap
from tests.test_self_graveyard_replacement_interactions import ROWS


@pytest.fixture
def observed_entries(monkeypatch):
    from rules_engine import events
    original = events.emit_event
    observed = []

    def observe(state, event, payload):
        if event == 'enters_graveyard':
            card = state.cards[payload['card_id']]
            assert card.zone == Zone.GRAVEYARD
            assert state.players[card.owner].graveyard.count(card.id) == 1
            observed.append(deepcopy(payload))
        return original(state, event, payload)

    monkeypatch.setattr(events, 'emit_event', observe)
    return observed


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('origin', [Zone.BATTLEFIELD, Zone.HAND, Zone.LIBRARY, Zone.STACK, Zone.EXILE])
def test_committed_transition_has_exact_references_once(seat, origin, observed_entries, tmp_path):
    state, card, _, _, _ = position('Kozilek, Butcher of Truth', seat, 'sacrifice', True)
    # Explicit retained-zone fixture, not a claimed naturally cast/control episode.
    state.players[seat].battlefield.remove(card.id)
    card.move_to_zone(origin)
    holder = seat if origin == Zone.BATTLEFIELD else card.owner
    if origin != Zone.STACK:
        getattr(state.players[holder], origin.value).append(card.id)
    plan = select_graveyard_entry_plan(state, card.id)
    before = snap(state)
    assert select_graveyard_entry_plan(state, card.id) == plan and snap(state) == before
    assert execute_graveyard_entry(state, plan) == Zone.GRAVEYARD
    assert observed_entries == [{
        'card_id': card.id, 'owner': card.owner, 'from_zone': origin.value,
        'previous_controller': plan.controller,
        'previous_reference': {'incarnation': plan.incarnation, 'zone_change_sequence': plan.sequence},
        'entry_reference': {'incarnation': object_incarnation(card),
                            'zone_change_sequence': card.zone_change_sequence},
    }]
    assert card.zone_change_sequence == plan.sequence + 1
    assert len([item for item in state.stack if item.source_card_id == card.id]) == 1
    state = restart(state, tmp_path, 'committed-entry')
    assert state.stack[-1].controller == card.owner
    before = snap(state)
    with pytest.raises(ActionRejected):
        execute_graveyard_entry(state, plan)
    assert snap(state) == before and len(observed_entries) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', ['library', 'exile', 'same_graveyard'])
def test_no_entry_event_for_replaced_or_same_zone_move(seat, destination, observed_entries):
    name = 'Darksteel Colossus' if destination == 'library' else 'Kozilek, Butcher of Truth'
    state, card, _, _, _ = position(name, seat, 'discard')
    if destination == 'exile':
        raw_card(state, ROWS['Rest in Peace'], 3-seat, Zone.BATTLEFIELD)
    elif destination == 'same_graveyard':
        state.players[seat].hand.remove(card.id)
        card.move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(card.id)
    plan = select_graveyard_entry_plan(state, card.id)
    sequence = card.zone_change_sequence
    assert execute_graveyard_entry(state, plan) == plan.destination
    assert not observed_entries
    assert not any(item.source_card_id == card.id for item in state.stack)
    if destination == 'same_graveyard':
        assert card.zone_change_sequence == sequence
