"""Canonical private optional reveal at controller upkeep; no Oracle mutations."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from card_data.sync import ScryfallSyncService
from card_data.hydration import hydrate_deck_cards
from game_state.serializers import serialize_match, serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import _trigger_from_oracle
from rules_engine.optional_reveal import parse_upkeep_reveal

ROOT = Path(__file__).parent / 'fixtures'
RAW = json.loads((ROOT / 'human_transform_audit/canonical.json').read_text())
ISLAND = json.loads((ROOT / 'human_flow_audit/canonical.json').read_text())['Island']
DELVER = RAW['Delver of Secrets // Insectile Aberration']
ENGINE = RulesEngine()


def position(seat, eligible=True, empty=False):
    declarations = [(DELVER, 2), (RAW['Shock'], 1), (ISLAND, 57)]
    cache = {row['name'].lower(): SimpleNamespace(**ScryfallSyncService._normalize_payload(row, None))
             for row, _ in declarations}
    rows = hydrate_deck_cards(SimpleNamespace(get_cached_cards_by_names=lambda names: cache),
                              [{'card_name': row['name'], 'quantity': count} for row, count in declarations])
    state = MatchFactory.from_decks(rows, rows, seed=19)
    for p in state.players.values():
        p.hand.clear()
        p.library = [cid for cid, c in state.cards.items() if c.owner == p.id]
        for cid in p.library:
            if state.cards[cid].zone != Zone.LIBRARY:
                state.cards[cid].move_to_zone(Zone.LIBRARY)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.UNTAP
    source = next(c for c in state.cards.values() if c.owner == seat and c.card_faces)
    state.players[seat].library.remove(source.id)
    state.players[seat].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    top = next(c for c in state.cards.values() if c.owner == seat and c.name == ('Shock' if eligible else 'Island'))
    state.players[seat].library.remove(top.id)
    state.players[seat].library.append(top.id)
    if empty:
        # Explicit empty-library position; move canonical objects, never alter facts.
        for cid in list(state.players[seat].library):
            state.cards[cid].move_to_zone(Zone.GRAVEYARD)
            state.players[seat].graveyard.append(cid)
        state.players[seat].library.clear()
    return state, source.id, top.id


def pending(seat, eligible=True):
    state, source, top = position(seat, eligible)
    ENGINE.next_step(state)
    assert state.step == Step.UPKEEP and len(state.stack) == 1
    assert (state.cards[source].selected_face_index or 0) == 0
    assert top not in state.card_observations.get(seat, {})
    assert not any('inspected_cards' in move for move in ENGINE.legal_moves(state, seat))
    for _ in range(2):
        state = checked_action(state, ENGINE, state.priority_player, {'type': 'pass_priority'})
    assert state.pending_mechanic_choice['kind'] == 'optional_reveal'
    return state, source, top


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('eligible', [True, False])
@pytest.mark.parametrize('choice', ['reveal', 'decline'])
def test_real_upkeep_optional_choice_restores_and_does_not_reorder(seat, eligible, choice):
    state, source, top = pending(seat, eligible)
    before = serialize_match_snapshot(state)
    cards = list(state.players[seat].library)
    moves = ENGINE.legal_moves(state, seat)
    assert moves[0]['inspected_cards'][0]['name'] == ('Shock' if eligible else 'Island')
    assert ENGINE.legal_moves(state, 3-seat) == []
    assert serialize_match_snapshot(state) == before
    assert state.card_observations[seat][top]['name'] == ('Shock' if eligible else 'Island')
    assert top not in state.card_observations.get(3-seat, {})
    public = serialize_match(state)['pending_mechanic_choice']
    assert set(public) == {'kind', 'player_id', 'label', 'count'}
    assert top not in json.dumps(public)
    state = deserialize_match_snapshot(before)
    result = checked_action(state, ENGINE, seat, {'type': 'choose_mechanic', 'card_ids': [choice]})
    assert serialize_match_snapshot(state) == before
    assert result.players[seat].library == cards
    assert result.pending_mechanic_choice is None and not result.stack
    assert (result.cards[source].selected_face_index or 0) == (1 if eligible and choice == 'reveal' else 0)
    assert result.step == Step.UPKEEP
    assert (top in result.card_observations.get(3-seat, {})) == (choice == 'reveal')
    assert not any('reveals' in line for line in result.log) if choice == 'decline' else True


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('action', [
    {'type': 'choose_mechanic', 'card_ids': []},
    {'type': 'choose_mechanic', 'card_ids': ['reveal', 'decline']},
    {'type': 'choose_mechanic', 'card_ids': ['unknown']},
    {'type': 'pass_priority'},
])
def test_malformed_or_wrong_owner_rejects_without_root_mutation(seat, action):
    state, _, _ = pending(seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, ENGINE, seat, action)
    with pytest.raises(ActionRejected):
        checked_action(state, ENGINE, 3-seat, {'type': 'choose_mechanic', 'card_ids': ['reveal']})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_stale_top_rejected_and_blinked_source_not_transformed(seat):
    state, source, top = pending(seat)
    stale = deepcopy(state)
    library = stale.players[seat].library
    library[-1], library[-2] = library[-2], library[-1]
    before = serialize_match_snapshot(stale)
    with pytest.raises(ActionRejected):
        checked_action(stale, ENGINE, seat, {'type': 'choose_mechanic', 'card_ids': ['reveal']})
    assert serialize_match_snapshot(stale) == before
    state.cards[source].move_to_zone(Zone.HAND)
    state.cards[source].move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source)
    result = checked_action(state, ENGINE, seat, {'type': 'choose_mechanic', 'card_ids': ['reveal']})
    assert (result.cards[source].selected_face_index or 0) == 0
    assert top in result.card_observations[3-seat]


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_top_finishes_real_upkeep_trigger_without_fake_choice(seat):
    state, source, _ = position(seat, empty=True)
    ENGINE.next_step(state)
    for _ in range(2):
        state = checked_action(state, ENGINE, state.priority_player, {'type': 'pass_priority'})
    assert state.step == Step.UPKEEP and not state.pending_mechanic_choice
    assert (state.cards[source].selected_face_index or 0) == 0


def test_parser_uses_complete_canonical_instruction_and_own_upkeep_only():
    text = DELVER['card_faces'][0]['oracle_text']
    assert parse_upkeep_reveal(text)['required_types'] == ['Instant', 'Sorcery']
    assert parse_upkeep_reveal(text + ' Draw a card.') is None
    state, source, _ = position(1)
    for step, active in [('end_step', 1), ('upkeep', 2), ('untap', 1)]:
        row = _trigger_from_oracle(state, source, 1, text, 'canonical trigger', 'begin_step',
                                   {'step': step, 'active_player': active})
        assert row['effect_key'] == 'noop'
