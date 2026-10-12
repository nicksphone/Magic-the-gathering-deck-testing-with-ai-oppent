"""Malformed cache containers remain unavailable despite a canonical seed."""
from types import SimpleNamespace

import pytest

from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.sync import ScryfallSyncService


@pytest.mark.parametrize('stored', ['{}', 'invalid json', '1', '"faces"', 'true', '[null]'])
def test_malformed_face_cache_cannot_hide_behind_canonical_seed(stored, monkeypatch):
    monkeypatch.setattr(ScryfallSyncService, 'sync_card_by_name',
                        lambda *args, **kwargs: pytest.fail('Hydration must stay offline'))
    row = SimpleNamespace(oracle_text='', card_faces_json=stored)
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {'brutal cathar': row})
    result = hydrate_deck_cards(repo, [{'card_name': 'Brutal Cathar', 'quantity': 4}])[0]
    assert not ready_for_match(result)
    assert result['oracle_text'] == result['type_line'] == ''
    assert result['card_faces'] == result['card_data_sources'] == []
