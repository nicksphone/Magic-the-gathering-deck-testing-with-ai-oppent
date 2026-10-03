"""Canonical combat scenarios and independent checked-action enumeration."""
import json
from itertools import combinations, product
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.block_search import block_intents
from ai.declaration_policy import finalize_declaration
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_combat_domain_temporary_costs import fixture, add, activate, zero_mana, attack_step
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_declaration_limits import add as limit_card
from tests.test_api_input_contracts import game, persist, snapshot

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/combat_ability_provenance.json').read_text())}


def board(seat=1, count=2, guard='Wall of Glare', life=2):
    state = fixture()
    zero_mana(state)
    attackers = [add(state, 'Grizzly Bears', seat).id for _ in range(count)]
    blocker = raw_add(state, guard, 3-seat, cards=ROWS) if guard in ROWS else add(state, guard, 3-seat)
    state.players[3-seat].life = life
    attack_step(state, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': attackers})
    state.step = Step.DECLARE_BLOCKERS
    state.priority_player = 3-seat
    state.passed_priority = set()
    return state, attackers, blocker.id


def key(groups):
    return tuple(sorted((aid, tuple(sorted(ids))) for aid, ids in groups.items() if ids))


def independent_checked_intents(state, attackers, blockers):
    # Generate every pair subset; the engine, not this reference, checks capacity,
    # minimum groups, alone restrictions, requirements and payment affordability.
    choices = [[subset for count in range(len(attackers)+1) for subset in combinations(attackers, count)] for _ in blockers]
    accepted = set()
    for options in product(*choices):
        groups = {}
        for bid, targets in zip(blockers, options):
            for aid in targets:
                groups.setdefault(aid, []).append(bid)
        try:
            checked_action(state, RulesEngine(), 3-state.active_player, {'type': 'block', 'blocks': groups})
        except ActionRejected:
            continue
        accepted.add(key(groups))
    return accepted


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('guard', ['Wall of Glare', 'Mogg Flunkies'])
@pytest.mark.parametrize('tax', [None, 0, 1])
def test_intents_match_independent_checked_actions_for_capacity_requirements_and_costs(seat, guard, tax):
    state, attackers, bid = board(seat, guard=guard)
    elf = add(state, 'Llanowar Elves', 3-seat)
    # Canonical Prized Unicorn adds a targeted maximum-required-block test.
    unicorn = add(state, 'Prized Unicorn', seat)
    state.attackers[0] = unicorn.id
    state.attack_targets[unicorn.id] = f'player:{3-seat}'
    attackers = list(state.attackers)
    if tax is not None:
        state.step = Step.DECLARE_ATTACKERS
        state, _ = activate(state, 'War Cadence', seat, tax)
        state.step = Step.DECLARE_BLOCKERS
        state.priority_player = 3-seat
    before = serialize_match_snapshot(state)
    actual = block_intents(state, attackers, [bid, elf.id])
    assert actual is not None
    assert {key(groups) for groups in actual} == independent_checked_intents(state, attackers, [bid, elf.id])
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master', 'master_plus'])
def test_actual_ai_uses_multi_block_capacity_to_survive(seat, difficulty):
    state, attackers, bid = board(seat)
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, 3-seat), 3-seat)
    assert serialize_match_snapshot(state) == before
    paid = checked_action(state, rules, 3-seat, decision.action)
    assert paid.blocks == {aid: [bid] for aid in attackers}
    rules.take_action(paid, seat, {'type': 'combat_damage'})
    assert paid.players[3-seat].life == 2 and paid.winner is None
    assert paid.cards[bid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['master', 'master_plus'])
def test_positive_power_multi_blocker_damage_choices_use_live_public_policy(seat, difficulty):
    state, attackers, bid = board(seat)
    aura = add(state, 'Rancor', 3-seat)
    aura.attached_to = bid
    state.mechanic_choice_players = {1, 2}
    rules = RulesEngine()
    decision = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, 3-seat), 3-seat)
    paid = checked_action(state, rules, 3-seat, decision.action)
    assert paid.blocks == {aid: [bid] for aid in attackers}
    rules.next_step(paid)
    assert paid.pending_mechanic_choice and paid.pending_mechanic_choice['kind'] == 'combat_damage'
    agent = AIAgent(difficulty)
    assert agent._finish_combat_projection(paid, state)
    assert paid.players[3-seat].life == 2 and paid.winner is None
    assert sum(paid.cards[aid].zone == Zone.GRAVEYARD for aid in attackers) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['master', 'master_plus'])
def test_search_does_not_discard_planeswalker_protection_as_safe_life_chump(seat, difficulty):
    state, attackers, bid = board(seat, life=20)
    walker = limit_card(state, 'Ugin, the Spirit Dragon', 3-seat)
    walker.loyalty = 3
    state.attack_targets = {aid: f'planeswalker:{walker.id}' for aid in attackers}
    rules = RulesEngine()
    decision = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, 3-seat), 3-seat)
    paid = checked_action(state, rules, 3-seat, decision.action)
    assert paid.blocks == {aid: [bid] for aid in attackers}
    rules.take_action(paid, seat, {'type': 'combat_damage'})
    assert paid.cards[walker.id].zone == Zone.BATTLEFIELD and paid.cards[walker.id].loyalty == 3
    assert paid.players[3-seat].life == 20


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_alone_restriction_finalizer_never_returns_an_illegal_retry(difficulty):
    state, attackers, bid = board(count=1, guard='Mogg Flunkies')
    final = finalize_declaration(state, {'type': 'block', 'blocks': {attackers[0]: [bid]}})
    assert final['blocks'] == {}
    checked_action(state, RulesEngine(), 2, final)
    rules = RulesEngine()
    decision = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, 2), 2)
    checked_action(state, rules, 2, decision.action)


def test_alone_restriction_is_locked_before_another_blocker_pays_by_sacrifice():
    from tests.test_combat_domain_temporary_costs import blocking_board
    state, attacker = blocking_board()
    gold = add(state, 'Goldhound', 2)
    guard = raw_add(state, 'Mogg Flunkies', 2, cards=ROWS)
    state.players[2].mana_pool['U'] = 1
    final = finalize_declaration(state, {'type': 'block', 'blocks': {attacker.id: [gold.id, guard.id]}})
    assert set(final['blocks'][attacker.id]) == {gold.id, guard.id}
    result = checked_action(state, RulesEngine(), 2, final)
    assert result.cards[gold.id].zone == Zone.GRAVEYARD
    assert result.blocks == {attacker.id: [guard.id]}


def test_budget_exhaustion_is_explicit_and_does_not_return_a_partial_optimum():
    state, attackers, bid = board(count=4)
    blockers = [bid] + [add(state, 'Wall of Glare', 2).id for _ in range(4)]
    assert block_intents(state, attackers, blockers) is None
    assert block_intents(state, attackers, [bid], node_budget=1) is None
    assert len(block_intents(state, attackers, [bid])) == 16
    with pytest.raises(ValueError):
        block_intents(state, attackers, [bid], node_budget=0)


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_block_forecast_is_not_treated_as_opponent_passing(monkeypatch, seat):
    state, attackers, _ = board(seat, count=1)
    state.turn = 6
    state.step = Step.DECLARE_ATTACKERS
    state.priority_player = seat
    state.attackers_declared = False
    state.attackers = []
    state.attack_targets = {}
    state.cards[attackers[0]].tapped = False
    agent = AIAgent('master')
    monkeypatch.setattr(agent, '_search_block_assignments', lambda *args: None)
    assert agent._search_attack_assignments(state, attackers, seat) == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_direct_intent_is_not_replaced_with_illegal_band_propagation(seat, difficulty):
    state = fixture()
    zero_mana(state)
    hero = raw_add(state, 'Benalish Hero', seat, cards=ROWS)
    stalker = raw_add(state, 'Invisible Stalker', seat, cards=ROWS)
    for card in (hero, stalker):
        card.summoning_sick = False
    guard = add(state, 'Grizzly Bears', 3-seat)
    attack_step(state, seat)
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {'type': 'attack', 'attackers': [hero.id, stalker.id],
                                              'bands': [[hero.id, stalker.id]]})
    state.step = Step.DECLARE_BLOCKERS
    state.priority_player = 3-seat
    final = finalize_declaration(state, {'type': 'block', 'blocks': {hero.id: [guard.id]}})
    assert final['blocks'] == {hero.id: [guard.id]}
    paid = checked_action(state, rules, 3-seat, final)
    assert paid.blocks == {hero.id: [guard.id], stalker.id: [guard.id]}
    actual = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, 3-seat), 3-seat)
    checked_action(state, rules, 3-seat, actual.action)


@pytest.mark.parametrize('seat', [1, 2])
def test_http_same_blocker_multiple_attackers_commits_and_restores(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, attackers, bid = board(seat)
    state.id = match.state.id
    match.state = state
    persist(match)
    before = snapshot(match)[0]
    response = client.post(f'/matches/{state.id}/action', json={'player_id': 3-seat,
                           'action': {'type': 'block', 'blocks': {aid: [bid] for aid in attackers}}})
    assert response.status_code == 200, response.text
    assert snapshot(match)[0] != before
    assert match.state.blocks == {aid: [bid] for aid in attackers}
    committed = snapshot(match)[0]
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id])[0] == committed
