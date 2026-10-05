"""Canonical paid selection through the installed production AI consumer."""
import json
from math import comb
from pathlib import Path
import pickle
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from ai.pending_effects import planning_copy, settled_public_position
from ai.selection_activation import (selection_activation_plan, selection_activation_score,
                                     pending_selection_expectation)
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.card_faces import apply_transform_face
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities, infer_effect_from_oracle


FIXTURES = Path(__file__).parent / 'fixtures'
STYLES = ['Tempo', 'Tribal', 'Midrange', 'Control']
RULES = RulesEngine()


def row(slug, quantity):
    if slug == 'lightning-bolt':
        raw = json.loads((FIXTURES.parents[1] / 'card_data/builtin_oracle_seed.json').read_text())['cards']['Lightning Bolt']
        return {**raw, 'card_name': raw['name'], 'quantity': quantity}
    folder = 'selection_activation_policy' if slug in {'duskwatch-recruiter', 'search-for-azcanta'} else 'activated_top_selection'
    if slug == 'counterspell':
        folder = 'opaque_selection'
    raw = json.loads((FIXTURES / folder / f'{slug}.json').read_text())
    return {**raw, 'card_name': raw['name'], 'quantity': quantity}


def relocate(state, name, seat, zone):
    card = next(c for c in state.cards.values() if c.owner == seat and c.name == name and c.zone == Zone.LIBRARY)
    state.players[seat].library.remove(card.id)
    card.move_to_zone(zone)
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def position(seat=1, scenario='favorable'):
    eligible = scenario != 'ineligible'
    own = [row('recruitment-officer', 1), row('savannah-lions', 24 if eligible else 0),
           row('plains', 24), row('serra-angel', 8), row('counterspell', 1), row('opt', 4)]
    opp = [row('plains', 24), row('serra-angel', 8), row('lightning-bolt', 1)]
    state = MatchFactory.from_decks(own if seat == 1 else opp, opp if seat == 1 else own, seed=321)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 10
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
    source = relocate(state, 'Recruitment Officer', seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'W': 1, 'U': 2, 'C': 1}
    if scenario != 'terminal':
        relocate(state, 'Lightning Bolt', 3-seat, Zone.HAND)
    if scenario == 'mana_poor':
        state.players[seat].mana_pool = {'W': 1, 'C': 2}
    if scenario in {'reservation', 'terminal'}:
        relocate(state, 'Counterspell', seat, Zone.HAND)
    if scenario == 'deploy':
        relocate(state, 'Serra Angel', seat, Zone.HAND)
        state.players[seat].mana_pool = {'W': 2, 'U': 2, 'C': 3}
    if scenario == 'terminal':
        state.active_player = 3-seat
        state.players[seat].life = 1
        threat = relocate(state, 'Lightning Bolt', 3-seat, Zone.HAND)
        state.priority_player = 3-seat
        state.players[3-seat].mana_pool = {'R': 1}
        RULES.take_action(state, 3-seat, {'type': 'cast_spell', 'card_id': threat.id,
                                       'targets': {'target_player': seat}}, reject_invalid=True)
        state.priority_player = seat
    return state, source


def policy_agent(style, difficulty='master'):
    return AIAgent(difficulty, style, 'Control')


@pytest.mark.parametrize('seat', [1, 2])
def test_fractional_prior_does_not_project_guaranteed_filtered_card(seat):
    state, source = position(seat)
    before = pickle.dumps(state, 5)
    view, moves = decision_view(state, seat, RULES.legal_moves(state, seat))
    move = next(m for m in moves if m['type'] == 'activate_ability')
    plan = selection_activation_plan(view, move, seat)
    assert plan['expected_hand_cards'] == pytest.approx(1-comb(61-24, 4)/comb(61, 4))
    assert 0 < plan['expected_hand_cards'] < 1
    branch = planning_copy(view)
    RULES.take_action(branch, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}, reject_invalid=True)
    assert pending_selection_expectation(branch, seat) == plan['expected_hand_cards']
    assert settled_public_position(branch, seat, opaque_draw_counts=True) is None
    assert not branch.players[seat].hand
    restored = deserialize_match_snapshot(serialize_match_snapshot(branch))
    restored, _ = decision_view(restored, seat, [])
    assert pending_selection_expectation(restored, seat) == plan['expected_hand_cards']
    assert pickle.dumps(state, 5) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('scenario', ['favorable', 'ineligible', 'mana_poor', 'deploy', 'reservation', 'terminal'])
@pytest.mark.parametrize('difficulty', ['master', 'strong'])
def test_actual_production_decisions_are_legal_pure_and_hidden_order_invariant(seat, style, scenario, difficulty):
    state, source = position(seat, scenario)
    before = pickle.dumps(state, 5)
    ai = policy_agent(style, difficulty)
    decision = ai.choose_action(state, RULES.legal_moves(state, seat), seat)
    permuted = planning_copy(state)
    for player in permuted.players.values():
        player.library.reverse()
    # Swap only a hidden opponent card's canonical metadata, not public facts.
    hidden_row = row('opt', 1)
    for cid in permuted.players[3-seat].hand:
        hidden = permuted.cards[cid]
        hidden.name = hidden_row['name']
        hidden.oracle_text = hidden_row['oracle_text']
        hidden.mana_cost = hidden_row['mana_cost']
        hidden.colors = hidden_row['colors']
    permuted_before = pickle.dumps(permuted, 5)
    repeated = policy_agent(style, difficulty).choose_action(permuted, RULES.legal_moves(permuted, seat), seat)
    assert repeated.action == decision.action
    assert pickle.dumps(permuted, 5) == permuted_before
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    restored_before = pickle.dumps(restored, 5)
    replayed = policy_agent(style, difficulty).choose_action(restored, RULES.legal_moves(restored, seat), seat)
    assert replayed.action == decision.action
    assert pickle.dumps(restored, 5) == restored_before
    accepted = planning_copy(state)
    RULES.take_action(accepted, seat, decision.action, reject_invalid=True)
    assert pickle.dumps(state, 5) == before
    if scenario == 'favorable':
        assert decision.action['type'] == 'activate_ability'
    if scenario in {'ineligible', 'reservation'}:
        assert decision.action['type'] == 'pass_priority'
    if scenario == 'mana_poor':
        assert decision.action['type'] != 'activate_ability'
    if scenario == 'deploy':
        assert decision.action['type'] == 'cast_spell'
    if scenario == 'terminal':
        assert decision.action['type'] == 'cast_spell' and state.cards[decision.action['card_id']].name == 'Counterspell'


@pytest.mark.parametrize('slug,face', [('duskwatch-recruiter', 0), ('search-for-azcanta', 1)])
def test_canonical_other_requested_sources_are_explicitly_engine_unsupported(slug, face):
    state = MatchFactory.from_decks([row(slug, 8)], [row('plains', 24)], seed=17)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.priority_player = state.active_player = 1
    state.players[1].mana_pool = {'G': 3, 'U': 3, 'C': 10}
    source = next(c for c in state.cards.values() if c.owner == 1)
    getattr(state.players[1], source.zone.value).remove(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    state.players[1].battlefield.append(source.id)
    apply_transform_face(source, face)
    ability = extract_activated_abilities(source)[0]
    proxy = SimpleNamespace(id=source.id, name=source.name, oracle_text=ability['text'])
    assert infer_effect_from_oracle(state, proxy, 1)[0] == 'noop'
    assert not any(m['type'] == 'activate_ability' for m in RULES.legal_moves(state, 1))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['missing_inventory', 'inconsistent_inventory', 'known_library', 'wrong_perspective'])
def test_unavailable_prior_is_explicit_not_fabricated_eligibility(seat, case):
    state, _ = position(seat)
    view, moves = decision_view(state, seat, RULES.legal_moves(state, seat))
    move = next(m for m in moves if m['type'] == 'activate_ability')
    if case == 'missing_inventory':
        view.starting_decks = {}
    if case == 'inconsistent_inventory':
        view.starting_decks[seat][0]['quantity'] += 1
    if case == 'known_library':
        cid = view.players[seat].library[-1]
        view.cards[cid] = state.cards[cid]
    if case == 'wrong_perspective':
        assert selection_activation_plan(view, move, 3-seat) is None
        return
    before = pickle.dumps(view, 5)
    plan = selection_activation_plan(view, move, seat)
    assert plan['expected_hand_cards'] is None
    assert plan['eligible_population'] is None
    assert selection_activation_score(plan, hand_value=1.25, interaction_reservation=6) < 0
    assert pickle.dumps(view, 5) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_reservation_tracks_real_remaining_payment_and_end_step(seat):
    state, _ = position(seat, 'reservation')
    for pool, step, loses in [({'W': 1, 'U': 2, 'C': 1}, Step.PRECOMBAT_MAIN, True),
                              ({'W': 1, 'U': 2, 'C': 3}, Step.PRECOMBAT_MAIN, False),
                              ({'W': 1, 'U': 2, 'C': 1}, Step.END_STEP, False)]:
        state.players[seat].mana_pool = pool
        state.step = step
        view, moves = decision_view(state, seat, RULES.legal_moves(state, seat))
        move = next(m for m in moves if m['type'] == 'activate_ability')
        assert selection_activation_plan(view, move, seat)['loses_known_interaction'] is loses


@pytest.mark.parametrize('seat', [1, 2])
def test_partial_clause_and_payload_expansions_are_not_admitted(seat):
    state, source = position(seat)
    view, moves = decision_view(state, seat, RULES.legal_moves(state, seat))
    move = next(m for m in moves if m['type'] == 'activate_ability')
    branch = planning_copy(view)
    RULES.take_action(branch, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}, reject_invalid=True)
    branch.stack[0].payload['mv_max'] = 4
    assert pending_selection_expectation(branch, seat) is None
    view.cards[source.id].oracle_text += ' ' + row('lightning-bolt', 1)['oracle_text']
    assert selection_activation_plan(view, move, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reservation', [False, True])
def test_unknown_inventory_is_not_zero_hits_but_preserves_known_interaction(seat, reservation):
    state, source = position(seat, 'reservation' if reservation else 'favorable')
    state.starting_decks = {}
    before = pickle.dumps(state, 5)
    decision = policy_agent('Midrange', 'strong').choose_action(state, RULES.legal_moves(state, seat), seat)
    assert pickle.dumps(state, 5) == before
    if reservation:
        assert decision.action['type'] == 'pass_priority'
    else:
        assert decision.action['type'] == 'activate_ability'
        assert decision.action['card_id'] == source.id


@pytest.mark.parametrize('seat', [1, 2])
def test_multiple_unsettled_acquisitions_and_terminal_state_have_no_single_prior(seat):
    state, source = position(seat)
    view, moves = decision_view(state, seat, RULES.legal_moves(state, seat))
    move = next(m for m in moves if m['type'] == 'activate_ability')
    branch = planning_copy(view)
    RULES.take_action(branch, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}, reject_invalid=True)
    assert pending_selection_expectation(branch, seat) is not None
    branch.stack.append(branch.stack[0])
    assert pending_selection_expectation(branch, seat) is None
    view.winner = 3-seat
    assert selection_activation_plan(view, move, seat) is None
    assert pending_selection_expectation(view, seat) is None
