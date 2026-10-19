"""Canonical quantity regression now qualified with the self-death compiler."""
import pytest

from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_activated_sacrifice_identity import add, activate, cards


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_dependent_death_token_quantity(seat):
    state = cards.position(seat)
    tower = add(state, 'Phyrexian Tower', seat)
    victim = add(state, 'Hangarback Walker', seat)
    victim.counters['+1/+1'] = 2
    result = activate(state, seat, tower, victim)
    assert result.cards[victim.id].last_known_battlefield['counters']['+1/+1'] == 2
    resolve_top_of_stack(result)
    tokens = [result.cards[cid] for cid in result.players[seat].battlefield if result.cards[cid].is_token]
    assert len(tokens) == 2
