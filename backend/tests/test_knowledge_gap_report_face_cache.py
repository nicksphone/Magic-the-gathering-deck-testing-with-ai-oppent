"""Actual repository alias methods with recorded query results, not SQL execution."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from persistence.models import CardCache
from knowledge.models import CardKnowledge
from persistence.repository import Repository
from scripts import knowledge_gap_report as gap


def parent_cache(faces):
    return CardCache(scryfall_id='diagnostic-cache', name='Front // Back',
                     layout='transform', type_line='Creature',
                     image_uri='/card-images/front.jpg', card_faces_json=faces)


def stored_knowledge(present):
    return [] if not present else [CardKnowledge(name='Back', oracle_source='manual',
        profiles_json=json.dumps({'card_data': {'name': 'Back', 'oracle_text': ''}}))]


def recorded_repository(cache, knowledge=(), *, alias=True):
    session = Mock()
    # The real list methods, exact-name miss, then the real DFC alias resolver run.
    batches = [list(knowledge), [cache], [] if alias else [cache]]
    if alias:
        batches.append([cache])
    session.exec.side_effect = [SimpleNamespace(all=lambda rows=rows: rows) for rows in batches]
    return Repository(session), session


CASES = [
    ('missing', json.dumps([{'name': 'Front', 'image_uri': '/card-images/front.jpg'},
                           {'name': 'Back', 'image_uri': '/card-images/back.jpg'}]),
     False, 'missing'),
    ('local', json.dumps([{'name': 'Front', 'image_uri': '/card-images/front.jpg'},
                         {'name': 'Back', 'image_uri': '/card-images/back.jpg'}]),
     True, 'local'),
    ('absent', '[]', None, 'unavailable'),
    ('malformed', 'invalid-json', None, 'unavailable'),
    ('invalid_member', '[null]', None, 'unavailable'),
    ('ambiguous', json.dumps([{'name': 'Back', 'image_uri': '/card-images/front.jpg'},
                             {'name': 'BACK', 'image_uri': '/card-images/back.jpg'}]),
     None, 'unavailable'),
]


@pytest.mark.parametrize('knowledge_present', [False, True])
@pytest.mark.parametrize('label,faces,local,status', CASES, ids=[row[0] for row in CASES])
def test_cache_alias_image_is_independent_of_canonical_knowledge(
        tmp_path, knowledge_present, label, faces, local, status):
    # Opposite physical availability distinguishes the selected face from parent URI.
    (tmp_path / ('back.jpg' if label == 'local' else 'front.jpg')).write_bytes(b'public diagnostic')
    cache = parent_cache(faces)
    repo, session = recorded_repository(cache, stored_knowledge(knowledge_present))
    before = cache.model_dump()
    row = gap.knowledge_report(repo, ['Back'], image_cache_dir=tmp_path)['cards'][0]
    assert session.exec.call_count == 4
    assert 'cardcache.name' in str(session.exec.call_args.args[0])
    assert row['cached'] is True
    assert row['knowledge_present'] is knowledge_present
    assert (row['local_image'], row['image_status']) == (local, status)
    assert cache.model_dump() == before


@pytest.mark.parametrize('name,faces', [('Front // Back', json.dumps([
    {'name': 'Front', 'image_uri': '/card-images/front.jpg'},
    {'name': 'Back', 'image_uri': '/card-images/back.jpg'}])), ('Vanilla', '[]')])
def test_exact_parent_and_single_face_keep_their_own_uri(tmp_path, name, faces):
    (tmp_path / 'front.jpg').write_bytes(b'public diagnostic')
    cache = parent_cache(faces)
    cache.name = name
    repo, session = recorded_repository(cache, alias=False)
    row = gap.knowledge_report(repo, [name], image_cache_dir=tmp_path)['cards'][0]
    assert session.exec.call_count == 3
    assert (row['local_image'], row['image_status']) == (True, 'local')
