"""Canonical conditional taxes and explicit grammar boundaries, not new cards."""
import pytest

from ai.agent import AIAgent
from ai.declaration_policy import finalize_declaration
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.combat_payments import attack_payment_view, block_payment_view, parse_static_combat_tax
from rules_engine.combat_constraints import combat_rule_view, combat_clause_coverage
from rules_engine.engine import RulesEngine
from rules_engine.static_conditions import evaluate_static_condition
from tests.test_combat_domain_temporary_costs import add, activate, fixture, zero_mana, attack_step
from tests.test_conditional_combat import lose
from tests.test_conditional_combat import add as conditional_add
from tests.test_declaration_limits import add as limit_card
from tests.test_api_input_contracts import game, persist, rejected, snapshot


def board(seat=1, kind='attack'):
    state = fixture()
    zero_mana(state)
    source = add(state, 'Archangel of Tithes', 3-seat if kind == 'attack' else seat)
    bear = add(state, 'Grizzly Bears', seat)
    elf = add(state, 'Llanowar Elves', seat if kind == 'attack' else 3-seat)
    attack_step(state, seat)
    if kind == 'block':
        state = checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [source.id, bear.id]})
        state.step = Step.DECLARE_BLOCKERS
        state.priority_player = 3-seat
        state.priority_passes = 0
    return state, source.id, bear.id, elf.id


@pytest.mark.parametrize('seat', [1, 2])
def test_untapped_source_taxes_player_and_walker_but_not_own_attack(seat):
    state, sid, bear, elf = board(seat)
    source = state.cards[sid]
    assert attack_payment_view(state, [bear])['mana_cost'] == '{1}'
    walker = limit_card(state, 'Ugin, the Spirit Dragon', 3-seat)
    assert attack_payment_view(state, [bear], {bear: f'planeswalker:{walker.id}'})['mana_cost'] == '{1}'
    assert not combat_rule_view(state, bear)['unsupported']
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected, match='attack costs'):
        checked_action(state, RulesEngine(), seat, {'type': 'attack', 'attackers': [bear, elf]})
    assert serialize_match_snapshot(state) == before
    source.tapped = True
    assert attack_payment_view(state, [bear])['payments'] == []
    source.tapped = False
    lose(state, source)
    assert attack_payment_view(state, [bear])['payments'] == []


@pytest.mark.parametrize('seat', [1, 2])
def test_attacking_source_taxes_every_blocker_not_only_its_own(seat):
    state, sid, bear, elf = board(seat, 'block')
    assert state.cards[sid].tapped and sid in state.attackers
    assert block_payment_view(state, [elf])['mana_cost'] == '{1}'
    # Elf cannot block the flying Archangel, but blocking its Bear still costs.
    paid = checked_action(state, RulesEngine(), 3-seat, {'type': 'block', 'blocks': {bear: [elf]}})
    assert paid.blocks == {bear: [elf]} and paid.cards[elf].tapped
    assert paid.players[3-seat].mana_pool['G'] == 0
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert block_payment_view(restored, [elf])['mana_cost'] == '{1}'
    restored.attackers.remove(sid)
    assert block_payment_view(restored, [elf])['payments'] == []


@pytest.mark.parametrize('seat', [1, 2])
def test_source_departure_control_and_suppression_are_live(seat):
    state, sid, bear, elf = board(seat, 'block')
    source = state.cards[sid]
    # This global cost persists while the source is attacking, even if its
    # controller-relative scope is not the creature being blocked.
    assert block_payment_view(state, [elf])['payments']
    lose(state, source)
    assert not block_payment_view(state, [elf])['payments']
    source.counters.clear()
    source.move_to_zone(Zone.GRAVEYARD)
    assert not block_payment_view(state, [elf])['payments']


@pytest.mark.parametrize('status', ['tapped', 'untapped', 'attacking', 'blocking'])
def test_shared_source_status_and_full_or_short_self_names(status):
    state, sid, bear, _ = board()
    source = state.cards[sid]
    source.name = 'Actual Source, Named Test Boundary'
    source.tapped = status == 'tapped'
    state.attackers = [sid] if status == 'attacking' else []
    state.blocks = {bear: [sid]} if status == 'blocking' else {}
    for alias in ['this creature', 'this permanent', source.name.lower(), 'actual source']:
        assert evaluate_static_condition(state, source, state.cards[bear], f'{alias} is {status}') is True
    source.move_to_zone(Zone.GRAVEYARD)
    assert evaluate_static_condition(state, source, source, f'this creature is {status}') is False


@pytest.mark.parametrize('condition', ['you control three or more lands', 'there are three or more cards in your graveyard',
                                     'this permanent has two or more counters on it', 'an unknown predicate',
                                     'it is blue', 'defending player controls an island'])
def test_source_condition_grammar_and_unsupported_recipient_predicates(condition):
    clause = f"as long as {condition}, creatures can't block unless their controller pays {{1}} for each of those creatures"
    supported = condition in {'you control three or more lands', 'there are three or more cards in your graveyard',
                              'this permanent has two or more counters on it'}
    assert bool(parse_static_combat_tax(clause)) == supported
    assert bool(combat_clause_coverage(clause)) != supported


@pytest.mark.parametrize('scope', ['', ' you control', ' your opponents control'])
@pytest.mark.parametrize('controller', [1, 2])
def test_static_block_scope_fixed_before_payment(scope, controller):
    state, sid, bear, elf = board(1, 'block')
    source = state.cards[sid]
    source.controller = controller
    # Explicit parser composition fixture, not an invented card/deck.
    source.oracle_text = f"As long as this creature is untapped, creatures{scope} can't block unless their controller pays {{1}} for each of those creatures."
    source.tapped = False
    taxed = not scope or (controller == 2) == (scope == ' you control')
    assert bool(block_payment_view(state, [elf])['payments']) == taxed
    source.tapped = True
    assert not block_payment_view(state, [elf])['payments']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master', 'master_plus'])
def test_all_ai_declarations_pay_conditional_block_costs(seat, difficulty):
    state, _, bear, elf = board(seat, 'block')
    agent = AIAgent(difficulty)
    action = finalize_declaration(state, {'type': 'block', 'blocks': {bear: [elf]}})
    paid = checked_action(state, RulesEngine(), 3-seat, action)
    assert paid.blocks == {bear: [elf]}
    actual = agent.choose_action(state, RulesEngine().legal_moves(state, 3-seat), 3-seat)
    checked_action(state, RulesEngine(), 3-seat, actual.action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
def test_http_conditional_cost_hints_reject_atomic_and_restore(game, seat, kind):
    import main
    client, match = game
    state, sid, bear, elf = board(seat, kind)
    state.id = match.state.id
    match.state = state
    persist(match)
    actor = seat if kind == 'attack' else 3-seat
    move = next(row for row in client.get(f'/matches/{state.id}/legal-moves?player_id={actor}').json()['moves'] if row['type'] == kind)
    cost = move['attack_costs'][bear][f'player:{3-seat}'] if kind == 'attack' else move['block_costs'][elf]
    assert cost['mana_cost'] == '{1}'
    if kind == 'attack':
        rejected(client, match, {'type': 'attack', 'attackers': [bear, elf]}, seat)
        match.state.players[seat].mana_pool['U'] = 1
        action = {'type': 'attack', 'attackers': [bear]}
    else:
        extra = add(match.state, 'Grizzly Bears', actor)
        persist(match)
        rejected(client, match, {'type': 'block', 'blocks': {bear: [elf, extra.id]}}, actor)
        action = {'type': 'block', 'blocks': {bear: [elf]}}
    persist(match)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': actor, 'action': action})
    assert response.status_code == 200, response.text
    before = snapshot(match)[0]
    main.ACTIVE_MATCHES.pop(state.id)
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(f'/matches/{state.id}').status_code == 200
    assert snapshot(main.ACTIVE_MATCHES[state.id])[0] == before


def test_canonical_coverage_and_resolved_plus_static_costs_are_additive():
    state, sid, _, elf = board(1, 'block')
    assert combat_clause_coverage(state.cards[sid].oracle_text, state.cards[sid].name) == []
    state, _ = activate(state, 'War Cadence', 1, 2)
    view = block_payment_view(state, [elf])
    assert view['mana_cost'] == '{1}{2}'
    assert len(view['payments']) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master', 'master_plus'])
def test_actual_agent_blocks_lethal_flyer_instead_of_profitable_ground_trade(seat, difficulty):
    state, source, bear, elf = board(seat, 'block')
    defender = 3-seat
    drake = conditional_add(state, 'Hinterland Drake', defender)
    state.players[defender].life = 3
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, defender), defender)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'block'
    paid = checked_action(state, rules, defender, decision.action)
    assert paid.blocks == {source: [drake.id]}
    assert paid.cards[elf].tapped  # Mana pays for the flyer blocker, not a ground trade.
    rules.take_action(paid, seat, {'type': 'combat_damage'})
    assert paid.players[defender].life == 1 and paid.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['master', 'master_plus'])
def test_small_board_search_projects_actual_blocks_without_taxes(seat, difficulty):
    state, source, bear, elf = board(seat, 'block')
    defender = 3-seat
    state.cards[source].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].battlefield.remove(source)
    state.players[seat].graveyard.append(source)
    flyer = conditional_add(state, 'Hinterland Drake', seat)
    guard = conditional_add(state, 'Hinterland Drake', defender)
    state.attackers = [flyer.id, bear]
    state.attack_targets = {cid: f'player:{defender}' for cid in state.attackers}
    state.players[defender].life = 2
    rules = RulesEngine()
    decision = AIAgent(difficulty).choose_action(state, rules.legal_moves(state, defender), defender)
    paid = checked_action(state, rules, defender, decision.action)
    assert paid.blocks.get(flyer.id) == [guard.id]
    assert paid.blocks.get(bear) == [elf]
    rules.take_action(paid, seat, {'type': 'combat_damage'})
    assert paid.players[defender].life == 2 and paid.winner is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
def test_tax_condition_preserves_existing_otherwise_continuation(seat, kind):
    from rules_engine.restrictions import card_cant_attack, card_cant_block
    state, sid, bear, elf = board(seat, kind)
    source = state.cards[sid]
    predicate = 'untapped' if kind == 'attack' else 'attacking'
    tax_body = ("creatures can't attack you or planeswalkers you control unless their controller pays {1} for each of those creatures"
                if kind == 'attack' else "creatures can't block unless their controller pays {1} for each of those creatures")
    # Explicit clause-composition boundary, not a new Magic card/deck.
    source.oracle_text = f"As long as this creature is {predicate}, {tax_body}. Otherwise, creatures can't {kind}."
    prohibited = card_cant_attack if kind == 'attack' else card_cant_block
    target = bear if kind == 'attack' else elf
    assert not combat_clause_coverage(source.oracle_text, source.name)
    assert not prohibited(state, target)
    if kind == 'attack':
        source.tapped = True
    else:
        state.attackers.remove(sid)
    assert prohibited(state, target)
    assert not combat_rule_view(state, target)['unsupported']
