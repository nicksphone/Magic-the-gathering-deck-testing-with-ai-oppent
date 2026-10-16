"""Pure first-consumer/birth checks; not ordinary execution of the old six tests."""
from copy import deepcopy
from dataclasses import fields
import importlib
import json

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from tests.cleanup_canonical_db4e import (
    FIXTURES, PRINTED, canonical_card, canonical_entry, raw_card, set_printed,
)

NAMES = ('Island', 'Counterspell', 'Grizzly Bears', 'Sangromancer',
         'Elvish Clancaller', 'Llanowar Elves')
CASES = (
    ('test_ai_cleanup_discards_excess_land_instead_of_first_spell', 'Counterspell', 1, None),
    ('test_human_cleanup_choice_is_owned_validated_and_resumable_before_expiry', 'Grizzly Bears', 2,
     {'__eot_toughness': 1, '__damage_marked': 2}),
    ('test_cleanup_discard_trigger_grants_priority_then_repeats_cleanup', 'Sangromancer', 2, {}),
    ('test_cleanup_stabilizes_cascading_state_based_actions_before_priority', 'Elvish Clancaller', 1,
     {'-1/-1': 1, '__eot_toughness': 1}),
    ('test_cleanup_stabilizes_cascading_state_based_actions_before_priority', 'Llanowar Elves', 1, {'-1/-1': 1}),
)


class Consumed(BaseException):
    pass


def expected_card(name):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    state = MatchFactory.from_decks([entry], [], seed=0)
    return next(card for card in state.cards.values() if card.zone == Zone.LIBRARY)


@pytest.mark.parametrize('body,name,owner,counters', CASES, ids=[row[1] for row in CASES])
def test_actual_original_first_cleanup_consumer_has_complete_printed_facts(monkeypatch, body, name, owner, counters):
    original = importlib.import_module('tests.test_cleanup_choices')
    expected = expected_card(name)

    def observe(self, state):
        cards = [card for card in state.cards.values() if card.name == name]
        assert len(cards) == 1
        actual = cards[0]
        assert not [field for field in PRINTED if getattr(actual, field) != getattr(expected, field)]
        assert actual.owner == actual.controller == owner
        if counters is not None:
            assert actual.counters == counters
        raise Consumed

    monkeypatch.setattr(original.RulesEngine, 'next_step', observe)
    with pytest.raises(Consumed):
        getattr(original, body)()


@pytest.mark.parametrize('player_id', [1, 2])
def test_original_setup_has_full_Island_at_actual_factory_birth(monkeypatch, player_id):
    original = importlib.import_module('tests.test_cleanup_choices')
    expected, factory = expected_card('Island'), MatchFactory.from_decks
    observed = []

    def capture(deck_a, deck_b, *args, **kwargs):
        state = factory(deck_a, deck_b, *args, **kwargs)
        assert len(state.cards) == 120
        assert all(all(getattr(card, field) == getattr(expected, field) for field in PRINTED)
                   for card in state.cards.values())
        observed.append(state)
        return state

    monkeypatch.setattr(original.MatchFactory, 'from_decks', capture)
    state, _ = original.setup(player_id)
    assert observed == [state]
    assert len(state.players[player_id].hand) == 8
    assert len(state.players[3 - player_id].hand) == 7
    assert state.active_player == state.priority_player == player_id


@pytest.mark.parametrize('name', NAMES)
def test_materializer_matches_normal_factory_and_full_RAW_is_fresh(name):
    raw = raw_card(name)
    assert len(raw) > 30 and raw['object'] == 'card' and raw['legalities'] and raw['image_uris']
    actual, expected = canonical_card(name, id='fixture', owner=2, controller=2, zone=Zone.HAND), expected_card(name)
    assert all(getattr(actual, field) == getattr(expected, field) for field in PRINTED)
    assert actual.id == 'fixture' and actual.owner == actual.controller == 2
    assert actual.instance_order == 0 and actual.summoning_sick
    raw['legalities'].clear()
    assert raw_card(name)['legalities']


def test_printed_overrides_rejected_and_source_manifest_has_only_the_six_names():
    assert set(json.loads((FIXTURES / 'cleanup_choices_db4e/SOURCES.json').read_text())) == set(NAMES)
    with pytest.raises(ValueError):
        canonical_card('Sangromancer', id='forged', owner=1, controller=1,
                       zone=Zone.BATTLEFIELD, oracle_text='Deliberate noncanonical override')


def test_controlled_hand_reprint_preserves_runtime_rng_and_stock_without_repair():
    original = importlib.import_module('tests.test_cleanup_choices')
    state, _ = original.setup()
    card = state.cards[state.players[1].hand[0]]
    card.counters = {'__damage_marked': 1}
    before = deepcopy(vars(card))
    rng, stock, decks = state.rng.getstate(), deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    set_printed(card, 'Counterspell')
    assert all(getattr(card, f.name) == before[f.name] for f in fields(CardInstance) if f.name not in PRINTED)
    assert state.rng.getstate() == rng and state.sideboard_facts == stock and state.starting_decks == decks
    sibling = canonical_card('Counterspell', id='other', owner=1, controller=1, zone=Zone.HAND)
    assert card.characteristic_record == sibling.characteristic_record
    assert card.characteristic_record is not sibling.characteristic_record
    card.characteristic_record.clear()
    assert sibling.characteristic_record


def test_canonical_setup_preserves_original_seed_resources_and_stock_identities():
    original = importlib.import_module('tests.test_cleanup_choices')
    deck = [{'quantity': 60, 'card_name': 'Island', 'type_line': 'Basic Land - Island'}]
    # Explicit legacy structural reference, not a real-card printed-fidelity waiver.
    state, _ = original.setup(2)
    reference = MatchFactory.from_decks(deck, deck, seed=9, game_id=state.id)
    assert state.rng.getstate() == reference.rng.getstate()
    assert state.sideboard_facts == reference.sideboard_facts
    assert list(state.cards) == list(reference.cards)
    assert [(p.life, p.poison, p.mana_pool) for p in state.players.values()] == [
        (p.life, p.poison, p.mana_pool) for p in reference.players.values()]
    assert [canonical_entry('Island', 60)['quantity']] == [60]


def test_actual_first_spell_has_genuine_stock_and_roundtrips_before_cleanup(monkeypatch):
    original = importlib.import_module('tests.test_cleanup_choices')

    def observe(self, state):
        cid = state.players[1].hand[0]
        assert state.cards[cid].name == 'Counterspell'
        assert state.sideboard_facts['inventory'][cid] == {'owner': 1, 'stock_key': 'Counterspell'}
        before = serialize_match_snapshot(state)
        restored = deserialize_match_snapshot(before)
        assert serialize_match_snapshot(restored) == before
        raise Consumed

    monkeypatch.setattr(original.RulesEngine, 'next_step', observe)
    with pytest.raises(Consumed):
        original.test_ai_cleanup_discards_excess_land_instead_of_first_spell()
