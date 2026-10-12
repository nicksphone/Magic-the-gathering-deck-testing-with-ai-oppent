"""Real persisted canonical knowledge through hydration and AI consumption."""
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from ai.agent import AIAgent
from card_data.hydration import hydrate_deck_cards
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from knowledge.ingest import KnowledgeIngestor
from persistence.repository import Repository
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from scripts.sync_corpus_cards import profile_corpus

FIXTURE = Path(__file__).parent / 'fixtures/knowledge_profiles'
CARDS = {card['name']: card for card in map(json.loads, (FIXTURE / 'seed155-scryfall.jsonl').read_bytes().splitlines())}
RULINGS = {row['url']: row['payload'] for row in map(json.loads, (FIXTURE / 'seed155-rulings.jsonl').read_bytes().splitlines())}


@pytest.fixture
def database():
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def ingest(repo, names, monkeypatch):
    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    requests = []

    def respond(request):
        url = str(request.url)
        assert url in RULINGS
        requests.append(url)
        return httpx.Response(200, json=RULINGS[url])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        source = KnowledgeIngestor(repo, client)
        for name in names:
            source.sync_payload(deepcopy(CARDS[name]))
    assert len(requests) == len(names)
    assert profile_corpus(repo, names) == {'profiled': len(names), 'profiles_updated': len(names), 'errors': []}


def test_all_155_actual_persisted_rows_hydrate_and_keep_private_factory_carriers(database, monkeypatch):
    with Session(database) as session:
        repo = Repository(session)
        ingest(repo, list(CARDS), monkeypatch)
    with Session(database) as session:
        repo = Repository(session)
        seed = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_bytes())['cards']
        deck = hydrate_deck_cards(repo, [{'card_name': name, 'quantity': 1} for name in seed])
        missing = [row['card_name'] for row in deck if not row.get('knowledge_snapshot')]
        assert missing == [], f'Canonical persisted rows lost carriers in hydration: {missing}'
        assert len(deck) == 155
        assert all(row['knowledge_snapshot']['rulings_pending'] is False for row in deck)
    state = MatchFactory.from_decks(deck, deck, seed=419)
    assert len(state.cards) == 310
    assert all(card.knowledge_snapshot for card in state.cards.values())
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(deepcopy(snapshot))
    assert serialize_match_snapshot(restored) == snapshot
    for seat in (1, 2):
        assert 'knowledge_snapshot' not in json.dumps(serialize_match(restored, look_players=[seat]))


@pytest.mark.parametrize('seat', [1, 2])
def test_real_repository_paid_choice_and_cold_restore_need_no_live_database(database, monkeypatch, seat):
    names = ['Lightning Bolt', 'Mountain', 'Forest']
    with Session(database) as session:
        repo = Repository(session)
        ingest(repo, names, monkeypatch)
    with Session(database) as session:
        repo = Repository(session)
        own = hydrate_deck_cards(repo, [{'card_name': 'Lightning Bolt', 'quantity': 12},
                                       {'card_name': 'Mountain', 'quantity': 12}])
        enemy = hydrate_deck_cards(repo, [{'card_name': 'Forest', 'quantity': 24}])
        assert all(row.get('knowledge_snapshot') for row in own + enemy), 'Real row hydration did not attach canonical carriers'
    database.dispose()
    state = MatchFactory.from_decks(own if seat == 1 else enemy, enemy if seat == 1 else own, seed=731)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    # Trusted initial board declaration; subsequent mana/cast/passes are checked.
    for cid in list(state.players[seat].hand):
        state.players[seat].hand.remove(cid)
        state.players[seat].library.append(cid)
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    bolt = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Lightning Bolt')
    mountain = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Mountain')
    for card, zone in ((bolt, Zone.HAND), (mountain, Zone.BATTLEFIELD)):
        state.players[seat].library.remove(card.id)
        getattr(state.players[seat], zone.value).append(card.id)
        card.move_to_zone(zone)
        card.summoning_sick = False
    engine = RulesEngine()
    state = checked_action(state, engine, seat, {'type': 'tap_land_for_mana', 'card_id': mountain.id, 'color': 'R'})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    import _sqlite3
    import sqlite3

    def forbidden(*args, **kwargs):
        pytest.fail('AI decision attempted a live SQL connection')

    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(sqlite3.dbapi2, 'connect', forbidden)
    monkeypatch.setattr(_sqlite3, 'connect', forbidden)
    decision = AIAgent(difficulty='strong', archetype='Aggro').choose_action(state, engine.legal_moves(state, seat), seat)
    assert decision.knowledge_usage['persisted'] > 0
    assert decision.knowledge_usage['fallback'] == 0
    assert decision.action['type'] == 'cast_spell'
    result = checked_action(state, engine, seat, decision.action)
    assert result.stack[-1].source_card_id == bolt.id
    assert result.stack[-1].payload['mana_spent'] == 1
    for _ in range(2):
        result = checked_action(result, engine, result.priority_player, {'type': 'pass_priority'})
    assert result.players[3 - seat].life == 17
    assert result.cards[bolt.id].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before
