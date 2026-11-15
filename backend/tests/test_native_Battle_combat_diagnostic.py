"""Complete-printing native attack diagnostic; initial zones are declared policy.

No card printing, Oracle text or causal paid history is invented. This small
diagnostic precedes the complete Task5 module and does not qualify combat.
"""
import pytest

from game_state.state import Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
from tests.test_battle_transformed_cast import position, row
from tests.test_battle_entry import BATTLE, place
from tests.test_battle_characteristics import mark


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_native_attack_choice_includes_own_siege(seat):
    for name in (BATTLE, 'Forest', 'Grizzly Bears'):
        raw = row(name, 1)
        assert raw['object'] == 'card' and len(raw) >= 50
        assert all(raw.get(key) for key in ('id', 'oracle_id', 'uri', 'scryfall_uri', 'layout'))
    state, battle = position(seat, extra=('Grizzly Bears',))
    attacker = place(state, seat, 'Grizzly Bears', Zone.BATTLEFIELD)
    state.step = Step.DECLARE_ATTACKERS
    state.active_player = state.priority_player = seat
    assert state.cards[battle].controller == seat and state.cards[battle].battle_protector == 3-seat
    assert state.cards[battle].counters['defense'] == 3
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move['type'] == 'attack')
    assert attacker in move['options']
    mark('native-own-Siege-attack-destination-assertion-reached')
    target = 'battle:' + battle
    assert target in {choice['id'] for choice in move['defenders']}
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'attack', 'attackers': [attacker], 'attack_targets': {attacker: target}})
    assert state.attack_targets[attacker] == target and state.cards[attacker].tapped
    assert state.cards[battle].counters['defense'] == 3
    assert state.players[1].life == state.players[2].life == 20
