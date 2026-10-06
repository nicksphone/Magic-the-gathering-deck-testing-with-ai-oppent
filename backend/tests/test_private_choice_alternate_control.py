"""A second canonical eligible Officer card, not an inferred first option."""
import pytest

from rules_engine.engine import RulesEngine
from tests.test_private_choice_intent_boundary import position, environment


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_second_officer_option_is_not_replaced_by_first(seat):
    state, _, _ = position('officer', seat)
    view = RulesEngine().legal_moves(state, seat)[0]
    choices = [cid for cid in view['options'] if cid != '__none__']
    assert len(choices) == 2
    assert state.cards[choices[1]].name == 'Militia Bugler'
    env = environment(state)
    action = {'type': 'choose_mechanic', 'card_ids': [choices[1]]}
    before = env.snapshot()
    normalized = env.lookup_intent(action, seat)['action']
    assert normalized == action and env.snapshot() == before
    env.step(normalized, seat)
    assert env._state.players[seat].hand == [choices[1]]
    assert choices[0] in env._state.players[seat].library
