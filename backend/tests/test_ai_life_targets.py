"""Original and copied life instructions use public replacement outcomes."""
import pytest

from ai.agent import AIAgent
from ai.life_targets import life_target_score
from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_landfall_alternatives import position
from tests.test_life_conversion import permanent


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
@pytest.mark.parametrize('source', ['tainted-remedy', 'plague-drone'])
def test_original_life_spell_uses_conversion_for_lethal_instead_of_healing_self(seat, style, source):
    state, spell, _, _ = position('rest-for-the-weary', seat)
    permanent(state, source, seat)
    state.players[3-seat].life = 4
    before = serialize_match_snapshot(state)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m.get('card_id') == spell.id and m['type'] == 'cast_spell')
    action = AIAgent(archetype=style)._materialize_action(state, move, seat)
    assert serialize_match_snapshot(state) == before
    assert action['targets']['target_player'] == 3-seat
    state = checked_action(state, RulesEngine(), seat, action)
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_adversarial_replacement_order_is_not_newest_source_guessing(seat):
    state, _, _, _ = position('rest-for-the-weary', seat)
    permanent(state, 'tainted-remedy', seat)
    permanent(state, 'alhammarrets-archive', 3-seat)
    before = serialize_match_snapshot(state)
    assert life_target_score(state, seat, 3-seat, 4) == 4
    assert serialize_match_snapshot(state) == before
    assert life_target_score(state, 3-seat, 3-seat, 4) == -4


@pytest.mark.parametrize('seat', [1, 2])
def test_private_draw_replacement_is_unknown_and_does_not_read_library(seat):
    from unittest.mock import patch
    state, _, _, _ = position('rest-for-the-weary', seat)
    permanent(state, 'lich', seat)
    before = serialize_match_snapshot(state)
    with patch('effects.handlers.draw_cards', side_effect=AssertionError('Private draw forecast')):
        assert life_target_score(state, seat, seat, 4) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_life_at_zero_is_not_a_win_when_public_effect_prevents_losing(seat):
    state, _, _, _ = position('rest-for-the-weary', seat)
    permanent(state, 'tainted-remedy', seat)
    permanent(state, 'platinum-angel', 3-seat)
    state.players[3-seat].life = 4
    assert life_target_score(state, seat, 3-seat, 4) == 4


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['lightning-helix', 'essence-drain'])
@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Midrange'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_caster_gain_conversion_does_not_make_ai_cast_suicidal_damage_spell(seat, name, style, difficulty):
    from tests.test_ai_beneficial_alternatives import damage_gain_position
    state, spell = damage_gain_position(seat, name)
    permanent(state, 'tainted-remedy', 3-seat)
    state.players[seat].life = 3
    before = serialize_match_snapshot(state)
    action = AIAgent(difficulty=difficulty, archetype=style).choose_action(
        state, RulesEngine().legal_moves(state, seat), seat).action
    assert serialize_match_snapshot(state) == before
    assert not (action['type'] == 'cast_spell' and action.get('card_id') == spell.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enhanced', [False, True])
def test_conditional_copied_life_spell_redirects_to_conversion_lethal(seat, enhanced):
    state, spell, _, _ = position('rest-for-the-weary', seat)
    permanent(state, 'tainted-remedy', seat)
    state.land_entries_this_turn[seat] = int(enhanced)
    state.players[3-seat].life = 8 if enhanced else 4
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
                           'card_id': spell.id, 'targets': {'target_player': seat}})
    original_id = state.stack[-1].id
    resolve_effect(state, seat, 'copy_spell', {'target_stack_id': original_id, 'may_choose_new_targets': True})
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    choice = AIAgent().choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert choice.action['card_ids'] == [f'target_player:{3-seat}']
    state = checked_action(state, RulesEngine(), seat, choice.action)
    assert resolve_top_of_stack(state)
    assert state.players[3-seat].life == 0
    assert state.stack[-1].id == original_id
    assert state.stack[-1].payload['__announced_targets']['target_player'] == seat
