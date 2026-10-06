"""Real paid graveyard-target normal/stale controls; no SQLite fixtures."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from tests.test_announced_target_reference_product import (
    setup, raw_card, ROWS, ref, cast, passes, act, restart)

CREMATE = json.loads((Path(__file__).parent / 'fixtures/kozilek_trigger_audit/cremate.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('response', [False, True])
def test_actual_graveyard_target_receipt_resolves_normally_or_fizzles_after_paid_exile(seat, response, tmp_path):
    state, target = setup(seat)
    bolt = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.HAND)
    state = cast(state, seat, bolt.id, {'target_card_id': target})
    state = passes(state)
    assert state.cards[target].zone == Zone.GRAVEYARD
    graveyard_reference = ref(state.cards[target])
    cremator = raw_card(state, CREMATE, seat, Zone.HAND)
    state = cast(state, seat, cremator.id, {'target_card_id': target})
    announced = deepcopy(state.stack[-1].payload['__announced_target_references'])
    assert announced['targets']['target_card_id'] == graveyard_reference
    after_announcement = len(state.players[seat].hand)
    if response:
        opponent = 3-seat
        state.players[opponent].mana_pool = {'B': 1}  # Declared response resource, real cost still paid.
        responder = raw_card(state, CREMATE, opponent, Zone.HAND)
        state = act(state, seat, {'type': 'pass_priority'})
        state = cast(state, opponent, responder.id, {'target_card_id': target})
        assert state.players[opponent].mana_pool['B'] == 0
        state = passes(state)
        assert state.cards[target].zone == Zone.EXILE
        assert ref(state.cards[target]) != graveyard_reference
        assert state.stack[-1].payload['__announced_target_references'] == announced
    state = passes(restart(state, tmp_path, 'graveyard-target-after-response'))
    assert state.cards[target].zone == Zone.EXILE
    assert state.cards[cremator.id].zone == Zone.GRAVEYARD
    assert len(state.players[seat].hand) == after_announcement + (0 if response else 1)
    assert not state.stack
