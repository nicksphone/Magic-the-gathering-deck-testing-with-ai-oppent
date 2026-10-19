"""Real paid triggered target boundary, with independent lawful-target controls."""
import pytest

import test_paid_exchange_desired as original
import test_exchange_edges as edges
import domain_paid_support as g
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine

facts = edges.facts


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_triggered_ability_rejects_opponent_stormdrake_but_resolves_lawful_target(facts, seat):
    state = g.position(facts, seat)
    protected = g.add(state, facts, original.SOURCE, 3-seat)
    target = g.add(state, facts, 'Raging Goblin', 3-seat)
    alternate = g.add(state, facts, 'Raging Goblin', 3-seat)
    state.cards[target].counters['+1/+1'] = 1  # Declared initial resources, not a claimed cast.
    source = g.add(state, facts, 'Suncleanser', seat, Zone.HAND)
    private = (list(state.players[3-seat].hand), list(state.players[3-seat].library))
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = g.cast(state, seat, source)
    assert next(item for item in state.stack if item.source_card_id == source).payload['mana_spent'] == 2
    for _ in range(16):
        if state.cards[source].zone == Zone.BATTLEFIELD:
            break
        state = g.act(state, state.priority_player, 'pass_priority')
    assert state.cards[source].zone == Zone.BATTLEFIELD
    options = [(move, option) for move in original.moves(state, seat) if move['type'] == 'choose_mechanic'
               for option in move.get('options', [])
               if str(move.get('option_labels', {}).get(option, '')).startswith('Remove all counters from target creature')]
    assert len(options) == 1
    state = g.act(state, seat, 'choose_mechanic', choice_id=options[0][1])
    offered = original.moves(state, seat)
    legal = [move for move in offered if move['type'] == 'choose_trigger_target']
    assert any(move.get('target_card_id') == alternate for move in legal)
    choice = next(move for move in legal if move.get('target_card_id') == target)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {**choice, 'target_card_id': protected})
    assert serialize_match_snapshot(state) == before
    state = edges.settle(checked_action(state, RulesEngine(), seat, choice))
    assert state.cards[target].counters.get('+1/+1', 0) == 0
    assert state.cards[protected].zone == Zone.BATTLEFIELD
    assert (state.players[3-seat].hand, state.players[3-seat].library) == private
    assert state.cards[protected].oracle_text == facts[original.SOURCE]['oracle_text']
    original.record(f'edge-triggered-hexproof-{seat}-terminal', state, offered=offered)
