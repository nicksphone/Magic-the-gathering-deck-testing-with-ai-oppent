"""Complete canonical paid controls; JSON/protocol cases are not SQL or games."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import inspect_target_hints
from tests.canonical_positive_fixtures import raw_card
from tests.domain_printed_fixtures76 import raw as domain_raw


ROOT = Path(__file__).parent / 'fixtures/glimpse_cave_full_printings'
PRINTINGS = {
    'Glimpse the Core': {
        'file': 'glimpse-the-core-lci.json', 'fields': 64,
        'sha256': 'ec77f6bc5180a7e676f83a5f688fbb7e3ac5ae6a6b8455bf982c3520576901bc',
        'id': 'de7d6aed-3dc8-417d-a190-1660cfc8ee4a',
        'oracle_id': 'fa44fa48-d270-4f0f-b672-d63e1c1942ce',
    },
    'Hidden Courtyard': {
        'file': 'hidden-courtyard-lci.json', 'fields': 64,
        'sha256': '920ace871e92dd50a9d37376c761b7731537be02db15d864b96e2bb74434e06a',
        'id': 'b8685d46-99fc-44b3-be95-707a4b7b8327',
        'oracle_id': 'e19d5071-4ea1-4883-b067-a21e553f96e0',
    },
    'Spelunking': {
        'file': 'spelunking-lci.json', 'fields': 63,
        'sha256': '506ed65f67a9e43ec228e17befb646353f33ad07c2199a52707b6f2e00a0458c',
        'id': 'd3be4257-2316-4a2e-b347-f71c0368a947',
        'oracle_id': '2962fe4c-bf48-454b-8a6b-0f8253352ae8',
    },
}
# Full archival bytes/provenance: alanwsmith/mtg-data at
# d1d5859940650910bf0a9bed0099511f94cef22b; no art-series face projection.
FOREST_MODE = ('Search your library for a basic Forest card, put that card onto '
               'the battlefield tapped, then shuffle.')
CAVE_MODE = 'Return target Cave card from your graveyard to the battlefield tapped.'


class MissingForestSearchPrompt(AssertionError):
    """Literal failure stage; no native values or diagnostic bodies are emitted."""


class MissingCaveReturnEntry(AssertionError):
    """Literal failure stage after paid settlement, without native values."""


class MissingCaveMoveTarget(AssertionError):
    """Literal missing candidate in the unselected hand-casting move."""


def printing(name):
    pin = PRINTINGS[name]
    encoded = (ROOT / pin['file']).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == pin['sha256']
    raw = json.loads(encoded)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['layout'] == 'normal' and raw['lang'] == 'en' and raw['set'] == 'lci'
    assert raw['id'] == pin['id'] and raw['oracle_id'] == pin['oracle_id']
    assert len(raw) == pin['fields']
    return raw


def add(state, name, seat, zone, *, raw=None):
    raw = printing(name) if raw is None else raw
    sample = MatchFactory.from_decks(
        [{**raw, 'card_name': name, 'quantity': 1}], [], seed=7619)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id, card.owner, card.controller = state.allocate_object_id(), seat, seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        card.summoning_sick = False
        card.entered_turn = state.turn
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def take_forest(state, seat, zone):
    player = state.players[seat]
    cid = next(cid for cid in player.library if state.cards[cid].name == 'Forest')
    player.library.remove(cid)
    card = state.cards[cid]
    card.move_to_zone(zone)
    card.controller, card.tapped = seat, False
    getattr(player, zone.value).append(cid)
    if zone == Zone.BATTLEFIELD:
        card.summoning_sick = False
        card.entered_turn = state.turn
        assign_static_order_on_battlefield_entry(state, cid)
    return cid


def position(seat, *, spelunking=False, manual=False):
    forest = raw_card('Forest')
    assert forest['object'] == 'card' and forest['name'] == 'Forest'
    deck = [{**forest, 'card_name': 'Forest', 'quantity': 40}]
    state = MatchFactory.from_decks(deck, deck, seed=7619)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step, state.turn = Step.PRECOMBAT_MAIN, 5
    state.mechanic_choice_players = {1, 2}
    state.replacement_choice_players = {1, 2}
    state.replacement_choice_required = manual
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.mana_pool = {}
    lands = [take_forest(state, seat, Zone.BATTLEFIELD) for _ in range(3)]
    source = add(state, 'Glimpse the Core', seat, Zone.HAND)
    cave = add(state, 'Hidden Courtyard', seat, Zone.GRAVEYARD)
    if spelunking:
        add(state, 'Spelunking', seat, Zone.BATTLEFIELD)
    assert '• ' + FOREST_MODE in state.cards[source].oracle_text
    assert '• ' + CAVE_MODE in state.cards[source].oracle_text
    return state, source, cave, lands


def act(state, seat, request):
    before, supplied = serialize_match_snapshot(state), deepcopy(request)
    rng, local = random.getstate(), state.rng.getstate()
    try:
        result = checked_action(state, RulesEngine(), seat, request)
    finally:
        assert serialize_match_snapshot(state) == before and request == supplied
        assert random.getstate() == rng and state.rng.getstate() == local
    return result


def settle(state):
    for _ in range(48):
        if state.pending_mechanic_choice or state.pending_replacement_choice or not state.stack:
            return state
        assert not state.pending_trigger_order, 'No guessed trigger ordering'
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Bounded native settlement exhausted')


def restore(state):
    encoded = json.dumps(serialize_match_snapshot(state), sort_keys=True,
                         separators=(',', ':'), allow_nan=False)
    result = deserialize_match_snapshot(json.loads(encoded))
    assert json.dumps(serialize_match_snapshot(result), sort_keys=True,
                      separators=(',', ':'), allow_nan=False) == encoded
    assert result.rng.getstate() == state.rng.getstate()
    return result


def offered_mode(state, seat, source, printed_mode):
    modes = inspect_target_hints(state, state.cards[source], seat).get('modes', [])
    matches = [mode for mode in modes
               if mode.rstrip(' ;:.') == printed_mode.rstrip(' ;:.')]
    assert len(matches) == 1
    return matches[0]


def paid(state, seat, source, lands, mode, target=None):
    targets = {'mode_text': offered_mode(state, seat, source, mode)}
    if target is not None:
        targets['target_card_id'] = target
    result = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                              'cost_choice': {'id': 'base'}, 'targets': targets})
    assert result.cards[source].zone == Zone.STACK
    assert result.stack[-1].source_card_id == source
    assert result.stack[-1].payload['mana_spent'] == 2
    assert sum(result.cards[cid].tapped for cid in lands) == 2
    return result


def finished(state, seat, source):
    assert not state.stack and state.pending_mechanic_choice is None
    assert state.pending_replacement_choice is None and not state.pending_trigger_order
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.players[seat].graveyard.count(source) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('find', [False, True])
def test_paid_basic_forest_mode(seat, find):
    state, source, cave, lands = position(seat)
    eligible = set(state.players[seat].library)
    island, nonbasic = domain_raw('Island'), domain_raw('Temple Garden')
    assert island['layout'] == nonbasic['layout'] == 'normal'
    assert island['type_line'] == 'Basic Land — Island'
    prefix, subtypes = nonbasic['type_line'].split(' — ')
    assert 'Land' in prefix.split() and 'Basic' not in prefix.split()
    assert 'Forest' in subtypes.split()
    decoys = {
        add(state, 'Island', seat, Zone.LIBRARY, raw=island),
        add(state, 'Temple Garden', seat, Zone.LIBRARY, raw=nonbasic),
        add(state, 'Hidden Courtyard', seat, Zone.LIBRARY),
        add(state, 'Spelunking', seat, Zone.LIBRARY),
    }
    library = list(state.players[seat].library)
    other = deepcopy(serialize_match_snapshot(state)['players'][str(3-seat)])
    state = settle(paid(state, seat, source, lands, FOREST_MODE))
    pending = state.pending_mechanic_choice
    if pending is None:
        raise MissingForestSearchPrompt()
    assert pending['kind'] == 'search_library' and pending['player_id'] == seat
    assert pending['min_count'] == 0 and set(pending['options']) == eligible
    assert not decoys.intersection(pending['options'])
    for decoy in decoys:
        with pytest.raises(ActionRejected):
            act(state, seat, {'type': 'choose_mechanic', 'card_ids': [decoy]})
    rng = state.rng.getstate()
    chosen = next(cid for cid in library if cid in eligible)
    state = settle(act(state, seat, {'type': 'choose_mechanic',
                                    'card_ids': [chosen] if find else []}))
    finished(state, seat, source)
    assert state.rng.getstate() != rng
    assert len(state.players[seat].library) == len(library) - int(find)
    assert state.cards[cave].zone == Zone.GRAVEYARD
    if find:
        assert state.cards[chosen].zone == Zone.BATTLEFIELD and state.cards[chosen].tapped
        assert state.cards[chosen].owner == state.cards[chosen].controller == seat
    assert serialize_match_snapshot(state)['players'][str(3-seat)] == other


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('roundtrip', [False, True])
def test_paid_cave_mode_enters_tapped(seat, roundtrip):
    state, source, cave, lands = position(seat)
    moves = [move for move in RulesEngine().legal_moves(state, seat)
             if move['type'] == 'cast_spell' and move['card_id'] == source]
    assert len(moves) == 1
    hints = moves[0]['target_hints']
    offered = {row['id'] for key, rows in hints.items()
               if key.startswith('graveyard_') and key.endswith('_targets')
               for row in rows}
    if cave not in offered:
        raise MissingCaveMoveTarget()
    assert offered == {cave}
    assert offered_mode(state, seat, source, CAVE_MODE) in hints['available_modes']
    before_entries = state.land_entries_this_turn.get(seat, 0)
    other = deepcopy(serialize_match_snapshot(state)['players'][str(3-seat)])
    state = paid(state, seat, source, lands, CAVE_MODE, cave)
    if roundtrip:
        state = restore(state)
    state = settle(state)
    finished(state, seat, source)
    if state.cards[cave].zone != Zone.BATTLEFIELD:
        raise MissingCaveReturnEntry()
    assert state.cards[cave].zone == Zone.BATTLEFIELD and state.cards[cave].tapped
    assert state.cards[cave].owner == state.cards[cave].controller == seat
    assert state.players[seat].battlefield.count(cave) == 1
    assert cave not in state.players[seat].graveyard
    assert state.land_entries_this_turn[seat] == before_entries + 1
    assert serialize_match_snapshot(state)['players'][str(3-seat)] == other


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['opponent', 'battlefield', 'noncave', 'missing'])
def test_cave_mode_rejects_invalid_targets(seat, fault):
    state, source, cave, lands = position(seat)
    if fault == 'opponent':
        target = add(state, 'Hidden Courtyard', 3-seat, Zone.GRAVEYARD)
    elif fault == 'battlefield':
        target = add(state, 'Hidden Courtyard', seat, Zone.BATTLEFIELD)
    elif fault == 'noncave':
        target = take_forest(state, seat, Zone.GRAVEYARD)
    else:
        target = None
    mode = offered_mode(state, seat, source, CAVE_MODE)
    hints = inspect_target_hints(state, state.cards[source], seat, {'mode_text': mode})
    offered = {row['id'] for key, rows in hints.items()
               if key.startswith('graveyard_') and key.endswith('_targets')
               for row in rows}
    assert offered == {cave}
    targets = {'mode_text': mode}
    if target is not None:
        targets['target_card_id'] = target
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'cast_spell', 'card_id': source,
                         'cost_choice': {'id': 'base'}, 'targets': targets})
    assert state.cards[source].zone == Zone.HAND
    assert not any(state.cards[cid].tapped for cid in lands)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('entry', ['auto', 'tapped', 'untapped'])
def test_cave_return_composes_spelunking_entry(seat, entry):
    state, source, cave, lands = position(seat, spelunking=True, manual=entry != 'auto')
    library, life = len(state.players[seat].library), state.players[seat].life
    before_entries = state.land_entries_this_turn.get(seat, 0)
    state = settle(paid(state, seat, source, lands, CAVE_MODE, cave))
    if entry != 'auto':
        assert state.pending_mechanic_choice['kind'] == 'land_entry'
        assert state.pending_mechanic_choice['player_id'] == seat
        assert set(state.pending_mechanic_choice['options']) == {'tapped', 'untapped'}
        assert state.cards[cave].zone == Zone.GRAVEYARD
        with pytest.raises(ActionRejected):
            act(state, 3-seat, {'type': 'choose_mechanic', 'choice_id': entry})
        state = settle(act(restore(state), seat,
                           {'type': 'choose_mechanic', 'choice_id': entry}))
    finished(state, seat, source)
    assert state.cards[cave].zone == Zone.BATTLEFIELD
    assert state.cards[cave].tapped is (entry == 'tapped')
    assert state.players[seat].battlefield.count(cave) == 1
    assert state.land_entries_this_turn[seat] == before_entries + 1
    assert len(state.players[seat].library) == library and state.players[seat].life == life
    if entry != 'auto':
        with pytest.raises(ActionRejected):
            act(state, seat, {'type': 'choose_mechanic', 'choice_id': entry})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['leave', 'leave_reenter'])
def test_paid_cave_target_departure_protocol(seat, fault):
    state, source, cave, lands = position(seat)
    state = paid(state, seat, source, lands, CAVE_MODE, cave)
    # Deliberate reference-protocol injection, not a claimed printed-card sequence.
    state.players[seat].graveyard.remove(cave)
    state.cards[cave].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(cave)
    if fault == 'leave_reenter':
        state.players[seat].exile.remove(cave)
        state.cards[cave].move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(cave)
    state = settle(restore(state))
    finished(state, seat, source)
    assert state.cards[cave].zone == (Zone.GRAVEYARD if fault == 'leave_reenter' else Zone.EXILE)
    assert cave not in state.players[seat].battlefield
