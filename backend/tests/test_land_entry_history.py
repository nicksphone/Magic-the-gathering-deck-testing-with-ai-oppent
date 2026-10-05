"""Turn-local entry history is not a land-play allowance or current board count."""
import pytest

from effects.registry import resolve_effect
from game_state.state import Zone, Step
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event, emit_event_batch
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_recurring_engines import add


def land(state, seat, zone=Zone.HAND):
    cid = state.players[seat].library.pop()
    card = state.cards[cid]
    assert card.name == 'Island'
    card.move_to_zone(zone)
    getattr(state.players[seat], zone.value).append(cid)
    return card


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('method', ['play', 'effect'])
def test_land_entry_sources_share_history_without_sharing_play_allowances(seat, method):
    state = bare_state(seat)
    card = land(state, seat)
    if method == 'play':
        state = checked_action(state, RulesEngine(), seat, {'type': 'play_land', 'card_id': card.id})
    else:
        resolve_effect(state, seat, 'put_land_from_hand', {'land_id': card.id})
    assert state.land_entries_this_turn == {seat: 1, 3-seat: 0}
    assert state.players[seat].lands_played_this_turn == (1 if method == 'play' else 0)
    resolve_effect(state, seat, 'exile', {'target_card_id': card.id})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.land_entries_this_turn == state.land_entries_this_turn
    assert restored.land_entry_history_known is True


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('batch', [False, True])
def test_entry_events_record_actual_controller_and_ignore_nonlands(seat, batch):
    state = bare_state(seat)
    one = land(state, seat, Zone.BATTLEFIELD)
    two = land(state, 3-seat, Zone.BATTLEFIELD)
    creature = add(state, 'Grizzly Bears', seat)
    events = [{'card_id': card.id, 'controller': 3-card.controller} for card in [one, two, creature]]
    if batch:
        emit_event_batch(state, 'enters_battlefield', events)
    else:
        for event in events:
            emit_event(state, 'enters_battlefield', event)
    assert state.land_entries_this_turn == {1: 1, 2: 1}
    assert all(player.lands_played_this_turn == 0 for player in state.players.values())


@pytest.mark.parametrize('seat', [1, 2])
def test_history_includes_opponents_turn_and_resets_at_real_turn_boundary(seat):
    state = bare_state(seat)
    card = land(state, 3-seat)
    resolve_effect(state, 3-seat, 'put_land_from_hand', {'land_id': card.id})
    assert state.land_entries_this_turn[3-seat] == 1
    state.step = Step.CLEANUP
    RulesEngine().next_step(state)
    assert state.land_entries_this_turn == {1: 0, 2: 0}
    assert state.land_entry_history_known is True
    assert card.id in state.players[3-seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
def test_pregame_entry_does_not_claim_entry_during_turn_one(seat):
    state = bare_state(seat)
    state.pregame_pending = True
    card = land(state, seat, Zone.BATTLEFIELD)
    emit_event(state, 'enters_battlefield', {'card_id': card.id, 'controller': seat})
    assert state.land_entries_this_turn == {1: 0, 2: 0}


@pytest.mark.parametrize('seat', [1, 2])
def test_legacy_snapshot_does_not_invent_missing_land_entry_history(seat):
    state = bare_state(seat)
    payload = serialize_match_snapshot(state)
    payload.pop('land_entries_this_turn', None)
    payload.pop('land_entry_history_known', None)
    state = deserialize_match_snapshot(payload)
    assert state.land_entries_this_turn == {1: 0, 2: 0}
    assert state.land_entry_history_known is False
    state.step = Step.CLEANUP
    RulesEngine().next_step(state)
    assert state.land_entry_history_known is True


@pytest.mark.parametrize('seat', [1, 2])
def test_landfall_status_preserves_unknown_absence_but_new_entry_proves_presence(seat):
    from rules_engine.land_history import landfall_status
    state = bare_state(seat)
    assert landfall_status(state, seat) is False
    payload = serialize_match_snapshot(state)
    payload.pop('land_entries_this_turn')
    state = deserialize_match_snapshot(payload)
    assert landfall_status(state, seat) is None
    card = land(state, seat)
    resolve_effect(state, seat, 'put_land_from_hand', {'land_id': card.id})
    assert landfall_status(state, seat) is True
    assert landfall_status(state, 3-seat) is None
    assert state.land_entry_history_known is False


@pytest.mark.parametrize('seat', [1, 2])
def test_graveyard_return_records_entry_without_a_land_play(seat):
    from effects.handlers import return_permanent_from_graveyard_to_battlefield
    state = bare_state(seat)
    card = land(state, seat, Zone.GRAVEYARD)
    return_permanent_from_graveyard_to_battlefield(state, seat, {'target_card_id': card.id})
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.land_entries_this_turn[seat] == 1
    assert state.players[seat].lands_played_this_turn == 0


@pytest.mark.parametrize('seat', [1, 2])
def test_land_entry_choice_records_only_committed_entry_after_snapshot_resume(seat):
    from copy import deepcopy
    from game_state.state import MatchFactory
    from tests.test_land_entry_choice import FOUNDRY
    state = bare_state(seat)
    state.mechanic_choice_players = {seat}
    sample = MatchFactory.from_decks([{**FOUNDRY, 'quantity': 8}], [], seed=835)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.HAND)
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    resolve_effect(state, seat, 'put_land_from_hand', {'land_id': card.id})
    assert state.pending_mechanic_choice['kind'] == 'land_entry'
    assert state.land_entries_this_turn[seat] == 0
    assert state.cards[card.id].zone == Zone.HAND
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'choice_id': 'tapped'})
    assert state.land_entries_this_turn[seat] == 1
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.players[seat].lands_played_this_turn == 0
