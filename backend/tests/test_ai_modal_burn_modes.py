"""Full printed modal spell outcomes, not whole-card tag preferences."""
import pytest

from ai.agent import AIAgent
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import choose, position, settle


def charm_position(seat, **options):
    return position(seat, ['Boros Charm'], ['Plateau', 'Mountain'], **options)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('step', [Step.UPKEEP, Step.DRAW, Step.PRECOMBAT_MAIN])
def test_damage_mode_not_noop_indestructibility_on_only_lands(seat, difficulty, step):
    state, cards, _, _ = charm_position(seat)
    state.step = step
    action = choose(state, seat, 'Burn', difficulty)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Boros Charm']
    assert action['targets'].get('target_player') == 3 - seat, action
    assert 'deals 4 damage' in action['targets']['mode_text'], action
    result = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Burn', difficulty)
    assert result.players[3 - seat].life == 16
    assert result.cards[cards['Boros Charm']].zone == Zone.GRAVEYARD
    assert all(result.cards[cid].tapped for cid in result.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_modal_damage_takes_actual_lethal(seat, difficulty):
    state, cards, _, _ = charm_position(seat)
    state.players[3 - seat].life = 4
    action = choose(state, seat, 'Burn', difficulty)
    result = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Burn', difficulty)
    assert result.winner == seat, action


def announced_sweeper(seat, name):
    lands = ['Plains'] * 5 if name == 'Sunfall' else ['Plains'] * 3 + ['Island']
    state, cards, _, move = charm_position(seat,
        reserve=['Sheoldred, the Apocalypse', 'Torrential Gearhulk', name, *lands])
    protected = [move(name, seat, Zone.BATTLEFIELD)
                 for name in ['Sheoldred, the Apocalypse', 'Torrential Gearhulk']]
    sweeper = move(name, 3 - seat, Zone.HAND)
    for land in lands:
        move(land, 3 - seat, Zone.BATTLEFIELD)
    state.active_player = state.priority_player = 3 - seat
    state = checked_action(state, RulesEngine(), 3 - seat,
        {'type': 'cast_spell', 'card_id': sweeper, 'targets': {}})
    state = checked_action(state, RulesEngine(), 3 - seat, {'type': 'pass_priority'})
    return state, cards, protected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_indestructible_mode_saves_actual_creatures_from_destroy(seat, difficulty):
    state, _, protected = announced_sweeper(seat, 'Supreme Verdict')
    action = choose(state, seat, 'Burn', difficulty)
    assert 'indestructible' in action.get('targets', {}).get('mode_text', ''), action
    result = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Burn', difficulty)
    assert all(result.cards[cid].zone == Zone.BATTLEFIELD for cid in protected)
    assert result.players[3 - seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_indestructible_is_not_an_answer_to_actual_exile(seat, difficulty):
    state, _, protected = announced_sweeper(seat, 'Sunfall')
    action = choose(state, seat, 'Burn', difficulty)
    assert action.get('targets', {}).get('target_player') == 3 - seat, action
    result = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Burn', difficulty)
    assert result.players[3 - seat].life == 16
    assert all(result.cards[cid].zone == Zone.EXILE for cid in protected)
