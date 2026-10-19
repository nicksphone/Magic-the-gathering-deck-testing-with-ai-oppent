"""The copy ability must receive the actual printed card, not its former Forest."""
from copy import deepcopy

import pytest

from rules_engine.copiable_values import values
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory
from tests.creature_copy_canonical_current import deck_entry, source_id
from tests.test_creature_copy_tokens import _put, _state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Reflection of Kiki-Jiki', 'Bloodtithe Harvester',
                                 'Sheoldred, the Apocalypse', 'Topiary Stomper', 'Forest'])
def test_printed_fixture_replacement_has_matching_retained_stock(seat, name):
    state = _state()
    old_id = source_id(state, seat, name)
    old = state.cards[old_id]
    identity = (old.id, old.owner, old.controller, old.zone_change_sequence,
                old.tapped, deepcopy(old.counters))
    rng = state.rng.getstate()
    count = len(state.cards)

    card_id = _put(state, seat, name)

    card = state.cards[card_id]
    stock = values(card)
    assert card_id == old_id
    assert stock['name'] == card.name == name
    assert stock['oracle_text'] == card.oracle_text
    assert stock['type_line'] == card.type_line
    assert stock['power'] == card.power and stock['toughness'] == card.toughness
    assert (card.id, card.owner, card.controller, card.zone_change_sequence,
            card.tapped, card.counters) == identity
    assert card.summoning_sick is False
    assert state.rng.getstate() == rng and len(state.cards) == count
    assert card_id not in state.players[seat].library
    assert state.players[seat].battlefield.count(card_id) == 1
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot


def test_declared_birth_retains_original_rng_ids_and_opening_resources():
    deck = [deck_entry('Forest', 60)]
    reference = MatchFactory.from_decks(deck, deck, seed=49)
    state = _state()
    assert state.players == reference.players
    assert set(state.cards) == set(reference.cards) and len(state.cards) == 120
    assert state.rng.getstate() == reference.rng.getstate()
    assert all(state.cards[cid].name == 'Forest'
               for player in state.players.values() for cid in player.hand)
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('corruption', ['birth-name', 'faces'])
def test_snapshot_still_rejects_corrupted_physical_stock(seat, corruption):
    state = _state()
    card_id = _put(state, seat, 'Reflection of Kiki-Jiki')
    snapshot = serialize_match_snapshot(state)
    corrupt = deepcopy(snapshot)
    if corruption == 'birth-name':
        corrupt['cards'][card_id]['printed_characteristics']['name'] = 'Forest'
    else:
        corrupt['cards'][card_id]['card_faces'][1]['name'] = 'incorrect-physical-face'
    with pytest.raises(ValueError, match='Sideboard stock does not match physical printed source'):
        deserialize_match_snapshot(corrupt)
    assert serialize_match_snapshot(state) == snapshot
