"""Land rejection must precede spell-only typed timing, without weakening it."""
import pytest

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine
import rules_engine.engine as engine_module


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('typed', [False, True])
def test_land_is_not_submitted_to_spell_timing_or_paid(seat, typed, monkeypatch):
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    player = state.players[seat]
    cid = player.hand[0]
    card = state.cards[cid]
    card.name = 'Forest'
    card.types = ['Land'] if typed else []
    card.type_line = 'Land' if typed else ''
    player.mana_pool = {'G': 2}
    before = (list(player.hand), dict(player.mana_pool), card.zone)

    def not_a_spell(*args, **kwargs):
        pytest.fail('Land reached spell timing/type admission')

    monkeypatch.setattr(engine_module, 'can_cast_in_current_timing', not_a_spell)
    RulesEngine().take_action(state, seat, {'type': 'cast_spell', 'card_id': cid})
    assert (player.hand, player.mana_pool, card.zone) == before
    assert state.stack == []
    assert any('cannot cast land card Forest as a spell' in line for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_nonland_spell_types_stay_fail_closed(seat):
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    player = state.players[seat]
    cid = player.hand[0]
    card = state.cards[cid]
    card.name, card.types, card.type_line = 'Unknown object', [], ''
    player.mana_pool = {'G': 2}
    before = (list(player.hand), dict(player.mana_pool), card.zone)
    RulesEngine().take_action(state, seat, {'type': 'cast_spell', 'card_id': cid})
    assert (player.hand, player.mana_pool, card.zone) == before
    assert state.stack == []
    assert any('prohibits casting from this zone' in line for line in state.log)
