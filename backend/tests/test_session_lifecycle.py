"""Request dependencies release pooled connections even when references survive."""
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

import main
import persistence.db as db
from persistence.models import DeckRecord


@pytest.mark.parametrize('outcome', ['read', 'success', 'rejected', 'error'])
def test_request_scoped_session_releases_pool_and_rolls_back_errors(tmp_path, monkeypatch, outcome):
    engine = create_engine(f'sqlite:///{tmp_path / "sessions.db"}', pool_size=1,
                           max_overflow=0, pool_timeout=0.1)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, 'engine', engine)
    retained = []
    app = FastAPI()

    @app.post('/exercise')
    def exercise(repo=Depends(main.get_repo)):
        retained.append(repo.session)
        repo.session.exec(text('SELECT 1'))
        if outcome == 'read':
            return {'ok': True}
        repo.session.add(DeckRecord(name='Lifecycle fixture', source='test',
                                   mainboard_json='[]', sideboard_json='[]', archetype_guess='unknown'))
        repo.session.flush()
        if outcome == 'rejected':
            raise HTTPException(422, 'Rejected before commit')
        if outcome == 'error':
            raise RuntimeError('Failure before commit')
        repo.session.commit()
        return {'ok': True}

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            for _ in range(20):
                response = client.post('/exercise')
                assert response.status_code == {'read': 200, 'success': 200, 'rejected': 422, 'error': 500}[outcome]
                assert engine.pool.checkedout() == 0
        with Session(engine) as session:
            assert len(session.exec(select(DeckRecord)).all()) == (20 if outcome == 'success' else 0)
    finally:
        for session in retained:
            session.close()
        engine.dispose()
