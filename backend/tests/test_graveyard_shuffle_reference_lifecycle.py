"""Actual paid-trigger lifecycle; helper-negative controls are supplementary."""
from copy import deepcopy
import json

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Zone, object_incarnation
from rules_engine.engine import RulesEngine
from rules_engine.shuffle_actions import shuffle_library
from tests.test_kozilek_graveyard_trigger_audit import (
    start, enter, trigger, save, passes, opposing_priority, FRESH, ROWS,
)
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import act, snap


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('response', ['none', 'Cremate', 'Stifle'])
def test_paid_trigger_reference_response_restart_and_private_info(seat, response, tmp_path):
    state, cid, _, old, action = start(seat, 'discard')
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    response_card = None
    if response != 'none':
        response_card = raw_card(state, FRESH[response], 3-seat, Zone.HAND)
        state.players[3-seat].mana_pool = {'B' if response == 'Cremate' else 'U': 1}
    state = enter(state, seat, 'discard', action)
    item = trigger(state, cid)
    reference = {'incarnation': object_incarnation(state.cards[cid]),
                 'zone_change_sequence': state.cards[cid].zone_change_sequence}
    assert item.payload['__trigger_source_reference'] == reference
    state = save(tmp_path, 'actual-entry-retained', state)
    if response_card is not None:
        state = opposing_priority(state, 3-seat)
        targets = ({'target_card_id': cid} if response == 'Cremate'
                   else {'target_stack_id': item.id})
        state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': response_card.id, 'targets': targets})
        state = passes(state)
        assert state.cards[response_card.id].zone == Zone.GRAVEYARD
        assert not state.players[3-seat].mana_pool.get('B' if response == 'Cremate' else 'U', 0)
        state = save(tmp_path, 'actual-paid-response-retained', state)
    if response == 'Stifle':
        assert not any(other.id == item.id for other in state.stack)
        assert {cid, old}.issubset(state.players[seat].graveyard)
        assert not any(other.source_card_id == probe.id for other in state.stack)
        assert not any('shuffles their library' in line for line in state.log)
        return
    assert any(other.id == item.id for other in state.stack)
    if response == 'Cremate':
        assert state.cards[cid].zone == Zone.EXILE
        assert state.cards[cid].zone_change_sequence > reference['zone_change_sequence']
    state = passes(state)
    receipts = [other for other in state.stack if other.source_card_id == probe.id]
    assert len(receipts) == 1
    cause = receipts[0].payload['__shuffle_cause']
    assert cause['kind'] == 'triggered' and cause['stack_id'] == item.id
    assert cause['source_card_id'] == cid and cause['controller'] == seat
    assert cause['source_reference'] == reference
    assert not state.players[seat].graveyard and old in state.players[seat].library
    assert state.cards[cid].zone == (Zone.EXILE if response == 'Cremate' else Zone.LIBRARY)
    assert sum('shuffles their library' in line for line in state.log) == 1
    state = save(tmp_path, 'actual-observer-retained-cause', state)
    view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert all(is_unknown(view.cards[other]) for other in state.players[seat].hand
               + state.players[seat].library)
    (tmp_path / 'actual-cause.json').write_text(json.dumps(cause, sort_keys=True))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reference', [None, {}, {'incarnation': 0},
    {'incarnation': True, 'zone_change_sequence': 1},
    {'incarnation': 0, 'zone_change_sequence': -1},
    {'incarnation': '0', 'zone_change_sequence': 1},
    {'incarnation': 0, 'zone_change_sequence': 1, 'extra': 0}])
def test_malformed_retained_reference_rejects_before_rng_log_or_state(seat, reference):
    # A real paid trigger is retained first; only the helper's negative input is damaged.
    from dataclasses import asdict
    state, cid, _, _, action = start(seat, 'discard')
    state = enter(state, seat, 'discard', action)
    frame = asdict(trigger(state, cid))
    frame['payload']['__trigger_source_reference'] = deepcopy(reference)
    before = snap(state)
    with pytest.raises(ValueError):
        shuffle_library(state, seat, resolving_item=frame)
    assert snap(state) == before
