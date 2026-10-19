"""Unchanged generic-import fixtures extracted from archived characterization."""
from copy import deepcopy
import json
import os
import pickle
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.deck_analysis import analyze_deck
from ai.information import decision_view, is_unknown
from card_data import hydration
from card_data.sync import ScryfallSyncService
from decks.builtin_decks import BUILTIN_DECKS
from decks.service import DeckService
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from tests.test_builtin_metadata_refresh import repo, rows, seed_cache

FAMILIES = [('Burn', 'Burn'), ('Dimir Control', 'Control')]
def parsed(repo, name):
    result = DeckService(repo).parser.parse(BUILTIN_DECKS[name])
    assert not result.errors
    return result


def card_rows(repo):
    return [row.model_dump(mode='json') for row in repo.list_cards()]


@pytest.fixture
def client(repo, monkeypatch):
    import main
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})
    monkeypatch.setattr(main.app, 'dependency_overrides', {main.get_repo: lambda: repo})
    def forbidden(*a, **k):
        pytest.fail('No application startup, default database or remote sync')
    monkeypatch.setattr(main, 'init_db', forbidden)
    monkeypatch.setattr(main.app.router, 'lifespan_context', forbidden)
    monkeypatch.setattr(ScryfallSyncService, 'sync_card_by_name', forbidden)
    value = TestClient(main.app)  # Do not enter lifespan or listen on a socket.
    yield value
    value.close()


def observed_admission(deck):
    actual = analyze_deck(deck)
    admitted = (bool(deck) and all(c.get('card_data_sources') and hydration.ready_for_match(c) for c in deck)
                and actual['type_metadata_coverage'] == 1 and actual['confidence'] > 0
                and not {'missing_card_metadata', 'partial_card_metadata', 'fallback_midrange'}
                .intersection(actual['signals']))
    return {'actual_analysis': actual, 'canonical_complete': admitted,
            'unsupported_cards': [c['card_name'] for c in deck if not c.get('card_data_sources') or not hydration.ready_for_match(c)],
            'sources': sorted({s for c in deck for s in c.get('card_data_sources', [])}),
            'canonical_cards': deck}
