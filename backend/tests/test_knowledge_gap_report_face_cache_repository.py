"""Real memory SQL qualification: execution requires the reviewed mixed I/O scope."""
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from persistence.repository import Repository
from scripts import knowledge_gap_report as gap
from tests import test_knowledge_gap_report_face_cache as fixtures


@pytest.mark.parametrize('knowledge_present', [False, True])
@pytest.mark.parametrize('case_index', [0, 1, 5], ids=['missing', 'local', 'ambiguous'])
def test_real_repository_cached_alias_has_no_parent_front_fallback(
        tmp_path, knowledge_present, case_index):
    label, faces, local, status = fixtures.CASES[case_index]
    (tmp_path / ('back.jpg' if label == 'local' else 'front.jpg')).write_bytes(b'public diagnostic')
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            cache = fixtures.parent_cache(faces)
            session.add(cache)
            for knowledge in fixtures.stored_knowledge(knowledge_present):
                session.add(knowledge)
            session.commit()
            repo = Repository(session)
            assert repo.get_cached_card_by_name('Back').id == cache.id
            before = cache.model_dump()
            row = gap.knowledge_report(repo, ['Back'], image_cache_dir=tmp_path)['cards'][0]
            assert row['cached'] is True
            assert row['knowledge_present'] is knowledge_present
            assert (row['local_image'], row['image_status']) == (local, status)
            assert cache.model_dump() == before
    finally:
        engine.dispose()
