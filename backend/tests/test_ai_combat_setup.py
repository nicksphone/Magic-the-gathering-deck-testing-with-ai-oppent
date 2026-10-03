"""Canonical public-board setup decisions, not competitive deck templates."""
import pytest

from ai.agent import AIAgent
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action
from tests.test_bestow import cast_board
from tests.test_aura_costs import add as aura_add
from tests.test_restricted_mana import add as restricted_add
from tests.test_ai_recurring_engines import resolve
from tests.test_pending_removal import add_card as pending_add
from tests.test_api_input_contracts import game


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('archetype', ['Aggro', 'Tempo', 'Control', 'Ramp', 'Tokens', 'Tribal'])
@pytest.mark.parametrize('kind', ['bestow', 'aura', 'equip', 'pump', 'removal'])
def test_actual_master_setup_choice_forecasts_and_executes_winning_combat(seat, archetype, kind):
    state, source, host = cast_board(seat, 4)
    host.summoning_sick = False
    state.turn = 3
    state.players[3-seat].life = 4
    if kind != 'bestow':
        state.players[seat].hand.remove(source.id)
        source.move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(source.id)
        if kind == 'aura':
            source = aura_add(state, 'Rancor', seat, Zone.HAND)
        elif kind == 'equip':
            source = restricted_add(state, 'Bonesplitter', seat)
        elif kind == 'pump':
            source = pending_add(state, 'Giant Growth', Zone.HAND, seat)
            state.players[3-seat].life = 5
        else:
            source = pending_add(state, 'Go for the Throat', Zone.HAND, seat)
            state.players[seat].mana_pool['B'] = 2
            state.players[3-seat].life = 2
            aura_add(state, 'Colossal Dreadmaw', 3-seat)
    agent = AIAgent('master', archetype=archetype)
    before = serialize_match_snapshot(state)
    decision = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['card_id'] == source.id
    if kind == 'bestow':
        assert decision.action['cost_choice']['id'] == 'bestow'
    if kind == 'equip':
        assert decision.action['type'] == 'equip'
    tactical = agent._tactical_combat_setup_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert tactical and tactical['card_id'] == source.id
    if kind != 'removal':
        assert decision.reasoning == 'Public-board combat setup forecasts a winning attack'
    result = resolve(checked_action(state, RulesEngine(), seat, decision.action))
    rules = RulesEngine()
    while result.step != Step.DECLARE_ATTACKERS:
        rules.next_step(result)
    projected = agent._project_attack_line(result, seat, [host.id])
    assert projected is not None and projected[0].winner == seat


@pytest.mark.parametrize('restriction', ['sick', 'tapped', 'blocked', 'postcombat', 'underfunded'])
def test_nonwinning_or_illegal_setup_does_not_claim_lethal(restriction):
    state, source, host = cast_board()
    host.summoning_sick = restriction == 'sick'
    host.tapped = restriction == 'tapped'
    state.players[2].life = 4
    if restriction == 'blocked':
        aura_add(state, 'Colossal Dreadmaw', 2)
    if restriction == 'postcombat':
        state.step = Step.POSTCOMBAT_MAIN
    if restriction == 'underfunded':
        state.players[1].mana_pool['G'] = 2
    before = serialize_match_snapshot(state)
    agent = AIAgent('master', archetype='Tempo')
    assert agent._tactical_combat_setup_action(state, RulesEngine().legal_moves(state, 1), 1) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_already_winning_board_preserves_cards_and_moves_toward_combat(seat):
    state, source, host = cast_board(seat)
    host.summoning_sick = False
    host.counters['+1/+1'] = 2
    state.players[3-seat].life = 4
    before = serialize_match_snapshot(state)
    agent = AIAgent('master', archetype='Tempo')
    decision = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert decision.action == {'type': 'pass_priority'}
    assert serialize_match_snapshot(state) == before


def test_hidden_zone_change_or_unresolved_choice_is_unknown_not_lethal():
    from ai.pending_effects import planning_copy
    from rules_engine.stack_engine import add_to_stack
    state, source, host = cast_board()
    host.summoning_sick = False
    host.counters['+1/+1'] = 2
    state.players[2].life = 4
    before = serialize_match_snapshot(state)
    simulated = planning_copy(state)
    add_to_stack(simulated, source.id, 1, 'Known draw instruction', 'draw_cards', {'amount': 1})
    agent = AIAgent('master')
    assert agent._setup_combat_forecast(simulated, 1) is None
    simulated = planning_copy(state)
    simulated.pending_mechanic_choice = {'kind': 'test_unknown', 'player_id': 2}
    assert agent._setup_combat_forecast(simulated, 1) is None
    simulated = planning_copy(state)
    simulated.log.append('Oracle effect not inferred: diagnostic fixture')
    assert agent._setup_combat_forecast(simulated, 1) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_http_autoplay_chooses_bestow_persists_and_completes_real_combat(game, seat):
    import main
    from tests.test_api_input_contracts import persist
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, source, host = cast_board(seat)
    state.id = match.state.id
    host.summoning_sick = False
    state.players[3-seat].life = 4
    match.state = state
    match.controllers = {1: 'ai', 2: 'ai'}
    match.ai = {pid: AIAgent('master', archetype='Tempo') for pid in (1, 2)}
    match.best_of = 1
    persist(match)
    response = client.post(f'/matches/{state.id}/autoplay?ticks=1')
    assert response.status_code == 200, response.text
    assert match.state.cards[source.id].bestow_characteristics
    assert match.state.players[seat].mana_pool['G'] == 0
    committed = serialize_match_snapshot(match.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert serialize_match_snapshot(restored.state) == committed
    response = client.post(f'/matches/{state.id}/autoplay?ticks=100')
    assert response.status_code == 200, response.text
    assert restored.match_complete and restored.state.winner == seat
