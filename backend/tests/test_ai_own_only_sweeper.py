"""Canonical public pose from a closed TRAIN flag, not a replayed match."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.pending_effects import friendly_destruction_profit
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ai_recurring_engines import add, fixture
from tests.pending_permanent_fullraw import raw_card
from tests.test_any_player_cast_damage import settle


RAW = json.loads((Path(__file__).parent / 'fixtures/ai_burn_foretell/CANONICAL-RAW.json').read_bytes())
RECEIPTS = []


def own_only_pose(seat):
    state = fixture()
    state.turn = 15
    state.active_player = state.priority_player = seat
    state.players[seat].life = 11
    state.players[3-seat].life = 12
    for player in state.players.values():
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
        player.snow_mana_pool.clear()
    for name in ['Island'] * 5 + ['Plains'] * 3:
        add(state, name, seat, cards=RAW)
    for i, name in enumerate(['Mountain', 'Plains', 'Mountain', 'Mountain', 'Plateau', 'Mountain', 'Plains']):
        add(state, name, 3-seat, cards=RAW).tapped = i < 3
    for name in ['Cosmos Charger', 'Augury Raven']:
        body = add(state, name, seat, cards=RAW)
        body.summoning_sick = False
    wipe = add(state, 'Doomskar', seat, Zone.HAND, cards=RAW)
    add(state, 'Swords to Plowshares', seat, Zone.HAND, cards=RAW)
    add(state, 'Island', seat, Zone.HAND, cards=RAW)
    add(state, 'Plains', 3-seat, Zone.HAND, cards=RAW)
    # The recorded land drop already happened immediately before the flagged cast.
    state.players[seat].lands_played_this_turn = 1
    state.players[seat].last_land_play_turn = state.turn
    state.players[seat].land_plays_recorded_on_turn = 1
    return state, wipe


@pytest.mark.parametrize('seat', [1, 2])
def test_master_does_not_wipe_only_own_ready_flyers(seat):
    state, wipe = own_only_pose(seat)
    rules = RulesEngine()
    moves = rules.legal_moves(state, seat)
    assert not any(move['type'] == 'play_land' for move in moves)
    assert any(move.get('card_id') == wipe.id and move['type'] == 'cast_spell' for move in moves)
    before = serialize_match_snapshot(state)
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    decision = agent.choose_action(state, moves, seat)
    checked_action(state, rules, seat, decision.action)
    assert serialize_match_snapshot(state) == before
    RECEIPTS.append({'seat': seat, 'initial': before, 'offers': moves,
                     'decision': decision.action, 'reasoning': decision.reasoning})
    print(json.dumps({'seat': seat, 'action': decision.action, 'reasoning': decision.reasoning}))
    assert not (decision.action.get('type') == 'cast_spell'
                and decision.action.get('card_id') == wipe.id), decision.reasoning


@pytest.mark.parametrize('seat', [1, 2])
def test_known_unprofitable_own_sweep_is_removed_before_all_planners(seat):
    state, wipe = own_only_pose(seat)
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    moves = agent.engine.legal_moves(state, seat)
    action = {'type': 'cast_spell', 'card_id': wipe.id, 'targets': {}}
    before = serialize_match_snapshot(state)
    assert friendly_destruction_profit(state, seat, action) is False
    kept = agent._without_losing_mass_destruction(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    assert not any(move['type'] == 'cast_spell' and move.get('card_id') == wipe.id for move in kept)
    assert any(move['type'] == 'pass_priority' for move in kept)
    assert any(move['type'] == 'foretell' and move.get('card_id') == wipe.id for move in kept)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enemy', [False, True])
def test_empty_or_enemy_board_does_not_use_own_only_certificate(monkeypatch, seat, enemy):
    state, _ = own_only_pose(seat)
    if enemy:
        add(state, 'Serra Angel', 3-seat, cards=RAW)
    else:
        for cid in list(state.players[seat].battlefield):
            if 'Creature' in state.cards[cid].types:
                state.players[seat].battlefield.remove(cid)
                state.players[seat].graveyard.append(cid)
                state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    moves = agent.engine.legal_moves(state, seat)
    def unexpected(*args, **kwargs):
        raise AssertionError('Not an own-only sweep')
    monkeypatch.setattr('ai.pending_effects.friendly_destruction_profit', unexpected)
    assert agent._without_losing_mass_destruction(state, moves, seat) == moves


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_own_death_win_remains_admitted(seat):
    state, wipe = own_only_pose(seat)
    add(state, 'Bastion of Remembrance', seat,
        cards={'Bastion of Remembrance': raw_card('Bastion of Remembrance')})
    state.players[3-seat].life = 2
    action = {'type': 'cast_spell', 'card_id': wipe.id, 'targets': {}}
    before = serialize_match_snapshot(state)
    forecast = friendly_destruction_profit(state, seat, action)
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    moves = agent.engine.legal_moves(state, seat)
    kept = agent._without_losing_mass_destruction(state, moves, seat)
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == wipe.id for move in kept)
    result = settle(checked_action(state, agent.engine, seat, action))
    print(json.dumps({'case': 'death_win', 'seat': seat, 'forecast': forecast,
                      'winner': result.winner, 'life': {pid: p.life for pid, p in result.players.items()},
                      'log': result.log[-12:]}))
    # Simultaneous trigger ordering is deliberately unknown without a policy.
    assert forecast is None, forecast
    assert result.winner == seat and result.players[3-seat].life == 0
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('certificate', [True, None])
def test_profit_provider_protocol_keeps_completed_positive_and_unknown(monkeypatch, certificate):
    """Caller contract only, not a fabricated canonical winning outcome."""
    state, wipe = own_only_pose(1)
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    moves = agent.engine.legal_moves(state, 1)
    calls = []
    def provider(game, player, action):
        calls.append((player, action['card_id']))
        return certificate
    monkeypatch.setattr('ai.pending_effects.friendly_destruction_profit', provider)
    assert agent._without_losing_mass_destruction(state, moves, 1) == moves
    assert calls == [(1, wipe.id)]


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_unresolved_death_choice_is_not_rejected_as_unprofitable(seat):
    state, wipe = own_only_pose(seat)
    add(state, 'Blood Artist', seat, cards={'Blood Artist': raw_card('Blood Artist')})
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = state.mechanic_choice_players = {1, 2}
    action = {'type': 'cast_spell', 'card_id': wipe.id, 'targets': {}}
    before = serialize_match_snapshot(state)
    assert friendly_destruction_profit(state, seat, action) is None
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    moves = agent.engine.legal_moves(state, seat)
    assert agent._without_losing_mass_destruction(state, moves, seat) == moves
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('turn', [15, 20, 30])
def test_healthy_control_does_not_exile_own_flyer_to_force_progress(seat, turn):
    from ai.heuristics import evaluate_board, _board_value
    state, _ = own_only_pose(seat)
    state.turn = state.players[seat].last_land_play_turn = turn
    state.players[seat].life = 20
    sword = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Swords to Plowshares')
    target = next(cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Cosmos Charger')
    action = {'type': 'cast_spell', 'card_id': sword, 'targets': {'target_card_id': target}}
    before = serialize_match_snapshot(state)
    result = settle(checked_action(state, RulesEngine(), seat, action))
    metrics = {'life_before': state.players[seat].life, 'life_after': result.players[seat].life,
               'material_before': _board_value(state, seat), 'material_after': _board_value(result, seat),
               'value_before': evaluate_board(state, seat), 'value_after': evaluate_board(result, seat)}
    assert result.players[seat].life == 23 and result.cards[target].zone == Zone.EXILE
    assert metrics['value_after'] < metrics['value_before']
    assert friendly_destruction_profit(state, seat, action) is False
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    moves = agent.engine.legal_moves(state, seat)
    decision = agent.choose_action(state, moves, seat)
    checked_action(state, agent.engine, seat, decision.action)
    assert serialize_match_snapshot(state) == before
    RECEIPTS.append({'case': 'healthy_self_exile', 'seat': seat, 'turn': turn, 'metrics': metrics,
                     'initial': before, 'offers': moves, 'decision': decision.action,
                     'reasoning': decision.reasoning, 'tags': sorted(agent._spell_tags(state.cards[sword]))})
    assert decision.action.get('card_id') != sword, decision.reasoning


@pytest.mark.parametrize('seat', [1, 2])
def test_self_exile_still_saves_low_life_from_native_burn(seat):
    state, _ = own_only_pose(seat)
    state.players[seat].life = 2
    rules = RulesEngine()
    burn = add(state, 'Skullcrack', 3-seat, Zone.HAND, cards=RAW)
    state = checked_action(state, rules, seat, {'type': 'pass_priority'})
    state = checked_action(state, rules, 3-seat, {'type': 'cast_spell', 'card_id': burn.id,
                                               'targets': {'target_player': seat}})
    state = checked_action(state, rules, 3-seat, {'type': 'pass_priority'})
    before = serialize_match_snapshot(state)
    baseline = settle(state)
    assert baseline.winner == 3-seat
    agent = AIAgent('master', 'Control', opponent_archetype='Burn')
    decision = agent.choose_action(state, rules.legal_moves(state, seat), seat)
    assert state.cards[decision.action.get('card_id')].name == 'Swords to Plowshares'
    assert friendly_destruction_profit(state, seat, decision.action) is True
    saved = settle(checked_action(state, rules, seat, decision.action))
    assert saved.winner is None and saved.players[seat].life == 2
    assert serialize_match_snapshot(state) == before
