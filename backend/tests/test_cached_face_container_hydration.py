"""Malformed cache containers must not become valid through seed fallback."""
from copy import deepcopy

import pytest
from fastapi import HTTPException

import main
from api_contracts import DeckEntry
from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.service import CardService
from tests.test_oracle_metadata_types import ReadOnlyRows, raw_card


BAD_CONTAINERS = [
    pytest.param('{}', id='empty-object'),
    pytest.param('{"oracle_text":37}', id='object-with-bad-text'),
    pytest.param('false', id='json-false'),
    pytest.param('true', id='json-true'),
    pytest.param('0', id='json-zero'),
    pytest.param('37', id='json-integer'),
    pytest.param('""', id='json-empty-string'),
    pytest.param('"[]"', id='json-list-string'),
    pytest.param('"face"', id='json-string'),
    pytest.param('[null]', id='list-null'),
    pytest.param('[false]', id='list-boolean'),
    pytest.param('["face"]', id='list-string'),
    pytest.param('[', id='invalid-json'),
    pytest.param(False, id='stored-boolean'),
    pytest.param(0, id='stored-integer'),
    pytest.param([], id='stored-list'),
    pytest.param({}, id='stored-object'),
]


@pytest.mark.parametrize('container', BAD_CONTAINERS)
def test_hydration_and_completeness_reject_before_cache_coercion(container):
    raw = raw_card('Deadly Dispute')
    repo = ReadOnlyRows(raw, 'cache')
    repo.row.card_faces_json = deepcopy(container)
    before = deepcopy(vars(repo))
    deck = hydrate_deck_cards(repo, [{'card_name': raw['name'], 'quantity': 8}])
    assert ready_for_match(deck[0]) is False
    assert deck[0]['oracle_text'] == '' and deck[0]['type_line'] == ''
    assert deck[0]['card_faces'] == [] and deck[0]['card_data_sources'] == []
    card = CardService(repo).completeness_report([raw['name']])['cards'][0]
    assert card['match_ready'] is False and card['needs_card_sync'] is True
    assert card['oracle'] is False and card['faces'] == []
    assert vars(repo) == before


@pytest.mark.parametrize('container', BAD_CONTAINERS)
@pytest.mark.parametrize('seat', [1, 2])
def test_public_match_preflight_rejects_before_factory_or_publication(container, seat, monkeypatch):
    raw = raw_card('Deadly Dispute')
    repo = ReadOnlyRows(raw, 'cache')
    repo.row.card_faces_json = deepcopy(container)
    before = deepcopy(vars(repo))
    before_active = dict(main.ACTIVE_MATCHES)
    entry = DeckEntry(card_name=raw['name'], quantity=8)
    good = DeckEntry(card_name='Lightning Bolt', quantity=8)
    payload = main.StartMatchRequest(deck_a=[entry if seat == 1 else good],
                                     deck_b=[entry if seat == 2 else good], sandbox=True)
    reached = []

    def forbidden_factory(*args, **kwargs):
        reached.append(True)
        pytest.fail('Malformed cached faces reached MatchFactory')

    monkeypatch.setattr(main.MatchFactory, 'from_decks', forbidden_factory)
    with pytest.raises(HTTPException) as caught:
        main._create_match(payload, repo, None, 'pure-cached-container-boundary')
    assert caught.value.status_code == 422
    assert caught.value.detail['code'] == 'card_data_unavailable'
    assert caught.value.detail['cards'] == [raw['name']]
    assert not reached and main.ACTIVE_MATCHES == before_active
    assert vars(repo) == before


@pytest.mark.parametrize('name', ['Deadly Dispute', 'Grizzly Bears', 'Island'])
@pytest.mark.parametrize('container', ['missing', None, '', '[]', 'null'])
def test_legitimate_absent_and_empty_face_containers_keep_canonical_fallback(name, container):
    raw = raw_card(name)
    repo = ReadOnlyRows(raw, 'cache')
    if container == 'missing':
        del repo.row.card_faces_json
    else:
        repo.row.card_faces_json = container
    before = deepcopy(vars(repo))
    entry = DeckEntry(card_name=name, quantity=8)
    deck = main._validated_deck_cards(repo, [entry])
    assert ready_for_match(deck[0]) is True
    assert deck[0].get('oracle_text', '') == (raw.get('oracle_text') or
                                            (raw.get('card_faces') or [{}])[0].get('oracle_text', ''))
    if raw.get('card_faces'):
        assert [face['oracle_text'] for face in deck[0]['card_faces']] == [
            face['oracle_text'] for face in raw['card_faces']]
    card = CardService(repo).completeness_report([name])['cards'][0]
    assert card['match_ready'] is True and card['needs_card_sync'] is False
    assert vars(repo) == before


def test_complete_canonical_multiface_container_keeps_every_original_body():
    raw = raw_card('Bala Ged Recovery // Bala Ged Sanctuary')
    repo = ReadOnlyRows(raw, 'cache')
    before = deepcopy(vars(repo))
    deck = main._validated_deck_cards(repo, [DeckEntry(card_name=raw['name'], quantity=8)])
    assert ready_for_match(deck[0]) is True
    assert [face['oracle_text'] for face in deck[0]['card_faces']] == [
        face['oracle_text'] for face in raw['card_faces']]
    assert vars(repo) == before
