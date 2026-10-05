"""Canonical value-spell timing uses own cards and public resources only."""
import pytest

from ai.agent import AIAgent
from card_data.fallback_cards import fallback_card_payload
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot
from tests.test_ai_opaque_selection_horizon import ROWS
from tests.test_ai_recurring_engines import add
from tests.test_ai_search_prefix import bare_state


def position(seat, name='Memory Deluge', lands=7, flashback=True):
    state = bare_state(seat)
    state.turn = 20
    state.active_player = 3-seat
    state.step = Step.UPKEEP
    cards = dict(ROWS)
    for key in ('Island', 'Counterspell'):
        raw = fallback_card_payload(key)
        assert raw is not None
        cards[key] = {**raw, 'power': None, 'toughness': None,
                      'keywords': raw.get('keywords', []), 'colors': raw.get('colors', [])}
    spell = add(state, name, seat, Zone.GRAVEYARD if flashback else Zone.HAND, cards=cards)
    add(state, 'Counterspell', seat, Zone.HAND, cards=cards)
    for _ in range(lands):
        add(state, 'Island', seat, cards=cards)
    for _ in range(3):
        add(state, 'Island', 3-seat, cards=cards)
    ai = AIAgent(difficulty='master', archetype='Control')
    move = next(m for m in ai.engine.legal_moves(state, seat)
                if m.get('type') == 'cast_spell' and m.get('card_id') == spell.id)
    return state, ai, move


@pytest.mark.parametrize('seat', [1, 2])
def test_opponent_upkeep_is_not_an_endstep_draw_bonus(seat):
    state, ai, move = position(seat)
    early = ai._cast_bias(state, move, seat)
    state.step = Step.END_STEP
    assert ai._cast_bias(state, move, seat) > early


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Midrange', 'Ramp'])
def test_actual_flashback_payment_prices_lost_interaction_and_is_pure(seat, style):
    state, ai, move = position(seat)
    ai.archetype = style
    before = serialize_match_snapshot(state)
    assert ai._instant_value_reservation(state, move, seat) < 0
    assert serialize_match_snapshot(state) == before
    state.step = Step.END_STEP
    assert ai._instant_value_reservation(state, move, seat) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,lands', [('Memory Deluge', 9), ('Impulse', 4), ('Anticipate', 4)])
def test_value_cast_that_keeps_counter_mana_is_not_penalized(seat, name, lands):
    state, ai, move = position(seat, name, lands, name == 'Memory Deluge')
    assert ai._instant_value_reservation(state, move, seat) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_no_available_interaction_or_own_turn_does_not_force_wait(seat):
    state, ai, move = position(seat)
    state.players[seat].hand.clear()
    assert ai._instant_value_reservation(state, move, seat) == 0
    state, ai, move = position(seat)
    state.active_player = seat
    state.step = Step.PRECOMBAT_MAIN
    assert ai._instant_value_reservation(state, move, seat) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_master_holds_flashback_until_opponent_endstep(seat):
    state, ai, move = position(seat)
    decision = ai.choose_action(state, ai.engine.legal_moves(state, seat), seat)
    assert decision.action['type'] == 'pass_priority'
    state.step = Step.END_STEP
    decision = ai.choose_action(state, ai.engine.legal_moves(state, seat), seat)
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == move['card_id']


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_stack_response_does_not_inherit_empty_stack_reservation(seat):
    state, ai, move = position(seat)
    spell = add(state, 'Impulse', 3-seat, Zone.HAND, cards=ROWS)
    state.priority_player = 3-seat
    ai.engine.take_action(state, 3-seat, {'type': 'cast_spell', 'card_id': spell.id}, reject_invalid=True)
    assert state.stack
    assert ai._instant_value_reservation(state, move, seat) == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_opponent_hand_does_not_change_reservation(seat):
    state, ai, move = position(seat)
    before = ai._instant_value_reservation(state, move, seat)
    add(state, 'Impulse', 3-seat, Zone.HAND, cards=ROWS)
    assert ai._instant_value_reservation(state, move, seat) == before
