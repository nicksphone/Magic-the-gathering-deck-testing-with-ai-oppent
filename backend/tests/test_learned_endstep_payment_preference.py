"""Canonical paid-cost components with synthetic Q; no trained-model qualification."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from ai import learned_policy, learned_qv, pending_effects
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from tests.test_ai_final_spell_payment_value import RULES, move_for, position, settle
from tests.test_ai_joint_cast_resources import snapshot
from tests.test_linked_damage_targets import raw_card
from tests.test_live_learned_policy import _binding
from tests.test_training_reference_context import _expanded, _field


def offered(state, seat, selected):
    moves = RULES.legal_moves(deepcopy(state), seat)
    for move in moves:
        if move['type'] == 'cast_spell':
            move['cost_choice'] = {'id': 'base', 'sacrifice_card_ids': [selected]}
    return moves


def route(monkeypatch, state, seat, moves, *, q_cast=.9, q_pass=-.9, style='Control',
          proposals=None):
    """Only Q/shortlist are doubles; projection, admission and forecasts are real."""
    ai = AIAgent('master', style)
    cast = next(m for m in moves if m['type'] == 'cast_spell')
    if proposals is None:
        proposals = [complete_action(ai._materialize_action(state, cast, seat)),
                     {'type': 'pass_priority'}]
    assert all('cost_options' not in p for p in proposals)
    binding = _binding(learned_policy)
    calls = dict(scored=[], classes=[])
    original = pending_effects.unanswered_action_classification

    class Scores:
        def predict(self, pack):
            kind = _field(_expanded(pack), 'type')['value']
            calls['scored'].append(kind)
            return {'q': q_pass if kind == 'pass_priority' else q_cast, 'v': 0.0}

    def forecast(view, actor, action, **kwargs):
        answer = original(view, actor, action, **kwargs)
        calls['classes'].append((deepcopy(action), answer))
        return answer

    monkeypatch.setattr(AIAgent, '_strategic_top_actions', lambda *a: deepcopy(proposals))
    monkeypatch.setattr(learned_qv.QVPolicy, 'prepare', lambda *a: Scores())
    monkeypatch.setattr(pending_effects, 'unanswered_action_classification', forecast)
    before, old_moves = snapshot(state), deepcopy(moves)
    rng, state_rng = random.getstate(), state.rng.getstate()
    view, supplied = decision_view(state, seat, moves)
    assert all(is_unknown(view.cards[cid]) for cid in view.players[3-seat].hand)
    view_before = snapshot(view)
    action = learned_policy.choose_learned_action(binding, ai, view, supplied, seat,
        admit=lambda a: checked_action(state, RULES, seat, a))
    assert snapshot(state) == before and snapshot(view) == view_before and moves == old_moves
    assert random.getstate() == rng and state.rng.getstate() == state_rng
    assert calls['scored'] == ['cast_spell', 'pass_priority']
    return action, calls


@pytest.mark.parametrize('seat', [1, 2])
def test_expensive_final_cost_prefers_pass_despite_higher_synthetic_q(monkeypatch, seat):
    state, ids = position(seat, lands=2)
    moves = offered(state, seat, ids['Serra Angel'])
    action, calls = route(monkeypatch, state, seat, moves)
    assert action == {'type': 'pass_priority'}
    assert calls['classes'][0][1][0] is not True
    assert calls['classes'][0][0]['cost_choice']['sacrifice_card_ids'] == [ids['Serra Angel']]
    assert state.cards[ids['Serra Angel']].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('resource', ['Treasure', 'Ornithopter'])
def test_cheap_selected_resource_remains_castable_without_q_unit_mixing(monkeypatch, seat, resource):
    state, ids = position(seat, lands=2)
    if resource == 'Ornithopter':
        raw = json.loads((Path(__file__).parent/'fixtures/attached_characteristics/ornithopter.json').read_text())
        ids[resource] = raw_card(state, raw, seat, Zone.BATTLEFIELD).id
    moves = offered(state, seat, ids[resource])
    action, _ = route(monkeypatch, state, seat, moves, q_cast=1e-9, q_pass=0.)
    assert action['type'] == 'cast_spell'
    assert action['cost_choice'] == {'id': 'base', 'sacrifice_card_ids': [ids[resource]]}
    paid = checked_action(state, RULES, seat, action)
    assert paid.cards[ids[resource]].zone == (Zone.CEASED if resource == 'Treasure' else Zone.GRAVEYARD)
    assert paid.cards[ids['Serra Angel']].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_expensive_native_winning_payoff_is_not_vetoed(monkeypatch, seat):
    state, ids = position(seat, lands=2, artist=True)
    moves = offered(state, seat, ids['Serra Angel'])
    action, calls = route(monkeypatch, state, seat, moves)
    assert action['cost_choice']['sacrifice_card_ids'] == [ids['Serra Angel']]
    # The real actor-choice callback now settles the public targeted trigger.
    assert calls['classes'][0][1] == (True, None)
    assert settle(checked_action(state, RULES, seat, action)).winner == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_protocol_known_win_precedes_payment_preference_and_higher_pass_q(monkeypatch, seat):
    state, ids = position(seat, lands=2)
    moves = offered(state, seat, ids['Serra Angel'])
    # A terminal-class protocol double, not an alleged win in this quiet unit pose.
    monkeypatch.setattr(pending_effects, 'unanswered_action_classification',
        lambda view, actor, action, **kw: (True, None) if action['type'] == 'cast_spell' else (False, False))
    action, _ = route(monkeypatch, state, seat, moves, q_cast=-.9, q_pass=.9)
    assert action['type'] == 'cast_spell'
    assert action['cost_choice']['sacrifice_card_ids'] == [ids['Serra Angel']]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['own_main', 'stack', 'payoff'])
def test_nonconditional_or_unresolved_payoff_context_keeps_original_q(monkeypatch, seat, context):
    state, ids = position(seat, lands=2, spells=('Deadly Dispute', 'Opt') if context == 'stack'
                          else ('Deadly Dispute',), artist=context == 'payoff')
    if context == 'own_main':
        state.active_player = seat
        state.step = Step.POSTCOMBAT_MAIN
    elif context == 'stack':
        opt = complete_action(AIAgent()._materialize_action(state, move_for(state, seat, ids['Opt']), seat))
        state = checked_action(state, RULES, seat, opt)
        assert state.stack
    else:
        state.players[3-seat].life = 20
    moves = offered(state, seat, ids['Serra Angel'])
    action, _ = route(monkeypatch, state, seat, moves)
    assert action['type'] == 'cast_spell'
    assert action['cost_choice']['sacrifice_card_ids'] == [ids['Serra Angel']]


@pytest.mark.parametrize('seat', [1, 2])
def test_unpaid_cantrip_keeps_q_not_a_general_endstep_pass_rule(monkeypatch, seat):
    state, ids = position(seat, spells=('Opt',))
    moves = RULES.legal_moves(state, seat)
    action, _ = route(monkeypatch, state, seat, moves)
    assert action['type'] == 'cast_spell' and action['card_id'] == ids['Opt']


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'wrong_source', 'wrong_cost', 'wrong_face'])
def test_only_one_matching_public_option_can_supply_payment_metadata(kind):
    state, ids = position(1, lands=2)
    public = move_for(state, 1, ids['Deadly Dispute'])
    action = complete_action(AIAgent()._materialize_action(state,
        {**public, 'cost_choice': {'id': 'base', 'sacrifice_card_ids': [ids['Serra Angel']]}}, 1))
    moves = [deepcopy(public)]
    if kind == 'missing':
        moves[0].pop('cost_options')
    elif kind == 'duplicate':
        moves.append(deepcopy(public))
    elif kind == 'wrong_source':
        moves[0]['card_id'] = ids['Serra Angel']
    elif kind == 'wrong_cost':
        moves[0]['cost_options'][0]['id'] = 'unoffered'
    else:
        moves[0]['selected_face_index'] = 1
    assert learned_policy._public_cost_option(action, moves) is None


def test_public_option_is_retained_even_when_canonical_action_has_no_display_fields():
    state, ids = position(1, lands=2)
    public = move_for(state, 1, ids['Deadly Dispute'])
    action = complete_action(AIAgent()._materialize_action(state, public, 1))
    assert 'cost_options' not in action
    before = deepcopy(public)
    assert learned_policy._public_cost_option(action, [public]) == public['cost_options'][0]
    assert public == before


@pytest.mark.parametrize('action', [None, [], {}, {'type': 'cast_spell', 'cost_choice': 'invalid'}])
def test_metadata_retention_does_not_bypass_complete_action_validation(action):
    assert learned_policy._public_cost_option(action, []) is None


@pytest.mark.parametrize('option', [None, {}, {'id': 'base'}])
def test_unknown_payment_metadata_abstains_without_infinite_or_zero_pricing(monkeypatch, option):
    state, ids = position(1, lands=2)
    moves = offered(state, 1, ids['Serra Angel'])
    action = complete_action(AIAgent()._materialize_action(state,
        next(m for m in moves if m['type'] == 'cast_spell'), 1))
    view, _ = decision_view(state, 1, moves)

    def forbidden(*args, **kwargs):
        pytest.fail('Unknown public payment must not be priced')

    monkeypatch.setattr(AIAgent, '_spell_payment_loss', forbidden)
    assert learned_policy._prefer_pass_to_paid_draw(AIAgent('master', 'Control'), view, action, 1, option) is False


def test_old_engine_contract_is_rejected_without_reading_a_trained_checkpoint():
    from tests.test_learned_qv import blank_checkpoint
    payload = blank_checkpoint(learned_qv)
    payload['contract'] = learned_policy._current_contract()
    payload['contract']['engine_hash'] = '80a1250f842d91cf9669971c8307bc324757420b1a08e3af9d817cfe4726b732'
    payload['provenance']['updates'] = payload['provenance']['samples'] = 1
    with pytest.raises(ValueError):
        learned_policy.bind_live_policy(json.dumps(payload).encode())


@pytest.mark.parametrize('container', [None, {}, 'base', [None], ['base'],
                                     [{'id': None}], [{'id': 1}], [{'id': True}], [{'id': ''}]])
def test_nullable_or_malformed_public_cost_options_abstain(container):
    action = {'type': 'cast_spell', 'card_id': 'spell', 'cost_choice': {'id': 'base'}}
    moves = [{'type': 'cast_spell', 'card_id': 'spell', 'cost_options': container}]
    assert learned_policy._public_cost_option(action, moves) is None


@pytest.mark.parametrize('selected', [None, 1, True, ''])
def test_cost_choice_and_offered_ids_are_closed_nonempty_strings(selected):
    action = {'type': 'cast_spell', 'card_id': 'spell', 'cost_choice': {'id': selected}}
    moves = [{'type': 'cast_spell', 'card_id': 'spell', 'cost_options': [{'id': selected}]}]
    assert learned_policy._public_cost_option(action, moves) is None


def test_complex_canonical_cast_face_abstains_before_reading_physical_front(monkeypatch):
    import rules_engine.type_effects as types
    state, _ = position(1, lands=2)
    rows = json.loads((Path(__file__).parent/'fixtures/modal_spell_faces.json').read_text())
    raw = rows['Brazen Borrower // Petty Theft']
    card = raw_card(state, raw, 1, Zone.HAND)
    assert card.layout == 'adventure' and 'Instant' in card.card_faces[1]['type_line']
    action = {'type': 'cast_spell', 'card_id': card.id, 'selected_face_index': 1,
              'cost_choice': {'id': 'base'}}
    view, _ = decision_view(state, 1, RULES.legal_moves(state, 1))

    def forbidden(*args, **kwargs):
        pytest.fail('Complex selected face must abstain before classifying the physical front')

    monkeypatch.setattr(types, 'effective_types', forbidden)
    assert learned_policy._prefer_pass_to_paid_draw(AIAgent('master', 'Control'), view, action, 1,
        {'id': 'base', 'pay_life': 0, 'discard_cards': 0, 'sacrifice_creatures': 0}) is False


def test_opaque_battlefield_protocol_abstains_without_assuming_no_payoff(monkeypatch):
    state, ids = position(1, lands=2)
    moves = offered(state, 1, ids['Serra Angel'])
    public = next(m for m in moves if m['type'] == 'cast_spell')
    action = complete_action(AIAgent()._materialize_action(state, public, 1))
    view, _ = decision_view(state, 1, moves)
    # An explicit opacity protocol marker, not a fabricated native payoff or card definition.
    view.cards[view.players[2].battlefield[0]].ai_unknown = True

    def forbidden(*args, **kwargs):
        pytest.fail('Opaque public context cannot establish the conditional economic preference')

    monkeypatch.setattr(AIAgent, '_spell_payment_loss', forbidden)
    assert learned_policy._prefer_pass_to_paid_draw(AIAgent('master', 'Control'), view, action, 1,
        public['cost_options'][0]) is False
