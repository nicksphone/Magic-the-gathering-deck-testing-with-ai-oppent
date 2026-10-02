"""Two mechanic families exercised with canonical cards, not invented decks."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.declaration_policy import finalize_declaration
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.combat_payments import attack_payment_view, attack_payment_state
from rules_engine.combat_requirements import best_required_blocks, block_requirement_score
from rules_engine.combat_constraints import combat_clause_coverage
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_ai_recurring_engines import fixture, add as raw_add
from tests.test_declaration_limits import add as limit_card, attack_step
from tests.test_ability_suppression import add as printed
from tests.test_conditional_combat import lose
from tests.test_api_input_contracts import game, persist, rejected, snapshot

ROWS = {}
for filename in ('combat_payments_requirements.json', 'combat_coverage.json', 'restricted_mana.json'):
    ROWS.update({row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures' / filename).read_text())})


def add(state, name, player=1):
    card = raw_add(state, name, player, cards=ROWS)
    card.summoning_sick = False
    return card


def zero_mana(state):
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in ('W', 'U', 'B', 'R', 'G', 'C')}
        player.snow_mana_pool = dict(player.mana_pool)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tax', ['Propaganda', 'Ghostly Prison', 'Archon of Absolution'])
def test_fixed_tax_paid_once_and_insufficient_declaration_is_atomic(seat, tax):
    state = fixture()
    zero_mana(state)
    add(state, tax, 3-seat)
    attackers = [add(state, 'Llanowar Elves', seat) for _ in range(2)]
    attack_step(state, seat)
    cost = 2 if tax != 'Archon of Absolution' else 1
    state.players[seat].mana_pool['U'] = cost
    action = {'type': 'attack', 'attackers': [c.id for c in attackers]}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='attack costs'):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    action['attackers'] = action['attackers'][:1]
    paid = checked_action(state, RulesEngine(), seat, action)
    assert paid.players[seat].mana_pool['U'] == 0
    assert len(paid.attackers) == 1
    assert sum('mana in attack costs' in line for line in paid.log) == 1


def test_dynamic_tax_counts_all_enchantments_and_multiple_sources():
    state = fixture()
    zero_mana(state)
    sphere = add(state, 'Sphere of Safety', 2)
    add(state, 'Ghostly Prison', 2)
    add(state, 'Lure', 2)
    attacker = add(state, 'Llanowar Elves')
    attack_step(state, 1)
    view = attack_payment_view(state, [attacker.id])
    assert view['total_generic'] == 5  # Three enchantments + Prison's two.
    assert len(view['payments']) == 2
    state.players[1].mana_pool['R'] = 5
    paid = checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': [attacker.id]})
    assert paid.players[1].mana_pool['R'] == 0
    lose(state, sphere)
    assert attack_payment_view(state, [attacker.id])['total_generic'] == 2


@pytest.mark.parametrize('tax,expected', [('Propaganda', 0), ('Ghostly Prison', 0), ('Sphere of Safety', 1), ('Archon of Absolution', 1)])
def test_player_only_taxes_do_not_protect_planeswalkers(tax, expected):
    state = fixture()
    add(state, tax, 2)
    walker = limit_card(state, 'Ugin, the Spirit Dragon', 2)
    attacker = add(state, 'Llanowar Elves')
    attack_step(state, 1)
    assert attack_payment_view(state, [attacker.id], {attacker.id: f'planeswalker:{walker.id}'})['total_generic'] == expected


def test_mandatory_attack_never_forces_optional_tax_payment():
    state = fixture()
    add(state, 'Propaganda', 2)
    limit_card(state, 'Juggernaut')
    attack_step(state, 1)
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': []})
    assert result.attackers == []
    assert result.players[1].mana_pool == state.players[1].mana_pool
    assert serialize_match_snapshot(state) == before
    walker = limit_card(state, 'Ugin, the Spirit Dragon', 2)
    with pytest.raises(ActionRejected, match='requirements'):
        checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': []})
    assert walker.id in state.cards


def test_nonvigilant_attacker_cannot_tap_for_its_own_tax():
    state = fixture()
    zero_mana(state)
    add(state, 'Propaganda', 2)
    elves = [add(state, 'Llanowar Elves') for _ in range(2)]
    attack_step(state, 1)
    assert attack_payment_state(state, [elves[0].id]) is None  # Only one other mana creature.
    add_keyword_effect(state, elves[0].id, ['vigilance'])
    paid = checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': [elves[0].id]})
    assert all(paid.cards[c.id].tapped for c in elves)


def test_combat_cost_does_not_spend_creature_restricted_mana_or_spell_discounts():
    from rules_engine.mana import add_mana_to_pool
    state = fixture()
    zero_mana(state)
    add(state, 'Propaganda', 2)
    sage = add(state, 'Somberwald Sage')
    attacker = add(state, 'Llanowar Elves')
    attacker.tapped = False
    attack_step(state, 1)
    add_mana_to_pool(state, 1, 'G', 3, source_id=sage.id)
    assert attack_payment_state(state, [attacker.id]) is None


@pytest.mark.parametrize('name', ['Lure', 'Nemesis Mask', 'Prized Unicorn', 'Taunting Elf'])
@pytest.mark.parametrize('seat', [1, 2])
def test_target_requirement_rejects_blocking_only_other_attacker(name, seat):
    state = fixture()
    source = add(state, name, seat)
    if name in {'Lure', 'Nemesis Mask'}:
        target = add(state, 'Llanowar Elves', seat)
        source.attached_to = target.id
    else:
        target = source
    other = add(state, 'Llanowar Elves', seat)
    guards = [add(state, 'Llanowar Elves', 3-seat) for _ in range(2)]
    state.active_player, state.priority_player = seat, 3-seat
    state.step = Step.DECLARE_BLOCKERS
    state.attackers = [target.id, other.id]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='requirements'):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {other.id: [c.id for c in guards]}})
    solution = best_required_blocks(state)
    assert set(solution[target.id]) == {c.id for c in guards}
    result = checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': solution})
    assert set(result.blocks[target.id]) == {c.id for c in guards}
    assert serialize_match_snapshot(state) == before
    lose(state, source)
    assert block_requirement_score(state, solution) == 0


def test_conflicting_target_requirements_respect_menace_and_distinct_blocker_cap():
    state = fixture()
    targets = [add(state, 'Prized Unicorn') for _ in range(2)]
    guard = add(state, 'Llanowar Elves', 2)
    limit_card(state, 'Silent Arbiter')
    state.step, state.priority_player = Step.DECLARE_BLOCKERS, 2
    state.attackers = [c.id for c in targets]
    optimum = best_required_blocks(state)
    assert block_requirement_score(state, optimum) == 1
    checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {targets[1].id: [guard.id]}})
    for card in targets:
        add_keyword_effect(state, card.id, ['menace'])
    assert block_requirement_score(state, best_required_blocks(state)) == 0
    checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {}})


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_ai_exercises_both_payment_and_target_requirement_without_mutation(difficulty):
    state = fixture()
    zero_mana(state)
    add(state, 'Ghostly Prison', 2)
    attacker = add(state, 'Prized Unicorn')
    state.players[1].mana_pool['U'] = 2
    attack_step(state, 1)
    before = serialize_match_snapshot(state)
    intent = finalize_declaration(state, {'type': 'attack', 'attackers': [attacker.id]})
    result = checked_action(state, RulesEngine(), 1, intent)
    assert result.players[1].mana_pool['U'] == 0
    assert serialize_match_snapshot(state) == before
    guard = add(result, 'Llanowar Elves', 2)
    result.step, result.priority_player = Step.DECLARE_BLOCKERS, 2
    result.blockers_declared = False
    before = serialize_match_snapshot(result)
    agent = AIAgent(difficulty)
    decision = agent.choose_action(result, RulesEngine().legal_moves(result, 2), 2)
    final = checked_action(result, RulesEngine(), 2, decision.action)
    assert final.blocks[attacker.id] == [guard.id]
    assert serialize_match_snapshot(result) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_http_restart_preserves_both_mechanic_families_and_atomic_rejections(game, seat):
    client, match = game
    state = match.state
    zero_mana(state)
    add(state, 'Ghostly Prison', 3-seat)
    attacker = add(state, 'Prized Unicorn', seat)
    guard = add(state, 'Llanowar Elves', 3-seat)
    attack_step(state, seat)
    persist(match)
    action = {'type': 'attack', 'attackers': [attacker.id]}
    rejected(client, match, action, seat)
    state = match.state
    state.players[seat].mana_pool['U'] = 2
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    match_id = state.id
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    match = main.ACTIVE_MATCHES[match_id]
    restored = match.state
    restored.step, restored.priority_player = Step.DECLARE_BLOCKERS, 3-seat
    match.state = restored
    persist(match)
    rejected(client, match, {'type': 'block', 'blocks': {}}, 3-seat)
    before = snapshot(match)
    report = client.get(f'/matches/{state.id}/rules-diagnostics').json()
    assert report['attack_taxes'][0]['amount'] == 2
    assert report['target_block_requirements'][0]['attacker_id'] == attacker.id
    assert snapshot(match) == before
    response = client.post(f'/matches/{state.id}/action', json={'player_id': 3-seat, 'action': {'type': 'block', 'blocks': {attacker.id: [guard.id]}}})
    assert response.status_code == 200, response.text


def test_coverage_recognizes_supported_mana_costs_and_target_requirements():
    for name in ('Propaganda', 'Ghostly Prison', 'Sphere of Safety', 'Lure', 'Nemesis Mask', 'Prized Unicorn', 'Taunting Elf', "Norn's Annex"):
        assert combat_clause_coverage(ROWS[name]['oracle_text'], name) == []


def test_many_blockers_with_competing_targets_and_unequal_requirement_weights():
    state = fixture()
    target = add(state, 'Prized Unicorn')
    source = add(state, 'Lure')
    source.attached_to = target.id
    other = add(state, 'Taunting Elf')
    guards = [add(state, 'Llanowar Elves', 2) for _ in range(101)]
    state.step, state.priority_player = Step.DECLARE_BLOCKERS, 2
    state.attackers = [target.id, other.id]
    solution = best_required_blocks(state)
    assert set(solution[target.id]) == {c.id for c in guards}
    assert block_requirement_score(state, solution) == 202


def test_losing_recipient_abilities_does_not_remove_attached_lure_requirement():
    state = fixture()
    target = add(state, 'Llanowar Elves')
    source = add(state, 'Lure')
    source.attached_to = target.id
    guard = add(state, 'Llanowar Elves', 2)
    state.step, state.priority_player = Step.DECLARE_BLOCKERS, 2
    state.attackers = [target.id]
    lose(state, target)
    solution = best_required_blocks(state)
    assert solution[target.id] == [guard.id]
    lose(state, source)
    assert block_requirement_score(state, solution) == 0


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_ai_unpayable_tax_intent_becomes_legal_no_attack_not_retry_loop(difficulty):
    state = fixture()
    zero_mana(state)
    add(state, 'Ghostly Prison', 2)
    attacker = add(state, 'Prized Unicorn')
    attack_step(state, 1)
    before = serialize_match_snapshot(state)
    intent = finalize_declaration(state, {'type': 'attack', 'attackers': [attacker.id]})
    assert intent['attackers'] == []
    decision = AIAgent(difficulty).choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    result = checked_action(state, RulesEngine(), 1, decision.action)
    assert result.attackers == []
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_block_declaration_precedes_active_priority_and_returns_priority_afterward(seat):
    state = fixture()
    attacker = add(state, 'Prized Unicorn', seat)
    guard = add(state, 'Llanowar Elves', 3-seat)
    attack_step(state, seat)
    state.attackers = [attacker.id]
    state.attackers_declared = True
    rules = RulesEngine()
    rules.next_step(state)
    assert state.step == Step.DECLARE_BLOCKERS
    assert state.priority_player == 3-seat
    result = checked_action(state, rules, 3-seat, {'type': 'block', 'blocks': {attacker.id: [guard.id]}})
    assert result.priority_player == seat
    assert result.passed_priority == set()


@pytest.mark.parametrize('seat', [1, 2])
def test_passing_cannot_bypass_required_attack_or_targeted_block(seat):
    state = fixture()
    required = limit_card(state, 'Juggernaut', seat)
    attack_step(state, seat)
    with pytest.raises(ActionRejected, match='required attackers'):
        checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    add(state, 'Ghostly Prison', 3-seat)
    passed = checked_action(state, RulesEngine(), seat, {'type': 'pass_priority'})
    assert passed.attackers_declared and passed.attackers == []
    target = add(state, 'Prized Unicorn', seat)
    add(state, 'Llanowar Elves', 3-seat)
    state.attackers = [target.id]
    state.step, state.priority_player = Step.DECLARE_BLOCKERS, 3-seat
    with pytest.raises(ActionRejected, match='required blockers'):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    lose(state, target)
    passed = checked_action(state, RulesEngine(), 3-seat, {'type': 'pass_priority'})
    assert passed.blockers_declared and passed.blocks == {}
    assert passed.priority_player == seat and passed.passed_priority == set()


@pytest.mark.parametrize('seat', [1, 2])
def test_attacker_sacrificed_for_locked_attack_cost_never_becomes_attacking(seat):
    state = fixture()
    zero_mana(state)
    add(state, 'Ghostly Prison', 3-seat)
    attacker = add(state, 'Goldhound', seat)
    add_keyword_effect(state, attacker.id, ['vigilance'])
    state.players[seat].mana_pool['G'] = 1
    attack_step(state, seat)
    before = serialize_match_snapshot(state)
    intent = finalize_declaration(state, {'type': 'attack', 'attackers': [attacker.id]})
    assert intent['attackers'] == []  # AI should not pay for an attack that disappears.
    result = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker.id]})
    assert result.attackers == []
    assert result.cards[attacker.id].zone == Zone.GRAVEYARD
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert not any('Attackers declared:' in line for line in result.log)
    assert serialize_match_snapshot(state) == before
