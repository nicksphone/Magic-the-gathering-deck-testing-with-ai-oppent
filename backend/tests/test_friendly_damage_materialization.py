"""Public conditional damage, canonical sibling damage and opaque consumer controls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.conditional_instructions import selected_instruction
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import CARDS, add
from tests.natural_heat_diagnostic_support import canonical, canonical_control, private_cards


def public_condition(state, seat, enhanced):
    if enhanced:
        for name in ('Go for the Throat', 'Damnation', 'Torrential Gearhulk'):
            add(state, name, seat, Zone.GRAVEYARD)


def move_to_graveyard(state, cid):
    card = state.cards[cid]
    state.players[card.controller].battlefield.remove(cid)
    card.move_to_zone(Zone.GRAVEYARD)
    state.players[card.owner].graveyard.append(cid)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
@pytest.mark.parametrize('enhanced', [False, True])
def test_public_conditional_damage_both_amounts_reject_known_losing_self_target(seat, window, enhanced):
    state, heat, victim = canonical_control(seat, window)
    public_condition(state, seat, enhanced)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = canonical(serialize_match_snapshot(state))
    rules = RulesEngine()
    declared = {'type': 'cast_spell', 'card_id': heat, 'targets': {'target_card_id': victim}}
    announced = checked_action(state, rules, seat, declared).stack[-1]
    assert announced.effect_key == 'conditional_instruction'
    key, payload = selected_instruction(state, seat, announced.payload)
    assert key == 'deal_damage'
    assert payload['amount'] == (6 if enhanced else 2)
    view, moves = decision_view(state, seat, rules.legal_moves(state, seat))
    assert all(private_cards(view, seat).values())
    ai = AIAgent(difficulty='master', archetype='Tempo', opponent_archetype='Control')
    move = next(move for move in moves if move.get('card_id') == heat)
    rejected = ai._materialize_action(view, move, seat)
    assert rejected.get('_invalid_ai_choice')
    decision = ai.choose_action(state, rules.legal_moves(state, seat), seat)
    assert decision.action.get('card_id') != heat
    checked_action(state, rules, seat, decision.action)
    assert canonical(serialize_match_snapshot(state)) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_continuation_uses_actual_conditional_lethality_not_spell_name(seat):
    results = []
    for enhanced in (False, True):
        state, heat, victim = canonical_control(seat, 'response')
        move_to_graveyard(state, victim)
        target = add(state, 'Torrential Gearhulk', seat)
        public_condition(state, seat, enhanced)
        view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
        ai = AIAgent(difficulty='master', archetype='Tempo', opponent_archetype='Control')
        action = ai._materialize_action(view, {**next(m for m in moves if m.get('card_id') == heat),
            'targets': {'target_card_id': target.id}}, seat)
        results.append(bool(action.get('_invalid_ai_choice')))
    # Two damage cannot prove this six-toughness target departed before the private continuation.
    assert results == [False, True]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
def test_shared_guard_redirects_a_stronger_friendly_target_to_an_offered_opponent(seat, window):
    state, heat, victim = canonical_control(seat, window)
    move_to_graveyard(state, victim)
    friendly = add(state, 'Torrential Gearhulk', seat)
    opponent = add(state, 'Grizzly Bears', 3-seat)
    public_condition(state, seat, True)
    before = canonical(serialize_match_snapshot(state))
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    ai = AIAgent(difficulty='master', archetype='Tempo', opponent_archetype='Control')
    move = next(move for move in moves if move.get('card_id') == heat)
    action = ai._materialize_action(view, {**move, 'targets': {'target_card_id': friendly.id}}, seat)
    assert not action.get('_invalid_ai_choice')
    assert action['targets']['target_card_id'] == opponent.id
    candidate = checked_action(state, RulesEngine(), seat, action)
    while candidate.cards[opponent.id].zone == Zone.BATTLEFIELD:
        candidate = checked_action(candidate, RulesEngine(), candidate.priority_player, {'type': 'pass_priority'})
    assert candidate.cards[friendly.id].zone == Zone.BATTLEFIELD
    assert canonical(serialize_match_snapshot(state)) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_nonwinning_death_payoff_is_not_assumed_harmful(seat):
    state, heat, victim = canonical_control(seat, 'response', payoff='Bastion of Remembrance')
    state.players[3-seat].life = 2
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    ai = AIAgent(difficulty='master', archetype='Tempo', opponent_archetype='Control')
    action = ai._materialize_action(view, {**next(m for m in moves if m.get('card_id') == heat),
        'targets': {'target_card_id': victim}}, seat)
    assert not action.get('_invalid_ai_choice')
    checked_action(state, RulesEngine(), seat, action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('window', ['response', 'proactive'])
def test_canonical_nonconditional_sibling_uses_same_materialization_guard(seat, window):
    state, heat, victim = canonical_control(seat, window)
    state.players[seat].hand.remove(heat)
    state.cards[heat].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(heat)
    raw = {row['name']: row for row in json.loads(
        (Path(__file__).parent / 'fixtures' / 'ai_oracle_semantics.json').read_text())}
    sibling = add(state, 'Lightning Strike', seat, Zone.HAND, cards=raw)
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    ai = AIAgent(difficulty='master', archetype='Tempo', opponent_archetype='Control')
    action = ai._materialize_action(view, {**next(m for m in moves if m.get('card_id') == sibling.id),
        'targets': {'target_card_id': victim}}, seat)
    assert action.get('_invalid_ai_choice')
    enemy = add(state, 'Grizzly Bears', 3-seat)
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    action = ai._materialize_action(view, {**next(m for m in moves if m.get('card_id') == sibling.id),
        'targets': {'target_card_id': victim}}, seat)
    assert not action.get('_invalid_ai_choice')
    assert action['targets']['target_card_id'] == enemy.id
    checked_action(state, RulesEngine(), seat, action)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_consumer_decisions_ignore_hidden_order_and_opponent_hand_identity(seat):
    state, heat, victim = canonical_control(seat, 'response')
    add(state, 'Blood Artist', 3-seat, Zone.HAND)
    add(state, 'Damnation', 3-seat, Zone.LIBRARY)
    changed = deepcopy(state)
    for player in changed.players.values():
        player.library.reverse()
    hidden = changed.cards[changed.players[3-seat].hand[0]]
    replacement = add(changed, 'Grizzly Bears', 3-seat, Zone.HAND)
    changed.players[3-seat].hand.remove(hidden.id)
    hidden.move_to_zone(Zone.GRAVEYARD)
    changed.players[3-seat].graveyard.append(hidden.id)
    # Keep the public graveyard identical; the changed hidden hand is the only identity difference.
    changed.players[3-seat].graveyard.remove(hidden.id)
    changed.cards.pop(hidden.id)
    results = []
    for root in (state, changed):
        before = canonical(serialize_match_snapshot(root))
        legal = RulesEngine().legal_moves(root, seat)
        view, _ = decision_view(root, seat, legal)
        assert all(private_cards(view, seat).values())
        ai = AIAgent(difficulty='master', archetype='Tempo', opponent_archetype='Control')
        decision = ai.choose_action(root, legal, seat)
        assert decision.action.get('card_id') != heat
        checked_action(root, RulesEngine(), seat, decision.action)
        assert canonical(serialize_match_snapshot(root)) == before
        results.append(decision.action)
    assert results[0] == results[1]
