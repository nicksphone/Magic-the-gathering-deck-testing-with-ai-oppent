"""Genuine publication and retained physical reference; no valid injected frames."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.keyword_triggers import schedule_control_loss_tap
from tests.test_temporary_control_lifecycle_audit import position, cast, snap, raw_card


@pytest.mark.parametrize('seat', [1, 2])
def test_real_returned_spell_not_cast_trigger_top_receives_physical_pre_reference(seat, monkeypatch):
    state, ray, target = position(seat, 'ray-of-command')
    path = Path(__file__).parent / 'fixtures/announced_costs/young-pyromancer.json'
    raw_card(state, json.loads(path.read_text()), seat, Zone.BATTLEFIELD)
    import rules_engine.resource_events as resource_events
    publish = resource_events.emit_graveyard_departures
    observed = []

    def spy(current, departures):
        source = current.cards[ray]
        observed.append((source.zone, {'incarnation': object_incarnation(source),
                                      'zone_change_sequence': source.zone_change_sequence}))
        return publish(current, departures)

    monkeypatch.setattr(resource_events, 'emit_graveyard_departures', spy)
    state = cast(state, seat, ray, target)
    item = next(item for item in state.stack if item.source_card_id == ray)
    assert state.stack[-1].id != item.id
    assert item.payload['mana_spent'] == 4
    published_stack_references = [reference for zone, reference in observed if zone == Zone.STACK]
    assert published_stack_references
    receipt = item.payload['__control_source_frame']
    assert receipt == {'stack_id': item.id, 'source_card_id': ray,
                       'cast_controller': seat, 'label': item.label,
                       'source_reference': published_stack_references[-1]}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [None, {}, {'payload': []}])
def test_scheduler_missing_or_malformed_transport_is_pure_rejection(seat, bad):
    state, ray, target = position(seat, 'ray-of-command')
    state = cast(state, seat, ray, target)
    payload = deepcopy(state.stack[-1].payload)
    payload['__resolving_item'] = bad
    before = snap(state)
    with pytest.raises(ActionRejected, match='retained control resolution'):
        schedule_control_loss_tap(state, seat, payload)
    assert snap(state) == before
