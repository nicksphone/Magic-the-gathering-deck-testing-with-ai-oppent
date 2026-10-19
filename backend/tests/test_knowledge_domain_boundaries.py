from __future__ import annotations

import json
from math import inf,nan

import pytest
from sqlalchemy import event
from sqlmodel import Session,SQLModel,create_engine

from knowledge.models import CardKnowledge
from persistence.repository import Repository


@pytest.fixture
def repo():
    engine=create_engine('sqlite://')
    SQLModel.metadata.create_all(engine,tables=[CardKnowledge.__table__])
    with Session(engine) as session:
        yield Repository(session)
    engine.dispose()


def payload(**changes):
    return {'name':'Domain boundary control','oracle_source':'manual',
            'play_value':5.0,'threat_level':2,'profiles':{'opaque':'retain'},**changes}


@pytest.mark.parametrize('field,value',[
    ('oracle_source','fallback'),('oracle_source','bulk'),('oracle_source',''),
    ('oracle_source',None),('play_value',-0.01),('play_value',10.01),
    ('play_value',nan),('play_value',inf),('play_value',-inf),
    ('threat_level',-1),('threat_level',4),('threat_level',1.5),
])
@pytest.mark.parametrize('existing',[False,True])
def test_invalid_knowledge_domain_rejects_before_insert_or_update(repo,field,value,existing):
    if existing:repo.upsert_card_knowledge(payload())
    before=[row.model_dump() for row in repo.list_card_knowledge()]
    writes=[]
    def observed(connection,cursor,statement,*args):
        if statement.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')):writes.append(statement.split()[0])
    event.listen(repo.session.bind,'before_cursor_execute',observed)
    try:
        with pytest.raises(ValueError):repo.upsert_card_knowledge(payload(**{field:value}))
    finally:event.remove(repo.session.bind,'before_cursor_execute',observed)
    assert writes==[]
    assert [row.model_dump() for row in repo.list_card_knowledge()]==before
    assert not repo.session.new and not repo.session.dirty


@pytest.mark.parametrize('score,threat',[(None,None),(0.0,0),(10.0,3),(7.25,2)])
@pytest.mark.parametrize('source',['manual','scryfall'])
def test_valid_knowledge_domains_preserve_existing_row_and_json(repo,score,threat,source):
    first=repo.upsert_card_knowledge(payload(play_value=score,threat_level=threat,oracle_source=source))
    row=repo.upsert_card_knowledge(payload(name='  DOMAIN BOUNDARY CONTROL  ',play_value=score,threat_level=threat,oracle_source=source))
    assert row.id==first.id and len(repo.list_card_knowledge())==1
    assert row.play_value==score and row.threat_level==threat and row.oracle_source==source
    assert json.loads(row.profiles_json)=={'opaque':'retain'}


def test_declared_schema_exposes_the_original_provenance_and_score_domains():
    fields=CardKnowledge.model_json_schema()['properties']
    assert set(fields['oracle_source']['enum'])=={'scryfall','manual'}
    for field,maximum in [('play_value',10),('threat_level',3)]:
        numeric=next(item for item in fields[field]['anyOf'] if item['type']!='null')
        assert numeric['minimum']==0 and numeric['maximum']==maximum


def test_legacy_invalid_rows_remain_readable_without_rewrite(repo):
    # SQLAlchemy loading stays compatible; public repository admission is validated.
    legacy=CardKnowledge(name='Legacy domain control',oracle_source='old-unverified',
                         play_value=12.0,threat_level=4,profiles_json='{"legacy":true}')
    repo.session.add(legacy)
    repo.session.commit()
    repo.session.refresh(legacy)
    before=legacy.model_dump()
    repo.session.expire_all()
    loaded=repo.get_card_knowledge('Legacy domain control')
    assert loaded.model_dump()==before
