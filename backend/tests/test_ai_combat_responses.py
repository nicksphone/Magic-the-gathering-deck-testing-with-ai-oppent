"""Actual post-block decisions and checked combat, using canonical card data."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import fixture, add
from tests.test_devotion import ROWS
from tests.test_pending_removal import add_card
from tests.test_api_input_contracts import game, persist


def combat_board(seat=1, name='Aspect of Hydra', life=4, *, crowded=False):
    state = fixture()
    state.active_player = state.priority_player = seat
    state.step = Step.DECLARE_ATTACKERS
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    state.players[3-seat].life = life
    host = add(state, 'Burning-Tree Emissary', seat, cards=ROWS)
    host.summoning_sick = False
    attackers = [host.id]
    blocks = {}
    if crowded:
        larger = add(state, 'Torrential Gearhulk', seat)
        larger.summoning_sick = False
        blocker = add(state, 'Torrential Gearhulk', 3-seat)
        attackers.append(larger.id)
        blocks[larger.id] = [blocker.id]
    spell = (add(state, name, seat, Zone.HAND, cards=ROWS) if name in ROWS
             else add_card(state, name, Zone.HAND, seat))
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {'type': 'attack', 'attackers': attackers})
    rules.next_step(state)
    state = checked_action(state, rules, 3-seat, {'type': 'block', 'blocks': blocks})
    while state.priority_player != seat:
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.blockers_declared
    # Step transitions empty mana; this resource belongs to the response window.
    state.players[seat].mana_pool['G'] = 1
    return state, spell.id, host.id


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('archetype', ['Aggro', 'Tempo', 'Control', 'Ramp', 'Tokens', 'Tribal'])
@pytest.mark.parametrize('name', ['Aspect of Hydra', 'Giant Growth'])
def test_master_uses_winning_post_block_pump_and_checked_damage(seat, archetype, name):
    state, spell, host = combat_board(seat, name)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    agent = AIAgent('master', archetype=archetype)
    rules = RulesEngine()
    decision = agent.choose_action(state, rules.legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == spell
    assert decision.action['targets']['target_card_id'] == host
    assert_checked_win(state, rules, seat, decision.action)


def assert_checked_win(state, rules, seat, action):
    state = checked_action(state, rules, seat, action)
    assert state.players[seat].mana_pool['G'] == 0
    for _ in range(12):
        if state.winner is not None:
            break
        state = checked_action(state, rules, state.priority_player, {'type': 'pass_priority'})
    assert state.winner == seat and state.players[3-seat].life <= 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Aspect of Hydra', 'Giant Growth'])
def test_winning_recipient_beats_larger_but_blocked_recipient(seat, name):
    state, spell, host = combat_board(seat, name, crowded=True)
    agent = AIAgent('master', archetype='Tempo')
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    decision = agent.choose_action(state, rules.legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'cast_spell'
    assert decision.action['card_id'] == spell
    assert decision.action['targets']['target_card_id'] == host
    assert_checked_win(state, rules, seat, decision.action)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['already_lethal', 'not_lethal', 'underfunded', 'not_declared'])
def test_no_proved_win_does_not_force_a_pump(seat, case):
    state, spell, host = combat_board(seat)
    if case == 'already_lethal':
        state.players[3-seat].life = 2
    elif case == 'not_lethal':
        state.players[3-seat].life = 20
    elif case == 'underfunded':
        state.players[seat].mana_pool['G'] = 0
    else:
        state.blockers_declared = False
    agent = AIAgent('master', archetype='Tempo')
    before = serialize_match_snapshot(state)
    action = agent._tactical_combat_setup_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert action == ({'type': 'pass_priority'} if case == 'already_lethal' else None)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('unknown', ['draw', 'choice', 'unsupported'])
def test_unknown_response_outcome_is_not_claimed_as_winning(seat, unknown):
    from ai.pending_effects import planning_copy
    from rules_engine.stack_engine import add_to_stack
    state, spell, host = combat_board(seat)
    projected = planning_copy(state)
    if unknown == 'draw':
        add_to_stack(projected, spell, seat, 'Canonical draw instruction', 'draw_cards', {'amount': 1})
    elif unknown == 'choice':
        projected.pending_mechanic_choice = {'kind': 'unknown_fixture', 'player_id': seat}
    else:
        projected.log.append('Oracle effect not inferred: diagnostic fixture')
    agent = AIAgent('master')
    assert agent._setup_combat_forecast(projected, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_http_autoplay_casts_pump_and_restored_game_finishes_combat(game, seat):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    state, spell, host = combat_board(seat)
    state.id = match.state.id
    match.state = state
    match.controllers = {1: 'ai', 2: 'ai'}
    match.ai = {pid: AIAgent('master', archetype='Tempo') for pid in (1, 2)}
    match.best_of = 1
    persist(match)
    response = client.post(f'/matches/{state.id}/autoplay?ticks=1')
    assert response.status_code == 200, response.text
    assert match.state.cards[spell].zone == Zone.STACK
    assert match.state.players[seat].mana_pool['G'] == 0
    committed = serialize_match_snapshot(match.state)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert serialize_match_snapshot(restored.state) == committed
    response = client.post(f'/matches/{state.id}/autoplay?ticks=20')
    assert response.status_code == 200, response.text
    assert restored.match_complete and restored.state.winner == seat
