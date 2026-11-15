"""Complete canonical entry controls; no injected lore or stack objects."""
from copy import deepcopy
import json
from pathlib import Path
import random

import pytest

from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
FACTS = json.loads((Path(__file__).parent / 'fixtures' / 'saga_land_entry.json').read_bytes())


def add(state, name, seat, zone):
    raw = FACTS[name]
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 1}], [], seed=7311)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False
    return card.id


def position(seat):
    deck = [{**FACTS['Forest'], 'card_name': 'Forest', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=7311)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.mechanic_choice_players = state.replacement_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {}
    for _ in range(8):
        add(state, 'Forest', seat, Zone.BATTLEFIELD)
    return state


def settle(state):
    for _ in range(48):
        if not state.stack or state.pending_mechanic_choice:
            return state
        assert not state.pending_replacement_choice and not state.pending_trigger_order
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Announced stack did not settle within 48 checked passes')


def act(state, seat, action):
    before = serialize_match_snapshot(state)
    request = deepcopy(action)
    rng, local = random.getstate(), state.rng.getstate()
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before and action == request
    assert random.getstate() == rng and state.rng.getstate() == local
    return result


def restored(state):
    snap = serialize_match_snapshot(state)
    other = deserialize_match_snapshot(deepcopy(snap))
    assert serialize_match_snapshot(other) == snap
    return other


@pytest.mark.parametrize('seat', [1, 2])
def test_real_land_saga_enters_once_with_chapter_and_atomic_quota(seat):
    state = position(seat)
    saga = add(state, "Urza's Saga", seat, Zone.HAND)
    second = add(state, 'Forest', seat, Zone.HAND)
    state = act(state, seat, {'type': 'play_land', 'card_id': saga})
    assert state.cards[saga].zone == Zone.BATTLEFIELD
    assert state.cards[saga].counters.get('__lore') == 1
    chapters = [x for x in state.stack if x.source_card_id == saga]
    assert len(chapters) == 1 and chapters[0].payload['__chapter_number'] == 1
    assert state.players[seat].lands_played_this_turn == 1
    assert state.players[seat].land_plays_recorded_on_turn == 1
    snap = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': second})
    assert serialize_match_snapshot(state) == snap
    restored(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_land_saga_counter_replacement_pauses_offboard_and_resumes_snapshot(seat):
    state = position(seat)
    saga = add(state, "Urza's Saga", seat, Zone.HAND)
    add(state, 'Vorinclex, Monstrous Raider', seat, Zone.BATTLEFIELD)
    add(state, 'Vorinclex, Monstrous Raider', 3-seat, Zone.BATTLEFIELD)
    state = act(state, seat, {'type': 'play_land', 'card_id': saga})
    assert state.pending_replacement_choice, 'Entry counters must offer their real replacement order'
    assert state.cards[saga].zone == Zone.HAND and saga not in state.players[seat].battlefield
    assert state.players[seat].lands_played_this_turn == 0
    snapshot = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
                       {'type': 'choose_replacement', 'replacement_source_id': 'not-an-offered-source'})
    assert serialize_match_snapshot(state) == snapshot
    state = restored(state)
    for _ in range(4):
        pending = state.pending_replacement_choice
        if not pending:
            break
        state = act(state, pending['player_id'], {'type': 'choose_replacement',
                    'replacement_source_id': pending['options'][0]['source_id']})
    assert not state.pending_replacement_choice
    assert state.cards[saga].zone == Zone.BATTLEFIELD
    assert state.cards[saga].counters.get('__lore', 0) in (0, 1)
    assert state.players[seat].battlefield.count(saga) == 1
    assert state.players[seat].lands_played_this_turn == 1
    assert state.players[seat].land_plays_recorded_on_turn == 1


@pytest.mark.parametrize('seat', [1, 2])
def test_land_saga_respects_native_counter_prohibition(seat):
    state = position(seat)
    saga = add(state, "Urza's Saga", seat, Zone.HAND)
    add(state, 'Solemnity', seat, Zone.BATTLEFIELD)
    state = act(state, seat, {'type': 'play_land', 'card_id': saga})
    assert state.cards[saga].zone == Zone.BATTLEFIELD
    assert not state.cards[saga].counters.get('__lore', 0)
    assert not any(x.source_card_id == saga for x in state.stack)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['tapped', 'pay_two_life'])
def test_ordinary_shockland_choice_and_payment_are_unchanged(seat, choice):
    state = position(seat)
    land = add(state, 'Hallowed Fountain', seat, Zone.HAND)
    before = state.players[seat].life
    result = act(state, seat, {'type': 'play_land', 'card_id': land, 'entry_choice': choice})
    assert result.cards[land].tapped is (choice == 'tapped')
    assert result.players[seat].life == before - (2 if choice == 'pay_two_life' else 0)
    assert result.players[seat].lands_played_this_turn == 1
    assert not result.cards[land].counters.get('__lore', 0)
    snapshot = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat,
                       {'type': 'play_land', 'card_id': land, 'entry_choice': 'not-an-entry-choice'})
    assert serialize_match_snapshot(state) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_modal_land_face_is_not_changed_to_the_spell_front(seat):
    state = position(seat)
    land = add(state, 'Bala Ged Recovery // Bala Ged Sanctuary', seat, Zone.HAND)
    state = act(state, seat, {'type': 'play_land', 'card_id': land, 'selected_face_index': 1})
    assert state.cards[land].zone == Zone.BATTLEFIELD and state.cards[land].name == 'Bala Ged Sanctuary'
    assert state.cards[land].selected_face_index == 1 and state.cards[land].tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['History of Benalia', 'The Phasing of Zhalfir'])
def test_nonland_saga_and_read_ahead_keep_genuine_entry_pipeline(seat, name):
    state = position(seat)
    saga = add(state, name, seat, Zone.HAND)
    for _ in range(3):
        add(state, 'Plains' if name == 'History of Benalia' else 'Island', seat, Zone.BATTLEFIELD)
    state = act(state, seat, {'type': 'cast_spell', 'card_id': saga,
                             'targets': {}, 'cost_choice': {'id': 'base'}})
    for _ in range(8):
        if state.pending_mechanic_choice or state.cards[saga].zone == Zone.BATTLEFIELD:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    if name == 'The Phasing of Zhalfir':
        assert state.pending_mechanic_choice['kind'] == 'saga_entry'
        state = restored(state)
        state = act(state, seat, {'type': 'choose_mechanic', 'choice_id': '2'})
        expected = 2
    else:
        expected = 1
    assert state.cards[saga].zone == Zone.BATTLEFIELD
    assert state.cards[saga].counters['__lore'] == expected
    assert {x.payload.get('__chapter_number') for x in state.stack if x.source_card_id == saga} == {expected}
