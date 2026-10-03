"""Canonical recipient costs and alternative block-requirement recipients."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.combat_payments import attack_payment_view, block_payment_view
from rules_engine.combat_requirements import best_required_blocks, target_block_requirements
from rules_engine.combat_constraints import combat_clause_coverage
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_combat_domain_temporary_costs import fixture, add, zero_mana, attack_step
from tests.test_conditional_combat import lose
from tests.test_api_input_contracts import game, persist, rejected, snapshot

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/recipient_combat.json').read_text())}


def enchant(state, name, target, controller):
    aura = raw_add(state, name, controller, cards=ROWS)
    aura.attached_to = target.id
    return aura


def recipient_board(seat=1, kind='attack'):
    state = fixture()
    zero_mana(state)
    bear = add(state, 'Grizzly Bears', seat)
    if kind == 'attack':
        guard = bear
        free = add(state, 'Llanowar Elves', seat)
    else:
        guard = add(state, 'Wall of Glare', 3-seat)
        free = add(state, 'Llanowar Elves', 3-seat)
        add(state, 'Grizzly Bears', seat)
    enchant(state, 'Oppressive Rays', guard, 3-guard.controller)
    attack_step(state, seat)
    if kind == 'block':
        attackers = [cid for cid in state.players[seat].battlefield if 'Creature' in state.cards[cid].types]
        state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': attackers})
        state.step = Step.DECLARE_BLOCKERS
        state.priority_player = 3-seat
    return state, guard.id, free.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
def test_http_recipient_cost_is_atomic_charges_once_and_restores(game, seat, kind):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, guard, free = recipient_board(seat, kind)
    state.id = match.state.id
    match.state = state
    persist(match)
    actor = seat if kind == 'attack' else 3-seat
    action = {'type': 'attack', 'attackers': [guard, free]} if kind == 'attack' else {
        'type': 'block', 'blocks': {aid: [guard] for aid in state.attackers}}
    rejected(client, match, action, actor)
    match.state.players[actor].mana_pool['G'] = 3
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': actor, 'action': action})
    assert response.status_code == 200, response.text
    assert match.state.players[actor].mana_pool['G'] == 0
    committed = snapshot(match)[0]
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert snapshot(main.ACTIVE_MATCHES[state.id])[0] == committed


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Oppressive Rays', 'Brainwash'])
def test_attached_attack_cost_targets_only_enchanted_creature_and_survives_resume(seat, name):
    state = fixture()
    zero_mana(state)
    bear = add(state, 'Grizzly Bears', seat)
    other = add(state, 'Grizzly Bears', seat)
    aura = enchant(state, name, bear, 3-seat)
    attack_step(state, seat)
    assert attack_payment_view(state, [bear.id])['mana_cost'] == '{3}'
    assert attack_payment_view(state, [other.id])['payments'] == []
    assert attack_payment_view(state, [bear.id, other.id])['mana_cost'] == '{3}'
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='attack costs'):
        checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [bear.id]})
    assert serialize_match_snapshot(state) == before
    resumed = deserialize_match_snapshot(before)
    assert attack_payment_view(resumed, [bear.id])['mana_cost'] == '{3}'
    resumed.players[seat].mana_pool['U'] = 3
    paid = checked_action(resumed, RulesEngine(), seat, {'type': 'attack', 'attackers': [bear.id, other.id]})
    assert paid.players[seat].mana_pool['U'] == 0 and len(paid.attackers) == 2
    aura.attached_to = other.id
    assert not attack_payment_view(state, [bear.id])['payments']
    assert attack_payment_view(state, [other.id])['mana_cost'] == '{3}'
    lose(state, aura)
    assert not attack_payment_view(state, [other.id])['payments']


@pytest.mark.parametrize('seat', [1, 2])
def test_specific_block_cost_and_free_alternative_do_not_become_global(seat):
    state = fixture()
    zero_mana(state)
    attacker = add(state, 'Grizzly Bears', seat)
    guard = add(state, 'Grizzly Bears', 3-seat)
    free = add(state, 'Grizzly Bears', 3-seat)
    enchant(state, 'Oppressive Rays', guard, seat)
    enchant(state, 'Brainwash', free, seat)
    attack_step(state, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [attacker.id]})
    state.step = Step.DECLARE_BLOCKERS
    state.priority_player = 3-seat
    assert block_payment_view(state, [guard.id])['mana_cost'] == '{3}'
    assert not block_payment_view(state, [free.id])['payments']
    with pytest.raises(ActionRejected, match='block costs'):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker.id: [guard.id]}})
    checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker.id: [free.id]}})
    state.players[3-seat].mana_pool['G'] = 3
    paid = checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {attacker.id: [guard.id]}})
    assert paid.blocks == {attacker.id: [guard.id]} and paid.players[3-seat].mana_pool['G'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_alternative_requirement_recipient_and_optional_specific_payment_in_real_ai(seat, difficulty):
    state = fixture()
    zero_mana(state)
    source = raw_add(state, 'Noble Quarry', seat, cards=ROWS)
    source.summoning_sick = False
    target = source
    taxed = add(state, 'Grizzly Bears', 3-seat)
    free = add(state, 'Grizzly Bears', 3-seat)
    enchant(state, 'Oppressive Rays', taxed, seat)
    attack_step(state, seat)
    state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [target.id]})
    state.step = Step.DECLARE_BLOCKERS
    state.priority_player = 3-seat
    assert {row['attacker_id'] for row in target_block_requirements(state)} == {target.id}
    optimum = best_required_blocks(state)
    assert optimum == {target.id: [free.id]}
    rules = RulesEngine()
    decision = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, 3-seat), 3-seat)
    result = checked_action(state, rules, 3-seat, decision.action)
    assert result.blocks == {target.id: [free.id]}
    resumed = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert best_required_blocks(resumed) == optimum


@pytest.mark.parametrize('seat', [1, 2])
def test_bestow_recipient_characteristics_are_a_static_read_not_casting_acceptance(seat):
    # Bestow execution is explicitly unsupported. Test only the static reader on
    # its defined characteristics; do not run SBA or pretend a cast succeeded.
    state = fixture()
    zero_mana(state)
    source = raw_add(state, 'Noble Quarry', seat, cards=ROWS)
    bear = add(state, 'Grizzly Bears', seat)
    guard = add(state, 'Grizzly Bears', 3-seat)
    source.types = ['Enchantment']
    source.type_line = 'Enchantment - Aura'
    source.attached_to = bear.id
    state.active_player = seat
    state.attackers = [bear.id]
    assert {row['attacker_id'] for row in target_block_requirements(state)} == {bear.id}
    assert best_required_blocks(state) == {bear.id: [guard.id]}
    assert best_required_blocks(deserialize_match_snapshot(serialize_match_snapshot(state))) == {bear.id: [guard.id]}


def test_recipient_parsers_admit_only_supported_combat_clauses_not_other_card_abilities():
    from rules_engine.coverage import known_unsupported_mechanics
    for name, row in ROWS.items():
        assert combat_clause_coverage(row['oracle_text'], name) == []
    assert combat_clause_coverage("Enchanted creature can't attack unless its controller sacrifices a land.")
    assert combat_clause_coverage('All creatures with magnet counters able to block this creature do so.')
    assert 'bestow' in known_unsupported_mechanics(ROWS['Noble Quarry']['oracle_text'])
    assert 'activation cost modifiers' not in known_unsupported_mechanics(ROWS['Oppressive Rays']['oracle_text'])
