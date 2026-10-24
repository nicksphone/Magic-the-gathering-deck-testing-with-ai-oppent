"""Consideration only: no required cast/X value; parser strings are not prints."""
from copy import deepcopy
from dataclasses import replace
import sys

import pytest

from ai import agent as agent_module
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.engine import RulesEngine
from tests.browser_positive83_canonical import entry
from tests.test_meathook_etb import _canonical_meathook


def _land_only_position(seat):
    deck = [entry('Swamp', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=209)
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
        for _ in range(4):
            cid = player.library.pop(0)
            player.battlefield.append(cid)
            state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
            assign_static_order_on_battlefield_entry(state, cid)
            state.cards[cid].summoning_sick = False
        assert not any(player.mana_pool.values())
        assert all('Land' in state.cards[cid].types
                   and 'Creature' not in state.cards[cid].types
                   and not state.cards[cid].tapped for cid in player.battlefield)
    hook = replace(_canonical_meathook(), owner=seat, controller=seat)
    assert hook.id not in state.cards
    state.cards[hook.id] = hook
    state.players[seat].hand.append(hook.id)
    return state, hook


@pytest.mark.parametrize('seat', [1, 2])
def test_full_print_compound_permanent_reaches_actual_ranker(monkeypatch, seat):
    state, hook = _land_only_position(seat)
    rules = RulesEngine()
    legal = rules.legal_moves(state, seat)
    casts = [move for move in legal
             if move.get('type') == 'cast_spell' and move.get('card_id') == hook.id]
    assert len(casts) == 1, 'Genuine affordable Meathook cast must be offered'
    assert hook.types == ['Enchantment'] and '{X}' in hook.mana_cost
    assert not state.stack and state.players[seat].hand == [hook.id]

    ai = agent_module.AIAgent(difficulty='strong', archetype='Midrange')
    original_rank = agent_module.AIAgent._rank_moves
    inner = agent_module.AIAgent._choose_action
    choose = agent_module.AIAgent.choose_action
    observed = []

    def observe_rank(self, view, moves, player_id, *, shallow=False):
        caller = sys._getframe(1)
        outer = caller.f_back
        if (self is ai and caller.f_code is inner.__code__
                and caller.f_globals is inner.__globals__
                and outer is not None and outer.f_code is choose.__code__
                and outer.f_globals is choose.__globals__
                and outer.f_locals['authoritative_state'] is state):
            assert player_id == seat and caller.f_locals['state'] is view
            observed.append(deepcopy(moves))
        return original_rank(self, view, moves, player_id, shallow=shallow)

    monkeypatch.setattr(agent_module.AIAgent, '_rank_moves', observe_rank)
    decision = ai.choose_action(state, legal, seat)
    assert isinstance(decision, agent_module.AIDecision)
    assert observed, 'The genuine outer candidate-ranking path must execute'
    assert any(casts[0] in moves for moves in observed), (
        'Full compound-permanent cast was removed before actual consideration')


@pytest.mark.parametrize('text, expected', [
    ('All creatures get -X/-X until end of turn', True),
    ('All creatures get -X/-X until end of turn.', True),
    ('Each creature gets -x/-x until end of turn.', True),
    (' \nAll creatures get -X/-X until end of turn.\n\t', True),
    ('All creatures get -X/-X until end of turn. (Reminder (nested reminder).)', True),
    ('When this enters the battlefield, all creatures get -X/-X until end of turn.', False),
    ('All creatures get -X/-X until end of turn.\nDraw a card.', False),
    ('Draw a card. All creatures get -X/-X until end of turn.', False),
    ('Draw a card.', False),
    ('', False),
    ('All creatures get -X/-X until end of turn..', False),
    ('All creatures get -X/-X until end of turn. (Unclosed reminder', False),
    ('All creatures get -X/-X.', False),
], ids=[
    'sole_no_period', 'sole_one_period', 'each_case_insensitive', 'outer_whitespace',
    'nested_reminder', 'etb_prefix', 'additional_clause', 'prefix_clause',
    'unrelated', 'empty', 'two_periods', 'unclosed_reminder', 'incomplete_clause',
])
def test_only_variable_sweep_text_parser_protocol(text, expected):
    predicate = getattr(agent_module, '_only_variable_sweep_text', None)
    assert callable(predicate), 'Proposed whole-effect helper is absent; parser contract RED'
    assert predicate(text) is expected
