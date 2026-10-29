"""Paid canonical Gearhulk choices with SYNTHETIC_ZERO numeric protocol weights.

The existing binding helper builds zeros against the current engine contract.
This is a public decision/progress regression, not fitted-model readiness,
model strength, or qualification of the historical 7c7d checkpoint.
"""
from copy import deepcopy
import json

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.canonical_positive_fixtures import raw_card
from tests.scheduler_fixture_position import ordinary_position
from tests.test_live_learned_policy import _binding, _subject


def _paid_gearhulk(seat):
    names = ('Island', 'Torrential Gearhulk', 'Go for the Throat',
             'Counterspell', 'Grizzly Bears')
    # Complete pinned objects reach the real factory; only zones/mana are posed.
    deck = [{**raw_card(name), 'card_name': name,
             'quantity': 20 if name == 'Island' else 1} for name in names]
    state = MatchFactory.from_decks(deck, deck, seed=713,
                                   game_id=f'canonical-choice-cycle-{seat}')
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    ordinary_position(state)
    state.mechanic_choice_players = {seat}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    ids = {}
    for player in state.players.values():
        player.mana_pool.clear()
        for cid in list(player.hand):
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
    for card in state.cards.values():
        raw = raw_card(card.name)
        for field in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout'):
            assert getattr(card, field) == raw[field]
        assert card.printed_power == raw.get('power')
        assert card.printed_toughness == raw.get('toughness')
        assert card.card_faces == raw.get('card_faces', [])
        destination = None
        if card.name == 'Grizzly Bears':
            destination = Zone.BATTLEFIELD
            ids['friendly' if card.owner == seat else 'hostile'] = card.id
            assert 'Creature' in card.types and 'Artifact' not in card.types
        elif card.owner == seat and card.name != 'Island':
            destination = Zone.HAND if card.name == 'Torrential Gearhulk' else Zone.GRAVEYARD
            ids[card.name] = card.id
        if destination is not None:
            player = state.players[card.owner]
            player.library.remove(card.id)
            card.move_to_zone(destination)
            getattr(player, destination.value).append(card.id)
    state.players[seat].mana_pool.update(C=4, U=2)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': ids['Torrential Gearhulk']})
    assert state.cards[ids['Torrential Gearhulk']].zone == Zone.STACK
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert state.spells_cast_this_turn[seat] == 1
    assert not state.pending_trigger_order and not state.pending_mechanic_choice
    return state, ids


def _pass_to_choice(state):
    for _ in range(4):
        if state.pending_trigger_order or state.pending_mechanic_choice:
            return state
        assert state.stack, 'Expected the real announced spell/trigger'
        state = checked_action(state, RulesEngine(), state.priority_player,
                               {'type': 'pass_priority'})
    pytest.fail('Paid Gearhulk did not reach a public choice within four passes')


def _permission(state, seat, ids):
    state = _pass_to_choice(state)
    assert state.pending_trigger_order['phase'] == 'targets'
    assert state.pending_trigger_order['current_controller'] == seat
    assert state.cards[ids['Torrential Gearhulk']].zone == Zone.BATTLEFIELD
    moves = RulesEngine().legal_moves(state, seat)
    assert {move['target_card_id'] for move in moves} == {
        ids['Go for the Throat'], ids['Counterspell']}
    target = next(move for move in moves if move['target_card_id'] == ids['Go for the Throat'])
    state = checked_action(state, RulesEngine(), seat, target)
    state = _pass_to_choice(state)
    assert not state.pending_trigger_order
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    assert state.pending_mechanic_choice['player_id'] == seat
    assert state.pending_mechanic_choice['effect_payload']['target_card_id'] == ids['Go for the Throat']
    assert state.pending_mechanic_choice.get('resolving_item')
    return state


def _choose_checked(state, seat, agent):
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    moves_before = deepcopy(moves)
    decision = agent.choose_action(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    assert moves == moves_before
    changed = checked_action(state, RulesEngine(), seat, decision.action)
    assert serialize_match_snapshot(state) == before
    assert serialize_match_snapshot(changed) != before
    return changed, decision


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('frontier', ['announced_gearhulk', 'effect_cast_permission'])
def test_canonical_paid_gearhulk_choice_progress_with_synthetic_zero_binding(seat, frontier, record_property):
    binding = _binding(_subject())  # SYNTHETIC_ZERO protocol, never a retagged fitted checkpoint.
    agent = AIAgent(difficulty='master', archetype='Control', learned_binding=binding)
    record_property('qualification', 'SYNTHETIC_ZERO_CURRENT_CONTRACT_PUBLIC_PROTOCOL_ONLY')
    record_property('checkpoint_sha256', binding.checkpoint_sha256)
    record_property('engine_hash', binding.contract['engine_hash'])
    state, ids = _paid_gearhulk(seat)
    if frontier == 'announced_gearhulk':
        state, decision = _choose_checked(state, seat, agent)
        assert decision.action['type'] == 'pass_priority'
        record_property('announced_decision', json.dumps(decision.action, sort_keys=True))
    state = _permission(state, seat, ids)
    assert all(state.cards[ids[key]].zone == Zone.BATTLEFIELD for key in ('friendly', 'hostile'))
    state, decision = _choose_checked(state, seat, agent)
    record_property('permission_decision', json.dumps(decision.action, sort_keys=True))
    assert not state.pending_mechanic_choice and not state.pending_trigger_order
    assert decision.action['type'] in {'cast_spell', 'choose_mechanic'}
    if decision.action['type'] == 'cast_spell':
        assert decision.action['card_id'] == ids['Go for the Throat']
        assert decision.action['from_graveyard'] is True
        target = decision.action['targets']['target_card_id']
        assert target in (ids['friendly'], ids['hostile'])
        for _ in range(2):
            state = checked_action(state, RulesEngine(), state.priority_player,
                                   {'type': 'pass_priority'})
        assert not state.stack
        assert state.cards[target].zone == Zone.GRAVEYARD
        assert state.cards[ids['Go for the Throat']].zone == Zone.EXILE
    else:
        assert decision.action['card_ids'] == ['decline']
        assert state.cards[ids['Go for the Throat']].zone == Zone.GRAVEYARD
        assert not state.stack
    assert state.cards[ids['Torrential Gearhulk']].zone == Zone.BATTLEFIELD
