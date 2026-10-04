"""Canonical defensive resources, announced stack interactions and strike windows."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from effects.registry import resolve_effect
from tests.test_ai_recurring_engines import fixture, add, CARDS
from tests.test_pending_removal import CARDS as REMOVAL
from tests.test_devotion import ROWS as DEVOTION
from tests.test_api_input_contracts import game, persist

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/defensive_responses.json').read_text())}
ROWS.update(CARDS)
ROWS.update(REMOVAL)
ROWS.update(DEVOTION)
ROWS.update({row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/keyword_effect_timestamps.json').read_text())})


def board(seat=1, spell='Giant Growth', *, attacker='Burning-Tree Emissary',
          blocker='Burning-Tree Emissary', first=False, responding_attacker=False, ready=True):
    state = fixture()
    active = seat if responding_attacker else 3-seat
    defender = 3-active
    state.active_player = state.priority_player = active
    state.step = Step.DECLARE_ATTACKERS
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    threat = add(state, attacker, active, cards=ROWS)
    threat.summoning_sick = False
    if blocker == 'soldier_token':
        maker = add(state, 'Raise the Alarm', defender, Zone.GRAVEYARD, cards=ROWS)
        key, payload = infer_effect_from_oracle(state, maker, defender)
        resolve_effect(state, defender, key, {**payload, '__source_card_id': maker.id})
        guard = state.cards[state.players[defender].battlefield[-1]]
        assert guard.power == guard.toughness == 1 and guard.is_token
    else:
        guard = add(state, blocker, defender, cards=ROWS) if blocker else None
    source = add(state, spell, seat, Zone.HAND, cards=ROWS)
    rules = RulesEngine()
    state = checked_action(state, rules, active, {'type': 'attack', 'attackers': [threat.id]})
    rules.next_step(state)
    state = checked_action(state, rules, defender, {
        'type': 'block', 'blocks': {threat.id: [guard.id]} if guard else {},
    })
    if first:
        rules.next_step(state)
        assert state.step == Step.COMBAT_DAMAGE and state.combat_damage_stage == 'first'
    while ready and state.priority_player != seat:
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    state.players[seat].mana_pool = {color: (2 if color != 'C' else 1) for color in 'WUBRGC'}
    return state, source.id, threat.id, guard.id if guard else None


def finish(state, action, seat):
    rules = RulesEngine()
    state = checked_action(state, rules, seat, action)
    for _ in range(24):
        if state.winner is not None or state.step == Step.END_COMBAT:
            return state
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Checked response did not complete combat')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('archetype', ['Aggro', 'Tempo', 'Control', 'Ramp', 'Tokens', 'Tribal'])
@pytest.mark.parametrize('spell', ['Giant Growth', 'Aspect of Hydra', 'Adamant Will', 'Moment of Heroism'])
def test_master_defends_with_resource_profitable_pump(seat, archetype, spell):
    state, source, threat, guard = board(seat, spell)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    decision = AIAgent('master', archetype=archetype).choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == source
    assert decision.action['targets']['target_card_id'] == guard
    result = finish(state, decision.action, seat)
    assert result.cards[guard].zone == Zone.BATTLEFIELD
    assert result.cards[threat].zone == Zone.GRAVEYARD
    if spell == 'Moment of Heroism':
        assert result.players[seat].life == 24


@pytest.mark.parametrize('seat', [1, 2])
def test_compound_indestructibility_preserves_blocker_that_pump_alone_cannot(seat):
    state, source, threat, guard = board(seat, 'Adamant Will', attacker='Torrential Gearhulk')
    decision = AIAgent('master', archetype='Control').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['card_id'] == source
    result = finish(state, decision.action, seat)
    assert result.cards[guard].zone == result.cards[threat].zone == Zone.BATTLEFIELD
    assert result.cards[guard].counters['__damage_marked'] == 5
    RulesEngine()._clear_marked_damage(result)
    from rules_engine.continuous import effective_combat_stats, has_keyword
    assert effective_combat_stats(result, guard) == (2, 2)
    assert not has_keyword(result, guard, 'indestructible')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('role', ['defender', 'attacker'])
@pytest.mark.parametrize('spell', ['Giant Growth', 'Aspect of Hydra'])
def test_between_strike_steps_uses_remaining_damage_and_marked_damage(seat, role, spell):
    active_response = role == 'attacker'
    state, source, threat, guard = board(
        seat, spell, attacker='Burning-Tree Emissary' if active_response else 'Fencing Ace',
        blocker='Fencing Ace' if active_response else 'Burning-Tree Emissary',
        first=True, responding_attacker=active_response)
    recipient = threat if active_response else guard
    victim = guard if active_response else threat
    assert state.cards[recipient].counters['__damage_marked'] == 1
    before = serialize_match_snapshot(state)
    decision = AIAgent('master', archetype='Tempo').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['card_id'] == source
    assert decision.action['targets']['target_card_id'] == recipient
    result = finish(state, decision.action, seat)
    assert result.cards[recipient].zone == Zone.BATTLEFIELD
    assert result.cards[victim].zone == Zone.GRAVEYARD
    assert result.cards[recipient].counters['__damage_marked'] == 2


def announce_pump(state, threat, seat):
    rules = RulesEngine()
    opponent = 3-seat
    assert state.priority_player == opponent
    pump = add(state, 'Giant Growth', opponent, Zone.HAND, cards=ROWS)
    state.players[opponent].mana_pool['G'] = 1
    state = checked_action(state, rules, opponent, {
        'type': 'cast_spell', 'card_id': pump.id, 'targets': {'target_card_id': threat},
    })
    state = checked_action(state, rules, opponent, {'type': 'pass_priority'})
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Counterspell', 'Lightning Bolt'])
def test_announced_hostile_pump_is_answered_through_actual_stack(seat, spell):
    state, source, threat, guard = board(seat, spell, ready=False)
    state = announce_pump(state, threat, seat)
    decision = AIAgent('master', archetype='Control').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['card_id'] == source
    if spell == 'Counterspell':
        assert decision.action['targets']['target_stack_id'] == state.stack[-1].id
    result = finish(state, decision.action, seat)
    assert result.cards[threat].zone == Zone.GRAVEYARD
    assert result.cards[guard].zone == (Zone.GRAVEYARD if spell == 'Counterspell' else Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
def test_removal_beats_counter_when_it_also_preserves_blocker(seat):
    state, counter, threat, guard = board(seat, 'Counterspell', ready=False)
    bolt = add(state, 'Lightning Bolt', seat, Zone.HAND, cards=ROWS)
    state = announce_pump(state, threat, seat)
    decision = AIAgent('master', archetype='Control').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action['card_id'] == bolt.id
    assert decision.action['targets']['target_card_id'] == threat
    result = finish(state, decision.action, seat)
    assert result.cards[guard].zone == Zone.BATTLEFIELD
    assert counter in result.players[seat].hand


@pytest.mark.parametrize('seat', [1, 2])
def test_public_bounce_prevents_loss_without_reading_hidden_cards(seat):
    state, source, threat, _ = board(seat, 'Unsummon', attacker='Torrential Gearhulk', blocker=None)
    state.players[seat].life = 3
    before = serialize_match_snapshot(state)
    decision = AIAgent('master', archetype='Control').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['card_id'] == source
    assert decision.action['targets']['target_card_id'] == threat
    result = finish(state, decision.action, seat)
    assert result.winner is None and result.players[seat].life == 3
    assert threat in result.players[3-seat].hand


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Adamant Will', 'Moment of Heroism'])
def test_canonical_compound_pump_keeps_both_clauses(seat, spell):
    from rules_engine.continuous import effective_combat_stats, has_keyword
    state, source, threat, guard = board(seat, spell)
    key, payload = infer_effect_from_oracle(state, state.cards[source], seat, {'target_card_id': guard})
    assert key == 'effect_sequence'
    resolve_effect(state, seat, key, payload)
    assert effective_combat_stats(state, guard) == (4, 4)
    assert has_keyword(state, guard, 'indestructible' if spell == 'Adamant Will' else 'lifelink')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['survives', 'disposable', 'underfunded', 'already_dead',
                                 'unknown_draw', 'replacement', 'not_declared'])
def test_resource_waste_and_unknown_projection_do_not_force_responses(seat, case):
    from ai.combat_response import choose_response
    spell = {'disposable': 'Adamant Will', 'unknown_draw': 'Leap',
             'replacement': 'Moment of Heroism'}.get(case, 'Giant Growth')
    state, source, threat, guard = board(
        seat, spell, attacker='Knight of Meadowgrain' if case == 'already_dead' else 'Burning-Tree Emissary' if case == 'replacement' else 'Torrential Gearhulk',
        blocker='Darksteel Myr' if case == 'survives' else 'soldier_token' if case == 'disposable' else 'Burning-Tree Emissary',
        first=case == 'already_dead')
    if case == 'underfunded':
        state.players[seat].mana_pool = {color: 0 for color in 'WUBRGC'}
    elif case == 'not_declared':
        state.blockers_declared = False
    elif case == 'replacement':
        add(state, 'Boon Reflection', seat, cards=ROWS)
        add(state, 'Boon Reflection', seat, cards=ROWS)
    agent = AIAgent('master', archetype='Control')
    before = serialize_match_snapshot(state)
    selected = choose_response(agent, state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    if case in {'unknown_draw', 'replacement', 'not_declared', 'underfunded'}:
        assert selected is None
    else:
        assert selected == {'type': 'pass_priority'}


@pytest.mark.parametrize('seat', [1, 2])
def test_counter_war_targets_hostile_counter_not_own_pending_pump(seat):
    state, growth, threat, guard = board(seat)
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {
        'type': 'cast_spell', 'card_id': growth, 'targets': {'target_card_id': guard},
    })
    own_spell = state.stack[-1].id
    state = checked_action(state, rules, seat, {'type': 'pass_priority'})
    hostile = add(state, 'Counterspell', 3-seat, Zone.HAND, cards=ROWS)
    state.players[3-seat].mana_pool['U'] = 2
    state = checked_action(state, rules, 3-seat, {
        'type': 'cast_spell', 'card_id': hostile.id, 'targets': {'target_stack_id': own_spell},
    })
    hostile_spell = state.stack[-1].id
    state = checked_action(state, rules, 3-seat, {'type': 'pass_priority'})
    answer = add(state, 'Counterspell', seat, Zone.HAND, cards=ROWS)
    decision = AIAgent('master', archetype='Control').choose_action(
        state, rules.legal_moves(state, seat), seat)
    assert decision.action['card_id'] == answer.id
    assert decision.action['targets']['target_stack_id'] == hostile_spell
    result = finish(state, decision.action, seat)
    assert result.cards[guard].zone == Zone.BATTLEFIELD
    assert result.cards[threat].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Giant Growth', 'Counterspell'])
def test_http_response_payment_restore_and_actual_outcome(game, seat, spell):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, source, threat, guard = board(seat, spell, ready=spell != 'Counterspell')
    if spell == 'Counterspell':
        state = announce_pump(state, threat, seat)
    state.id = match.state.id
    match.state = state
    match.controllers = {1: 'ai', 2: 'ai'}
    match.ai = {pid: AIAgent('master', archetype='Control') for pid in (1, 2)}
    match.best_of = 1
    persist(match)
    before_mana = dict(state.players[seat].mana_pool)
    response = client.post(f'/matches/{state.id}/autoplay?ticks=1')
    assert response.status_code == 200, response.text
    assert match.state.cards[source].zone == Zone.STACK
    assert match.state.players[seat].mana_pool['G' if spell == 'Giant Growth' else 'U'] == before_mana['G' if spell == 'Giant Growth' else 'U'] - (1 if spell == 'Giant Growth' else 2)
    committed = serialize_match_snapshot(match.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert serialize_match_snapshot(restored.state) == committed
    response = client.post(f'/matches/{state.id}/autoplay?ticks=20')
    assert response.status_code == 200, response.text
    assert restored.state.cards[source].zone == Zone.GRAVEYARD
    assert restored.state.cards[threat].zone == Zone.GRAVEYARD
    assert restored.state.cards[guard].zone == (Zone.BATTLEFIELD if spell == 'Giant Growth' else Zone.GRAVEYARD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('life', [2, 3, 20])
def test_phyrexian_response_values_actual_life_cost_and_remaining_resources(seat, life):
    state, source, threat, guard = board(seat, 'Mutagenic Growth')
    state.players[seat].life = life
    state.players[seat].mana_pool = {color: 0 for color in 'WUBRGC'}
    decision = AIAgent('master', archetype='Tempo').choose_action(
        state, RulesEngine().legal_moves(state, seat), seat)
    if life <= 3:
        assert decision.action == {'type': 'pass_priority'}
        assert source in state.players[seat].hand
    else:
        assert decision.action['card_id'] == source
        result = finish(state, decision.action, seat)
        assert result.players[seat].life == 18
        assert result.cards[guard].zone == Zone.BATTLEFIELD
        assert result.cards[threat].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_hand_identity_does_not_change_public_response_policy(seat):
    from ai.pending_effects import planning_copy
    from ai.combat_response import choose_response
    state, source, threat, guard = board(seat)
    state.players[3-seat].mana_pool['U'] = 2
    actions = []
    for secret in ['Counterspell', 'Giant Growth']:
        branch = planning_copy(state)
        add(branch, secret, 3-seat, Zone.HAND, cards=ROWS)
        actions.append(choose_response(AIAgent('master', archetype='Control'), branch,
                                       RulesEngine().legal_moves(branch, seat), seat))
    assert actions[0] == actions[1]
    assert actions[0]['card_id'] == source


@pytest.mark.parametrize('text', [
    'Target creature gets +2/+2 and gains unknown until end of turn.',
    'Target creature gets +2/+2 and gains ward {2} until end of turn.',
    'Target creature gets +2/+2 and gains lifelink until end of turn. Draw a card.',
])
def test_target_buff_parser_does_not_drop_unknown_or_extra_clauses(text):
    from rules_engine.oracle_effects import parse_temporary_target_buff
    assert parse_temporary_target_buff(text) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_copy_stack_exhaustion_does_not_certify_partial_search(seat):
    from ai.combat_response import choose_response
    state, source, threat, guard = board(seat, 'Counterspell', ready=False)
    bolt = add(state, 'Lightning Bolt', 3-seat, Zone.HAND, cards=ROWS)
    state.players[3-seat].mana_pool['R'] = 1
    rules = RulesEngine()
    state = checked_action(state, rules, 3-seat, {
        'type': 'cast_spell', 'card_id': bolt.id, 'targets': {'target_card_id': guard},
    })
    original = state.stack[-1].id
    for _ in range(64):
        resolve_effect(state, 3-seat, 'copy_spell', {'target_stack_id': original})
    state = checked_action(state, rules, 3-seat, {'type': 'pass_priority'})
    assert len(state.stack) == 65
    before = serialize_match_snapshot(state)
    assert choose_response(AIAgent('master'), state, rules.legal_moves(state, seat), seat) is None
    assert serialize_match_snapshot(state) == before
