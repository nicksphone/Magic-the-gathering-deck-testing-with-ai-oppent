"""Full Vraska remains closed; the separate primitive exercises AI destroy guards."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body
from rules_engine.engine import RulesEngine
from tests.loyalty_destruction_diagnostic_support import source
from tests.test_ineffective_destruction import settled_state
from tests.test_pending_removal import CARDS, add_card
from tests.test_self_removal import canonical_cards


def test_full_canonical_vraska_is_not_partially_admitted_and_rejection_is_atomic():
    state, victim, _ = settled_state()
    row = CARDS['Vraska the Unseen']
    card = CardInstance('canonical-vraska', row['name'], 1, 1, Zone.BATTLEFIELD,
                        ['Planeswalker'], oracle_text=row['oracle_text'],
                        type_line=row['type_line'], colors=row['colors'], loyalty=int(row['loyalty']))
    state.cards[card.id] = card
    state.players[1].battlefield.append(card.id)
    before = serialize_match_snapshot(state)
    assert len(card.oracle_text.splitlines()) == 3
    assert compile_body(card.oracle_text, card.name) is None
    assert not any(move.get('card_id') == card.id for move in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty', 'card_id': card.id,
                                               'ability_index': 1, 'targets': {'target_card_id': victim}})
    assert serialize_match_snapshot(state) == before and card.oracle_text == row['oracle_text']


def test_closed_diagnostic_ai_holds_indestructible_but_human_can_pay_loyalty():
    state, victim, _ = settled_state()
    card = source(state)
    before = serialize_match_snapshot(state)
    move = next(m for m in RulesEngine().legal_moves(state, 1)
                if m.get('card_id') == card.id and m.get('ability_delta') == -3)
    assert AIAgent()._materialize_action(state, move, 1).get('_invalid_ai_choice')
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty', 'card_id': card.id,
                        'ability_index': 0, 'targets': {'target_card_id': victim}})
    assert state.cards[card.id].loyalty == 2
    while state.stack:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.cards[victim].zone == Zone.BATTLEFIELD


def test_closed_diagnostic_ai_uses_original_canonical_creature_for_death_win():
    state, _, _ = settled_state()
    add_card(state, 'Bastion of Remembrance', Zone.BATTLEFIELD)
    creature = add_card(state, 'Sprite Dragon', Zone.BATTLEFIELD)
    walker = source(state)
    state.players[2].life = 1
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Midrange').choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action['type'] == 'activate_loyalty'
    assert decision.action['card_id'] == walker.id
    assert decision.action['targets']['target_card_id'] == creature.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, RulesEngine(), 1, decision.action)
    while state.stack and state.winner is None:
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.winner == 1 and state.players[2].life == 0
    assert state.cards[creature.id].zone == Zone.GRAVEYARD
    assert state.cards[walker.id].loyalty == 2


def test_unknown_companion_still_blocks_the_entire_diagnostic_surface_atomically():
    state, victim, _ = settled_state()
    card = source(state)
    card.oracle_text += '\nUnaccounted diagnostic companion.'
    before = serialize_match_snapshot(state)
    assert compile_body(card.oracle_text, card.name) is None
    assert not any(m.get('card_id') == card.id for m in RulesEngine().legal_moves(state, 1))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'activate_loyalty', 'card_id': card.id,
                         'ability_index': 0, 'targets': {'target_card_id': victim}})
    assert serialize_match_snapshot(state) == before
