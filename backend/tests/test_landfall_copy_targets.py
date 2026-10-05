"""Copied complete alternatives share announcements, not stale branch targets."""
import pytest

from effects.handlers import copy_spell, counter_spell
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_combat_stats
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_landfall_alternatives import position
from tests.test_ai_recurring_engines import add


def copied_position(name, seat, enhanced, target_self=False):
    state, spell, original_recipient, targets = position(name, seat)
    copier = 3-seat
    recipient = add(state, 'Torrential Gearhulk', copier)
    if target_self:
        targets = {'target_player': seat}
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    original = state.stack[-1].id
    state.land_entries_this_turn[copier] = int(enhanced)
    copy_spell(state, copier, {'target_stack_id': original, 'may_choose_new_targets': True})
    return state, original, original_recipient.id, recipient.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['groundswell', 'rest-for-the-weary'])
@pytest.mark.parametrize('enhanced', [False, True])
def test_alternative_copy_retarget_updates_both_branches_and_survives_counter(seat, name, enhanced):
    state, original, old, new = copied_position(name, seat, enhanced)
    selected = f'target_card_id:{new}' if name == 'groundswell' else f'target_player:{seat}'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 3-seat,
                           {'type': 'choose_mechanic', 'card_ids': [selected]})
    counter_spell(state, seat, {'target_stack_id': original})
    assert resolve_top_of_stack(state)
    if name == 'groundswell':
        amount = 4 if enhanced else 2
        assert effective_combat_stats(state, new) == (5+amount, 6+amount)
        assert effective_combat_stats(state, old) == (5, 6)
    else:
        assert state.players[seat].life == (28 if enhanced else 24)
        assert state.players[3-seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['groundswell', 'rest-for-the-weary'])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
def test_ai_redirects_alternative_copy_using_effect_not_card_name(seat, name, style):
    from ai.agent import AIAgent
    state, _, _, new = copied_position(name, seat, True, target_self=name == 'rest-for-the-weary')
    selected = f'target_card_id:{new}' if name == 'groundswell' else f'target_player:{3-seat}'
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty='master', archetype=style).choose_action(state, RulesEngine().legal_moves(state, 3-seat), 3-seat)
    assert decision.action == {'type': 'choose_mechanic', 'card_ids': [selected]}
    assert serialize_match_snapshot(state) == before
