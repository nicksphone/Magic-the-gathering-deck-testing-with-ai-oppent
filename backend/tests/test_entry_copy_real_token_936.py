"""Physical Steel copies an actually produced Treasure without becoming a token."""
import pytest

from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.card_types import is_token_card
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import cast_vaults, choose, place, snapshot
from tests.test_entry_copy_native_936 import cast, position, raw


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_steel_copy_of_genuine_treasure_survives_destroy_and_real_reentry(seat):
    names = ['Deadly Dispute', 'Grizzly Bears', 'Sculpting Steel', 'Disenchant', 'Open the Vaults']
    state = position(names, names, seat)
    bear = place(state, 'Grizzly Bears', Zone.BATTLEFIELD, seat)
    dispute = place(state, 'Deadly Dispute', Zone.HAND, seat)
    state.players[seat].mana_pool = {'B': 1, 'C': 1}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': dispute,
        'cost_choice': {'id': 'base', 'sacrifice_card_ids': [bear]}})
    assert not any(state.players[seat].mana_pool.values())
    assert state.cards[dispute].oracle_text == raw('Deadly Dispute')['oracle_text']
    assert resolve_top_of_stack(state) and state.cards[bear].zone == Zone.GRAVEYARD
    token, = [card for card in state.cards.values() if card.owner == seat and card.is_token]
    assert token.zone == Zone.BATTLEFIELD and token.name == 'Treasure' and is_token_card(token)
    assert token.types == ['Artifact'] and 'Add one mana of any color' in token.oracle_text
    state, steel = cast(snapshot(state), seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state) and token.id in state.pending_mechanic_choice['options']
    state = choose(snapshot(state), seat, token.id)
    for card in [state.cards[steel], snapshot(state).cards[steel]]:
        assert not card.is_token and not is_token_card(card) and 'Token' not in card.types
        assert card.owner == card.controller == seat and card.name == 'Treasure'
        assert card.oracle_text == token.oracle_text
    state, _ = cast(state, seat, 'Disenchant', target_card_id=steel)
    assert resolve_top_of_stack(state)
    assert steel in state.cards and state.cards[steel].zone == Zone.GRAVEYARD
    assert state.cards[steel].name == 'Sculpting Steel' and not is_token_card(state.cards[steel])
    assert snapshot(state).sideboard_facts['inventory'][steel]['stock_key'] == 'Sculpting Steel'
    state, _ = cast_vaults(state, seat)
    assert not resolve_top_of_stack(state) and token.id in state.pending_mechanic_choice['options']
    state = choose(snapshot(state), seat, token.id)
    assert state.cards[steel].zone == Zone.BATTLEFIELD and not is_token_card(state.cards[steel])
    assert snapshot(state).sideboard_facts['inventory'][steel]['stock_key'] == 'Sculpting Steel'
