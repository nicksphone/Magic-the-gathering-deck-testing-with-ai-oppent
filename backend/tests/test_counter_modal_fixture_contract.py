"""Genuine paid producer delivery and unchanged unknown-frame rejection."""
import pytest

from effects.handlers import counter_spell_unless_pay
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
import rules_engine.stack_engine as stack_engine
from tests.test_conditional_counter_rules import _state_with_stack
from tests.test_proliferation import card
from tests.test_restricted_mana import clean


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_canonical_cast_delivers_actual_spell_source_and_trigger(seat, monkeypatch):
    state = clean(seat)
    observer = card(state, 'Inexorable Tide', seat)
    spell = card(state, 'Contentious Plan', seat, Zone.HAND)
    state.players[seat].mana_pool = {'U': 2}
    events = []
    original = stack_engine.emit_event

    def observe(game_state, event, payload):
        if event == 'spell_cast':
            emitted_frame = next(item for item in game_state.stack
                                 if item.id == payload['source_stack_id'])
            assert payload['stack_payload'] == emitted_frame.payload
            events.append(dict(payload))
        return original(game_state, event, payload)

    monkeypatch.setattr(stack_engine, 'emit_event', observe)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id})
    assert state.players[seat].mana_pool.get('U', 0) == 0
    assert spell.id not in state.players[seat].hand
    assert state.cards[spell.id].zone == Zone.STACK
    frame = next(item for item in state.stack if item.source_card_id == spell.id)
    assert frame.payload['__announced_stack_kind'] == 'spell'
    assert len(events) == 1
    assert events[0]['source_card_id'] == spell.id
    assert events[0]['source_stack_id'] == frame.id
    assert events[0]['controller'] == seat
    assert events[0]['stack_payload']['__announced_stack_kind'] == 'spell'
    assert state.stack[-1].source_card_id == observer.id
    assert state.stack[-1].controller == seat
    assert state.stack[-1].payload['effects'][0]['effect_key'] == 'proliferate'


@pytest.mark.parametrize('controller', [1, 2])
@pytest.mark.parametrize('pay', [True, False])
def test_unknown_counter_frame_cannot_pay_or_be_countered(controller, pay):
    state = _state_with_stack(['Sorcery'], 'Draw a card.')
    state.stack[0].payload.pop('__announced_stack_kind', None)
    before = serialize_match_snapshot(state)
    counter_spell_unless_pay(state, controller, {
        'target_stack_id': 'target-stack', 'unless_cost': '{2}',
        'pay_unless_counter': pay})
    assert serialize_match_snapshot(state) == before
