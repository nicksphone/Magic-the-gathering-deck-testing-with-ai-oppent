"""Native resource-unit counterexamples against the frozen first C11 helper.

The impulse permission is an explicit trusted unit setup, not a claim that an
upstream impulse spell was executed. These positions are not TRAIN samples.
"""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.card_faces import ordinary_exile_permission
from rules_engine.engine import RulesEngine
from tests.test_ai_strategy_fundamentals import position
from tests.test_burn_core_native_outcomes import add as add_full_canonical

from ai.mana_resource_policy import prefer_nonregressive_land


def ready(state, seat):
    player = state.players[seat]
    player.lands_played_this_turn = player.land_plays_recorded_on_turn = 0
    player.last_land_play_turn = state.turn


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_entry_life_is_a_known_resource_tradeoff(seat):
    state, cards, _, _ = position(
        seat, ['Island', 'Hallowed Fountain'], ['Island'], ['Grizzly Bears'])
    add_full_canonical(state, 'Swords to Plowshares', seat)
    ready(state, seat)
    selected = {'type': 'play_land', 'card_id': cards['Island']}
    alternative = {'type': 'play_land', 'card_id': cards['Hallowed Fountain'],
                   'entry_choice': 'pay_two_life'}
    rules = RulesEngine()
    free = checked_action(state, rules, seat, selected)
    paid = checked_action(state, rules, seat, alternative)
    assert free.players[seat].life == state.players[seat].life
    assert paid.players[seat].life == state.players[seat].life - 2
    before = serialize_match_snapshot(state)
    answer = prefer_nonregressive_land(AIAgent(archetype='Control'), state, seat,
                                       selected, [selected, alternative])
    assert serialize_match_snapshot(state) == before
    # It may be strategically sensible to pay life, but it is not dominance.
    assert answer == selected, answer


@pytest.mark.parametrize('seat', [1, 2])
def test_known_ordinary_exile_permission_preserves_other_color_access(seat):
    state, cards, opponents, _ = position(
        seat, ['Mountain', 'Plains'], ['Island'], ['Grizzly Bears'])
    sword = add_full_canonical(state, 'Swords to Plowshares', seat)
    bolt = add_full_canonical(state, 'Lightning Bolt', seat, Zone.EXILE)
    # Native temporary permission, deliberately set up without an upstream spell.
    state.players[seat].exile_play_until[bolt] = state.turn
    ready(state, seat)
    assert not state.cards[bolt].exile_face_down
    assert ordinary_exile_permission(state, seat, bolt)
    selected = {'type': 'play_land', 'card_id': cards['Mountain']}
    alternative = {'type': 'play_land', 'card_id': cards['Plains']}
    rules = RulesEngine()
    red = checked_action(state, rules, seat, selected)
    white = checked_action(state, rules, seat, alternative)
    burn = {'type': 'cast_spell', 'card_id': bolt, 'from_exile': True,
            'targets': {'target_player': 3-seat}}
    assert checked_action(red, rules, seat, burn).stack[-1].source_card_id == bolt
    with pytest.raises(ActionRejected):
        checked_action(white, rules, seat, burn)
    removal = {'type': 'cast_spell', 'card_id': sword,
               'targets': {'target_card_id': opponents['Grizzly Bears']}}
    assert checked_action(white, rules, seat, removal).stack[-1].source_card_id == sword
    with pytest.raises(ActionRejected):
        checked_action(red, rules, seat, removal)
    before = serialize_match_snapshot(state)
    answer = prefer_nonregressive_land(AIAgent(archetype='Control'), state, seat,
                                       selected, [selected, alternative])
    assert serialize_match_snapshot(state) == before
    assert answer == selected, answer
