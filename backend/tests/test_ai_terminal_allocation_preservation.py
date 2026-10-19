"""Real rules controls; frozen method projections are comparison-only oracles.

Keyword grants/removals and counters are explicit old-board fixture boundaries,
not certificates for paid acquisition of those effects.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import ai.agent as production
from ai.agent import AIAgent, _terminal_utility
from game_state.serializers import serialize_match_snapshot
from rules_engine import combat
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_ai_terminal_draw_product import endpoints, raw
from tests.vraska_full.test_full_vraska import bare, add, act, Zone, Step


PREIMAGE = Path(__file__).parent / 'fixtures' / 'ai_terminal_draw' / 'agent-3a7-methods.json'
DATA = PREIMAGE.read_bytes()
assert hashlib.sha256(DATA).hexdigest() == 'df7e3d77e26c1918f9741335a7bc7721ed9fd9cdf5a559570f47b3f4cca64df7'
METHODS = json.loads(DATA)
assert METHODS['source_sha256'] == 'dec33731dd3298eb86f9b2467de5fd336bb4189e1f9d7b6880e63aeafce85bfb'


def original(name):
    namespace = dict(vars(production))
    exec(compile(METHODS['methods'][name], '<frozen-3a7-method-comparison>', 'exec'), namespace)
    return namespace[name]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('magnitude', [200.0, 1000.0, 100.0, 40.0])
def test_terminal_helper_exact_scale_and_nonterminal_sentinel(seat, magnitude):
    assert _terminal_utility(None, seat, magnitude) is None
    assert _terminal_utility(0, seat, magnitude) == 0.0
    assert _terminal_utility(seat, seat, magnitude) == magnitude
    assert _terminal_utility(3 - seat, seat, magnitude) == -magnitude


def test_nonterminal_and_existing_win_loss_methods_match_frozen_3a7(endpoints):
    seat, root, rats, draw, losing, winning = endpoints
    nonterminal = bare(seat)
    for style in ('Midrange', 'Aggro', 'Control'):
        agent = AIAgent(difficulty='master_plus', archetype=style)
        for state in (nonterminal, losing, winning):
            assert agent._strategic_features(state, seat) == original('_strategic_features')(agent, state, seat)
            assert agent._rollout_playout(deepcopy(state), seat, 0) == original('_rollout_playout')(agent, deepcopy(state), seat, 0)
        for state in (losing, winning):
            assert agent._rollout_delta(state, {'type': 'pass_priority'}, seat) == original('_rollout_delta')(agent, state, {'type': 'pass_priority'}, seat)
    agent = AIAgent(difficulty='master_plus')
    before = serialize_match_snapshot(nonterminal)
    assert agent._rollout_delta(nonterminal, {'type': 'pass_priority'}, seat) == original('_rollout_delta')(agent, nonterminal, {'type': 'pass_priority'}, seat)
    assert serialize_match_snapshot(nonterminal) == before


def test_search_nonterminal_and_win_loss_endpoint_ranks_match_frozen_3a7(endpoints, monkeypatch):
    seat, root, rats, draw, losing, winning = endpoints
    agent = AIAgent(difficulty='master')
    # Comparison-only endpoint delivery; not a claim of genuine attack results.
    for terminal in (root, losing, winning):
        monkeypatch.setattr(agent, '_project_attack_line',
                            lambda game, actor, subset: (deepcopy(terminal), list(subset)))
        assert agent._search_attack_assignments(root, [rats], seat, force=True) == original('_search_attack_assignments')(agent, root, [rats], seat, force=True)


def test_actual_terminal_callers_keep_their_original_magnitudes(endpoints, monkeypatch):
    seat, root, rats, draw, losing, winning = endpoints
    actual = production._terminal_utility
    calls = []

    def record(winner, player, magnitude):
        calls.append((winner, player, magnitude))
        return actual(winner, player, magnitude)

    monkeypatch.setattr(production, '_terminal_utility', record)
    agent = AIAgent(difficulty='master_plus')
    for state in (draw, losing, winning):
        calls.clear()
        agent._strategic_features(state, seat)
        assert calls == [(state.winner, seat, 200.0)]
        calls.clear()
        agent._rollout_delta(state, {'type': 'pass_priority'}, seat)
        assert calls == [(state.winner, seat, 100.0)]
        calls.clear()
        agent._rollout_playout(state, seat, 0)
        assert calls == [(state.winner, seat, 40.0)]
        calls.clear()
        monkeypatch.setattr(agent, '_project_attack_line',
                            lambda game, actor, subset: (deepcopy(state), list(subset)))
        agent._search_attack_assignments(root, [rats], seat, force=True)
        assert calls == [(state.winner, seat, 1000.0)] * 2


def offered_combat(seat, *, trample=False, deathtouch=False, marked=False,
                   foreign_chooser=False, suppress_sentinel=False):
    state = bare(seat)
    state.step = Step.DECLARE_ATTACKERS
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {}
    attacker = add(state, raw('rumbling-baloth'), seat, Zone.BATTLEFIELD, old_board=True).id
    sentinel = add(state, raw('darksteel-sentinel'), 3 - seat, Zone.BATTLEFIELD, old_board=True).id
    bear = add(state, raw('grizzly-bears'), 3 - seat, Zone.BATTLEFIELD, old_board=True).id
    if trample:
        add_keyword_effect(state, attacker, ['trample'])
        if not marked:
            state.cards[attacker].counters['+1/+1'] = 2
    if deathtouch:
        add_keyword_effect(state, attacker, ['deathtouch'])
    if marked:
        state.cards[bear].counters['__damage_marked'] = 1
    if foreign_chooser:
        add_keyword_effect(state, bear, ['banding'])
    if suppress_sentinel:
        add_keyword_effect(state, sentinel, ['indestructible'], operation='remove')
    assert state.cards[sentinel].oracle_text == raw('darksteel-sentinel')['oracle_text']
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
    choice = state.pending_mechanic_choice
    assert choice['kind'] == 'combat_damage' and choice['source_id'] == attacker
    assert choice['player_id'] == (3 - seat if foreign_chooser else seat)
    return state, attacker, sentinel, bear, choice


@pytest.mark.parametrize('seat', [1, 2])
def test_foreign_controller_protection_branch_and_remaining_algorithm_exact(seat):
    state, attacker, sentinel, bear, choice = offered_combat(seat, foreign_chooser=True)
    agent = AIAgent()
    before = serialize_match_snapshot(state)
    current = agent._choose_combat_damage_allocation(state, choice)
    assert current == original('_choose_combat_damage_allocation')(agent, state, choice)
    assert combat.valid_damage_assignment(state, 3 - seat, {'damage_assignment': current})
    act(state, 3 - seat, {'type': 'choose_mechanic', 'damage_assignment': current})
    assert serialize_match_snapshot(state) == before

    # Whole method recovers exactly by deleting only the one authorized stable sort.
    tree = ast.parse(Path(production.__file__).read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == '_choose_combat_damage_allocation')
    source = ast.get_source_segment(Path(production.__file__).read_text(), method)
    addition = '        creatures.sort(key=lambda target: has_keyword(state, target, "indestructible"))\n'
    assert source.count(addition) == 1
    assert source.replace(addition, '') == METHODS['methods']['_choose_combat_damage_allocation']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('deathtouch', [False, True])
def test_trample_still_requires_lethal_assignment_to_indestructible(seat, deathtouch):
    state, attacker, sentinel, bear, choice = offered_combat(seat, trample=True, deathtouch=deathtouch)
    assert has_keyword(state, sentinel, 'indestructible')
    action = AIAgent().choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    amounts = action['damage_assignment']
    assert amounts[sentinel] == (1 if deathtouch else 3)
    assert amounts[bear] == (1 if deathtouch else 2)
    assert amounts['player:' + str(3 - seat)] == (4 if deathtouch else 1)
    assert combat.valid_damage_assignment(state, seat, action)
    paid = act(state, seat, action)
    assert paid.cards[sentinel].zone == Zone.BATTLEFIELD
    assert paid.cards[bear].zone == Zone.GRAVEYARD
    assert paid.players[3 - seat].life == (16 if deathtouch else 19)


@pytest.mark.parametrize('seat', [1, 2])
def test_marked_damage_does_not_erase_indestructible_trample_requirement(seat):
    state, attacker, sentinel, bear, choice = offered_combat(seat, trample=True, marked=True)
    action = AIAgent().choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert action['damage_assignment'] == {sentinel: 3, bear: 1, 'player:' + str(3 - seat): 0}
    assert combat.valid_damage_assignment(state, seat, action)
    paid = act(state, seat, action)
    assert paid.cards[bear].zone == Zone.GRAVEYARD
    assert paid.cards[sentinel].zone == Zone.BATTLEFIELD
    assert paid.players[3 - seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_effective_removed_indestructible_not_printed_keyword_controls_killability(seat):
    state, attacker, sentinel, bear, choice = offered_combat(seat, suppress_sentinel=True)
    assert 'Indestructible' in state.cards[sentinel].keywords
    assert not has_keyword(state, sentinel, 'indestructible')
    action = AIAgent().choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert action['damage_assignment'] == {sentinel: 4, bear: 0}
    assert combat.valid_damage_assignment(state, seat, action)
    paid = act(state, seat, action)
    assert paid.cards[sentinel].zone == Zone.GRAVEYARD
    assert paid.cards[bear].zone == Zone.BATTLEFIELD
