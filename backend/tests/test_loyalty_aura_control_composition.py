"""Checked loyalty/attachment/bounce composition, with controlled canonical setup."""
import pytest

from game_state.state import Zone
from rules_engine.control_effects import control_layer_view
from tests.test_compleated_loyalty_full import (
    act, activate, cast_walker, raw_card, SEED, settle,
)
from tests.test_control_layer_contract import DOMINATE
from tests.test_static_aura_control_desired import BOOMERANG, ROWS, restart, snap


def resolve_with_declared_attachments(state, target_id):
    choices = 0
    for _ in range(32):
        pending = state.pending_mechanic_choice
        if pending:
            assert pending['kind'] == 'loyalty_attachment'
            assert pending['count'] == 1 and target_id in pending['options']
            state = restart(state)
            state = act(state, pending['player_id'], {
                'type': 'choose_mechanic', 'choice_id': target_id,
            })
            choices += 1
        elif state.stack:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        else:
            return state, choices
    raise AssertionError('Copied Aura attachment continuation exceeded bound')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('indefinite_underlying', [False, True])
def test_doubled_graveyard_aura_copy_control_survives_one_departure(seat, indefinite_underlying):
    state, walker = cast_walker(seat, doubling=True)
    assert state.cards[walker].loyalty == 10
    creature = raw_card(state, SEED['Llanowar Elves'], 3 - seat, Zone.BATTLEFIELD)
    if indefinite_underlying:
        dominate = raw_card(state, DOMINATE, seat, Zone.HAND)
        state.players[seat].mana_pool = {'C': 2, 'U': 2}
        state = settle(act(state, seat, {
            'type': 'cast_spell', 'card_id': dominate.id, 'cost_choice': {'id': 'base'},
            'targets': {'target_card_id': creature.id, 'x_value': 1},
        }))
        assert state.cards[creature.id].controller == seat
    original_ref = (state.cards[creature.id].battlefield_incarnation,
                    state.cards[creature.id].zone_change_sequence)
    aura = raw_card(state, ROWS['Confiscate'], seat, Zone.GRAVEYARD)
    state = activate(state, seat, walker, 1, {'target_card_id': aura.id, 'x_value': 6})
    assert state.cards[walker].loyalty == 4
    state, choices = resolve_with_declared_attachments(state, creature.id)
    tokens = [c for c in state.cards.values()
              if c.is_token and c.zone == Zone.BATTLEFIELD and c.name == 'Confiscate']
    assert choices == len(tokens) == 2
    assert state.cards[aura.id].zone == Zone.EXILE
    for token in tokens:
        assert token.oracle_text == ROWS['Confiscate']['oracle_text']
        assert token.attached_to == creature.id and token.owner == token.controller == seat
    assert state.cards[creature.id].owner == 3 - seat
    assert state.cards[creature.id].controller == seat
    before = snap(state)
    assert control_layer_view(state)[creature.id] == seat
    assert snap(state) == before
    for index, token in enumerate(tokens):
        bounce = raw_card(state, BOOMERANG, seat, Zone.HAND)
        state.players[seat].mana_pool = {'U': 2}
        state = settle(act(restart(state), seat, {
            'type': 'cast_spell', 'card_id': bounce.id, 'cost_choice': {'id': 'base'},
            'targets': {'target_card_id': token.id},
        }))
        expected = seat if index == 0 or indefinite_underlying else 3 - seat
        assert state.cards[creature.id].controller == expected
        assert state.players[expected].battlefield.count(creature.id) == 1
        assert creature.id not in state.players[3 - expected].battlefield
        assert (state.cards[creature.id].battlefield_incarnation,
                state.cards[creature.id].zone_change_sequence) == original_ref
        restart(state)
