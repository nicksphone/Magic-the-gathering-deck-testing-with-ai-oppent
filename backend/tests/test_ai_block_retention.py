"""Full-printing old-board combat fixtures, not paid births or policy-strength proof."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.ai_decisions_canonical_cdba import canonical_deck_entry


def position(seat, attackers, blockers, support=(), *, life=20, opponent_life=20):
    counts = Counter([*attackers, *blockers, *support])
    counts['Forest'] += 60 - sum(counts.values())
    deck = []
    for name, count in counts.items():
        if name == 'Ninja of the Deep Hours':
            data = (Path(__file__).parent / 'fixtures/ninjutsu_canonical/ninja-of-the-deep-hours.json').read_bytes()
            assert hashlib.sha256(data).hexdigest() == 'd5c28c0171ed64bf41b2435a9edcf4ebcef7cc5d121e27996c74b9a1a8f41b0f'
            deck.append({**json.loads(data), 'card_name': name, 'quantity': count})
        else:
            deck.append(canonical_deck_entry(name, count))
    state = MatchFactory.from_decks(deck, deck, seed=4261, game_id='block-retention')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 8
    state.active_player = state.priority_player = 3 - seat
    state.step = Step.DECLARE_ATTACKERS
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
    state.players[seat].life = life
    state.players[3 - seat].life = opponent_life

    def place(name, owner):
        player = state.players[owner]
        cid = next(cid for cid in player.library if state.cards[cid].name == name.split(' // ', 1)[0])
        player.library.remove(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        player.battlefield.append(cid)
        state.cards[cid].summoning_sick = False
        assign_static_order_on_battlefield_entry(state, cid)
        return cid

    attack_ids = [place(name, 3 - seat) for name in attackers]
    block_ids = [place(name, seat) for name in blockers]
    support_ids = [place(name, 3 - seat) for name in support]
    return state, attack_ids, block_ids, support_ids


def declare(state, seat, attackers):
    state = checked_action(state, RulesEngine(), 3 - seat, {
        'type': 'attack', 'attackers': attackers,
        'attack_targets': {cid: f'player:{seat}' for cid in attackers}})
    for _ in range(40):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == seat and not state.stack:
            return state
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Checked declaration did not reach the blocker window')


def decide_and_finish(state, seat, style):
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(deepcopy(state), seat)
    old_moves = deepcopy(moves)
    action = AIAgent(difficulty='strong', archetype=style).choose_action(state, moves, seat).action
    assert serialize_match_snapshot(state) == before and moves == old_moves
    assert action['type'] in {'block', 'pass_priority'}
    result = checked_action(state, RulesEngine(), seat, action)
    for _ in range(80):
        if result.winner is not None or result.step == Step.END_COMBAT:
            assert serialize_match_snapshot(state) == before
            return action, result
        if result.pending_mechanic_choice:
            pid = result.pending_mechanic_choice['player_id']
            next_action = AIAgent().choose_action(result, RulesEngine().legal_moves(result, pid), pid).action
        else:
            pid = result.priority_player
            next_action = {'type': 'pass_priority'}
        result = checked_action(result, RulesEngine(), pid, next_action)
    raise AssertionError('Checked combat did not finish')


@pytest.mark.parametrize('seat', [1, 2])
def test_strong_retains_wounded_grazer_and_keeps_healthy_block(seat):
    state, attackers, blockers, _ = position(seat,
        ['Delver of Secrets // Insectile Aberration'] * 3,
        ['Arboreal Grazer'] * 2, life=19)
    # Declared old-board damage, not altered printed toughness or a fake effect.
    state.cards[blockers[0]].counters['__damage_marked'] = 2
    state = declare(state, seat, attackers)
    _, result = decide_and_finish(state, seat, 'Ramp')
    assert all(result.cards[cid].zone == Zone.BATTLEFIELD for cid in blockers)
    assert result.players[seat].life == 17
    assert all(result.cards[cid].zone == Zone.BATTLEFIELD for cid in attackers)


@pytest.mark.parametrize('seat', [1, 2])
def test_strong_retains_clarion_engine_instead_of_nonlethal_chump(seat):
    state, attackers, blockers, _ = position(seat, ['Elvish Warmaster'],
        ['Clarion Spirit'], ['Elvish Archdruid'])
    assert effective_power(state, attackers[0]) == 3
    state = declare(state, seat, attackers)
    _, result = decide_and_finish(state, seat, 'Tokens')
    assert result.cards[blockers[0]].zone == Zone.BATTLEFIELD
    assert result.players[seat].life == 17 and result.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_strong_still_chumps_to_prevent_actual_lethal(seat):
    state, attackers, blockers, _ = position(seat, ['Elvish Warmaster'],
        ['Clarion Spirit'], ['Elvish Archdruid'], life=3)
    state = declare(state, seat, attackers)
    _, result = decide_and_finish(state, seat, 'Tokens')
    assert result.cards[blockers[0]].zone == Zone.GRAVEYARD
    assert result.players[seat].life == 3 and result.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_first_strike_trade_is_not_removed(seat):
    state, attackers, blockers, _ = position(seat, ['Grizzly Bears'],
        ['Thalia, Guardian of Thraben'])
    state = declare(state, seat, attackers)
    _, result = decide_and_finish(state, seat, 'Midrange')
    assert result.cards[blockers[0]].zone == Zone.BATTLEFIELD
    assert result.cards[attackers[0]].zone == Zone.GRAVEYARD
    assert result.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_winning_genuine_death_trigger_keeps_the_chump(seat):
    state, attackers, blockers, _ = position(seat, ['Elvish Warmaster'],
        ['Zulaport Cutthroat'], ['Elvish Archdruid'], opponent_life=1)
    state = declare(state, seat, attackers)
    _, result = decide_and_finish(state, seat, 'Drain')
    assert result.cards[blockers[0]].zone == Zone.GRAVEYARD
    assert result.winner == seat


@pytest.mark.parametrize('seat', [1, 2])
def test_unblocked_hidden_draw_is_unknown_not_permission_to_remove_block(seat):
    state, attackers, blockers, _ = position(seat, ['Ninja of the Deep Hours'],
        ['Clarion Spirit'])
    state.cards[blockers[0]].counters['-1/-1'] = 1
    state = declare(state, seat, attackers)
    _, result = decide_and_finish(state, seat, 'Tokens')
    assert result.cards[blockers[0]].zone == Zone.GRAVEYARD
    assert result.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_trampling_lethal_still_uses_real_reach_blocker(seat):
    state, attackers, blockers, _ = position(seat, ['Elvish Warmaster'],
        ['Arboreal Grazer'], ['Elvish Archdruid'], life=3)
    # Explicit runtime keyword grants; the canonical printed text stays intact.
    add_keyword_effect(state, attackers[0], ['trample', 'flying'])
    state = declare(state, seat, attackers)
    _, result = decide_and_finish(state, seat, 'Ramp')
    assert result.cards[blockers[0]].zone == Zone.GRAVEYARD
    assert result.players[seat].life == 3 and result.winner is None
