"""Read-only reconstruction helpers for a sealed synthetic natural-game receipt."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from ai.information import decision_view, is_unknown
from ai import pending_effects
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add, fixture


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def receipts():
    path = Path(os.environ['MTG_HEAT_WITNESS']).resolve()
    assert path.name == 'sealed-self-removal-witness.json'
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == 'c2eac237fe12c4783e65ccf692c239591378e3d6ad893fcbec31cecf8af9f653'
    return json.loads(data)


def witness():
    return next(row for row in receipts() if row['event'] == 'decision' and row['tick'] == 303)


def agent(row):
    ai = AIAgent(**row['config'])
    from scripts.natural_ai_consumer_audit import tuple_tree
    ai._main_pass_signature_counts = {tuple_tree(key): value for key, value in row['agent_memory']}
    return ai


def exact_state():
    row = witness()
    return row, deserialize_match_snapshot(row['snapshot'])


def private_cards(state, seat):
    return {'own_library_opaque': all(is_unknown(state.cards[cid]) for cid in state.players[seat].library),
            'opponent_library_opaque': all(is_unknown(state.cards[cid]) for cid in state.players[3-seat].library),
            'opponent_hand_opaque': all(is_unknown(state.cards[cid]) for cid in state.players[3-seat].hand),
            'opponent_deck_absent': 3-seat not in state.starting_decks}


def replay_receipt():
    row, state = exact_state()
    before = canonical(serialize_match_snapshot(state))
    ai = agent(row)
    with patch.object(pending_effects, 'friendly_destruction_profit',
                      wraps=pending_effects.friendly_destruction_profit) as profit:
        decision = ai.choose_action(state, row['legal_moves'], row['pid'])
        calls = profit.call_count
    assert canonical(serialize_match_snapshot(state)) == before
    return row, state, decision, calls


def rank_diagnostic():
    row, state = exact_state()
    view, legal = decision_view(state, row['pid'], row['legal_moves'])
    before = canonical(serialize_match_snapshot(view))
    ai = agent(row)
    scores = []
    forced_scores = []

    def profile(frame, event, result):
        if (event == 'return' and frame.f_code.co_qualname.endswith('_rank_moves_query.<locals>.score')
                and frame.f_locals.get('state') is view):
            scores.append({'move': frame.f_locals['move'], 'score': result})
        if (event == 'return' and frame.f_code.co_qualname.endswith('AIAgent._forced_stack_interaction')
                and frame.f_locals.get('state') is view and frame.f_locals.get('best')):
            forced_scores.append(frame.f_locals['best'][0])

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        ranked = ai._rank_moves(view, legal, row['pid'])
        forced = ai._forced_stack_interaction(view, legal, row['pid'])
    finally:
        sys.setprofile(previous)
    assert canonical(serialize_match_snapshot(view)) == before
    heat = next(move for move in legal if move.get('card_id') == row['action']['card_id'])
    return {'ranked_moves': ranked, 'actual_root_scores': scores,
            'privacy': private_cards(view, row['pid']),
            'stack_threat_score': ai._best_stack_threat_score(view, row['pid']),
            'friendly_burn_filter': ai._burn_has_only_friendly_targets(view, heat, row['pid']),
            'forced_stack_action': forced, 'actual_forced_stack_scores': forced_scores,
            'materialized_heat': ai._materialize_action(view, heat, row['pid']),
            'friendly_profit_raw': pending_effects.friendly_destruction_profit(state, row['pid'], row['action']),
            'friendly_profit_private': pending_effects.friendly_destruction_profit(view, row['pid'], row['action'])}


def canonical_control(seat, window, payoff=None, opponent_target=False):
    """Explicit canonical fixture, separate from and never rewriting the natural receipt."""
    row, original = exact_state()
    state = fixture()
    state.priority_player = state.active_player = seat
    for player in state.players.values():
        player.mana_pool = {'B': 10, 'U': 10, 'R': 10, 'C': 10}
        player.lands_played_this_turn = 1
    cards = {}
    for name in ('self_removal.json', 'recurring_engines.json'):
        cards.update({raw['name']: raw for raw in json.loads(
            (Path(__file__).parent / 'fixtures' / name).read_text())})

    def clone(cid, owner, zone):
        card = deepcopy(original.cards[cid])
        card.id = state.allocate_object_id()
        card.owner = card.controller = owner
        card.zone = zone
        state.cards[card.id] = card
        getattr(state.players[owner], zone.value).append(card.id)
        return card

    heat = clone(row['action']['card_id'], seat, Zone.HAND)
    if payoff == 'Blood Artist':
        victim = add(state, payoff, seat, cards=cards)
    else:
        victim = clone(row['action']['targets']['target_card_id'], 3-seat if opponent_target else seat,
                       Zone.BATTLEFIELD)
        if payoff:
            add(state, payoff, seat, cards=cards)
    if payoff:
        state.players[3-seat].life = 1
    if window == 'response':
        state.active_player = state.priority_player = 3-seat
        state.step = Step.END_STEP
        deluge = clone(original.stack[0].source_card_id, 3-seat, Zone.HAND)
        state = checked_action(state, RulesEngine(), 3-seat,
                               {'type': 'cast_spell', 'card_id': deluge.id, 'targets': {}})
        state = checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    return state, heat.id, victim.id


def advance_until(state, condition, ai):
    rules = RulesEngine()
    while not condition(state):
        legal = rules.legal_moves(state, state.priority_player)
        assert legal, 'Fixture continuation has no legal move'
        pending = state.pending_mechanic_choice or state.pending_trigger_order or state.pending_replacement_choice
        if pending:
            action = ai.choose_action(state, legal, state.priority_player).action
        else:
            assert state.stack, 'Expected fixture stack to resolve before continuing phases'
            action = {'type': 'pass_priority'}
        state = checked_action(state, rules, state.priority_player, action)
    return state


def removal_delta(state, action, victim):
    seat = state.cards[action['card_id']].controller
    before = evaluate_board(state, seat)
    candidate = checked_action(state, RulesEngine(), seat, action)
    candidate = advance_until(candidate, lambda s: s.cards[victim].zone != Zone.BATTLEFIELD,
                              AIAgent(archetype='Tempo', opponent_archetype='Control', difficulty='master'))
    return candidate, evaluate_board(candidate, seat) - before
