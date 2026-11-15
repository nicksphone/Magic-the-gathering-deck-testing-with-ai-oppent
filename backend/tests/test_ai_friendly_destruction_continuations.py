"""Canonical multi-target destruction decisions, not forecast-budget protocol tests."""
from copy import deepcopy
import pickle
import random

import pytest

from ai.agent import AIAgent
from ai.pending_effects import decision_projection_scope, friendly_destruction_profit, unproductive_destroy_targets
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.query_context import query_cache
from tests.combat_canonical_022 import canonical_entry, raw_card as combat_raw
from tests.pending_permanent_fullraw import raw_card as pending_raw
from tests.test_linked_damage_targets import raw_card


def position(seat, *, foreign_choice=False):
    deck = [canonical_entry('Forest', 20)]
    state = MatchFactory.from_decks(deck, deck, seed=7219, game_id='friendly-destruction-continuations')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 8
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    state.mechanic_choice_players = {1, 2}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
        player.lands_played_this_turn = 1

    def add(name, owner=seat, zone=Zone.BATTLEFIELD):
        raw = combat_raw(name) if name == 'Grizzly Bears' else pending_raw(name)
        card = raw_card(state, raw, owner, zone)
        assert (card.name, card.mana_cost, card.oracle_text, card.type_line) == tuple(
            raw[key] for key in ('name', 'mana_cost', 'oracle_text', 'type_line'))
        assert card.power == (int(raw['power']) if raw.get('power') is not None else None)
        assert card.toughness == (int(raw['toughness']) if raw.get('toughness') is not None else None)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, card.id)
        return card.id

    # Put a genuinely unproductive friendly candidate before the death payoff.
    own_myr = add('Darksteel Myr')
    bear = add('Grizzly Bears')
    artist = add('Blood Artist', 3-seat if foreign_choice else seat)
    add('Bastion of Remembrance')
    enemy_myr = add('Darksteel Myr', 3-seat)
    murder = add('Murder', zone=Zone.HAND)
    state.players[seat].mana_pool = {'B': 3}
    state.players[3-seat].life = 1 if foreign_choice else 2
    return state, murder, own_myr, bear, artist, enemy_myr


def native_result(state, seat, action):
    rules = RulesEngine()
    result = checked_action(state, rules, seat, action)
    assert result.stack[-1].payload['mana_spent'] == 3
    assert sum(result.players[seat].mana_pool.values()) == 0
    choosers = []
    actors = {pid: AIAgent('master', 'Aristocrats') for pid in (1, 2)}
    for _ in range(64):
        choice = result.pending_trigger_order or result.pending_mechanic_choice or result.pending_replacement_choice
        if result.winner is not None or not (result.stack or choice):
            return result, choosers
        if choice:
            pid = choice.get('player_id', choice.get('current_controller'))
            choosers.append(pid)
            action = actors[pid].choose_action(result, rules.legal_moves(result, pid), pid).action
        else:
            pid, action = result.priority_player, {'type': 'pass_priority'}
        result = checked_action(result, rules, pid, action)
    raise AssertionError('Canonical destruction did not settle within 64 native actions')


@pytest.mark.parametrize('seat', [1, 2])
def test_multi_target_decision_retains_owned_death_win_after_useless_candidates(seat):
    state, murder, own_myr, bear, artist, enemy_myr = position(seat)
    agent = AIAgent('master', 'Aristocrats')
    legal = agent.engine.legal_moves(state, seat)
    before, old_legal = pickle.dumps(state, protocol=5), deepcopy(legal)
    agent_before, rng_before = pickle.dumps(vars(agent), protocol=5), random.getstate()
    action = {'type': 'cast_spell', 'card_id': murder, 'targets': {'target_card_id': enemy_myr}}
    assert unproductive_destroy_targets(state, state.cards[murder], seat, action['targets'],
                                       candidates={enemy_myr}) == {enemy_myr}
    wasted, choices = native_result(state, seat, action)
    assert not choices and wasted.winner is None
    assert wasted.cards[enemy_myr].zone == Zone.BATTLEFIELD
    assert wasted.cards[murder].zone == Zone.GRAVEYARD
    assert friendly_destruction_profit(state, seat, {
        **action, 'targets': {'target_card_id': own_myr}}) is False

    selected = agent.choose_action(state, legal, seat).action
    assert selected.get('card_id') == murder
    assert selected.get('targets', {}).get('target_card_id') in {bear, artist}
    actual, choices = native_result(state, seat, selected)
    assert choices and set(choices) == {seat}
    assert actual.winner == seat and actual.players[3-seat].life == 0
    assert actual.cards[selected['targets']['target_card_id']].zone == Zone.GRAVEYARD
    assert actual.cards[own_myr].zone == actual.cards[enemy_myr].zone == Zone.BATTLEFIELD
    assert legal == old_legal and pickle.dumps(state, protocol=5) == before
    assert pickle.dumps(vars(agent), protocol=5) == agent_before
    assert random.getstate() == rng_before and query_cache(state) is None


@pytest.mark.parametrize('seat', [1, 2])
def test_foreign_death_choice_stays_unknown_without_rejecting_legal_own_target(seat):
    state, murder, _, bear, _, _ = position(seat, foreign_choice=True)
    agent = AIAgent('master', 'Aristocrats')
    move = next(row for row in agent.engine.legal_moves(state, seat) if row.get('card_id') == murder)
    before, old_move = pickle.dumps(state, protocol=5), deepcopy(move)
    agent_before, rng_before = pickle.dumps(vars(agent), protocol=5), random.getstate()
    selected = {**move, 'targets': {'target_card_id': bear}}
    calls = []

    def own_choice(projected, legal, actor):
        calls.append(actor)
        assert actor == seat
        return AIAgent('master', 'Aristocrats').choose_action(projected, legal, actor).action

    with decision_projection_scope(state, seat):
        assert friendly_destruction_profit(state, seat, selected, own_choice_action=own_choice) is None
        assert calls == []
        materialized = agent._materialize_action(state, selected, seat)
    assert not materialized.get('_invalid_ai_choice')
    assert materialized['targets']['target_card_id'] == bear
    actual, choices = native_result(state, seat, materialized)
    assert 3-seat in choices
    assert actual.cards[bear].zone == Zone.GRAVEYARD and actual.winner is None
    # The opponent Artist's drain offsets our Bastion; an unknown was not a win.
    assert actual.players[seat].life == 20 and actual.players[3-seat].life == 1
    assert move == old_move and pickle.dumps(state, protocol=5) == before
    assert pickle.dumps(vars(agent), protocol=5) == agent_before
    assert random.getstate() == rng_before and query_cache(state) is None
