"""Checked canonical tactical goldens, not full-deck piloting certification."""
from collections import Counter
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from tests.ai_decisions_canonical_cdba import canonical_deck_entry


def position(seat, hand, lands, enemy=(), reserve=()):
    counts = Counter([*hand, *lands, *enemy, *reserve])
    counts['Forest'] += 60 - sum(counts.values())
    deck = [canonical_deck_entry(name, count) for name, count in counts.items() if count]
    state = MatchFactory.from_decks(deck, deck, seed=4261, game_id='strategy-fundamentals')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 3
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()

    def move(name, owner, zone):
        player = state.players[owner]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        state.cards[cid].move_to_zone(zone)
        getattr(player, zone.value).append(cid)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, cid)
            state.cards[cid].summoning_sick = False
        return cid

    for name in lands:
        move(name, seat, Zone.BATTLEFIELD)
    state.players[seat].lands_played_this_turn = 1
    cards = {name: move(name, seat, Zone.HAND) for name in hand}
    opponents = {name: move(name, 3 - seat, Zone.BATTLEFIELD) for name in enemy}
    return state, cards, opponents, move


def choose(state, seat, style, difficulty):
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(deepcopy(state), seat)
    before_moves = deepcopy(moves)
    ai = AIAgent(archetype=style, difficulty=difficulty)
    action = ai.choose_action(state, moves, seat).action
    assert serialize_match_snapshot(state) == before and moves == before_moves
    restored = deserialize_match_snapshot(deepcopy(before))
    assert ai.choose_action(restored, RulesEngine().legal_moves(deepcopy(restored), seat), seat).action == action
    hidden = deepcopy(state)
    for player in hidden.players.values():
        player.library.reverse()
    assert ai.choose_action(hidden, RulesEngine().legal_moves(deepcopy(hidden), seat), seat).action == action
    return action


def settle(state, seat, style, difficulty):
    for _ in range(32):
        if state.pending_mechanic_choice:
            actor = state.pending_mechanic_choice['player_id']
            action = choose(state, actor, style, difficulty)
        elif not state.stack:
            return state
        else:
            actor = state.priority_player
            action = {'type': 'pass_priority'}
        state = checked_action(state, RulesEngine(), actor, action)
    raise AssertionError('Bounded checked continuation did not settle')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('style', ['Burn', 'Aggro', 'Tempo'])
def test_develop_prowess_before_burn_for_actual_extra_damage(seat, difficulty, style):
    state, cards, _, _ = position(seat, ['Monastery Swiftspear', 'Lava Spike'], ['Mountain'] * 2)
    state.turn = 2
    first = choose(state, seat, style, difficulty)
    assert first.get('card_id') == cards['Monastery Swiftspear'], first
    state = settle(checked_action(state, RulesEngine(), seat, first), seat, style, difficulty)
    second = choose(state, seat, style, difficulty)
    assert second.get('card_id') == cards['Lava Spike'], second
    state = settle(checked_action(state, RulesEngine(), seat, second), seat, style, difficulty)
    assert state.players[3 - seat].life == 17
    assert effective_power(state, cards['Monastery Swiftspear']) == 2
    for _ in range(16):
        if state.step == Step.DECLARE_ATTACKERS:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_ATTACKERS
    attack = choose(state, seat, style, difficulty)
    assert attack['type'] == 'attack' and cards['Monastery Swiftspear'] in attack['attackers']
    state = checked_action(state, RulesEngine(), seat, attack)
    state = settle(state, seat, style, difficulty)
    for _ in range(16):
        if state.step == Step.DECLARE_BLOCKERS:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    state = checked_action(state, RulesEngine(), 3 - seat, {'type': 'block', 'blocks': {}})
    for _ in range(16):
        if state.players[3 - seat].life == 15:
            break
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert state.players[3 - seat].life == 15


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('style', ['Burn', 'Aggro', 'Tempo'])
def test_immediate_lethal_beats_development_when_only_one_cast_is_payable(seat, difficulty, style):
    state, cards, _, _ = position(seat, ['Monastery Swiftspear', 'Lava Spike'], ['Mountain'])
    state.players[3 - seat].life = 3
    action = choose(state, seat, style, difficulty)
    assert action.get('card_id') == cards['Lava Spike'], action
    result = settle(checked_action(state, RulesEngine(), seat, action), seat, style, difficulty)
    assert result.winner == seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_control_counters_real_lethal_instead_of_cantripping(seat, difficulty):
    state, cards, _, move = position(seat, ['Counterspell', 'Opt'], ['Island'] * 3,
        reserve=['Lightning Bolt', 'Mountain'])
    state.players[seat].life = 3
    bolt = move('Lightning Bolt', 3 - seat, Zone.HAND)
    move('Mountain', 3 - seat, Zone.BATTLEFIELD)
    state.active_player = state.priority_player = 3 - seat
    state = checked_action(state, RulesEngine(), 3 - seat,
        {'type': 'cast_spell', 'card_id': bolt, 'targets': {'target_player': seat}})
    state = checked_action(state, RulesEngine(), 3 - seat, {'type': 'pass_priority'})
    action = choose(state, seat, 'Control', difficulty)
    assert action.get('card_id') == cards['Counterspell'], action
    state = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Control', difficulty)
    assert state.players[seat].life == 3 and state.winner is None
    assert state.cards[bolt].zone == Zone.GRAVEYARD
    assert state.cards[cards['Opt']].zone == Zone.HAND


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_midrange_removes_engine_over_small_mana_creature(seat, difficulty):
    state, cards, enemies, _ = position(seat, ['Go for the Throat'], ['Swamp'] * 2,
        ['Sheoldred, the Apocalypse', 'Elvish Mystic'])
    action = choose(state, seat, 'Midrange', difficulty)
    assert action.get('card_id') == cards['Go for the Throat'], action
    assert action.get('targets') == {'target_card_id': enemies['Sheoldred, the Apocalypse']}, action
    state = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Midrange', difficulty)
    assert state.cards[enemies['Sheoldred, the Apocalypse']].zone == Zone.GRAVEYARD
    assert state.cards[enemies['Elvish Mystic']].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_ramp_develops_real_land_and_hand_over_cantrip(seat, difficulty):
    state, cards, _, _ = position(seat, ['Cultivate', 'Consider'], ['Forest', 'Forest', 'Island'])
    action = choose(state, seat, 'Ramp', difficulty)
    assert action.get('card_id') == cards['Cultivate'], action
    state = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Ramp', difficulty)
    assert len(state.players[seat].battlefield) == 4
    assert state.cards[cards['Consider']].zone == Zone.HAND
    assert len(state.players[seat].hand) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_pass_recovery_keeps_ranked_ramp_over_unaffordable_followup(seat, difficulty):
    state, cards, _, _ = position(seat, ['Cultivate', 'Consider'], ['Forest', 'Forest', 'Island'])
    ai = AIAgent(archetype='Ramp', difficulty=difficulty)
    moves = RulesEngine().legal_moves(deepcopy(state), seat)
    assert ai._rank_moves(state, moves, seat)[0]['card_id'] == cards['Cultivate']
    before = serialize_match_snapshot(state)
    action = ai._avoid_pass_with_main_phase_options(state, moves, seat, {'type': 'pass_priority'})
    assert serialize_match_snapshot(state) == before
    assert action.get('card_id') == cards['Cultivate'], action
    state = settle(checked_action(state, RulesEngine(), seat, action), seat, 'Ramp', difficulty)
    assert len(state.players[seat].battlefield) == 4
