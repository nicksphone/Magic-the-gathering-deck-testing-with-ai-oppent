"""Oracle type boundaries; corrupted values are declared malformed, not Oracle.

Canonical controls preserve committed public rows and complete seed text.
All repository access is an owned in-memory read-only row provider, with no SQL.
"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import main
from api_contracts import DeckEntry
from card_data.fallback_cards import fallback_card_payload
from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.service import CardService
from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory

PUBLIC_ROWS = json.loads((Path(__file__).parent / 'fixtures/offline_hydration.json').read_text())
BAD = [pytest.param(37, id='integer'), pytest.param(0, id='zero'),
       pytest.param(True, id='true'), pytest.param(False, id='false'),
       pytest.param(1.5, id='float'), pytest.param([], id='list'),
       pytest.param({}, id='object')]


def raw_card(name):
    public = next((row for row in PUBLIC_ROWS if row['name'] == name), None)
    if public is not None:
        return deepcopy(public)
    # Explicit projection of a committed seed row, not an invented canonical body.
    raw = deepcopy(fallback_card_payload(name))
    raw['id'] = raw.pop('scryfall_id')
    raw['object'] = 'card'
    return raw


class ReadOnlyRows:
    def __init__(self, raw, source):
        self.raw = deepcopy(raw)
        self.source = source
        self.row = SimpleNamespace(
            name=raw['name'], scryfall_id=raw['id'], oracle_text=raw.get('oracle_text'),
            mana_cost=raw.get('mana_cost', ''), type_line=raw.get('type_line', ''),
            layout=raw.get('layout', ''), colors=','.join(raw.get('colors') or []),
            power=raw.get('power'), toughness=raw.get('toughness'), loyalty=raw.get('loyalty'),
            image_uri='https://invalid.example/declared-never-fetched.jpg',
            card_faces_json=json.dumps(raw.get('card_faces') or []),
            legalities_json=json.dumps(raw.get('legalities') or {}), rulings_json='[]',
            oracle_source='scryfall', profiles_json=json.dumps({'card_data': raw}))

    def get_cached_cards_by_names(self, names):
        return {name.lower(): self.row for name in names if name == self.row.name and self.source == 'cache'}

    def get_card_knowledge_by_names(self, names):
        return {name.casefold(): self.row for name in names if name == self.row.name and self.source == 'knowledge'}


@pytest.mark.parametrize('bad', BAD)
def test_raw_normalization_rejects_nonstring_oracle_before_fallback(bad):
    raw = raw_card('Deadly Dispute')
    raw['oracle_text'] = bad
    before = deepcopy(raw)
    with pytest.raises(ValueError, match='Oracle'):
        ScryfallSyncService._normalize_payload(raw, 'https://invalid.example/unused.jpg')
    assert raw == before


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('face_index', [0, 1])
def test_normalization_rejects_malformed_oracle_on_every_face(bad, face_index):
    raw = raw_card('Bala Ged Recovery // Bala Ged Sanctuary')
    raw['card_faces'][face_index]['oracle_text'] = bad
    before = deepcopy(raw)
    with pytest.raises(ValueError, match='Oracle'):
        ScryfallSyncService._normalize_payload(raw, 'https://invalid.example/unused.jpg')
    assert raw == before


@pytest.mark.parametrize('bad', BAD)
def test_face_projection_itself_rejects_malformed_oracle(bad):
    faces = raw_card('Bala Ged Recovery // Bala Ged Sanctuary')['card_faces']
    faces[1]['oracle_text'] = bad
    with pytest.raises(ValueError, match='Oracle'):
        ScryfallSyncService._normalize_faces(faces)


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('name', ['Deadly Dispute', 'Grizzly Bears'])
def test_readiness_rejects_nonstring_oracle_for_spells_and_vanilla(bad, name):
    raw = raw_card(name)
    raw['oracle_text'] = bad
    before = deepcopy(raw)
    assert ready_for_match(raw) is False
    assert raw == before


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('face_index', [0, 1])
def test_readiness_checks_all_face_oracle_types(bad, face_index):
    raw = raw_card('Bala Ged Recovery // Bala Ged Sanctuary')
    raw['card_faces'][face_index]['oracle_text'] = bad
    # This is already-hydrated metadata with a legitimate string-valued front;
    # the malformed second face must not hide behind that valid root text.
    raw['oracle_text'] = raw_card('Bala Ged Recovery // Bala Ged Sanctuary')['card_faces'][0]['oracle_text']
    assert ready_for_match(raw) is False


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('source', ['knowledge', 'cache'])
def test_hydration_and_completeness_fail_closed_without_seed_masking(bad, source):
    raw = raw_card('Deadly Dispute')
    raw['oracle_text'] = bad
    repo = ReadOnlyRows(raw, source)
    before = deepcopy(vars(repo))
    deck = hydrate_deck_cards(repo, [DeckEntry(card_name=raw['name'], quantity=8).model_dump()])
    assert len(deck) == 1 and ready_for_match(deck[0]) is False
    # Unknown/unavailable metadata must not contain an executable malformed body.
    assert deck[0].get('type_line', '') == ''
    assert deck[0].get('oracle_text', '') == ''
    row = CardService(repo).completeness_report([raw['name']])['cards'][0]
    assert row['match_ready'] is False
    assert row['needs_card_sync'] is True
    assert row['oracle'] is False
    assert vars(repo) == before


@pytest.mark.parametrize('source', ['knowledge', 'cache'])
@pytest.mark.parametrize('face_index', [0, 1])
def test_hydration_does_not_expose_malformed_face_to_coverage(source, face_index):
    raw = raw_card('Bala Ged Recovery // Bala Ged Sanctuary')
    raw['card_faces'][face_index]['oracle_text'] = 37
    repo = ReadOnlyRows(raw, source)
    deck = hydrate_deck_cards(repo, [{'card_name': raw['name'], 'quantity': 1}])
    assert ready_for_match(deck[0]) is False
    row = CardService(repo).completeness_report([raw['name']])['cards'][0]
    assert row['match_ready'] is False and row['needs_card_sync'] is True
    assert row['faces'] == []


@pytest.mark.parametrize('source', ['knowledge', 'cache'])
@pytest.mark.parametrize('seat', [1, 2])
def test_public_match_start_rejects_malformed_before_factory_or_publication(source, seat, monkeypatch):
    raw = raw_card('Deadly Dispute')
    raw['oracle_text'] = 37
    repo = ReadOnlyRows(raw, source)
    entry = DeckEntry(card_name=raw['name'], quantity=8)
    # Both seats must be reached: the other deck has ordinary complete seed data.
    good = DeckEntry(card_name='Lightning Bolt', quantity=8)
    payload = main.StartMatchRequest(deck_a=[entry if seat == 1 else good],
                                     deck_b=[entry if seat == 2 else good], sandbox=True)
    before = deepcopy(vars(repo))
    before_active = dict(main.ACTIVE_MATCHES)
    reached = []

    def forbidden_factory(*args, **kwargs):
        reached.append(True)
        pytest.fail('Malformed metadata reached MatchFactory')

    monkeypatch.setattr(main.MatchFactory, 'from_decks', forbidden_factory)
    with pytest.raises(HTTPException) as caught:
        main._create_match(payload, repo, None, 'pure-malformed-boundary')
    assert caught.value.status_code == 422
    assert caught.value.detail['code'] == 'card_data_unavailable'
    assert caught.value.detail['cards'] == ['Deadly Dispute']
    assert not reached
    assert main.ACTIVE_MATCHES == before_active and vars(repo) == before


@pytest.mark.parametrize('source', ['knowledge', 'cache'])
@pytest.mark.parametrize('name', ['Grizzly Bears', 'Bala Ged Recovery // Bala Ged Sanctuary', 'Deadly Dispute'])
def test_unchanged_public_and_full_seed_bodies_remain_ready_and_snapshot_safe(source, name):
    raw = raw_card(name)
    before = deepcopy(raw)
    repo = ReadOnlyRows(raw, source)
    deck = main._validated_deck_cards(repo, [DeckEntry(card_name=raw['name'], quantity=8)])
    assert ready_for_match(deck[0]) is True
    if name == 'Grizzly Bears':
        assert raw['oracle_text'] == '' and deck[0].get('oracle_text', '') == ''
    elif name.startswith('Bala Ged Recovery'):
        assert raw.get('oracle_text') is None
        assert deck[0]['oracle_text'] == raw['card_faces'][0]['oracle_text']
        assert [face['oracle_text'] for face in deck[0]['card_faces']] == [face['oracle_text'] for face in raw['card_faces']]
    else:
        assert deck[0]['oracle_text'] == raw['oracle_text']
    state = MatchFactory.from_decks(deck, deck, seed=94)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    for seat in (1, 2):
        cards = [card for card in restored.cards.values() if card.owner == seat]
        assert len(cards) == 8
        assert all(card.oracle_text == deck[0].get('oracle_text', '') for card in cards)
    row = CardService(repo).completeness_report([raw['name']])['cards'][0]
    assert row['match_ready'] is True and row['needs_card_sync'] is False
    assert raw == before
