"""Canonical checked terminal outcomes; attack endpoint ranking is utility-only.

Old-board creatures and mana are declared fixtures, not paid creature births.
The attack-search test injects genuinely resolved endpoints, not attack results;
it does not certify a complete AI attack or response decision.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind
from tests.vraska_full.test_full_vraska import bare, add, act, settle, Zone, Step


FIXTURES = Path(__file__).parent / 'fixtures' / 'ai_terminal_draw'
PINS = {
    'crypt-rats': 'a0337f0db28bf0b3a82073d59eef869bf517b800720f9339437858d06fcba70d',
    'darksteel-sentinel': 'cb8502e81d51884b604f60b56ca9adc85b8d943afde1ae585b714192f58bd423',
    'rumbling-baloth': 'ab65a43726637e99f78134b45ae3ad6a5a3043001b38af30307b2f960f0a82fd',
    'grizzly-bears': '150049326ad0c3b914719c54709331b3a51d11a18c02dde60c64246f3ac8239c',
    'lightning-bolt': 'e5c62f8029d332d232605077fcdd73549f7383fdc8f610da97c071b242e3d787',
}


def raw(name):
    data = (FIXTURES / (name + '.raw.json')).read_bytes()
    assert hashlib.sha256(data).hexdigest() == PINS[name]
    return json.loads(data)


def paid_bolt(state, actor, target):
    bolt = add(state, raw('lightning-bolt'), actor, Zone.HAND)
    state.players[actor].mana_pool = {'R': 1}
    offered = RulesEngine().legal_moves(state, actor)
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == bolt.id for m in offered)
    state = act(state, actor, {'type': 'cast_spell', 'card_id': bolt.id,
                              'targets': {'target_player': target}})
    assert state.stack[-1].payload['mana_spent'] == 1
    assert stack_object_kind(state, state.stack[-1]) == 'spell'
    assert state.cards[bolt.id].oracle_text == raw('lightning-bolt')['oracle_text']
    assert state.players[actor].mana_pool.get('R', 0) == 0
    return state


@pytest.fixture(scope='module', params=[1, 2])
def endpoints(request):
    seat = request.param
    root = bare(3 - seat)
    for pid in root.players:
        root.players[pid].life = 2
        root.players[pid].mana_pool = {}
    rats = add(root, raw('crypt-rats'), seat, Zone.BATTLEFIELD, old_board=True)
    for _ in range(3):
        add(root, raw('grizzly-bears'), seat, Zone.BATTLEFIELD, old_board=True)
    root.players[seat].mana_pool = {'B': 2}
    root = paid_bolt(root, 3 - seat, seat)
    root = act(root, 3 - seat, {'type': 'pass_priority'})
    assert root.priority_player == seat and root.winner is None
    assert root.cards[rats.id].oracle_text == raw('crypt-rats')['oracle_text']
    original = serialize_match_snapshot(root)
    losing = settle(act(root, seat, {'type': 'pass_priority'}))
    draw = act(root, seat, {'type': 'activate_ability', 'card_id': rats.id,
                            'ability_index': 0, 'targets': {'x_value': 2}})
    assert stack_object_kind(draw, draw.stack[-1]) == 'activated'
    assert draw.stack[-1].effect_key == 'damage_each_creature_and_player'
    assert draw.stack[-1].payload['amount'] == 2
    assert draw.players[seat].mana_pool.get('B', 0) == 0
    draw = settle(draw)
    winning = bare(seat)
    for pid in winning.players:
        winning.players[pid].life = 2
        winning.players[pid].mana_pool = {}
    winning = settle(paid_bolt(winning, seat, 3 - seat))
    assert serialize_match_snapshot(root) == original
    assert draw.winner == 0 and all(p.life == 0 for p in draw.players.values())
    assert losing.winner == 3 - seat and losing.players[seat].life == -1
    assert winning.winner == seat and winning.players[3 - seat].life == -1
    assert draw.cards[rats.id].zone == Zone.GRAVEYARD
    assert losing.cards[rats.id].zone == Zone.BATTLEFIELD
    return seat, root, rats.id, draw, losing, winning


def test_canonical_checked_outcomes_and_pinned_full_bodies(endpoints):
    seat, root, rats, draw, losing, winning = endpoints
    assert root.cards[rats].oracle_text == raw('crypt-rats')['oracle_text']
    assert draw.winner == 0
    assert losing.winner == 3 - seat
    assert winning.winner == seat
    assert len(draw.stack) == 1  # The paid Bolt is not resolved after the draw.


def test_strategic_features_neutral_draw_preserves_win_and_loss(endpoints):
    seat, root, rats, draw, losing, winning = endpoints
    agent = AIAgent(difficulty='master', archetype='Midrange')
    assert agent._strategic_features(winning, seat) == 200.75
    assert agent._strategic_features(losing, seat) == -200.75
    assert agent._strategic_features(draw, seat) == 0.0


def test_rollout_delta_neutral_draw_preserves_win_and_loss(endpoints):
    seat, root, rats, draw, losing, winning = endpoints
    agent = AIAgent(difficulty='master_plus', archetype='Midrange')
    action = {'type': 'pass_priority'}
    assert agent._rollout_delta(winning, action, seat) == 100.0
    assert agent._rollout_delta(losing, action, seat) == -100.0
    assert agent._rollout_delta(draw, action, seat) == 0.0


def test_rollout_playout_neutral_draw_preserves_win_and_loss(endpoints):
    seat, root, rats, draw, losing, winning = endpoints
    agent = AIAgent(difficulty='master_plus', archetype='Midrange')
    assert agent._rollout_playout(winning, seat, 0) == 40.0
    assert agent._rollout_playout(losing, seat, 0) == -40.0
    assert agent._rollout_playout(draw, seat, 0) == 0.0


def test_attack_endpoint_ranking_prefers_checked_draw_to_defeat(endpoints, monkeypatch):
    seat, root, rats, draw, losing, winning = endpoints
    agent = AIAgent(difficulty='master', archetype='Midrange')
    before = {name: serialize_match_snapshot(game)
              for name, game in [('root', root), ('draw', draw), ('lose', losing), ('win', winning)]}

    # Only endpoint delivery is injected. Both terminal outcomes were checked above.
    # This isolates production rank utility, not a claim these are combat projections.
    def project(state, player, subset):
        assert state is root and player == seat
        return deepcopy(draw if subset else losing), list(subset)

    monkeypatch.setattr(agent, '_project_attack_line', project)
    selected = agent._search_attack_assignments(root, [rats], seat, force=True)
    assert {name: serialize_match_snapshot(game)
            for name, game in [('root', root), ('draw', draw), ('lose', losing), ('win', winning)]} == before
    assert selected == [rats], 'A resolved draw must outrank defeat despite material retained in the losing endpoint'


@pytest.mark.parametrize('seat', [1, 2])
def test_offered_native_allocation_kills_destructible_blocker_instead_of_wasting_damage(seat):
    state = bare(seat)
    for player in state.players.values():
        player.mana_pool = {}
    state.step = Step.DECLARE_ATTACKERS
    state.mechanic_choice_players = {1, 2}
    attacker = add(state, raw('rumbling-baloth'), seat, Zone.BATTLEFIELD, old_board=True).id
    sentinel = add(state, raw('darksteel-sentinel'), 3 - seat, Zone.BATTLEFIELD, old_board=True).id
    bear = add(state, raw('grizzly-bears'), 3 - seat, Zone.BATTLEFIELD, old_board=True).id
    state = act(state, seat, {'type': 'attack', 'attackers': [attacker],
                              'attack_targets': {attacker: 'player:' + str(3 - seat)}})
    for _ in range(40):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == 3 - seat:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == 3 - seat
    state = act(state, 3 - seat, {'type': 'block', 'blocks': {attacker: [sentinel, bear]}})
    for _ in range(40):
        if state.pending_mechanic_choice:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'combat_damage' and pending['source_id'] == attacker
    assert pending['player_id'] == seat and pending['count'] == 4
    assert set(pending['options']) == {sentinel, bear}
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move['type'] == 'choose_mechanic' and move['kind'] == 'combat_damage' for move in moves)
    before = serialize_match_snapshot(state)
    decision = AIAgent(difficulty='master').choose_action(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    ai_result = act(state, seat, decision.action)
    alternative = act(state, seat, {'type': 'choose_mechanic',
                                    'damage_assignment': {sentinel: 2, bear: 2}})
    assert alternative.cards[bear].zone == Zone.GRAVEYARD
    assert alternative.cards[sentinel].zone == Zone.BATTLEFIELD
    assert alternative.cards[attacker].zone == Zone.GRAVEYARD
    assert ai_result.cards[sentinel].zone == Zone.BATTLEFIELD
    assert ai_result.cards[attacker].zone == Zone.GRAVEYARD
    assert ai_result.winner is None and alternative.winner is None
    print('PUBLIC_ALLOCATION', seat, decision.action['damage_assignment'],
          ai_result.cards[bear].zone.value, alternative.cards[bear].zone.value)
    assert ai_result.cards[bear].zone == Zone.GRAVEYARD
