"""Canonical bounded rummaging and per-turn discard-count integration."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.state import Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.zone_actions import discard_selected, discard_simultaneous
from tests.test_activation_modifiers import board
from tests.test_ai_recurring_engines import add as raw_add
from tests.test_surveil_mill import add
from tests.test_legendary_channels import choice, resolve_to_choice
from tests.test_api_input_contracts import game

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/discard_history.json').read_text())}
RUMMAGE = 'Discard up to two cards, then draw that many cards.'


def setup(name, seat=1, hand_names=('Island', 'Swamp', 'Grizzly Bears'), cast=True):
    state = board(seat)
    state.mechanic_choice_players = {1, 2}
    source = raw_add(state, name, seat, Zone.BATTLEFIELD if name == 'Daretti, Scrap Savant' else Zone.HAND, cards=ROWS)
    source.loyalty = 3 if name == 'Daretti, Scrap Savant' else None
    hand = [add(state, name, seat, Zone.HAND) for name in hand_names]
    state.players[seat].mana_pool.update(R=3, C=8)
    action = {'type': 'activate_loyalty', 'card_id': source.id, 'ability_index': 0} if name == 'Daretti, Scrap Savant' else {
        'type': 'cast_spell', 'card_id': source.id,
        'targets': {},
    }
    if name == 'Cathartic Pyre':
        from rules_engine.cast_choice import build_cast_hints
        action['targets']['mode_text'] = next(mode for mode in build_cast_hints(state, source, seat)['modes'] if mode.startswith('Discard'))
    if cast:
        state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    return state, source, hand, action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Daretti, Scrap Savant', 'Cathartic Pyre'])
@pytest.mark.parametrize('count', [0, 1, 2])
def test_bounded_discard_actual_draw_and_snapshot(seat, name, count):
    state, source, hand, _ = setup(name, seat)
    pending = state.pending_mechanic_choice
    assert pending['count'] == 2
    assert pending['min_count'] == 0
    state = choice(deserialize_match_snapshot(serialize_match_snapshot(state)), seat, [card.id for card in hand[:count]])
    assert len(state.players[seat].hand) == 3
    assert state.discards_this_turn[seat] == count
    assert state.draws_this_turn[seat] == count
    assert not state.pending_mechanic_choice
    assert not state.stack
    if name == 'Daretti, Scrap Savant':
        assert state.cards[source.id].loyalty == 5
        assert state.cards[source.id].zone == Zone.BATTLEFIELD
    else:
        assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_turn_history_counts_prior_and_current_discards(seat):
    state, source, hand, action = setup('Change of Fortune', seat, cast=False)
    assert discard_selected(state, seat, [hand[0].id])
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    state = choice(deserialize_match_snapshot(serialize_match_snapshot(state)), seat, [card.id for card in hand[1:]])
    assert len(state.players[seat].hand) == 3
    assert state.discards_this_turn[seat] == 3
    assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_discard_history_rejects_invalid_simultaneous_batch_atomically(seat):
    state, _, hand, _ = setup('Change of Fortune', seat, cast=False)
    before = serialize_match_snapshot(state)
    assert not discard_simultaneous(state, {seat: [hand[0].id], 3-seat: [hand[1].id]})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Daretti, Scrap Savant', 'Cathartic Pyre'])
@pytest.mark.parametrize('size', [0, 1, 2])
def test_bounded_discard_caps_to_available_hand(seat, name, size):
    state, _, hand, _ = setup(name, seat, ('Swamp',) * size)
    if size:
        assert state.pending_mechanic_choice['count'] == size
        state = choice(state, seat, [card.id for card in hand])
    assert not state.pending_mechanic_choice
    assert len(state.players[seat].hand) == size
    assert state.discards_this_turn[seat] == size


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Daretti, Scrap Savant', 'Cathartic Pyre'])
@pytest.mark.parametrize('bad', ['too-many', 'duplicate', 'opponent', 'source'])
def test_illegal_bounded_choices_are_atomic(seat, name, bad):
    state, source, hand, _ = setup(name, seat)
    other = add(state, 'Island', 3-seat, Zone.HAND)
    ids = [card.id for card in hand] if bad == 'too-many' else [hand[0].id] * 2 if bad == 'duplicate' else [other.id] if bad == 'opponent' else [source.id]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        choice(state, seat, ids)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_history_counts_exiled_discards_and_draw_replacements(seat):
    from tests.test_linked_discard import ROWS as LINKED
    from tests.test_draw_forecast import ROWS as DRAW
    state, source, hand, action = setup('Change of Fortune', seat, cast=False)
    raw_add(state, 'Leyline of the Void', 3-seat, cards=LINKED)
    raw_add(state, 'Thought Reflection', seat, cards=DRAW)
    assert discard_selected(state, seat, [hand[0].id])
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    state = choice(deserialize_match_snapshot(serialize_match_snapshot(state)), seat, [card.id for card in hand[1:]])
    assert state.discards_this_turn[seat] == 3
    assert state.draws_this_turn[seat] == 6
    assert len(state.players[seat].hand) == 6
    assert all(state.cards[card.id].zone == Zone.EXILE for card in hand)
    assert state.cards[source.id].zone == Zone.EXILE


@pytest.mark.parametrize('seat', [1, 2])
def test_simultaneous_history_and_turn_boundary_reset(seat):
    state, _, hand, _ = setup('Change of Fortune', seat, cast=False)
    other = add(state, 'Island', 3-seat, Zone.HAND)
    assert discard_simultaneous(state, {seat: [card.id for card in hand], 3-seat: [other.id]})
    assert state.discards_this_turn == {seat: 3, 3-seat: 1}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state.step = Step.CLEANUP
    RulesEngine().next_step(state)
    assert state.active_player == 3-seat
    assert state.discards_this_turn == {1: 0, 2: 0}


@pytest.mark.parametrize('seat', [1, 2])
def test_cost_and_cleanup_discards_share_history(seat):
    from tests.test_spell_cost_clauses import ROWS as COSTS
    state = board(seat)
    state.mechanic_choice_players = {seat}
    spell = raw_add(state, 'Cathartic Reunion', seat, Zone.HAND, cards=COSTS)
    hand = [add(state, 'Island', seat, Zone.HAND) for _ in range(10)]
    state.players[seat].mana_pool.update(R=1, C=1)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': spell.id,
        'cost_choice': {'id': 'base', 'discard_card_ids': [card.id for card in hand[:2]]},
    })
    assert state.discards_this_turn[seat] == 2
    state = resolve_to_choice(state)
    assert not state.stack
    state.step = Step.CLEANUP
    RulesEngine()._enforce_cleanup_hand_size(state, seat)
    pending = state.pending_mechanic_choice
    assert pending['count'] == 4
    state = choice(deserialize_match_snapshot(serialize_match_snapshot(state)), seat, pending['options'][:4])
    assert len(state.players[seat].hand) == 7
    assert state.discards_this_turn[seat] == 6


@pytest.mark.parametrize('seat', [1, 2])
def test_history_counts_same_card_discarded_twice_and_legacy_snapshot(seat):
    state, _, hand, _ = setup('Change of Fortune', seat, cast=False)
    cid = hand[0].id
    assert discard_selected(state, seat, [cid])
    state.players[seat].graveyard.remove(cid)
    state.cards[cid].move_to_zone(Zone.HAND)
    state.players[seat].hand.append(cid)
    assert discard_selected(state, seat, [cid])
    assert state.discards_this_turn[seat] == 2
    snapshot = serialize_match_snapshot(state)
    assert deserialize_match_snapshot(snapshot).discards_this_turn[seat] == 2
    snapshot.pop('discards_this_turn')
    assert deserialize_match_snapshot(snapshot).discards_this_turn == {1: 0, 2: 0}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
def test_ai_bounded_rummage_retains_good_cards_and_cycles_excess_lands(seat, level):
    state, _, hand, _ = setup('Cathartic Pyre', seat, ('Counterspell',) * 3)
    agent = AIAgent(level)
    agent.archetype = 'Control'
    before = serialize_match_snapshot(state)
    assert agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action['card_ids'] == []
    assert serialize_match_snapshot(state) == before
    state, _, hand, _ = setup('Cathartic Pyre', seat, ('Swamp',) * 3)
    for _ in range(5):
        add(state, 'Swamp', seat)
    decision = agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action
    assert len(decision['card_ids']) == 2
    state = choice(state, seat, decision['card_ids'])
    assert state.discards_this_turn[seat] == 2
    assert len(state.players[seat].hand) == 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
def test_ai_optional_draw_respects_caps_and_doubled_exhaustion(seat, level):
    from tests.test_draw_forecast import ROWS as DRAW
    state, _, hand, _ = setup('Cathartic Pyre', seat, ('Swamp',) * 3)
    for _ in range(5):
        add(state, 'Swamp', seat)
    agent = AIAgent(level)
    raw_add(state, 'Thought Reflection', seat, cards=DRAW)
    state.players[seat].library = state.players[seat].library[:3]
    assert len(agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action['card_ids']) == 1
    raw_add(state, 'Spirit of the Labyrinth', 3-seat, cards=DRAW)
    state.draws_this_turn[seat] = 1
    assert agent.choose_action(state, RulesEngine().legal_moves(state, seat), seat).action['card_ids'] == []


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
def test_ai_count_history_changes_refresh_admission_without_peeking(seat, level):
    state, source, _, _ = setup('Change of Fortune', seat, ('Counterspell',) * 3, cast=False)
    agent = AIAgent(level)
    agent.archetype = 'Control'
    move = {'type': 'cast_spell', 'card_id': source.id}
    assert agent._bad_shared_draw_cast(state, move, seat)
    earlier = [add(state, 'Swamp', seat, Zone.HAND).id for _ in range(3)]
    assert discard_selected(state, seat, earlier)
    before = serialize_match_snapshot(state)
    assert not agent._bad_shared_draw_cast(state, move, seat)
    assert serialize_match_snapshot(state) == before
    state.players[seat].library = state.players[seat].library[:4]
    assert agent._bad_shared_draw_cast(state, move, seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('level', ['casual', 'strong', 'master'])
def test_ai_modal_cast_does_not_spend_spell_to_discard_nothing(seat, level):
    state, source, _, _ = setup('Cathartic Pyre', seat, ('Counterspell',) * 3, cast=False)
    agent = AIAgent(level)
    agent.archetype = 'Control'
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == source.id)
    assert agent._bad_shared_draw_cast(state, move, seat)
    target = add(state, 'Grizzly Bears', 3-seat)
    move = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('card_id') == source.id)
    assert not agent._bad_shared_draw_cast(state, move, seat)
    action = agent._materialize_action(state, move, seat)
    assert 'damage' in action['targets']['mode_text'].lower()
    assert action['targets']['target_card_id'] == target.id
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    assert state.cards[target.id].zone == Zone.GRAVEYARD
    assert state.discards_this_turn[seat] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Daretti, Scrap Savant', 'Cathartic Pyre', 'Change of Fortune'])
def test_opposing_copy_uses_own_discard_budget_and_history(seat, name):
    from effects.registry import resolve_effect
    state, source, hand, action = setup(name, seat, cast=False)
    assert discard_selected(state, seat, [hand[0].id])
    other_hand = [add(state, 'Swamp', 3-seat, Zone.HAND) for _ in range(3)]
    assert discard_selected(state, 3-seat, [other_hand[0].id])
    state = checked_action(state, RulesEngine(), seat, action)
    key = 'copy_ability' if name == 'Daretti, Scrap Savant' else 'copy_spell'
    resolve_effect(state, 3-seat, key, {'target_stack_id': state.stack[-1].id})
    state = resolve_to_choice(state)
    assert state.pending_mechanic_choice['player_id'] == 3-seat
    state = choice(deserialize_match_snapshot(serialize_match_snapshot(state)), 3-seat, [card.id for card in other_hand[1:]])
    assert len(state.players[3-seat].hand) == (3 if name == 'Change of Fortune' else 2)
    assert state.discards_this_turn == {seat: 1, 3-seat: 3}
    state = resolve_to_choice(state)
    state = choice(state, seat, [card.id for card in hand[1:]])
    assert state.discards_this_turn == {1: 3, 2: 3}
    assert len(state.players[seat].hand) == (3 if name == 'Change of Fortune' else 2)


@pytest.mark.parametrize('seat', [1, 2])
def test_countering_history_spell_does_not_add_resolution_discards(seat):
    from effects.registry import resolve_effect
    state, source, hand, action = setup('Change of Fortune', seat, cast=False)
    assert discard_selected(state, seat, [hand[0].id])
    state = checked_action(state, RulesEngine(), seat, action)
    resolve_effect(state, 3-seat, 'counter_spell', {'target_stack_id': state.stack[-1].id})
    assert state.discards_this_turn[seat] == 1
    assert len(state.players[seat].hand) == 2
    assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_mill_and_hand_exile_are_not_discards(seat):
    from effects.registry import resolve_effect
    from rules_engine.zone_actions import exile_selected_from_hand
    state, _, hand, _ = setup('Change of Fortune', seat, cast=False)
    resolve_effect(state, seat, 'mill_cards', {'target_player': seat, 'amount': 2})
    assert exile_selected_from_hand(state, seat, [hand[0].id])
    assert state.discards_this_turn == {1: 0, 2: 0}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Daretti, Scrap Savant', 'Cathartic Pyre', 'Change of Fortune'])
def test_http_choice_and_sqlite_history_restore(game, seat, name):
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from tests.test_api_input_contracts import persist, rejected
    import main
    client, controller = game
    state, source, hand, action = setup(name, seat, cast=False)
    assert discard_selected(state, seat, [hand[0].id])
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    rejected(client, controller, {'type': 'choose_mechanic', 'card_ids': [hand[1].id]}, 3-seat)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    controller = main.ACTIVE_MATCHES[state.id]
    assert controller.state.discards_this_turn[seat] == 1
    response = client.post(f'/matches/{state.id}/action', json={
        'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': [card.id for card in hand[1:]]},
    })
    assert response.status_code == 200, response.text
    assert response.json()['discards_this_turn'][str(seat)] == 3
    assert controller.state.discards_this_turn[seat] == 3
    assert len(controller.state.players[seat].hand) == (3 if name == 'Change of Fortune' else 2)
