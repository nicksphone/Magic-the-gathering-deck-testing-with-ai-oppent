"""Complete-RAW boundary for extended entry selectors before delayed-draw compilation."""
import pytest

from effects.handlers import return_creature_from_graveyard_to_battlefield
from game_state.state import CardInstance, Zone
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_self_or_another_entry_observer_bf62 import board


BODY = "draw a card at the beginning of the next turn's upkeep."


def entry(seat, selector, tail=''):
    state = board(('Grizzly Bears',), ('Grizzly Bears',), seat)
    prefix = 'When ' if selector == 'this creature' else 'Whenever '
    text = prefix + selector + ' enters, ' + BODY + tail
    # Explicit compiler protocol, not invented printed facts on a canonical Factory card.
    source = CardInstance(id='delayed-entry-protocol', name='Delayed entry protocol',
                          owner=seat, controller=seat, zone=Zone.GRAVEYARD,
                          types=['Creature'], oracle_text=text)
    state.cards[source.id] = source
    state.players[seat].graveyard.append(source.id)
    hand = list(state.players[seat].hand)
    return_creature_from_graveyard_to_battlefield(state, seat, {'target_card_id': source.id})
    assert source.zone == Zone.BATTLEFIELD
    assert len(state.stack) == 1
    assert state.stack[-1].source_card_id == source.id
    assert state.stack[-1].controller == seat
    return state, hand


@pytest.mark.parametrize('seat', [1, 2])
def test_extended_entry_unknown_raw_tail_cannot_schedule_a_partial_draw(seat):
    state, hand = entry(seat, 'this creature or another creature you control', ' (You lose the game.)')
    assert state.stack[-1].effect_key == 'noop'
    assert state.stack[-1].payload['__unsupported_trigger_instruction']
    assert resolve_top_of_stack(state)
    assert state.delayed_triggers == []
    assert state.players[seat].hand == hand
    assert state.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selector', ['this creature', 'this creature or another creature you control'])
def test_complete_legacy_and_extended_delayed_draw_keep_native_route(seat, selector):
    state, hand = entry(seat, selector)
    assert state.stack[-1].effect_key == 'schedule_next_turn_draw'
    assert resolve_top_of_stack(state)
    assert state.players[seat].hand == hand
    assert len(state.delayed_triggers) == 1
    delayed = state.delayed_triggers[0]
    assert delayed['controller'] == seat
    assert delayed['effect_key'] == 'draw_cards'
    assert delayed['payload'] == {'amount': 1, 'target_player': seat}
    assert delayed['earliest_turn'] == state.turn + 1
