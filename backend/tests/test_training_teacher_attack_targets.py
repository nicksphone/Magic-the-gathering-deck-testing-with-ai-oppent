"""Canonical retained C2 combat poses; real producers, no replay/private witness.

The one-tick exporter case is intentionally incomplete and never a draw label.
No Oracle edits, new scene IDs, stock recapture, or forced AI decisions are used.
"""
from copy import deepcopy

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.declaration_policy import finalize_declaration
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from tests.scheduler_fixture_position import ordinary_position
from tests.test_training_environment import keep, place
from training.dataset import HeuristicTeacher, episode_records
from training.environment import TrainingEnvironment


def position(seat, *, walker=False):
    environment = TrainingEnvironment()
    decks = ('Mono Red Aggro', 'Ramp') if seat == 1 else ('Ramp', 'Mono Red Aggro')
    environment.reset(*decks, seed=17)
    keep(environment)
    state = environment._state
    # Explicit retained position: all originals remain in the original inventory.
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.mana_pool = {color: 0 for color in 'WUBRGC'}
    attacker = place(environment, 'Monastery Swiftspear', seat, Zone.BATTLEFIELD)
    state.cards[attacker].summoning_sick = False
    target = None
    if walker:
        target = place(environment, 'Ugin, the Spirit Dragon', 3-seat, Zone.BATTLEFIELD)
        state.cards[target].loyalty = 3
    state.active_player = state.priority_player = seat
    state.turn, state.step = 5, Step.DECLARE_ATTACKERS
    state.attackers_declared = state.blockers_declared = False
    state.players[3-seat].life = 20 if walker else 1
    state.passed_priority = set()
    ordinary_position(state)
    assert environment.acting_seat == seat and not environment.terminated
    assert not state.pending_mechanic_choice and not state.stack
    return environment, attacker, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_actual_teacher_attack_has_explicit_default_defender_before_lookup(seat, difficulty):
    environment, attacker, _ = position(seat)
    teacher = HeuristicTeacher(difficulty)
    before = environment.snapshot()
    action = teacher(environment)
    assert action['type'] == 'attack' and action['attackers'] == [attacker]
    assert environment.snapshot() == before
    accepted = environment.lookup(action, seat)
    assert accepted['action']['attack_targets'] == {attacker: f'player:{3-seat}'}
    assert environment.snapshot() == before
    environment.step(accepted['id'], seat)
    assert environment._state.attackers == [attacker]
    assert environment._state.attack_targets == {attacker: f'player:{3-seat}'}


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_teacher_export_accepts_attack_without_consumer_inference(seat):
    environment, attacker, _ = position(seat)
    records = list(episode_records(environment, HeuristicTeacher(),
        episode='episode-0000', groups=['position:' + 'a' * 64], tick_budget=1,
        origin='heuristic', decision_frame=True, public_context=True))
    assert [record['kind'] for record in records] == ['episode_start', 'transition', 'episode_end']
    assert records[1]['accepted'] is True and records[1]['action']['type'] == 'attack'
    assert records[2]['steps'] == 1 and records[2]['reason'] == 'tick_budget'
    assert records[2]['complete'] is False and records[2]['terminal_rewards'] is None
    assert environment._state.attackers == [attacker]
    assert environment._state.attack_targets == {attacker: f'player:{3-seat}'}


@pytest.mark.parametrize('seat', [1, 2])
def test_real_shortlist_uses_shared_completion_before_strict_lookup(seat):
    environment, attacker, _ = position(seat)
    view, moves = environment._view(seat)
    agent = AIAgent('strong')
    before = environment.snapshot()
    proposals = agent._strategic_top_actions(view, moves, seat, 8)
    attacks = [proposal for proposal in proposals
               if proposal['type'] == 'attack' and proposal.get('attackers')]
    assert attacks and environment.snapshot() == before
    # This is the actual learned-router completion boundary, not a consumer fix.
    action = complete_action(finalize_declaration(view, attacks[0]))
    accepted = environment.lookup(action, seat)
    assert accepted['action']['attack_targets'] == {attacker: f'player:{3-seat}'}
    environment.step(accepted['id'], seat)
    assert environment._state.attack_targets == {attacker: f'player:{3-seat}'}


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_planeswalker_intent_survives_materialization_and_completion(seat):
    environment, attacker, walker = position(seat, walker=True)
    view, moves = environment._view(seat)
    hint = next(move for move in moves if move['type'] == 'attack')
    selected = {attacker: f'planeswalker:{walker}'}
    intent = {**deepcopy(hint), 'attackers': [attacker],
              'attack_targets': selected, 'bands': []}
    original, before = deepcopy(intent), environment.snapshot()
    proposal = AIAgent('strong')._materialize_action(view, intent, seat)
    action = complete_action(finalize_declaration(view, proposal))
    assert action['attackers'] == [attacker] and action['attack_targets'] == selected
    assert action['bands'] == [] and intent == original
    assert environment.snapshot() == before
    accepted = environment.lookup(action, seat)
    environment.step(accepted['id'], seat)
    assert environment._state.attack_targets == selected
    assert environment._state.cards[walker].loyalty == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_attack_targets_are_still_rejected_atomically(seat):
    environment, attacker, _ = position(seat)
    before = environment.snapshot()
    incomplete = {'type': 'attack', 'attackers': [attacker]}
    with pytest.raises(ActionRejected, match='Missing required choice: attack_targets'):
        environment.lookup(incomplete, seat)
    with pytest.raises(ActionRejected, match='Missing required choice: attack_targets'):
        environment.step(incomplete, seat)
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_completion_does_not_repair_an_explicit_invalid_defender(seat):
    environment, attacker, _ = position(seat)
    view, _ = environment._view(seat)
    wrong = {attacker: 'planeswalker:unavailable-negative-protocol'}
    intent = {'type': 'attack', 'attackers': [attacker], 'attack_targets': wrong}
    original, before = deepcopy(intent), environment.snapshot()
    action = complete_action(finalize_declaration(view, intent))
    assert action['attack_targets'] == wrong and intent == original
    with pytest.raises(ActionRejected, match='Invalid attack target'):
        environment.lookup(action, seat)
    assert environment.snapshot() == before
