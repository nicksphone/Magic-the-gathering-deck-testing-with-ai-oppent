"""Extra canonical boundaries; original 45-case audit remains unchanged."""
import json

import pytest

from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.combat import _combat_damage_step
from rules_engine.engine import RulesEngine
from tests.test_soulscar_preflight_rules_audit import CARDS, DIRECTORY, add, cast, finish, position, receipt, restore

CARDS['Skullcrack'] = json.loads((DIRECTORY / 'skullcrack.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_skullcrack_cannot_prevent_rule_does_not_disable_replacement(seat):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    target = add(state, 'Torrential Gearhulk', 3-seat)
    spell = add(state, 'Skullcrack', seat, Zone.HAND)
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
        'card_id': spell, 'targets': {'target_player': 3-seat}})
    state = finish(state)
    assert state.turn_damage_cant_be_prevented
    assert state.players[3-seat].life == 17
    state, _ = cast(state, 'Lightning Bolt', seat, target)
    state = finish(restore(state))
    receipt('paid-unpreventable-replacement', state, target, seat=seat)
    assert state.cards[target].counters.get('-1/-1') == 3
    assert not state.cards[target].counters.get('__damage_marked')


@pytest.mark.parametrize('seat', [1, 2])
def test_combat_lifelink_still_deals_real_damage_with_replacement_source_present(seat):
    state = position(seat)
    add(state, 'Soul-Scar Mage', seat)
    nighthawk = add(state, 'Vampire Nighthawk', seat)
    state.attackers = [nighthawk]
    # This is the actual core combat path on an explicit unblocked fixture,
    # not a claim of naturally chosen attackers or a forged spell effect.
    _combat_damage_step(state, 3-seat, set(), False)
    assert state.players[seat].life == 22
    assert state.players[3-seat].life == 18
