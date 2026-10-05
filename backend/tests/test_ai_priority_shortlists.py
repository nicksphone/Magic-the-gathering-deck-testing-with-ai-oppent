"""Priority passes must reach resolution, not disappear below proactive beams."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent, _shortlist_with_priority_pass
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_strategic_pass import position, controlled_planner


ROWS = {row['card_name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/strategic_priority_cards.json').read_text())['cards']}


def add(state, name, seat, zone=Zone.HAND):
    row = {**ROWS[name], 'quantity': 8}
    sample = MatchFactory.from_decks([row], [], seed=937)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False
    return card


def test_shortlist_preserves_order_and_does_not_invent_or_duplicate_pass():
    cast = {'type': 'cast_spell', 'card_id': 'test-selection'}
    wait = {'type': 'pass_priority'}
    ranked = [cast, wait]
    assert _shortlist_with_priority_pass(ranked, ranked, 1) == [cast, wait]
    assert _shortlist_with_priority_pass(ranked, ranked, 2) == ranked
    assert _shortlist_with_priority_pass([cast], [cast], 1) == [cast]
    assert ranked == [cast, wait]


@pytest.mark.parametrize('seat', [1, 2])
def test_counterwar_reply_shortlist_retains_a_low_ranked_legal_pass(monkeypatch, seat):
    state, cast = position(seat)
    wait = {'type': 'pass_priority'}
    ai = AIAgent(difficulty='master', archetype='Tempo')
    ranked = [cast] * 9 + [wait]
    controlled_planner(monkeypatch, ai, ranked, {'cast_spell': -10, 'pass_priority': 10})
    before = serialize_match_snapshot(state)
    assert wait in ai._strategic_top_actions(state, ranked, seat, limit=3)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Aggro', 'Burn'])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_clear_board_and_payable_hand_are_not_held_forever(seat, style, difficulty):
    state = bare_state(seat)
    state.turn = 17
    state.players[seat].life, state.players[3-seat].life = 13, 8
    for _ in range(7):
        add(state, 'Mountain', seat, Zone.BATTLEFIELD)
    for _ in range(5):
        add(state, 'Mountain', 3-seat, Zone.BATTLEFIELD)
    add(state, 'Plains', 3-seat, Zone.BATTLEFIELD)
    for name in ['Light Up the Stage', 'Rift Bolt', 'Soul-Scar Mage', 'Rift Bolt']:
        add(state, name, seat)
    for _ in range(4):
        # These are genuinely hidden in the decision view, not known replies.
        cid = state.players[3-seat].library.pop()
        state.cards[cid].move_to_zone(Zone.HAND)
        state.players[3-seat].hand.append(cid)
    before = serialize_match_snapshot(state)
    ai = AIAgent(difficulty=difficulty, archetype=style)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['type'] == 'cast_spell', decision
    assert serialize_match_snapshot(state) == before
    result = checked_action(state, RulesEngine(), seat, decision.action)
    assert result.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_single_alternative_target_does_not_gain_an_extra_planeswalker_target(seat):
    state = bare_state(seat)
    add(state, 'Nissa, Who Shakes the World', 3-seat, Zone.BATTLEFIELD)
    spell = add(state, 'Lava Spike', seat)
    state.players[seat].mana_pool['R'] = 1
    ai = AIAgent(difficulty='master', archetype='Burn')
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == spell.id)
    action = ai._materialize_action(state, move, seat)
    targets = action['targets']
    assert int(targets.get('target_player') is not None) + int(bool(targets.get('target_card_id'))) == 1
    assert checked_action(state, RulesEngine(), seat, action).stack
