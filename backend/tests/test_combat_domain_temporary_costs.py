"""Canonical tax use; grammar boundaries are not competitive deck additions."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.combat_tax_policy import combat_tax_plan
from ai.declaration_policy import finalize_declaration
from effects.registry import resolve_effect
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.combat_payments import attack_payment_view, block_payment_view, block_payment_state
from rules_engine.combat_requirements import best_required_blocks, block_requirement_score
from rules_engine.combat_constraints import combat_clause_coverage
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import fixture, add as raw_add, resolve, CARDS as RECURRING
from tests.test_combat_payments_requirements import ROWS, zero_mana, attack_step
from tests.test_declaration_limits import add as limit_card
from tests.test_conditional_combat import lose
from tests.test_api_input_contracts import game, persist, rejected, snapshot

CARDS = {**ROWS, **RECURRING}
for name in ('combat_temporary_costs.json', 'combat_minimums.json', 'attached_scaling.json'):
    CARDS.update({row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures' / name).read_text())})


def add(state, name, seat=1):
    card = raw_add(state, name, seat, cards=CARDS)
    card.summoning_sick = False
    return card


def activate(state, name, controller=1, x=1):
    source = add(state, name, controller)
    state.priority_player = controller
    state.players[controller].mana_pool['U' if name == 'War Tax' else 'R'] = x+1
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0, 'targets': {'x_value': x}}
    before = serialize_match_snapshot(state)
    pending = checked_action(state, RulesEngine(), controller, action)
    assert serialize_match_snapshot(state) == before
    assert pending.combat_cost_effects == state.combat_cost_effects and len(pending.stack) == 1
    assert pending.stack[-1].effect_key == 'set_combat_cost'
    return resolve(pending), source.id


@pytest.mark.parametrize('seat', [1, 2])
def test_domain_counts_distinct_basic_land_types_not_land_or_basic_card_count(seat):
    state = fixture()
    zero_mana(state)
    source = add(state, 'Collective Restraint', 3-seat)
    attacker = add(state, 'Llanowar Elves', seat)
    attack_step(state, seat)
    assert attack_payment_view(state, [attacker.id])['mana_cost'] == '{0}'
    fountain = add(state, 'Hallowed Fountain', 3-seat)
    add(state, 'Hallowed Fountain', 3-seat)
    assert attack_payment_view(state, [attacker.id])['total_generic'] == 2
    add(state, 'Forest', 3-seat)
    assert attack_payment_view(state, [attacker.id])['total_generic'] == 3
    state.players[seat].mana_pool['R'] = 3
    result = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker.id]})
    assert result.players[seat].mana_pool['R'] == 0
    assert not known_unsupported_mechanics(source.oracle_text, card_name=source.name)
    assert combat_clause_coverage(source.oracle_text, source.name) == []
    # A stale zone-list entry must not contribute to domain.
    fountain.move_to_zone(Zone.GRAVEYARD)
    assert attack_payment_view(state, [attacker.id])['total_generic'] == 3  # The duplicate still supplies W/U.
    state.players[3-seat].battlefield.remove(source.id)
    state.players[seat].battlefield.append(source.id)
    source.controller = seat
    assert attack_payment_view(state, [attacker.id])['payments'] == []


def test_domain_zero_is_optional_and_untaxed_walker_still_requires_attack():
    state = fixture()
    add(state, 'Collective Restraint', 2)
    attacker = limit_card(state, 'Juggernaut')
    attack_step(state, 1)
    checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': []})
    walker = limit_card(state, 'Ugin, the Spirit Dragon', 2)
    assert attack_payment_view(state, [attacker.id], {attacker.id: f'planeswalker:{walker.id}'})['payments'] == []
    with pytest.raises(ActionRejected, match='requirements'):
        checked_action(state, RulesEngine(), 1, {'type': 'attack', 'attackers': []})


@pytest.mark.parametrize('name,kind', [('War Tax', 'attack'), ('War Cadence', 'block')])
@pytest.mark.parametrize('controller', [1, 2])
def test_resolved_tax_lifetime_source_loss_countering_and_legacy_snapshot(name, kind, controller):
    state = fixture()
    zero_mana(state)
    state, source_id = activate(state, name, controller, 2)
    row = state.combat_cost_effects[0]
    assert row['kind'] == kind and row['mana_cost'] == '{2}' and row['controller'] == controller
    assert row['source_id'] == source_id and row['timestamp'] > 0
    lose(state, state.cards[source_id])
    assert len(state.combat_cost_effects) == 1
    resolve_effect(state, controller, 'destroy_permanent', {'target_card_id': source_id})
    assert state.cards[source_id].zone == Zone.GRAVEYARD
    resumed = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resumed.combat_cost_effects == state.combat_cost_effects
    RulesEngine()._finish_cleanup(resumed)
    assert resumed.combat_cost_effects == []
    snapshot_data = serialize_match_snapshot(state)
    snapshot_data.pop('combat_cost_effects')
    assert deserialize_match_snapshot(snapshot_data).combat_cost_effects == []
    assert combat_clause_coverage(CARDS[name]['oracle_text'], name) == []


def test_countered_activation_does_not_create_tax_and_chosen_x_is_locked():
    state = fixture()
    zero_mana(state)
    source = add(state, 'War Tax')
    state.players[1].mana_pool['U'] = 4
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0, 'targets': {'x_value': 3}}
    pending = checked_action(state, RulesEngine(), 1, action)
    action['targets']['x_value'] = 99
    assert pending.stack[0].payload['mana_cost'] == '{3}'
    resolve_effect(pending, 2, 'counter_ability', {'target_stack_id': pending.stack[0].id})
    assert pending.stack == [] and pending.combat_cost_effects == []
    assert pending.players[1].mana_pool['U'] == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_temporary_attack_tax_is_global_stacks_and_applies_to_later_creatures(seat):
    state = fixture()
    zero_mana(state)
    state, _ = activate(state, 'War Tax', 1, 1)
    state, _ = activate(state, 'War Tax', 2, 2)
    attacker = add(state, 'Grizzly Bears', seat)
    walker = limit_card(state, 'Ugin, the Spirit Dragon', 3-seat)
    attack_step(state, seat)
    assert attack_payment_view(state, [attacker.id])['total_generic'] == 3
    assert attack_payment_view(state, [attacker.id], {attacker.id: f'planeswalker:{walker.id}'})['total_generic'] == 3
    state.players[seat].mana_pool['G'] = 3
    result = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker.id]})
    assert result.players[seat].mana_pool['G'] == 0


def blocking_board(seat=1, x=1):
    state = fixture()
    zero_mana(state)
    state, _ = activate(state, 'War Cadence', seat, x)
    attacker = add(state, 'Prized Unicorn', seat)
    state.active_player, state.priority_player = seat, 3-seat
    state.step, state.attackers = Step.DECLARE_BLOCKERS, [attacker.id]
    return state, attacker


@pytest.mark.parametrize('seat', [1, 2])
def test_block_payments_are_optional_but_volunteered_blockers_obey_requirements(seat):
    state, attacker = blocking_board(seat)
    other = add(state, 'Grizzly Bears', seat)
    state.attackers.append(other.id)
    guard = add(state, 'Grizzly Bears', 3-seat)
    assert block_requirement_score(state, best_required_blocks(state)) == 0
    checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {}})
    state.players[3-seat].mana_pool['G'] = 1
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='requirements'):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {other.id: [guard.id]}})
    result = checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker.id: [guard.id]}})
    assert result.players[3-seat].mana_pool['G'] == 0 and result.blocks[attacker.id] == [guard.id]
    assert serialize_match_snapshot(state) == before


def test_chosen_mana_blocker_may_tap_and_still_block():
    state, attacker = blocking_board()
    guard = add(state, 'Llanowar Elves', 2)
    result = checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {attacker.id: [guard.id]}})
    assert result.cards[guard.id].tapped and result.blocks[attacker.id] == [guard.id]
    assert result.players[2].mana_pool['G'] == 0


def test_canonical_zero_block_cost_is_optional_and_not_retroactive():
    state, attacker = blocking_board(x=0)
    guard = add(state, 'Grizzly Bears', 2)
    assert block_payment_view(state, [guard.id])['mana_cost'] == '{0}'
    checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {}})
    result = checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {attacker.id: [guard.id]}})
    assert result.blocks[attacker.id] == [guard.id]
    # A later resolution changes future declarations, not existing assignments.
    result, _ = activate(result, 'War Cadence', 1, 3)
    assert result.blocks[attacker.id] == [guard.id]
    assert result.players[2].mana_pool == state.players[2].mana_pool


def test_multiblock_capacity_pays_once_per_creature_not_per_pair():
    state, attacker = blocking_board()
    other = add(state, 'Grizzly Bears')
    state.attackers.append(other.id)
    wall = add(state, 'Wall of Glare', 2)
    state.players[2].mana_pool['W'] = 1
    assert block_payment_view(state, [wall.id, wall.id])['mana_cost'] == '{1}'
    result = checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {attacker.id: [wall.id], other.id: [wall.id]}})
    assert result.players[2].mana_pool['W'] == 0
    assert result.blocks == {attacker.id: [wall.id], other.id: [wall.id]}


def test_sacrificed_chosen_blocker_never_becomes_blocking_and_illegal_intent_stays_invalid():
    state, attacker = blocking_board()
    guard = add(state, 'Goldhound', 2)
    action = {'type': 'block', 'blocks': {attacker.id: [guard.id]}}
    result = checked_action(state, RulesEngine(), 2, action)
    assert result.cards[guard.id].zone == Zone.GRAVEYARD and result.blocks == {}
    assert not any('Targeted block requirements satisfied' in line for line in result.log)
    # A departed/tapped/otherwise ineligible object must not be excused as a cost.
    guard.move_to_zone(Zone.GRAVEYARD)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 2, action)


def test_locked_legal_menace_group_keeps_surviving_blocker_after_cost_sacrifice():
    from rules_engine.keyword_effects import add_keyword_effect
    state, attacker = blocking_board()
    add_keyword_effect(state, attacker.id, ['menace'])
    gold = add(state, 'Goldhound', 2)
    bear = add(state, 'Grizzly Bears', 2)
    state.players[2].mana_pool['U'] = 1
    result = checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {attacker.id: [gold.id, bear.id]}})
    assert result.cards[gold.id].zone == Zone.GRAVEYARD
    assert result.blocks[attacker.id] == [bear.id]
    assert result.players[2].mana_pool['U'] == 0


def test_payment_sacrifice_cannot_mask_ineligible_block_pair():
    from rules_engine.keyword_effects import add_keyword_effect
    state, attacker = blocking_board()
    add_keyword_effect(state, attacker.id, ['flying'])
    guard = add(state, 'Goldhound', 2)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='Illegal block assignment'):
        checked_action(state, RulesEngine(), 2, {'type': 'block', 'blocks': {attacker.id: [guard.id]}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('branch,life', [('W', 20), ('P', 18)])
def test_block_hybrid_branches_use_same_explicit_contract(branch, life):
    state, attacker = blocking_board()
    # A resolving-instruction grammar boundary, not a new card or deck entry.
    state.combat_cost_effects[0]['mana_cost'] = '{W/P}'
    guard = add(state, 'Grizzly Bears', 2)
    state.players[2].mana_pool['W'] = 1
    action = {'type': 'block', 'blocks': {attacker.id: [guard.id]}}
    with pytest.raises(ActionRejected, match='explicitly'):
        checked_action(state, RulesEngine(), 2, action)
    result = checked_action(state, RulesEngine(), 2, {**action, 'hybrid_choices': [branch]})
    assert result.players[2].life == life
    assert result.players[2].mana_pool['W'] == int(branch == 'P')


@pytest.mark.parametrize('seat', [1, 2])
def test_unpayable_block_is_atomic_and_restricted_mana_cannot_pay(seat):
    from rules_engine.mana import add_mana_to_pool
    state, attacker = blocking_board(seat, 2)
    guard = add(state, 'Grizzly Bears', 3-seat)
    action = {'type': 'block', 'blocks': {attacker.id: [guard.id]}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='block costs'):
        checked_action(state, RulesEngine(), 3-seat, action)
    assert serialize_match_snapshot(state) == before
    sage = add(state, 'Somberwald Sage', 3-seat)
    add_mana_to_pool(state, 3-seat, 'G', 3, source_id=sage.id)
    assert block_payment_state(state, [guard.id]) is None


@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_ai_block_finalization_reuses_actual_affordability_and_cost_choices(difficulty):
    state, attacker = blocking_board(x=2)
    guard = add(state, 'Grizzly Bears', 2)
    intent = {'type': 'block', 'blocks': {attacker.id: [guard.id]}}
    final = finalize_declaration(state, intent)
    assert not any(final['blocks'].values())
    checked_action(state, RulesEngine(), 2, final)
    state.players[2].mana_pool['G'] = 2
    final = finalize_declaration(state, intent)
    assert final['blocks'][attacker.id] == [guard.id]
    checked_action(state, RulesEngine(), 2, final)
    decision = AIAgent(difficulty).choose_action(state, RulesEngine().legal_moves(state, 2), 2)
    checked_action(state, RulesEngine(), 2, decision.action)


@pytest.mark.parametrize('kind,name,actor,step', [('attack', 'War Tax', 2, Step.BEGIN_COMBAT), ('block', 'War Cadence', 1, Step.DECLARE_ATTACKERS)])
def test_ai_tax_planning_uses_public_cost_capacity_and_only_relevant_windows(kind, name, actor, step):
    state = fixture()
    zero_mana(state)
    source = add(state, name, actor)
    state.active_player = 1
    attacker = add(state, 'Grizzly Bears')
    add(state, 'Grizzly Bears', 2)
    state.players[actor].mana_pool['U' if kind == 'attack' else 'R'] = 5
    state.step, state.priority_player = step, actor
    state.attackers_declared = kind == 'block'
    state.attackers = [attacker.id] if kind == 'block' else []
    moves = RulesEngine().legal_moves(state, actor)
    move = next(move for move in moves if move['type'] == 'activate_ability' and move['card_id'] == source.id)
    before = serialize_match_snapshot(state)
    plan = combat_tax_plan(state, move, actor)
    assert plan['x_value'] == 1 and plan['score'] > 0
    assert serialize_match_snapshot(state) == before
    state.step = Step.END_STEP
    assert combat_tax_plan(state, move, actor)['x_value'] == 0
    assert combat_tax_plan(state, move, actor)['score'] < 0


@pytest.mark.parametrize('seat', [1, 2])
def test_http_sqlite_resume_and_diagnostics_include_resolved_rule_costs(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, attacker = blocking_board(seat, 2)
    guard = add(state, 'Grizzly Bears', 3-seat)
    state.id = match.state.id
    match.state = state
    persist(match)
    report = client.get(f'/matches/{state.id}/rules-diagnostics').json()
    assert report['block_taxes'][0]['origin'] == 'resolution'
    before = snapshot(match)
    rejected(client, match, {'type': 'block', 'blocks': {attacker.id: [guard.id]}}, 3-seat)
    assert snapshot(match) == before
    match_id = state.id
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    match = main.ACTIVE_MATCHES[match_id]
    assert match.state.combat_cost_effects == state.combat_cost_effects
    match.state.players[3-seat].mana_pool['G'] = 2
    persist(match)
    response = client.post(f'/matches/{match_id}/action', json={'player_id': 3-seat, 'action': {'type': 'block', 'blocks': {attacker.id: [guard.id]}}})
    assert response.status_code == 200, response.text
    assert match.state.players[3-seat].mana_pool['G'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['War Tax', 'War Cadence'])
def test_actual_http_x_activation_resolves_then_survives_sqlite_restart(game, seat, name):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state = fixture()
    zero_mana(state)
    source = add(state, name, seat)
    state.id, state.priority_player = match.state.id, seat
    state.players[seat].mana_pool['U' if name == 'War Tax' else 'R'] = 3
    match.state = state
    persist(match)
    action = {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0, 'targets': {'x_value': 2}}
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert len(match.state.stack) == 1 and match.state.combat_cost_effects == []
    for _ in range(4):
        if not match.state.stack:
            break
        response = client.post(f'/matches/{state.id}/action', json={'player_id': match.state.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    assert match.state.combat_cost_effects[0]['mana_cost'] == '{2}'
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert main.ACTIVE_MATCHES[state.id].state.combat_cost_effects[0]['mana_cost'] == '{2}'
