"""Bounded production-agent acceptance of canonical affinity payments."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from tests.test_affinity import ROWS
from tests.test_announced_spell_costs import add
from tests.test_graveyard_play_permissions import position


def affinity_position(seat, name, artifacts=0, pool=None):
    state = position(seat)
    for player in state.players.values():
        player.mana_pool = {}
    state.players[seat].mana_pool = dict(pool or {})
    spell = add(state, name, seat, Zone.HAND, cards=ROWS)
    for _ in range(artifacts):
        add(state, 'Frogmite', seat, cards=ROWS)
    return state, spell


def accept_cast(state, spell, seat, spent, agent=None):
    # Strong uses production heuristics without master-only deep search.
    agent = agent or AIAgent(difficulty='strong')
    before = serialize_match_snapshot(state)
    assert agent._can_pay_card_cost(state, seat, spell)
    moves = agent.engine.legal_moves(state, seat)
    assert len(moves) <= 3
    move = next(move for move in moves
                if move['type'] == 'cast_spell' and move.get('card_id') == spell.id)
    assert move.get('cost_options')
    materialized = agent._materialize_action(state, move, seat)
    assert not materialized.get('_invalid_ai_choice')
    assert materialized.get('cost_choice', {}).get('id') in {
        option['id'] for option in move['cost_options']}
    action = agent.choose_action(state, moves, seat).action
    assert action['type'] == 'cast_spell', action
    assert action.get('card_id') == spell.id
    assert not action.get('_invalid_ai_choice')
    assert serialize_match_snapshot(state) == before
    # Execute both the standalone materializer and the actual agent decision.
    for candidate in (materialized, action):
        result = checked_action(state, agent.engine, seat, candidate)
        assert result.cards[spell.id].zone == Zone.STACK
        assert result.stack[-1].source_card_id == spell.id
        assert result.stack[-1].payload['mana_spent'] == spent
        assert sum(result.players[seat].mana_pool.values()) == 0
        assert result.cards[spell.id].mana_cost == ROWS[spell.name]['mana_cost']
        assert serialize_match_snapshot(state) == before
    return result


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,artifacts,pool,spent', [
    ('Frogmite', 3, {'C': 1}, 1),
    ('Frogmite', 4, {}, 0),
    ('Myr Enforcer', 7, {}, 0),
    ("Sojourner's Companion", 7, {}, 0),
    ('Thoughtcast', 4, {'U': 1}, 1),
])
def test_agent_selects_and_executes_discounted_cast(seat, name, artifacts, pool, spent):
    state, spell = affinity_position(seat, name, artifacts, pool)
    result = accept_cast(state, spell, seat, spent)
    assert len(result.players[seat].battlefield) == artifacts
    assert all(not result.cards[cid].tapped for cid in result.players[seat].battlefield)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('pool', [{}, {'C': 1}])
def test_missing_blue_never_repeatedly_selects_thoughtcast(seat, pool):
    state, spell = affinity_position(seat, 'Thoughtcast', 4, pool)
    agent = AIAgent(difficulty='strong', archetype='Control')
    before = serialize_match_snapshot(state)
    for _ in range(3):
        assert not agent._can_pay_card_cost(state, seat, spell)
        moves = agent.engine.legal_moves(state, seat)
        assert len(moves) <= 2
        action = agent.choose_action(state, moves, seat).action
        assert action['type'] == 'pass_priority', action
        assert not action.get('_invalid_ai_choice')
        assert serialize_match_snapshot(state) == before
    # Reusing the same agent must not retain a stale inability to cast.
    state.players[seat].mana_pool = {'U': 1}
    accept_cast(state, spell, seat, 1, agent)


@pytest.mark.parametrize('seat', [1, 2])
def test_higher_printed_cost_land_affinity_is_selected_and_paid(seat):
    state, spell = affinity_position(seat, 'Spire Golem', pool={'C': 3})
    assert spell.mana_cost == '{6}'
    islands = []
    for _ in range(3):
        cid = state.players[seat].library.pop()
        land = state.cards[cid]
        assert land.name == 'Island'
        land.types = ['Land']
        land.type_line = 'Basic Land - Island'
        land.move_to_zone(Zone.BATTLEFIELD)
        land.tapped = True
        state.players[seat].battlefield.append(cid)
        islands.append(cid)
    result = accept_cast(state, spell, seat, 3)
    assert all(result.cards[cid].tapped for cid in islands)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', [
    'Aggro', 'Burn', 'Control', 'Tempo', 'Midrange', 'Ramp', 'Drain',
    'Aristocrats', 'Tokens', 'Tribal',
])
@pytest.mark.parametrize('artifacts,pool,spent', [
    (3, {'C': 1}, 1),
    (4, {}, 0),
], ids=['cheap', 'free'])
def test_strong_styles_accept_single_affordable_affinity_artifact(
        seat, style, artifacts, pool, spent):
    # One affordable spell tests the cost path, not tactical superiority or balance.
    state, spell = affinity_position(seat, 'Frogmite', artifacts, pool)
    agent = AIAgent(difficulty='strong', archetype=style)
    result = accept_cast(state, spell, seat, spent, agent)
    assert len(result.players[seat].battlefield) == artifacts
    assert all(not result.cards[cid].tapped for cid in result.players[seat].battlefield)


def test_master_accepts_free_affinity_artifact_cost_path():
    # A single small-state Master decision is not expert-play acceptance.
    state, spell = affinity_position(1, 'Frogmite', artifacts=4)
    agent = AIAgent(difficulty='master', archetype='Midrange')
    accept_cast(state, spell, 1, 0, agent)
