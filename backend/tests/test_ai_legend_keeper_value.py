"""Independent canonical legend choices; gameplay diagnostics are not TRAIN data."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.extra_sequence_support import position
from tests.test_linked_damage_targets import raw_card


ROWS = {row['name']: row for row in map(json.loads, (
    Path(__file__).parent / 'fixtures/legend_keeper_audit/canonical.jsonl'
).read_text().splitlines())}
ROWS.update({row['name']: row for row in map(json.loads, (
    Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
).read_text().splitlines()) if row['name'] == 'Teferi, Hero of Dominaria'})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('name,advantage', [
    (name, advantage) for name in ['Isamaru, Hound of Konda', 'Progenitus']
    for advantage in ['ready', 'counters', 'fresh_value', 'fresh_untapped']
] + [('Teferi, Hero of Dominaria', advantage) for advantage in ['loyalty', 'fresh_loyalty']])
def test_keeper_retains_public_value_instead_of_first_option(seat, name, reverse, advantage):
    state = position(seat)
    state.mechanic_choice_players = {1, 2}
    state.players[seat].mana_pool = {color: 10 for color in 'WUBRGC'}
    # Library card IDs need not follow battlefield entry order.
    if reverse:
        new = raw_card(state, ROWS[name], seat, Zone.HAND)
    old = raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    if not reverse:
        new = raw_card(state, ROWS[name], seat, Zone.HAND)
    old.summoning_sick = False
    if advantage == 'counters':
        old.counters['+1/+1'] = 2
        old.tapped = True
    elif advantage == 'fresh_value':
        old.counters['-1/-1'] = 1
    elif advantage == 'fresh_untapped':
        old.tapped = True
    elif advantage == 'loyalty':
        old.loyalty = 7
    elif advantage == 'fresh_loyalty':
        old.loyalty = 1
    rules = RulesEngine()
    mana_before = sum(state.players[seat].mana_pool.values())
    state = checked_action(state, rules, seat, {'type': 'cast_spell', 'card_id': new.id, 'targets': {}})
    assert sum(state.players[seat].mana_pool.values()) < mana_before
    for _ in range(12):
        if state.pending_mechanic_choice:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.pending_mechanic_choice['kind'] == 'legend_keeper'
    if 'Creature' in new.types:
        assert state.cards[new.id].summoning_sick
    moves = rules.legal_moves(state, seat)
    choice = next(move for move in moves if move.get('type') == 'choose_mechanic')
    choice['options'] = [new.id, old.id] if reverse else [old.id, new.id]
    before = serialize_match_snapshot(state)
    offered = deepcopy(moves)
    rng = random.getstate(), state.rng.getstate()
    decision = AIAgent('master', 'Tokens').choose_action(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    assert moves == offered and (random.getstate(), state.rng.getstate()) == rng
    keeper, loser = (new, old) if advantage.startswith('fresh_') else (old, new)
    assert decision.action == {'type': 'choose_mechanic', 'card_ids': [keeper.id]}
    state = checked_action(state, rules, seat, decision.action)
    assert keeper.id in state.players[seat].battlefield
    assert loser.id not in state.players[seat].battlefield
    if advantage == 'ready':
        assert not state.cards[keeper.id].summoning_sick
