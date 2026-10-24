"""A negative X-timing hold must survive repeated same-board pass conversion."""
from dataclasses import replace

import pytest

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.engine import RulesEngine
from tests.ai_decisions_canonical_cdba import canonical_card
from tests.browser_positive83_canonical import entry
from tests.test_meathook_etb import _canonical_meathook


@pytest.mark.parametrize('seat', [1, 2])
def test_full_print_variable_sweeper_holds_on_repeated_main_pass(seat):
    deck = [entry('Swamp', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=973)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
    player = state.players[seat]
    for _ in range(3):
        cid = player.library.pop()
        player.battlefield.append(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, cid)
    spell = replace(_canonical_meathook(), owner=seat, controller=seat)
    assert spell.id not in state.cards
    state.cards[spell.id] = spell
    player.hand.append(spell.id)
    assert len(player.battlefield) == 3 and not any(player.mana_pool.values())
    assert all(state.cards[cid].name == 'Swamp' and not state.cards[cid].tapped
               for cid in player.battlefield)
    assert not state.players[3 - seat].battlefield and not state.stack
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move.get('type') == 'cast_spell' and move.get('card_id') == spell.id
               for move in moves)

    ai = AIAgent(difficulty='master', archetype='Control')
    for attempt in range(2):
        decision = ai.choose_action(state, moves, seat)
        assert decision.action['type'] == 'pass_priority', (attempt, decision.action)


@pytest.mark.parametrize('seat', [1, 2])
def test_full_print_variable_sweeper_holds_against_unreachable_large_creature(seat):
    deck = [entry('Swamp', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=973)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
    player = state.players[seat]
    for _ in range(3):
        cid = player.library.pop()
        player.battlefield.append(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, cid)
    spell = replace(_canonical_meathook(), owner=seat, controller=seat)
    assert spell.id not in state.cards
    state.cards[spell.id] = spell
    player.hand.append(spell.id)
    opponent = 3 - seat
    threat = canonical_card('Torrential Gearhulk', as_instance=True, id='large-threat',
                            owner=opponent, controller=opponent, zone=Zone.BATTLEFIELD)
    assert threat.id not in state.cards and threat.toughness == 6
    state.cards[threat.id] = threat
    state.players[opponent].battlefield.append(threat.id)
    assign_static_order_on_battlefield_entry(state, threat.id)
    assert len(player.battlefield) == 3 and not any(player.mana_pool.values())
    assert all(state.cards[cid].name == 'Swamp' and not state.cards[cid].tapped
               for cid in player.battlefield)
    assert state.players[opponent].battlefield == [threat.id] and not state.stack
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move.get('type') == 'cast_spell' and move.get('card_id') == spell.id
               for move in moves)

    ai = AIAgent(difficulty='master', archetype='Control')
    decision = ai.choose_action(state, moves, seat)
    assert decision.action['type'] == 'pass_priority', decision.action
