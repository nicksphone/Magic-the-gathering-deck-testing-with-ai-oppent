"""Checked canonical combat outcomes; old-board grants, not paid births or AI quality.

Full Oracle data is pinned. Counters and keyword effects are explicitly supplied
public-board fixtures; no Oracle text, winners, or projected endpoints are changed.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_power, effective_toughness, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_ai_terminal_draw_product import raw
from tests.vraska_full.test_full_vraska import bare, add, act, Zone, Step


CORPUS = Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
DATA = CORPUS.read_bytes()
assert hashlib.sha256(DATA).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
CARDS = {card['name']: card for card in map(json.loads, DATA.splitlines())}


def position(defender, *, trample=False, first_strike=False, large_counters=2,
             remove_deathtouch=False):
    attacker_seat = 3 - defender
    state = bare(attacker_seat)
    state.step = Step.DECLARE_ATTACKERS
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        player.mana_pool = {}
    attacker = add(state, CARDS['Atraxa, Grand Unifier'], attacker_seat,
                   Zone.BATTLEFIELD, old_board=True).id
    cheap = add(state, CARDS['Sprite Dragon'], defender,
                Zone.BATTLEFIELD, old_board=True).id
    large = add(state, raw('rumbling-baloth'), defender,
                Zone.BATTLEFIELD, old_board=True).id
    state.cards[large].counters['+1/+1'] = large_counters
    # Baloth can block flying Atraxa only through this declared effective grant.
    add_keyword_effect(state, large, ['flying'])
    first = None
    if first_strike:
        first = add(state, CARDS['Thalia, Guardian of Thraben'], defender,
                    Zone.BATTLEFIELD, old_board=True).id
        state.cards[first].counters['+1/+1'] = 5
        add_keyword_effect(state, first, ['flying'])
    if trample:
        add_keyword_effect(state, attacker, ['trample'])
    if remove_deathtouch:
        add_keyword_effect(state, attacker, ['deathtouch'], operation='remove')
    assert (effective_power(state, attacker), effective_toughness(state, attacker)) == (7, 7)
    assert has_keyword(state, attacker, 'deathtouch') is not remove_deathtouch
    assert has_keyword(state, attacker, 'trample') is trample
    assert state.cards[attacker].oracle_text == CARDS['Atraxa, Grand Unifier']['oracle_text']
    assert state.cards[large].oracle_text == raw('rumbling-baloth')['oracle_text']
    state = act(state, attacker_seat, {'type': 'attack', 'attackers': [attacker],
                'attack_targets': {attacker: 'player:' + str(defender)}})
    for _ in range(40):
        if state.step == Step.DECLARE_BLOCKERS and state.priority_player == defender:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.DECLARE_BLOCKERS and state.priority_player == defender
    moves = RulesEngine().legal_moves(state, defender)
    offered = {card['id'] for move in moves if move['type'] == 'block'
               for card in move.get('blockers', [])}
    assert {cheap, large} <= offered
    if first is not None:
        assert first in offered
    assert state.winner is None and not state.stack
    return state, attacker, cheap, large, first


def blocked(root, defender, attacker, blockers):
    before = serialize_match_snapshot(root)
    state = act(root, defender, {'type': 'block',
                'blocks': {attacker: list(blockers)} if blockers else {}})
    for _ in range(80):
        if state.step == Step.END_COMBAT or state.winner is not None:
            assert serialize_match_snapshot(root) == before
            return state
        choice = state.pending_mechanic_choice
        if choice:
            assert choice['kind'] == 'combat_damage'
            owner = choice['player_id']
            # Production allocation only, not an injected combat outcome/decision.
            action = AIAgent().choose_action(state, RulesEngine().legal_moves(state, owner), owner).action
            assert action['type'] == 'choose_mechanic'
            state = act(state, owner, action)
        else:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
    pytest.fail('Checked combat did not finish within 80 original actions')


@pytest.mark.parametrize('defender', [1, 2])
def test_single_small_and_large_blockers_save_same_life_but_not_same_material(defender):
    root, attacker, cheap, large, _ = position(defender)
    assert (effective_power(root, cheap), effective_toughness(root, cheap)) == (1, 1)
    assert (effective_power(root, large), effective_toughness(root, large)) == (6, 6)
    original = serialize_match_snapshot(root)
    low_loss = blocked(root, defender, attacker, [cheap])
    high_loss = blocked(root, defender, attacker, [large])
    no_block = blocked(root, defender, attacker, [])
    for state, sacrificed, retained in ((low_loss, cheap, large), (high_loss, large, cheap)):
        assert state.players[defender].life == 20
        assert state.players[3 - defender].life == 27  # Genuine full Atraxa lifelink.
        assert state.cards[sacrificed].zone == Zone.GRAVEYARD
        assert state.cards[retained].zone == Zone.BATTLEFIELD
        assert state.cards[attacker].zone == Zone.BATTLEFIELD
        assert state.winner is None
    assert no_block.players[defender].life == 13
    assert all(no_block.cards[cid].zone == Zone.BATTLEFIELD for cid in (attacker, cheap, large))
    assert evaluate_board(low_loss, defender) > evaluate_board(high_loss, defender)
    # Real checked outcomes, not a requirement to select any fixed named blocker.
    restored = deserialize_match_snapshot(original)
    replay = blocked(restored, defender, attacker, [cheap])
    assert serialize_match_snapshot(replay) == serialize_match_snapshot(low_loss)
    assert serialize_match_snapshot(root) == original


@pytest.mark.parametrize('defender', [1, 2])
def test_trample_deathtouch_requires_one_damage_not_largest_toughness(defender):
    root, attacker, cheap, large, _ = position(defender, trample=True)
    for blocker in (cheap, large):
        state = blocked(root, defender, attacker, [blocker])
        assert state.players[defender].life == 14
        assert state.players[3 - defender].life == 27
        assert state.cards[blocker].zone == Zone.GRAVEYARD
        assert state.cards[attacker].zone == Zone.BATTLEFIELD
        assert state.winner is None


@pytest.mark.parametrize('defender', [1, 2])
def test_both_blockers_are_a_distinct_genuine_attacker_killing_alternative(defender):
    root, attacker, cheap, large, _ = position(defender)
    state = blocked(root, defender, attacker, [cheap, large])
    assert state.players[defender].life == 20
    assert state.players[3 - defender].life == 27
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in (attacker, cheap, large))
    assert state.winner is None


@pytest.mark.parametrize('defender', [1, 2])
def test_real_first_strike_prevents_deathtouch_return_and_lifelink(defender):
    root, attacker, cheap, large, first = position(defender, first_strike=True)
    assert has_keyword(root, first, 'first strike')
    assert (effective_power(root, first), effective_toughness(root, first)) == (7, 6)
    state = blocked(root, defender, attacker, [first])
    assert state.cards[attacker].zone == Zone.GRAVEYARD
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in (cheap, large, first))
    assert state.players[defender].life == state.players[3 - defender].life == 20
    assert state.winner is None


@pytest.mark.parametrize('defender', [1, 2])
@pytest.mark.parametrize('remove_deathtouch', [False, True])
def test_effective_deathtouch_not_size_alone_decides_large_survival(defender, remove_deathtouch):
    root, attacker, _, large, _ = position(defender, large_counters=4,
                                        remove_deathtouch=remove_deathtouch)
    assert (effective_power(root, large), effective_toughness(root, large)) == (8, 8)
    assert 'Deathtouch' in root.cards[attacker].keywords
    state = blocked(root, defender, attacker, [large])
    assert state.cards[attacker].zone == Zone.GRAVEYARD
    assert state.cards[large].zone == (Zone.BATTLEFIELD if remove_deathtouch else Zone.GRAVEYARD)
    assert state.players[defender].life == 20 and state.winner is None


@pytest.mark.parametrize('defender', [1, 2])
def test_wrong_actor_rejection_preserves_complete_original_root(defender):
    root, attacker, cheap, _, _ = position(defender)
    before = serialize_match_snapshot(root)
    rng = deepcopy(root.rng.getstate())
    with pytest.raises(ActionRejected):
        checked_action(root, RulesEngine(), 3 - defender,
                       {'type': 'block', 'blocks': {attacker: [cheap]}})
    assert serialize_match_snapshot(root) == before
    assert root.rng.getstate() == rng
