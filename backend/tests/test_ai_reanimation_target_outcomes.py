"""Native paid target outcomes on canonical seeded poses, not expert deck play."""
from copy import deepcopy
from dataclasses import replace
import pickle
import random

import pytest

from ai.agent import AIAgent
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.library_canonical_fixtures import canonical_card, raw_card
from tests.damage_life_printed_79 import raw_card as life_raw_card
from tests.test_forge_negative_life_diagnostic import canonical_entry as cannot_lose_entry
from tests.scheduler_fixture_position import ordinary_position


class UnsafeAutomaticReanimationTarget(AssertionError):
    """Data-free RED identity; the observer never reads a failed result body."""


def position(seat, *, life=5, protection=None):
    row = raw_card('Swamp')
    deck = [{**row, 'card_name': row['name'], 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=76129)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn = 6
    state.step = Step.PRECOMBAT_MAIN
    ordinary_position(state)
    for player in state.players.values():
        player.library.extend(player.hand)
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.hand.clear()
        player.mana_pool.clear()
        player.lands_played_this_turn = 1
    state.players[seat].life = life

    def add(name, zone, *, protected=False):
        pose = dict(id=state.allocate_object_id(), owner=seat, controller=seat,
                    zone=zone, summoning_sick=False)
        if protected:
            row = (cannot_lose_entry(name) if name == 'Platinum Angel'
                   else {**life_raw_card(name), 'card_name': name})
            born = MatchFactory.from_decks([{**row, 'quantity': 8}], [], seed=0)
            template = next(card for card in born.cards.values() if card.zone == Zone.LIBRARY)
            card = replace(template, **pose)
        else:
            card = canonical_card(name, **pose)
        state.cards[card.id] = card
        getattr(state.players[seat], zone.value).append(card.id)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, card.id)
        return card.id

    land = add('Swamp', Zone.BATTLEFIELD)
    large = add('Griselbrand', Zone.GRAVEYARD)
    small = add('Grizzly Bears', Zone.GRAVEYARD)
    spell = add('Reanimate', Zone.HAND)
    if protection:
        add(protection, Zone.BATTLEFIELD, protected=True)
    return state, spell, large, small, land


def paid_result(state, seat, action):
    before = pickle.dumps(state, protocol=5)
    rules = RulesEngine()
    result = checked_action(state, rules, seat, action)
    assert pickle.dumps(state, protocol=5) == before
    assert result.stack[-1].payload['mana_spent'] == 1
    assert sum(result.players[seat].mana_pool.values()) == 0
    for _ in range(8):
        if result.winner is not None or not result.stack:
            return result
        assert not result.pending_mechanic_choice
        assert not result.pending_trigger_order
        assert not result.pending_replacement_choice
        result = checked_action(result, rules, result.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Reanimation failed to settle within eight checked passes')


@pytest.mark.parametrize('seat', [1, 2])
def test_native_paid_outcomes_distinguish_fatal_large_from_safe_small(seat):
    state, spell, large, small, land = position(seat)
    base = {'type': 'cast_spell', 'card_id': spell}
    losing = paid_result(state, seat, {**base, 'targets': {'target_card_id': large}})
    assert losing.winner == 3-seat and losing.players[seat].life == -3
    assert losing.cards[large].zone == Zone.BATTLEFIELD
    safe = paid_result(state, seat, {**base, 'targets': {'target_card_id': small}})
    assert safe.winner is None and safe.players[seat].life == 3
    assert safe.cards[small].zone == Zone.BATTLEFIELD
    assert safe.cards[large].zone == Zone.GRAVEYARD
    assert safe.cards[spell].zone == Zone.GRAVEYARD and safe.cards[land].tapped


@pytest.mark.parametrize('seat', [1, 2])
def test_automatic_target_avoids_proven_loss_when_safe_target_exists(seat):
    state, spell, _, small, land = position(seat)
    ai = AIAgent('master', 'Reanimator')
    move = next(row for row in ai.engine.legal_moves(state, seat) if row.get('card_id') == spell)
    before, original = pickle.dumps(state, protocol=5), deepcopy(move)
    action = ai._materialize_action(state, move, seat)
    assert pickle.dumps(state, protocol=5) == before and move == original
    if action.get('targets', {}).get('target_card_id') != small:
        raise UnsafeAutomaticReanimationTarget
    result = paid_result(state, seat, action)
    assert result.winner is None and result.players[seat].life == 3
    assert result.cards[small].zone == Zone.BATTLEFIELD and result.cards[land].tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['strong', 'master', 'master_plus'])
def test_native_reanimator_choice_casts_safe_target_instead_of_passing(seat, difficulty):
    state, spell, _, small, _ = position(seat)
    ai = AIAgent(difficulty, 'Reanimator')
    legal = ai.engine.legal_moves(state, seat)
    before, original = pickle.dumps(state, protocol=5), deepcopy(legal)
    agent_before, rng_before = pickle.dumps(vars(ai), protocol=5), random.getstate()
    action = ai.choose_action(state, legal, seat).action
    assert pickle.dumps(state, protocol=5) == before and legal == original
    assert pickle.dumps(vars(ai), protocol=5) == agent_before and random.getstate() == rng_before
    assert action.get('type') == 'cast_spell' and action.get('card_id') == spell
    assert action.get('targets', {}).get('target_card_id') == small
    result = paid_result(state, seat, action)
    assert result.winner is None and result.players[seat].life == 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('protection', [None, 'Platinum Emperion', 'Platinum Angel'])
def test_native_safe_large_target_retains_existing_preference(seat, protection):
    state, spell, large, _, _ = position(seat, life=12 if protection is None else 5,
                                        protection=protection)
    ai = AIAgent('master', 'Reanimator')
    move = next(row for row in ai.engine.legal_moves(state, seat) if row.get('card_id') == spell)
    action = ai._materialize_action(state, move, seat)
    assert action['targets']['target_card_id'] == large
    result = paid_result(state, seat, action)
    assert result.winner is None and result.cards[large].zone == Zone.BATTLEFIELD
    assert result.players[seat].life == (4 if protection is None else 5 if protection == 'Platinum Emperion' else -3)


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_losing_target_is_preserved_as_a_legal_choice(seat):
    state, spell, large, _, _ = position(seat)
    ai = AIAgent('master', 'Reanimator')
    move = next(row for row in ai.engine.legal_moves(state, seat) if row.get('card_id') == spell)
    move['targets'] = {'target_card_id': large}
    action = ai._materialize_action(state, move, seat)
    assert action['targets']['target_card_id'] == large
    result = paid_result(state, seat, action)
    assert result.winner == 3-seat and result.players[seat].life == -3
