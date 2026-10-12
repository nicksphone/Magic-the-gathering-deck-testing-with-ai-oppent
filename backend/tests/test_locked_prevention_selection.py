"""Trusted primitive controls; an unavailable explicit replacement stays invalid."""
import pytest

from effects.handlers import deal_damage
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.replacement import replacement_options
from tests.test_cant_prevent_scopes import _state


@pytest.mark.parametrize('seat', [1, 2])
def test_locked_prevention_rejects_explicit_source_then_applies_unselected_damage(seat):
    state = _state()
    lock = CardInstance('lock', 'Lock', seat, seat, Zone.BATTLEFIELD, ['Enchantment'],
                        oracle_text="Damage that would be dealt to you can't be prevented.")
    shield = CardInstance('shield', 'Shield', seat, seat, Zone.BATTLEFIELD, ['Enchantment'],
                          oracle_text='If a source would deal damage to you, prevent 1 of that damage.')
    source = CardInstance('source', 'Source', 3-seat, 3-seat, Zone.BATTLEFIELD, ['Creature'])
    state.cards.update({card.id: card for card in (lock, shield, source)})
    state.players[seat].battlefield.extend([lock.id, shield.id])
    state.players[3-seat].battlefield.append(source.id)
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    assert replacement_options(state, 'damage_to_player', target_player=seat,
                               source_card_id=source.id) == []
    payload = {'target_player': seat, 'amount': 3, '__source_card_id': source.id}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='no longer applicable'):
        deal_damage(state, 3-seat, {**payload, '__replacement_source_id': shield.id})
    assert serialize_match_snapshot(state) == before
    life = state.players[seat].life
    assert deal_damage(state, 3-seat, payload) == 3
    assert state.players[seat].life == life - 3
    assert state.pending_replacement_choice is None
