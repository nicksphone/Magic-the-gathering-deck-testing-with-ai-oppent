"""Canonical public boards plus explicitly marked grammar boundaries, not decks."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.declaration_policy import finalize_declaration
from game_state.state import Step
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.combat_constraints import combat_clause_coverage
from rules_engine.combat_payments import attack_payment_view, attack_payment_state, parse_attack_tax
from rules_engine.combat_requirements import best_required_blocks, block_requirement_score, target_block_requirements
from rules_engine.engine import RulesEngine
from tests.test_combat_payments_requirements import add, fixture, zero_mana, attack_step
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_declaration_limits import add as limit_card
from tests.test_conditional_combat import lose
from tests.test_api_input_contracts import game, persist, rejected

CARDS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/combat_minimums.json').read_text())}


def board(seat=1, count=2, name='Gorm the Great'):
    state = fixture()
    attacker = raw_add(state, name, seat, cards=CARDS)
    attacker.summoning_sick = False
    guards = [add(state, 'Llanowar Elves', 3-seat) for _ in range(count)]
    state.active_player, state.priority_player = seat, 3-seat
    state.step, state.attackers = Step.DECLARE_BLOCKERS, [attacker.id]
    return state, attacker, guards


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count,score', [(0, 0), (1, 1), (2, 2), (3, 2), (101, 2)])
def test_minimum_requirements_saturate_and_do_not_become_menace(seat, count, score):
    state, attacker, guards = board(seat, count)
    before = serialize_match_snapshot(state)
    rows = target_block_requirements(state)
    assert [row['minimum'] for row in rows] == [1, 2]
    optimum = best_required_blocks(state)
    assert block_requirement_score(state, optimum) == score
    assert sum(len(ids) for ids in optimum.values()) == min(count, 2)
    assert block_requirement_score(state, {attacker.id: [c.id for c in guards]}) == score
    if count:
        with pytest.raises(ActionRejected, match='requirements'):
            checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {}})
    if count >= 2:
        with pytest.raises(ActionRejected, match='requirements'):
            checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker.id: [guards[0].id]}})
    chosen = guards[:min(count, 2)]
    result = checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker.id: [c.id for c in chosen]} if chosen else {}})
    assert block_requirement_score(result, result.blocks) == score
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('name', ['Gorm the Great', 'Maarika, Brutal Gladiator'])
def test_caps_and_suppression_leave_maximum_achievable_requirements(name):
    state, attacker, guards = board(name=name)
    limit_card(state, 'Silent Arbiter')
    blocks = {attacker.id: [guards[0].id]}
    assert block_requirement_score(state, best_required_blocks(state)) == 1
    checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': blocks})
    assert combat_clause_coverage(CARDS[name]['oracle_text'], name) == []
    lose(state, attacker)
    assert target_block_requirements(state) == []
    checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {}})


def test_competing_group_and_pair_requirements_allow_all_maximum_ties():
    state, gorm, guards = board(count=2)
    other = raw_add(state, 'Maarika, Brutal Gladiator', cards=CARDS)
    state.attackers.append(other.id)
    # Two blockers on Gorm satisfy two requirements, as does one on each.
    for blocks in ({gorm.id: [c.id for c in guards]}, {gorm.id: [guards[0].id], other.id: [guards[1].id]}):
        assert block_requirement_score(state, blocks) == 2
        checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': blocks})
    lure = add(state, 'Lure')
    lure.attached_to = other.id
    optimum = best_required_blocks(state)
    assert block_requirement_score(state, optimum) == 3
    assert len(optimum[other.id]) >= 1


def test_wide_mixed_requirements_use_a_capacity_aware_saturated_bound():
    state, gorm, guards = board(count=101)
    unicorn = add(state, 'Prized Unicorn')
    state.attackers.append(unicorn.id)
    solution = best_required_blocks(state)
    # Gorm's two thresholds can score at most one per blocker, just like this
    # single Lure source. The bound must not pretend they stack on each pair.
    assert block_requirement_score(state, solution) == 101
    assert len(solution[unicorn.id]) == 101


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choices,white,life', [(['W', 'W'], 2, 20), (['W', 'P'], 1, 18), (['P', 'P'], 0, 16)])
def test_phyrexian_attacks_use_deliberate_branch_choices(seat, choices, white, life):
    state = fixture()
    zero_mana(state)
    add(state, "Norn's Annex", 3-seat)
    attackers = [add(state, 'Llanowar Elves', seat) for _ in range(2)]
    attack_step(state, seat)
    state.players[seat].mana_pool['W'] = white
    before = serialize_match_snapshot(state)
    action = {'type': 'attack', 'attackers': [c.id for c in attackers]}
    assert attack_payment_view(state, action['attackers'])['mana_cost'] == '{W/P}{W/P}'
    with pytest.raises(ActionRejected, match='explicitly'):
        checked_action(state, RulesEngine(), seat, action)
    result = checked_action(state, RulesEngine(), seat, {**action, 'hybrid_choices': choices})
    assert result.players[seat].life == life
    assert result.players[seat].mana_pool['W'] == 0
    assert result.attackers == action['attackers']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('choices', [[], ['G'], ['P', 'P'], ['W']])
def test_bad_or_unaffordable_branch_never_mutates(choices):
    state = fixture()
    zero_mana(state)
    add(state, "Norn's Annex", 2)
    attacker = add(state, 'Llanowar Elves')
    attack_step(state, 1)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': [attacker.id], 'hybrid_choices': choices})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
@pytest.mark.parametrize('white,branch', [(1, 'W'), (0, 'P')])
def test_ai_announces_shared_payment_and_fulfills_group_requirement(difficulty, white, branch):
    state, attacker, guards = board()
    zero_mana(state)
    add(state, "Norn's Annex", 2)
    state.players[1].mana_pool['W'] = white
    attack_step(state, 1)
    before = serialize_match_snapshot(state)
    action = finalize_declaration(state, {'type': 'attack', 'attackers': [attacker.id]})
    assert action['hybrid_choices'] == [branch]
    result = checked_action(state, RulesEngine(), 1, action)
    assert serialize_match_snapshot(state) == before
    result.step, result.priority_player = Step.DECLARE_BLOCKERS, 2
    result.blockers_declared = False
    decision = AIAgent(difficulty).choose_action(result, RulesEngine().legal_moves(result, 2), 2)
    final = checked_action(result, RulesEngine(), 2, decision.action)
    assert block_requirement_score(final, final.blocks) == 2


@pytest.mark.parametrize('cost,choices,pool,expected', [
    ('{U}', None, {'U': 1}, True), ('{U}', None, {'G': 1}, False),
    ('{C}', None, {'U': 1}, False), ('{C}', None, {'C': 1}, True),
    ('{U/R}', ['R'], {'R': 1}, True), ('{2/W}', ['2'], {'G': 2}, True),
    ('{2/W}', ['W'], {'G': 2}, False), ('{UB}', None, {}, False),
])
def test_mana_grammar_boundaries_reuse_normal_payment_legality(cost, choices, pool, expected):
    state = fixture()
    zero_mana(state)
    tax = add(state, 'Propaganda', 2)
    # Grammar fixture only: no invented card/deck enters the corpus.
    tax.oracle_text = f"Creatures can't attack you unless their controller pays {cost} for each of those creatures."
    attacker = add(state, 'Llanowar Elves')
    attack_step(state, 1)
    state.players[1].mana_pool.update(pool)
    parsed = parse_attack_tax(tax.oracle_text.lower().strip('.'))
    if cost == '{UB}':
        assert parsed is None
        assert combat_clause_coverage(tax.oracle_text, tax.name)
    else:
        assert (attack_payment_state(state, [attacker.id], hybrid_choices=choices) is not None) == expected


def test_zero_cost_and_phyrexian_payments_are_optional_even_for_required_attacks():
    for cost in ('{0}', '{W/P}'):
        state = fixture()
        tax = add(state, 'Propaganda', 2)
        tax.oracle_text = f"Creatures can't attack you unless their controller pays {cost} for each of those creatures."
        attacker = limit_card(state, 'Juggernaut')
        attack_step(state, 1)
        assert attack_payment_view(state, [attacker.id])['payments']
        result = checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': []})
        assert result.attackers == []


def test_ai_does_not_pay_its_last_life_for_an_attack():
    state = fixture()
    zero_mana(state)
    add(state, "Norn's Annex", 2)
    attacker = add(state, 'Llanowar Elves')
    attack_step(state, 1)
    state.players[1].life = 2
    before = serialize_match_snapshot(state)
    assert finalize_declaration(state, {'type': 'attack', 'attackers': [attacker.id]})['attackers'] == []
    state.players[1].life = 1
    with pytest.raises(ActionRejected, match='attack costs'):
        checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': [attacker.id], 'hybrid_choices': ['P']})
    state.players[1].life = 2
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('count', [1, 2, 3, 4])
@pytest.mark.parametrize('extra_capacity', [False, True])
def test_exact_solver_matches_small_independent_assignment_enumeration(count, extra_capacity):
    from itertools import product
    state, gorm, guards = board(count=count)
    unicorn = add(state, 'Prized Unicorn')
    state.attackers.append(unicorn.id)
    if extra_capacity:
        # A grammar boundary, not a new card: capacity and requirements compose.
        guards[0].oracle_text += '\nThis creature can block an additional creature each combat.'
    choices = [(), (gorm.id,), (unicorn.id,)]
    guard_options = [choices + ([(gorm.id, unicorn.id)] if extra_capacity and index == 0 else []) for index in range(count)]
    scores = []
    for assignment in product(*guard_options):
        groups = {aid: [guard.id for guard, aids in zip(guards, assignment) if aid in aids] for aid in state.attackers}
        # Independent definition: one Gorm requirement per threshold, one Lure
        # requirement per assigned pair; do not call the engine scorer here.
        scores.append(int(len(groups[gorm.id]) >= 1) + int(len(groups[gorm.id]) >= 2) + len(groups[unicorn.id]))
    optimum = best_required_blocks(state)
    assert block_requirement_score(state, optimum) == max(scores)


@pytest.mark.parametrize('text', [
    'This creature must be blocked by a red creature if able.',
    'All red creatures able to block this creature do so.',
    'This creature must be blocked if able, and an unknown extra requirement.',
])
def test_qualified_or_partial_unknown_requirement_stays_explicitly_unsupported(text):
    assert combat_clause_coverage(text, 'Grammar Boundary')


@pytest.mark.parametrize('seat', [1, 2])
def test_http_rejection_and_sqlite_resume_of_both_families(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, attacker, guards = board(seat)
    state.id = match.state.id
    zero_mana(state)
    add(state, "Norn's Annex", 3-seat)
    attack_step(state, seat)
    match.state = state
    persist(match)
    action = {'type': 'attack', 'attackers': [attacker.id]}
    rejected(client, match, action, seat)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': {**action, 'hybrid_choices': ['P']}})
    assert response.status_code == 200, response.text
    assert match.state.players[seat].life == 18
    match_id = state.id
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    match = main.ACTIVE_MATCHES[match_id]
    assert match.state.players[seat].life == 18 and match.state.attackers == [attacker.id]
    match.state.step, match.state.priority_player = Step.DECLARE_BLOCKERS, 3-seat
    persist(match)
    rejected(client, match, {'type': 'block', 'blocks': {attacker.id: [guards[0].id]}}, 3-seat)
    action = {'type': 'block', 'blocks': {attacker.id: [c.id for c in guards]}}
    response = client.post(f'/matches/{match_id}/action', json={'player_id': 3-seat, 'action': action})
    assert response.status_code == 200, response.text
    assert block_requirement_score(match.state, match.state.blocks) == 2
