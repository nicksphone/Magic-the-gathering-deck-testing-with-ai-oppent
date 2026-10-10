"""Public target schema parity at the native branch validator; no SQL or server."""
import json
import pickle

import pytest
from pydantic import ValidationError

from api_contracts import CastAction, ModeTarget
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.cast_choice import validate_mode_targets
from rules_engine.engine import RulesEngine
from tests.test_incendiary_modal_boundaries import FIX, permanent
from tests.test_incendiary_modal_root import MODES, announced, position, reload


BAD_PACKETS = [
    {'target_player': 2, 'mode_text': MODES[2]},
    {'target_player': 2, 'mode_texts': [MODES[2]]},
    {'target_player': 2, 'mode_targets': {}},
    {'target_player': 2, 'selected_face_index': 0},
    {'target_player': 2, 'x_value': 4},
    {'target_player': True}, {'target_player': '2'}, {'target_player': 2.0},
    {'target_card_id': 7}, {'target_card_id': []}, {'target_card_id': ''},
    None, [], 'not-a-target-packet',
]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('packet', BAD_PACKETS)
def test_native_branch_rejects_exact_public_schema_invalid_fields_and_types_root_pure(seat, packet):
    state, source = position(seat)
    targets = announced(seat, (0, 2))
    targets['mode_targets'][MODES[0]] = packet
    before = pickle.dumps(state)
    with pytest.raises(ValidationError):
        ModeTarget.model_validate(packet)
    valid, reason = validate_mode_targets(state, source, seat, targets)
    assert not valid and reason
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_typed_complete_public_action_genuinely_pays_casts_restores_and_resolves(seat):
    state, source = position(seat)
    action = CastAction.model_validate({'type': 'cast_spell', 'card_id': source.id,
                                       'targets': announced(seat, (0, 2))})
    assert set(ModeTarget.model_fields) == {'target_player', 'target_card_id', 'target_stack_id'}
    state = checked_action(state, RulesEngine(), seat, action.model_dump(exclude_none=True))
    assert state.cards[source.id].zone == Zone.STACK
    assert not any(state.players[seat].mana_pool.values())
    from rules_engine.stack_engine import resolve_top_of_stack
    state = reload(state)
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 16 and state.cards['nonbasic'].zone == Zone.GRAVEYARD
    reload(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selector', ['mode_text', 'mode_texts', 'mode_targets', 'selected_face_index'])
def test_actual_raw_alias_cast_rejects_before_payment_with_native_schema_reason(seat, selector):
    state, source = position(seat)
    targets = announced(seat, (0, 2))
    if selector == 'mode_text':
        targets['mode_targets'][MODES[0]] = {'mode_text': MODES[2], 'target_card_id': 'nonbasic'}
    else:
        targets['mode_targets'][MODES[0]][selector] = {} if selector == 'mode_targets' else 0
    before = pickle.dumps(state)
    with pytest.raises(ValidationError):
        CastAction.model_validate({'type': 'cast_spell', 'card_id': source.id, 'targets': targets})
    reason = ('Announce targets for each selected mode' if selector == 'mode_targets'
              else 'Invalid per-mode target packet')
    with pytest.raises(ActionRejected, match=reason):
        checked_action(state, RulesEngine(), seat,
                       {'type': 'cast_spell', 'card_id': source.id, 'targets': targets})
    assert pickle.dumps(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_legitimate_linked_multitarget_branch_is_not_rejected_by_blanket_exclusivity(seat):
    state, _ = position(seat)
    raw = json.loads((FIX / 'coupled_targets/searing-blaze.json').read_text())
    source = permanent(state, raw, seat)
    # Validator branch seam with an unmodified canonical linked body, not a
    # claim that this nonmodal card has a printed modal casting envelope.
    mode = raw['oracle_text']
    packet = {'target_player': 3-seat, 'target_card_id': f'creature-{3-seat}'}
    assert ModeTarget.model_validate(packet)
    before = pickle.dumps(state)
    valid, reason = validate_mode_targets(state, source, seat,
        {'mode_texts': [mode], 'mode_targets': {mode: packet}})
    assert valid, reason
    assert source.oracle_text == raw['oracle_text']
    assert pickle.dumps(state) == before
