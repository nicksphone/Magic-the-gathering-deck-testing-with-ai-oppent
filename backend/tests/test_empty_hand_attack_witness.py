"""Canonical retained-position witnesses, not historical snapshot reconstruction."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures/empty_hand_attack_witness'
ROWS = {}
for entry in json.loads((FIXTURES / 'provenance.json').read_text())['cards']:
    data = (FIXTURES / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    raw = json.loads(data)
    assert raw['name'] == entry['name'] and raw['oracle_id'] == entry['oracle_id']
    ROWS[raw['name']] = raw


def position(seat, creature, *, opponent_life=20, counter=False, tapped_lands=False):
    deck = [{**ROWS['Mountain'], 'card_name': 'Mountain', 'quantity': 32}]
    state = MatchFactory.from_decks(deck, deck, seed=1972639901)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 14
    state.active_player = state.priority_player = seat
    state.step = Step.DECLARE_ATTACKERS
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    state.players[seat].life = 30
    state.players[3-seat].life = opponent_life
    for name in ['Island'] * 4 + ['Swamp'] * 2:
        raw_card(state, ROWS[name], seat, Zone.BATTLEFIELD)
    for _ in range(9):
        land = raw_card(state, ROWS['Mountain'], 3-seat, Zone.BATTLEFIELD)
        land.tapped = tapped_lands
    source = raw_card(state, ROWS[creature], seat, Zone.BATTLEFIELD)
    source.summoning_sick = False
    if counter:
        raw_card(state, ROWS['Counterspell'], seat, Zone.HAND)
    return state, source.id


class ObservedAgent(AIAgent):
    """Read-only instrumentation delegates every decision and score unchanged."""
    def __init__(self):
        super().__init__(difficulty='master', archetype='Control', opponent_archetype='Aggro')
        self.observations = []

    def _strategic_line_score(self, state, move, player_id, depth):
        value = super()._strategic_line_score(state, move, player_id, depth)
        self.observations.append({'kind': 'line', 'move': deepcopy(move), 'depth': depth, 'score': value})
        return value

    def _strategic_state_score(self, state, player_id, depth, score):
        self.observations.append({'kind': 'horizon', 'depth': depth, 'step': str(state.step),
                                  'active_player': state.active_player, 'priority_player': state.priority_player,
                                  'winner': state.winner, 'life': {str(pid): p.life for pid, p in state.players.items()},
                                  'attackers': list(state.attackers), 'score': score})
        return super()._strategic_state_score(state, player_id, depth, score)


def finish_combat(state):
    engine = RulesEngine()
    for _ in range(50):
        if state.winner is not None or state.step == Step.POSTCOMBAT_MAIN:
            return state
        assert not state.stack and not state.pending_mechanic_choice
        state = checked_action(state, engine, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Checked empty-blocker combat continuation did not finish')


def record(name, value):
    target = Path(os.environ['MTG_ATTACK_WITNESS_EVIDENCE'])
    target.mkdir(parents=True, exist_ok=True)
    with (target / (name + '.json')).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creature', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
@pytest.mark.parametrize('counter', [False, True])
@pytest.mark.parametrize('lethal', [False, True])
def test_profitable_public_empty_hand_attack_decision(seat, creature, counter, lethal):
    printed_power = int(ROWS[creature]['power'])
    state, source = position(seat, creature, opponent_life=printed_power if lethal else 20, counter=counter)
    engine = RulesEngine()
    before = serialize_match_snapshot(state)
    legal = engine.legal_moves(state, seat)
    assert not state.players[3-seat].hand and not state.players[3-seat].graveyard
    assert all(state.cards[cid].name == 'Mountain' for cid in state.players[3-seat].battlefield)
    offered = next(move for move in legal if move['type'] == 'attack')
    assert source in offered.get('options', offered.get('attackers', []))
    record(f'input-{seat}-{creature}-{counter}-{lethal}', {'snapshot': before, 'legal': legal})
    agent = ObservedAgent()
    decision = agent.choose_action(state, legal, seat)
    assert serialize_match_snapshot(state) == before
    chosen = checked_action(state, engine, seat, decision.action)
    attack = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [source]})
    # The defending player gets a real response window, not guessed risk from untapped mana.
    response = checked_action(attack, engine, seat, {'type': 'pass_priority'})
    defender_types = {move['type'] for move in engine.legal_moves(response, 3-seat)}
    assert defender_types <= {'activate_mana_ability', 'pass_priority'}
    attack = finish_combat(attack)
    passed = finish_combat(checked_action(state, engine, seat, {'type': 'pass_priority'}))
    assert attack.players[3-seat].life == before['players'][str(3-seat)]['life'] - printed_power
    assert state.cards[source].zone == attack.cards[source].zone == Zone.BATTLEFIELD
    assert attack.winner == (seat if lethal else None)
    assert passed.winner is None and passed.players[3-seat].life == state.players[3-seat].life
    record(f'result-{seat}-{creature}-{counter}-{lethal}', {
        'decision': decision.action, 'reasoning': decision.reasoning, 'scores': agent.observations,
        'defender_response_types': sorted(defender_types),
        'chosen_prefix': serialize_match_snapshot(chosen),
        'attack_after_combat': serialize_match_snapshot(attack),
        'pass_after_combat': serialize_match_snapshot(passed),
    })
    assert decision.action['type'] == 'attack' and source in decision.action['attackers'], (
        'Actual master chose a nonattack over a legal guaranteed unblocked lethal/value line; '
        f'{decision.action!r}; {decision.reasoning}')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creature', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
def test_snapshot_restore_keeps_exact_decision_and_root_pure(seat, creature):
    state, source = position(seat, creature)
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(snapshot)
    engine = RulesEngine()
    decisions = [AIAgent(difficulty='master', archetype='Control', opponent_archetype='Aggro').choose_action(
        candidate, engine.legal_moves(candidate, seat), seat).action for candidate in [state, restored]]
    assert decisions[0] == decisions[1]
    assert serialize_match_snapshot(state) == serialize_match_snapshot(restored) == snapshot
    record(f'restored-{seat}-{creature}', {'snapshot': snapshot, 'decisions': decisions})


@pytest.mark.parametrize('seat', [1, 2])
def test_public_blocker_crackback_is_not_the_empty_board_witness(seat):
    state, source = position(seat, 'Torrential Gearhulk')
    state.players[seat].life = 1
    threat = raw_card(state, ROWS['Monastery Swiftspear'], 3-seat, Zone.BATTLEFIELD)
    threat.summoning_sick = False
    before = serialize_match_snapshot(state)
    engine = RulesEngine()
    outcomes = []
    for attackers in [[source], []]:
        sim = checked_action(state, engine, seat, {'type': 'attack', 'attackers': attackers})
        sim = finish_combat(sim)
        for _ in range(80):
            if (sim.active_player == 3-seat and sim.step == Step.DECLARE_ATTACKERS
                    and sim.priority_player == 3-seat):
                break
            sim = checked_action(sim, engine, sim.priority_player, {'type': 'pass_priority'})
        else:
            pytest.fail('Actual checked turn did not reach opponent combat')
        sim = checked_action(sim, engine, 3-seat, {'type': 'attack', 'attackers': [threat.id]})
        for _ in range(20):
            if sim.step == Step.DECLARE_BLOCKERS and sim.priority_player == seat:
                break
            sim = checked_action(sim, engine, sim.priority_player, {'type': 'pass_priority'})
        else:
            pytest.fail('Actual checked attack did not reach blocker choice')
        if not attackers:
            sim = checked_action(sim, engine, seat, {'type': 'block', 'blocks': {threat.id: [source]}})
        sim = finish_combat(sim)
        outcomes.append(sim)
    assert serialize_match_snapshot(state) == before
    record(f'crackback-{seat}', {'snapshot': before,
        'attack_actual_next_combat': serialize_match_snapshot(outcomes[0]),
        'pass_actual_next_combat': serialize_match_snapshot(outcomes[1])})
    assert outcomes[0].winner == 3-seat and outcomes[1].winner != 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_untapped_mana_has_real_interaction_only_with_an_available_resource(seat):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    bolt = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.HAND)
    engine = RulesEngine()
    state = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [source]})
    state = checked_action(state, engine, seat, {'type': 'pass_priority'})
    offered = engine.legal_moves(state, 3-seat)
    assert any(move.get('card_id') == bolt.id and move['type'] == 'cast_spell' for move in offered)
    state = checked_action(state, engine, 3-seat, {'type': 'cast_spell', 'card_id': bolt.id,
                                                'targets': {'target_card_id': source}})
    assert state.stack and not state.players[3-seat].hand
    record(f'actual-interaction-{seat}', {'offered': offered, 'paid_response_snapshot': serialize_match_snapshot(state)})


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_manland_public_empty_hand_is_not_basic_land_only(seat):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    manland = raw_card(state, ROWS['Mutavault'], 3-seat, Zone.BATTLEFIELD)
    engine = RulesEngine()
    state = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [source]})
    state = checked_action(state, engine, seat, {'type': 'pass_priority'})
    legal = engine.legal_moves(state, 3-seat)
    abilities = [move for move in legal if move['type'] == 'activate_ability' and move.get('card_id') == manland.id]
    record(f'manland-available-{seat}', {'snapshot': serialize_match_snapshot(state), 'legal': legal})
    assert abilities, 'Canonical Mutavault activation availability must be explicit; do not infer safety from zero hand cards'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creature', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
def test_existing_turn_twenty_progress_policy_bypasses_short_horizon(seat, creature):
    state, source = position(seat, creature)
    state.turn = 20
    before = serialize_match_snapshot(state)
    agent = ObservedAgent()
    action = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    record(f'progress20-{seat}-{creature}', {'snapshot': before, 'action': action.action,
        'reasoning': action.reasoning, 'scores': agent.observations})
    assert action.action['type'] == 'attack' and source in action.action['attackers']
    assert action.reasoning == 'Late-game progress attack to avoid stall timeout'
    assert not agent.observations and serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creature', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
def test_tapping_defending_basic_lands_does_not_remove_the_scoring_failure(seat, creature):
    state, source = position(seat, creature, tapped_lands=True)
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    agent = ObservedAgent()
    action = agent.choose_action(state, legal, seat)
    assert action.action['type'] == 'attack' and source in action.action['attackers']
    assert action.reasoning == 'Complex-board strategic planner selected best line'
    attacked = finish_combat(checked_action(state, RulesEngine(), seat, action.action))
    record(f'tapped-basic-{seat}-{creature}', {'snapshot': before, 'legal': legal,
        'action': action.action, 'reasoning': action.reasoning, 'scores': agent.observations,
        'checked_attack_after_combat': serialize_match_snapshot(attacked)})
    # Acceptance supersedes only the archived old-pass characterization.
    assert attacked.players[3-seat].life == state.players[3-seat].life - int(ROWS[creature]['power'])
    assert attacked.players[seat].life == state.players[seat].life
    assert attacked.winner is None and attacked.cards[source].zone == Zone.BATTLEFIELD
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('creature', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
def test_low_life_race_without_public_incoming_threat_still_takes_free_damage(seat, creature):
    state, source = position(seat, creature, opponent_life=int(ROWS[creature]['power']) + 1)
    state.players[seat].life = 1
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    agent = ObservedAgent()
    action = agent.choose_action(state, legal, seat)
    attacked = finish_combat(checked_action(state, RulesEngine(), seat,
                                         {'type': 'attack', 'attackers': [source]}))
    assert attacked.players[3-seat].life == 1 and attacked.players[seat].life == 1
    assert attacked.winner is None and attacked.cards[source].zone == Zone.BATTLEFIELD
    assert serialize_match_snapshot(state) == before
    record(f'race-{seat}-{creature}', {'snapshot': before, 'legal': legal,
        'action': action.action, 'reasoning': action.reasoning, 'scores': agent.observations,
        'checked_attack_after_combat': serialize_match_snapshot(attacked)})
    assert action.action['type'] == 'attack' and source in action.action['attackers']
