"""Count-only projection controls, not natural-game or strength evidence."""
from copy import deepcopy
import random
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from ai.pending_effects import granted_acquisition_forecast
from rules_engine.engine import RulesEngine
from rules_engine import stack_engine
from test_ai_granted_equip import prepare
from nadu_support import snapshot
from tests.test_equip_context import clean, add, resolve
from rules_engine.action_validation import checked_action

STYLES = ['Aggro', 'Burn', 'Midrange', 'Control', 'Tempo', 'Ramp', 'Drain',
          'Aristocrats', 'Reanimator', 'Tokens', 'Tribal', 'Combo-lite', 'Counter-heavy']


@pytest.fixture(scope='module', params=[1, 2])
def paid_position(request):
    p, _, _ = prepare(request.param, 'one_slot')
    return p


@pytest.mark.parametrize('case', ['valid', 'missing', 'unqualified', 'instruction_mismatch',
                                  'unsupported_entry', 'wrong_controller', 'wrong_occurrence', 'no_quota'])
def test_typed_published_forecast_closed_controls(paid_position, case):
    p = paid_position
    state = deepcopy(p.state)
    RulesEngine().take_action(state, p.seat, {'type': 'equip', 'card_id': p.ids['shuko'],
                                           'target_card_id': p.ids['elf']}, reject_invalid=True)
    item = next(i for i in state.stack if i.effect_key == 'reveal_top_conditional')
    receipt = item.payload['__granted_target_receipt']
    cause = next(i for i in state.stack if i.id == receipt['targeting_occurrence'][0])
    # Explicit helper-only malformed protocol counterfactuals, not gameplay.
    if case == 'missing':
        item.payload.pop('__granted_target_receipt')
    elif case == 'unqualified':
        cause.payload['__granted_target_published_capture'] = {'status': 'unqualified', 'captured': False}
    elif case == 'instruction_mismatch':
        item.payload['instruction'] = ['Creature', 'hand', 'hand']
    elif case == 'unsupported_entry':
        receipt['compiled_instruction'] = ['Creature', 'battlefield', 'hand']
        item.payload['instruction'] = receipt['compiled_instruction'][:]
    elif case == 'wrong_controller':
        item.controller = 3-p.seat
    elif case == 'wrong_occurrence':
        receipt['targeting_occurrence'][1] += 1
    elif case == 'no_quota':
        state.trigger_once_seen_this_turn.clear()
    before = snapshot(state)
    rng = random.getstate()
    assert granted_acquisition_forecast(state, item) == (p.seat if case == 'valid' else None)
    assert snapshot(state) == before and random.getstate() == rng


def test_projection_finishes_equip_without_resolving_opaque_reveal(paid_position):
    p = paid_position
    moves = RulesEngine().legal_moves(p.state, p.seat)
    view, offered = decision_view(p.state, p.seat, moves)
    move = next(m for m in offered if m['type'] == 'equip' and m['card_id'] == p.ids['shuko'])
    before = snapshot(view)
    rng = random.getstate()
    resolved = []
    original = stack_engine.resolve_top_of_stack

    def resolve_checked(state):
        key = state.stack[-1].effect_key
        assert key != 'reveal_top_conditional', 'Opaque top must not execute as an invented nonland'
        result = original(state)
        resolved.append(key)
        assert {pid: player.library for pid, player in state.players.items()} == {
            pid: player.library for pid, player in view.players.items()}
        assert {pid: player.hand for pid, player in state.players.items()} == {
            pid: player.hand for pid, player in view.players.items()}
        return result

    with patch.object(stack_engine, 'resolve_top_of_stack', resolve_checked):
        action, gain = AIAgent()._attachment_projection(view, move, p.seat)
    assert action == {'type': 'equip', 'card_id': p.ids['shuko'], 'target_card_id': p.ids['elf']}
    assert gain > 0 and 'equip_attachment' in resolved
    assert snapshot(view) == before and random.getstate() == rng


@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('seat', [1, 2])
def test_generic_ordinary_equip_thirteen_declared_styles(style, seat):
    # Existing canonical fixture recipe, not a representative deck certificate.
    state = clean()
    state.active_player = state.priority_player = seat
    source = add(state, 'Bonesplitter', seat)
    target = add(state, 'Fervent Champion', seat)
    add(state, 'Llanowar Elves', seat).tapped = True
    agent = AIAgent(archetype=style, difficulty='master')
    before = snapshot(state)
    rng = random.getstate()
    action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert action == {'type': 'equip', 'card_id': source.id, 'target_card_id': target.id}
    assert snapshot(state) == before and random.getstate() == rng
    state = resolve(checked_action(state, RulesEngine(), seat, action))
    assert agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action['type'] != 'equip'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['resource_gain', 'unknown_draw'])
def test_existing_canonical_aura_projection_controls(seat, case):
    # Two existing pure controls only; their mixed SQL module is NOT qualified here.
    from aura_fixture_controls import (
        test_aura_targets_are_selected_by_actual_resource_gain,
        test_draw_aura_keeps_resource_outcome_unknown,
    )
    control = (test_aura_targets_are_selected_by_actual_resource_gain if case == 'resource_gain'
               else test_draw_aura_keeps_resource_outcome_unknown)
    control(seat)
