"""Canonical controlled Burn positions, not private-game replay or strength proof."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.ai_decisions_canonical_cdba import canonical_deck_entry


def position(seat, hand=('Skullcrack', 'Lava Spike', 'Rift Bolt')):
    names = list(dict.fromkeys([*hand, 'Grizzly Bears']))
    deck = [canonical_deck_entry('Mountain', 58 - len(names)),
            canonical_deck_entry('Island', 2),
            *(canonical_deck_entry(name, 1) for name in names)]
    state = MatchFactory.from_decks(deck, deck, seed=9103, game_id='canonical-burn-efficiency')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 4
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()

    def move(name, owner, zone):
        player = state.players[owner]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        state.cards[cid].move_to_zone(zone)
        state.cards[cid].summoning_sick = False
        getattr(player, zone.value).append(cid)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, cid)
        return cid

    lands = [move('Mountain', seat, Zone.BATTLEFIELD) for _ in range(2)]
    enemy = move('Grizzly Bears', 3 - seat, Zone.BATTLEFIELD)
    cards = {name: move(name, seat, Zone.HAND) for name in hand}
    return state, cards, lands, enemy


def legal(state, seat):
    return RulesEngine().legal_moves(deepcopy(state), seat)


def agent(difficulty):
    return AIAgent(difficulty=difficulty, archetype='Burn', opponent_archetype='Aggro')


def pure_choice(state, seat, difficulty):
    before = serialize_match_snapshot(state)
    moves = legal(state, seat)
    original_moves = deepcopy(moves)
    action = agent(difficulty).choose_action(state, moves, seat).action
    assert serialize_match_snapshot(state) == before
    assert moves == original_moves
    replay = deserialize_match_snapshot(deepcopy(before))
    assert agent(difficulty).choose_action(replay, legal(replay, seat), seat).action == action
    hidden = deepcopy(state)
    for player in hidden.players.values():
        player.library.reverse()
    assert agent(difficulty).choose_action(hidden, legal(hidden, seat), seat).action == action
    assert serialize_match_snapshot(state) == before
    return action


def resolve(state):
    for _ in range(12):
        if not state.stack:
            return state
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice)
        state = checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Bounded spell continuation did not settle')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_player_only_burn_is_not_forced_creature_stabilization(seat, difficulty):
    state, cards, _, _ = position(seat)
    moves = legal(state, seat)
    assert {cards['Skullcrack'], cards['Lava Spike']} <= {
        move.get('card_id') for move in moves if move['type'] == 'cast_spell'}
    before = serialize_match_snapshot(state)
    forced = agent(difficulty)._forced_sweeper_stabilization_line(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    assert forced is None, 'Player-only burn cannot remove the opposing creature'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_equal_burn_prefers_cheaper_cast_and_retains_real_suspend_mana(seat, difficulty):
    state, cards, lands, _ = position(seat)
    assert any(move['type'] == 'suspend' and move['card_id'] == cards['Rift Bolt']
               for move in legal(state, seat))
    action = pure_choice(state, seat, difficulty)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Lava Spike'], action
    assert action['targets'] == {'target_player': 3 - seat}
    after = resolve(checked_action(state, RulesEngine(), seat, action))
    assert after.players[3 - seat].life == 17
    assert after.cards[cards['Lava Spike']].zone == Zone.GRAVEYARD
    assert sum(after.cards[cid].tapped for cid in lands) == 1
    assert not any(after.players[seat].mana_pool.values())
    suspend = pure_choice(after, seat, difficulty)
    assert suspend == {'type': 'suspend', 'card_id': cards['Rift Bolt']}
    final = checked_action(after, RulesEngine(), seat, suspend)
    assert all(final.cards[cid].tapped for cid in lands)
    assert final.cards[cards['Rift Bolt']].zone == Zone.EXILE
    assert final.cards[cards['Rift Bolt']].counters['time'] == 1
    assert final.cards[cards['Skullcrack']].zone == Zone.HAND
    assert not final.stack and final.spells_cast_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_actual_creature_damage_remains_a_stabilization_action(seat, difficulty):
    state, cards, _, enemy = position(seat, ('Lightning Bolt',))
    before = serialize_match_snapshot(state)
    forced = agent(difficulty)._forced_sweeper_stabilization_line(state, legal(state, seat), seat)
    assert forced is not None and forced['card_id'] == cards['Lightning Bolt']
    assert forced['targets'] == {'target_card_id': enemy}
    result = resolve(checked_action(state, RulesEngine(), seat, forced))
    assert result.cards[enemy].zone == Zone.GRAVEYARD
    assert result.players[3 - seat].life == 20
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_higher_damage_lethal_beats_cheaper_nonlethal_burn(seat, difficulty):
    state, cards, _, _ = position(seat, ('Lava Spike', 'Flame Rift'))
    state.players[3 - seat].life = 4
    action = pure_choice(state, seat, difficulty)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Flame Rift'], action
    result = resolve(checked_action(state, RulesEngine(), seat, action))
    assert result.winner == seat and result.players[3 - seat].life <= 0


@pytest.mark.parametrize('difficulty', ['strong', 'master'])
@pytest.mark.parametrize('window,name', [
    ('own_main', 'Lava Spike'), ('opponent_end', 'Skullcrack'), ('opponent_main', 'Lava Spike')])
def test_burn_uses_payable_damage_but_respects_opponent_turn_timing(difficulty, window, name):
    state, cards, _, _ = position(1, (name,))
    if window != 'own_main':
        state.active_player = 2
        state.step = Step.END_STEP if window == 'opponent_end' else Step.PRECOMBAT_MAIN
    offered = any(move['type'] == 'cast_spell' and move['card_id'] == cards[name]
                  for move in legal(state, 1))
    assert offered == (window != 'opponent_main')
    action = pure_choice(state, 1, difficulty)
    if not offered:
        assert action == {'type': 'pass_priority'}
    else:
        assert action['type'] == 'cast_spell' and action['card_id'] == cards[name]
        assert action['targets'] == {'target_player': 2}
        result = resolve(checked_action(state, RulesEngine(), 1, action))
        assert result.players[2].life == 17


def cast_offers(state, seat):
    return {state.cards[move['card_id']].name: move for move in legal(state, seat)
            if move['type'] == 'cast_spell'}


def test_cost_tie_prefers_the_cheaper_genuinely_offered_spell():
    state, _, _, _ = position(1)
    offered = cast_offers(state, 1)
    policy = agent('strong')
    ordered = policy._rank_moves(state, [offered['Skullcrack'], offered['Lava Spike']], 1)
    assert [move['card_name'] for move in ordered] == ['Lava Spike', 'Skullcrack']


def test_mana_tie_break_preserves_inter_type_precedence(monkeypatch):
    state, _, _, _ = position(1)
    moves = legal(state, 1)
    offered = [move for move in moves if move['type'] in {'pass_priority', 'cast_spell'}]
    policy = agent('strong')
    # Explicit scoring-protocol control: create a primary-score tie, not a game recommendation.
    monkeypatch.setattr(policy, '_cast_bias', lambda *_: 0)
    monkeypatch.setattr(policy, '_instant_value_reservation', lambda *_: 0)
    monkeypatch.setattr(policy, '_profile_cast_advice', lambda *_, **__: 0)
    monkeypatch.setattr(policy, '_matchup_move_adjustment', lambda *_: 0)
    monkeypatch.setattr(policy, '_pass_bias', lambda *_: 6)
    ordered = policy._rank_moves(state, offered, 1)
    assert [move['type'] for move in ordered] == sorted((move['type'] for move in offered), reverse=True)


def test_equal_cost_keeps_name_order_and_equal_keys_keep_input_order():
    state, _, _, _ = position(1, ('Lava Spike', 'Lightning Bolt'))
    moves = list(cast_offers(state, 1).values())
    policy = agent('strong')
    for sequence in (moves, list(reversed(moves))):
        ordered = sorted(sequence, key=policy._move_sort_key, reverse=True)
        assert [move['card_name'] for move in ordered] == ['Lightning Bolt', 'Lava Spike']
    first, second = deepcopy(moves[0]), deepcopy(moves[0])
    ordered = sorted([first, second], key=policy._move_sort_key, reverse=True)
    assert ordered[0] is first and ordered[1] is second


def test_actual_ranker_primary_score_precedes_mana_tie_break(monkeypatch):
    state, cards, _, _ = position(1)
    offered = cast_offers(state, 1)
    policy = agent('strong')
    # Synthetic scoring control only; canonical cards and offered costs are unchanged.
    monkeypatch.setattr(policy, '_cast_bias', lambda _state, move, _seat:
                        1000.0 if move['card_id'] == cards['Skullcrack'] else 0.0)
    ordered = policy._rank_moves(state, [offered['Lava Spike'], offered['Skullcrack']], 1)
    assert ordered[0]['card_id'] == cards['Skullcrack']


@pytest.mark.parametrize('difficulty', ['strong', 'master'])
def test_declared_lifegain_retains_skullcrack_response_over_cheaper_bolt(difficulty):
    from rules_engine.oracle_effects import inspect_target_hints

    state, cards, lands, _ = position(1, ('Skullcrack', 'Lightning Bolt'))
    encoded = (Path(__file__).parent / 'fixtures/soulscar_protection_boundaries/healing-salve.json').read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == 'bbb9f8e419f944cdab82ddf9eec451ad0b24d138d3d80554128ddbbfdc0d0325'
    raw = json.loads(encoded)
    assert raw['object'] == 'card' and raw['name'] == 'Healing Salve'
    deck = [{**raw, 'quantity': 8, 'card_name': raw['name'], 'image_uri': None}]
    sample = MatchFactory.from_decks(deck, deck, seed=9104)
    heal = deepcopy(sample.cards[sample.players[1].hand[0]])
    heal.id = state.allocate_object_id()
    heal.owner = heal.controller = 2
    heal.move_to_zone(Zone.HAND)
    state.cards[heal.id] = heal
    state.players[2].hand.append(heal.id)
    state.players[2].mana_pool = {'W': 1}  # Explicit fixture resource for the real announcement.
    state.active_player = state.priority_player = 2
    hints = inspect_target_hints(state, heal, 2)
    mode = next(mode for mode in hints['modes'] if mode.startswith('Target player gains'))
    state = checked_action(state, RulesEngine(), 2, {'type': 'cast_spell', 'card_id': heal.id,
        'targets': {'mode_text': mode, 'target_player': 2}})
    assert state.stack[-1].source_card_id == heal.id
    assert state.priority_player == 2
    state = checked_action(state, RulesEngine(), 2, {'type': 'pass_priority'})
    assert state.stack[-1].source_card_id == heal.id and state.priority_player == 1
    assert not any(state.players[2].mana_pool.values())
    action = pure_choice(state, 1, difficulty)
    assert action['type'] == 'cast_spell' and action['card_id'] == cards['Skullcrack'], action
    result = resolve(checked_action(state, RulesEngine(), 1, action))
    assert result.players[2].life == 17
    assert result.cards[heal.id].zone == Zone.GRAVEYARD
    assert result.cards[cards['Lightning Bolt']].zone == Zone.HAND
    assert all(result.cards[cid].tapped for cid in lands)
