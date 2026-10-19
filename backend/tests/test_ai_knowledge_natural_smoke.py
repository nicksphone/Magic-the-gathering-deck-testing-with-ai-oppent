"""Existing seeded head-to-head CLI with owned in-memory storage only."""
import json
from pathlib import Path
import sys

import httpx
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from knowledge.ingest import KnowledgeIngestor
from persistence.repository import Repository
from scripts import debug_head_to_head
from scripts.sync_corpus_cards import profile_corpus


def test_original_tempo_control_cli_completes_a_natural_seeded_game(monkeypatch, tmp_path):
    fixtures = Path(__file__).parent / 'fixtures/knowledge_profiles'
    cards = [json.loads(line) for line in (fixtures / 'seed155-scryfall.jsonl').read_bytes().splitlines()]
    pages = {page['url']: page['payload'] for page in map(json.loads, (fixtures / 'seed155-rulings.jsonl').read_bytes().splitlines())}
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr('knowledge.ingest.time.sleep', lambda seconds: None)
    try:
        with Session(engine) as session, httpx.Client(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=pages[str(request.url)]))) as client:
            repo = Repository(session)
            ingestor = KnowledgeIngestor(repo, client)
            for card in cards:
                ingestor.sync_payload(card)
            assert profile_corpus(repo, [card['name'] for card in cards])['errors'] == []
        # Storage relocation for this fresh schema; CLI/game logic remains real.
        monkeypatch.setattr(debug_head_to_head, 'engine', engine)
        monkeypatch.setattr(debug_head_to_head, 'init_db', lambda: SQLModel.metadata.create_all(engine))
        monkeypatch.setattr(sys, 'argv', ['debug_head_to_head.py', '--deck-a', 'Tempo',
            '--deck-b', 'Blue Control', '--matches', '1', '--seed', '731',
            '--max-ticks', '6000', '--out-dir', str(tmp_path)])
        assert debug_head_to_head.main() == 0
        summaries = list(tmp_path.glob('h2h-*/summary.json'))
        assert len(summaries) == 1
        summary = json.loads(summaries[0].read_bytes())
        assert summary['wins']['timeout'] == 0, 'Bounded smoke did not complete a natural game'
        games = list(tmp_path.glob('h2h-*/games.jsonl'))
        rows = [json.loads(line) for line in games[0].read_bytes().splitlines()]
        assert len(rows) == 1 and rows[0]['winner'] in (1, 2)
        traces = [json.loads(line[len('AI TRACE '):]) for line in rows[0]['log'] if line.startswith('AI TRACE ')]
        assert traces and all('knowledge_usage' in trace for trace in traces)
        assert sum(trace['knowledge_usage']['persisted'] for trace in traces) > 0
        assert not any('invalid target' in line.lower() or 'illegal action' in line.lower() for line in rows[0]['log'])
    finally:
        engine.dispose()
