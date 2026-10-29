"""Canonical reservation boundaries with synthetic finite Q, not fitted quality.

These are baseline-preserving controls, not full-game or model-strength claims.
"""
from copy import deepcopy
import json
import pickle
import random

import pytest

from ai import foretell_policy, learned_policy, learned_qv
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.costs import collect_cost_options
from rules_engine.foretell import can_look
from rules_engine.mana import can_pay_with_pool_and_lands
from tests import test_learned_pass_stall_guard as support
from tests.test_ai_strategy_fundamentals import position
from tests.test_learned_idle_banking_guard import FORETELL, RULES, WAIT
from tests.test_linked_damage_targets import raw_card
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _expanded, _field, _named_values


def add_foretell_card(state, name, seat, zone=Zone.HAND):
    raw = FORETELL[name]
    card = raw_card(state, raw, seat, zone)
    card.keywords = deepcopy(raw['keywords'])
    assert all(getattr(card, key) == raw[key] for key in
               ('name', 'oracle_text', 'mana_cost', 'type_line', 'keywords', 'colors'))
    return card


def scene(seat):
    state, _, _, move = position(seat, [], [], reserve=['Opt', 'Lightning Bolt', 'Llanowar Elves'])
    move('Opt', 3-seat, Zone.HAND)
    move('Lightning Bolt', 3-seat, Zone.HAND)
    behold = add_foretell_card(state, 'Behold the Multiverse', seat)
    return state, behold.id, move


def synthetic_foretell_preference(monkeypatch):
    calls = support.synthetic_q(monkeypatch)
    original_prepare = learned_qv.QVPolicy.prepare
    calls['foretell_names'] = []

    def prepare(policy, pack):
        prepared = original_prepare(policy, pack)
        original_predict = prepared.predict

        def predict(action_pack):
            result = original_predict(action_pack)
            kind = _field(action_pack['root'], 'type')['value']
            result['q'] = -0.5
            if kind == 'foretell':
                names = [node['value'] for node in _named_values(_expanded(action_pack), 'name')]
                calls['foretell_names'].append(names)
                result['q'] = 0.75 if 'Behold the Multiverse' in names else 0.25
            return result

        prepared.predict = predict
        return prepared

    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', prepare)
    return calls


def choose_pure_and_private(monkeypatch, state, seat, expected):
    calls = synthetic_foretell_preference(monkeypatch)
    binding = _binding(learned_policy)
    hidden = deepcopy(state)
    opponent = hidden.players[3-seat]
    hand_id, library_id = opponent.hand[0], opponent.library[0]
    opponent.hand[0], opponent.library[0] = library_id, hand_id
    hidden.cards[hand_id].move_to_zone(Zone.LIBRARY)
    hidden.cards[library_id].move_to_zone(Zone.HAND)
    opponent.hand.reverse()
    for player in hidden.players.values():
        player.library.reverse()
    hidden.log.append('PRIVATE_IDLE_RESERVATION_CANARY')
    assert hidden.players[3-seat].hand != state.players[3-seat].hand
    for root in (state, hidden):
        moves = RULES.legal_moves(deepcopy(root), seat)
        before = pickle.dumps((root, moves), protocol=5)
        rng = random.getstate()
        agent = AIAgent(difficulty='master', archetype='Control', learned_binding=binding)
        decision = agent.choose_action(root, moves, seat)
        assert decision.reasoning == 'Tactical-safeguarded Q ranking over a checked heuristic subset'
        assert decision.action == expected
        assert pickle.dumps((root, moves), protocol=5) == before
        assert random.getstate() == rng
        checked_action(root, RULES, seat, decision.action)
        assert pickle.dumps((root, moves), protocol=5) == before
    assert len(calls['states']) == 2 and calls['states'][0] == calls['states'][1]
    assert 'PRIVATE_IDLE_RESERVATION_CANARY' not in json.dumps(calls['states'])
    assert all(name not in json.dumps(calls['states']) for name in ('Lightning Bolt', 'Opt'))
    return calls


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stacked', [False, True])
def test_cosmos_charger_offturn_foretell_survives_without_affordable_answer(monkeypatch, seat, stacked):
    state, cid, move = scene(seat)
    add_foretell_card(state, 'Cosmos Charger', seat, Zone.BATTLEFIELD)
    counter = add_foretell_card(state, 'Saw It Coming', seat)
    state.active_player = 3-seat
    state.players[seat].mana_pool = {'C': 1}
    if stacked:
        spell = move('Llanowar Elves', 3-seat, Zone.HAND)
        state.priority_player = 3-seat
        state.players[3-seat].mana_pool = {'G': 1}
        state = checked_action(state, RULES, 3-seat,
                              complete_action({'type': 'cast_spell', 'card_id': spell}))
        state = checked_action(state, RULES, 3-seat, WAIT)
        assert len(state.stack) == 1 and state.priority_player == seat
    action = complete_action({'type': 'foretell', 'card_id': cid})
    agent = AIAgent(difficulty='master', archetype='Control')
    assert 'counter' in agent._spell_tags(state.cards[counter.id])
    assert not any(can_pay_with_pool_and_lands(
        state, seat, option.mana_cost, spell_types=state.cards[counter.id].types,
        source_card_id=counter.id) for option in collect_cost_options(state, seat, state.cards[counter.id]))
    moves = RULES.legal_moves(deepcopy(state), seat)
    assert next(m for m in moves if m['type'] == 'foretell' and m['card_id'] == cid)['mana_cost'] == '{1}'
    view, supplied = decision_view(state, seat, moves)
    assert foretell_policy.idle_foretell_action(agent, view, supplied, seat) is None
    choose_pure_and_private(monkeypatch, state, seat, action)
    after = checked_action(state, RULES, seat, action)
    assert after.cards[cid].zone == Zone.EXILE and after.cards[cid].exile_face_down
    assert after.players[seat].mana_pool['C'] == 0
    assert after.stack == state.stack and after.priority_player == seat
    assert can_look(after.cards[cid], seat) and not can_look(after.cards[cid], 3-seat)
    assert counter.id in after.players[seat].hand


@pytest.mark.parametrize('seat', [1, 2])
def test_model_may_prefer_other_affordable_foretell_than_idle_helper(monkeypatch, seat):
    state, cid, _ = scene(seat)
    doomskar = add_foretell_card(state, 'Doomskar', seat)
    state.players[seat].mana_pool = {'C': 2}
    action = complete_action({'type': 'foretell', 'card_id': cid})
    other = complete_action({'type': 'foretell', 'card_id': doomskar.id})
    moves = RULES.legal_moves(deepcopy(state), seat)
    view, supplied = decision_view(state, seat, moves)
    agent = AIAgent(difficulty='master', archetype='Control')
    assert foretell_policy.idle_foretell_action(agent, view, supplied, seat) == other
    for candidate in (action, other):
        offer = next(m for m in supplied if m['type'] == 'foretell' and m['card_id'] == candidate['card_id'])
        assert foretell_policy.idle_foretell_action(agent, view, [offer], seat) == candidate
        paid = checked_action(state, RULES, seat, candidate)
        assert paid.cards[candidate['card_id']].zone == Zone.EXILE
        assert paid.players[seat].mana_pool['C'] == 0
    calls = choose_pure_and_private(monkeypatch, state, seat, action)
    assert any('Behold the Multiverse' in names for names in calls['foretell_names'])
    assert any('Doomskar' in names for names in calls['foretell_names'])
    after = checked_action(state, RULES, seat, action)
    assert after.cards[cid].zone == Zone.EXILE and after.cards[cid].exile_face_down
    assert doomskar.id in after.players[seat].hand and after.players[seat].mana_pool['C'] == 0
