"""Name-key diagnostics, not fabricated Oracle data or gameplay qualification."""
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import event, func
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from knowledge.models import CardKnowledge
from persistence.models import CardCache
from persistence.repository import Repository
from card_data.seed_cards import seed_card_payload
from card_data.sync import ScryfallSyncService

W=Path(__file__).resolve().parents[2]
PAIRS=[('\u00c9clair','\u00e9clair'),('\u00c9clair','\u00c9CLAIR'),('Stra\u00dfe','STRASSE'),('\u039f\u03a3','\u03bf\u03c2')]

@pytest.fixture(params=['memory','file'])
def repo(request,tmp_path):
    url='sqlite:///:memory:' if request.param=='memory' else 'sqlite:///'+str(tmp_path/'names.sqlite')
    engine=create_engine(url,poolclass=StaticPool)
    SQLModel.metadata.create_all(engine,tables=[CardKnowledge.__table__,CardCache.__table__])
    try:
        with Session(engine) as session: yield Repository(session)
    finally: engine.dispose()

def manual(repo,name):
    return repo.upsert_card_knowledge({'name':name,'oracle_source':'manual','profiles':{'name_key_control':True}})

def cache_key(repo,name,identity='manual-name-key-control'):
    # Deliberately no Oracle text, type, verification, or real printing claim.
    return repo.upsert_card({'scryfall_id':identity,'name':name})

def lookup(repo,method,name):
    if method=='knowledge_single': return repo.get_card_knowledge(name)
    if method=='knowledge_batch': return repo.get_card_knowledge_by_names([name]).get(name.strip().casefold())
    if method=='knowledge_list':
        rows=repo.list_card_knowledge(names=[name])
        return rows[0] if rows else None
    if method=='cache_single': return repo.get_cached_card_by_name(name)
    return repo.get_cached_cards_by_names([name]).get(name.strip().lower())

@pytest.mark.parametrize('initial,repeat',[('\u00c9clair','\u00c9clair'),('\u00c9clair','\u00e9clair'),('Stra\u00dfe','STRASSE'),('\u039f\u03a3','\u03bf\u03c2')])
def test_manual_knowledge_upsert_is_idempotent_for_normalized_unicode_name(repo,initial,repeat):
    first=manual(repo,initial)
    original_id=first.id
    row=manual(repo,'  '+repeat+'  ')
    assert row.id==original_id
    assert row.name==initial
    assert len(repo.list_card_knowledge())==1
    assert row.oracle_source=='manual' and json.loads(row.profiles_json)=={'name_key_control':True}

@pytest.mark.parametrize('initial,requested',PAIRS)
@pytest.mark.parametrize('method',['knowledge_single','knowledge_batch','knowledge_list','cache_single','cache_batch'])
def test_unicode_equivalent_key_reaches_existing_manual_schema_row(repo,initial,requested,method):
    row=cache_key(repo,initial) if method.startswith('cache') else manual(repo,initial)
    wanted=row.id
    result=lookup(repo,method,requested)
    assert result is not None, 'Equivalent Unicode name key missed its existing row'
    assert result.id==wanted and result.name==initial

@pytest.mark.parametrize('name',['\u00c9clair','Stra\u00dfe','\u039f\u03a3'])
@pytest.mark.parametrize('method',['knowledge_single','knowledge_batch','cache_single','cache_batch'])
def test_exact_unicode_key_remains_a_positive_control(repo,name,method):
    row=cache_key(repo,name) if method.startswith('cache') else manual(repo,name)
    result=lookup(repo,method,name)
    assert result is not None and result.id==row.id

@pytest.mark.parametrize('field,value',[('oracle_source','fallback'),('play_value',11),('threat_level',4)])
@pytest.mark.parametrize('existing',[False,True])
def test_new_domain_validation_still_precedes_every_query_or_mutation(repo,field,value,existing):
    if existing: manual(repo,'\u00c9clair')
    before=[row.model_dump() for row in repo.list_card_knowledge()]
    statements=[]
    def observed(conn,cursor,sql,*args): statements.append(sql.split()[0])
    event.listen(repo.session.bind,'before_cursor_execute',observed)
    try:
        with pytest.raises(ValueError): repo.upsert_card_knowledge({'name':'\u00c9clair','oracle_source':'manual',field:value})
    finally: event.remove(repo.session.bind,'before_cursor_execute',observed)
    assert statements==[] and not repo.session.new and not repo.session.dirty
    assert [row.model_dump() for row in repo.list_card_knowledge()]==before

@pytest.mark.parametrize('initial,requested',PAIRS)
def test_sqlite_lower_mismatch_and_separate_connection_local_casefold_prototype(repo,initial,requested):
    row=manual(repo,initial)
    driver=repo.session.connection().connection.driver_connection
    driver.create_function('diagnostic_casefold',1,lambda value:value.strip().casefold(),deterministic=True)
    observed=repo.session.connection().exec_driver_sql('SELECT lower(?), diagnostic_casefold(?)',(initial,initial)).one()
    assert observed[0]!=initial.casefold()
    assert observed[1]==requested.casefold()
    # This prototype query does NOT patch or replace the real Repository methods.
    found=repo.session.exec(select(CardKnowledge).where(func.diagnostic_casefold(CardKnowledge.name)==requested.casefold())).one()
    assert found.id==row.id

def test_existing_seed_payloads_and_bytes_are_preserved():
    path=W/'backend/card_data/builtin_oracle_seed.json'
    before=path.read_bytes(); data=json.loads(before)['cards']
    assert hashlib.sha256(before).hexdigest()=='9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037'
    assert len(data)==155
    for name,payload in data.items(): assert seed_card_payload(name)==payload
    assert seed_card_payload('Delver of Secrets // Insectile Aberration')==data['Delver of Secrets']
    assert path.read_bytes()==before

def test_existing_complete_official_dfc_aliases_remain_unmodified(repo):
    path=W/'backend/tests/fixtures/knowledge_profiles/seed155-scryfall.jsonl'
    before=path.read_bytes()
    raw=next(json.loads(line) for line in before.splitlines() if json.loads(line)['name'].startswith('Delver of Secrets //'))
    row=repo.upsert_card_knowledge({'name':raw['name'],'scryfall_id':raw['id'],'oracle_source':'scryfall','profiles':{'card_data':raw}})
    cache=repo.upsert_card(ScryfallSyncService._normalize_payload(raw,ScryfallSyncService._extract_remote_image_uri(raw)))
    for name in [raw['name'],*(face['name'] for face in raw['card_faces'])]:
        assert repo.get_card_knowledge(name).id==row.id
        assert repo.get_cached_card_by_name(name).id==cache.id
    assert json.loads(repo.get_card_knowledge(raw['name']).profiles_json)['card_data']==raw
    assert path.read_bytes()==before

def test_generic_art_series_schema_key_does_not_produce_a_face_alias(repo):
    # Schema-only control: this does not assert a canonical/gameplay card exists.
    name='Manual art name // Manual art name'
    row=repo.upsert_card_knowledge({'name':name,'oracle_source':'manual','profiles':{'card_data':{'layout':'art_series','type_line':'Card'}}})
    cache=repo.upsert_card({'scryfall_id':'manual-art-key-control','name':name,'layout':'art_series','type_line':'Card'})
    assert repo.get_card_knowledge('Manual art name') is None
    assert repo.get_cached_card_by_name('Manual art name') is None
    assert repo.get_card_knowledge(name).id==row.id
    assert repo.get_cached_card_by_name(name).id==cache.id

def test_generic_exact_schema_key_precedes_alias_independent_of_insertion_order(repo):
    # Two manual schema keys, not invented Oracle/DFC payloads.
    compound='Shared manual key // Other manual key'
    alias=manual(repo,compound)
    alias_cache=cache_key(repo,compound,'manual-compound-key')
    exact=manual(repo,'Shared manual key')
    exact_cache=cache_key(repo,'Shared manual key','manual-exact-key')
    assert repo.get_card_knowledge('Shared manual key').id==exact.id
    assert repo.get_cached_card_by_name('Shared manual key').id==exact_cache.id
    repo.session.delete(exact); repo.session.delete(exact_cache); repo.session.commit()
    assert repo.get_card_knowledge('Shared manual key').id==alias.id
    assert repo.get_cached_card_by_name('Shared manual key').id==alias_cache.id


@pytest.mark.parametrize('operation', ['construct', 'invalid', 'empty_knowledge', 'empty_cache'])
def test_repository_does_not_acquire_a_connection_before_candidate_validation(monkeypatch, operation):
    with Session() as session:
        def forbidden(*args, **kwargs):
            pytest.fail('A connection/query was attempted before validation')
        monkeypatch.setattr(session, 'connection', forbidden)
        monkeypatch.setattr(session, 'exec', forbidden)
        repository = Repository(session)
        if operation == 'invalid':
            with pytest.raises(ValueError):
                repository.upsert_card_knowledge({'name': '\u00c9clair', 'play_value': 11})
        if operation == 'empty_knowledge':
            assert repository.get_card_knowledge_by_names([' ']) == {}
        if operation == 'empty_cache':
            assert repository.get_cached_cards_by_names([' ']) == {}
        assert not session.new and not session.dirty


def test_casefold_registration_follows_physical_connection_reuse_and_replacement(tmp_path):
    registrations = []
    class ObservedConnection(sqlite3.Connection):
        def create_function(self, name, *args, **kwargs):
            if name == 'mtg_card_name_casefold':
                registrations.append((self, kwargs.get('deterministic')))
            return super().create_function(name, *args, **kwargs)
    engine = create_engine('sqlite:///' + str(tmp_path/'reconnect.sqlite'),
                           connect_args={'factory': ObservedConnection})
    try:
        SQLModel.metadata.create_all(engine, tables=[CardKnowledge.__table__, CardCache.__table__])
        with Session(engine) as session:
            repository = Repository(session)
            row = manual(repository, '\u00c9clair')
            wanted = row.id
            assert repository.get_card_knowledge('\u00e9clair').id == wanted
            assert repository.get_card_knowledge('\u00c9CLAIR').id == wanted
        with Session(engine) as session:
            assert Repository(session).get_card_knowledge('\u00e9clair').id == wanted
        assert len(registrations) == 1 and registrations[0][1] is True
        engine.dispose()
        with Session(engine) as session:
            repository = Repository(session)
            assert repository.get_card_knowledge('\u00e9clair').id == wanted
            session.invalidate()
            assert repository.get_card_knowledge('\u00e9clair').id == wanted
        assert len(registrations) == 3
        assert len({id(connection) for connection, _ in registrations}) == 3
        assert all(deterministic is True for _, deterministic in registrations)
    finally:
        engine.dispose()


def test_unicode_cache_batch_preserves_each_requested_lowercase_key(repo):
    row = cache_key(repo, 'Stra\u00dfe')
    result = repo.get_cached_cards_by_names(['Stra\u00dfe', ' STRASSE '])
    assert set(result) == {'stra\u00dfe', 'strasse'}
    assert result['stra\u00dfe'].id == result['strasse'].id == row.id


@pytest.mark.parametrize('method', ['knowledge_single', 'cache_single'])
def test_unicode_manual_schema_face_aliases_keep_exact_and_art_exclusions(repo, method):
    compound = '\u00c9clair // Stra\u00dfe'
    alias = cache_key(repo, compound) if method.startswith('cache') else manual(repo, compound)
    assert lookup(repo, method, '\u00e9CLAIR').id == alias.id
    assert lookup(repo, method, 'STRASSE').id == alias.id
    exact = cache_key(repo, '\u00e9clair', 'manual-exact-unicode') if method.startswith('cache') else manual(repo, '\u00e9clair')
    assert lookup(repo, method, '\u00c9CLAIR').id == exact.id
    if method.startswith('cache'):
        alias.layout = 'art_series'
    else:
        alias.profiles_json = json.dumps({'card_data': {'layout': 'art_series'}})
    repo.session.add(alias)
    repo.session.commit()
    assert lookup(repo, method, 'STRASSE') is None


def test_existing_casefold_duplicates_keep_exact_identity_without_merging(repo):
    first = CardKnowledge(name='Stra\u00dfe', oracle_source='manual')
    second = CardKnowledge(name='STRASSE', oracle_source='manual')
    repo.session.add_all([first, second]); repo.session.commit()
    first_id, second_id = first.id, second.id
    assert repo.get_card_knowledge('Stra\u00dfe').id == first_id
    assert repo.get_card_knowledge('STRASSE').id == second_id
    assert manual(repo, 'STRASSE').id == second_id
    assert manual(repo, 'strasse').id == first_id
    assert len(repo.list_card_knowledge()) == 2


@pytest.mark.parametrize('method', ['knowledge_single', 'cache_single'])
def test_folded_manual_alias_pattern_escapes_sql_wildcards(repo, method):
    name = '\u00c9%_clair // Manual other'
    row = cache_key(repo, name) if method.startswith('cache') else manual(repo, name)
    assert lookup(repo, method, '\u00e9%_CLAIR').id == row.id
    assert lookup(repo, method, '\u00e9XXclair') is None


@pytest.mark.parametrize('method', ['knowledge_single', 'cache_single'])
def test_manual_exact_unicode_key_inserted_before_alias_keeps_precedence(repo, method):
    exact = cache_key(repo, '\u00c9clair') if method.startswith('cache') else manual(repo, '\u00c9clair')
    if method.startswith('cache'):
        cache_key(repo, '\u00c9clair // Other', 'manual-later-alias')
    else:
        manual(repo, '\u00c9clair // Other')
    assert lookup(repo, method, '\u00e9clair').id == exact.id


def test_folded_lookup_does_not_materialize_unrelated_profiles_and_exact_path_is_indexed(repo):
    rows = [{'name': 'Manual unrelated ' + str(i), 'oracle_source': 'manual',
             'profiles_json': '{not parsed'} for i in range(64)]
    rows.append({'name': '\u00c9clair', 'oracle_source': 'manual', 'profiles_json': '{}'})
    repo.session.execute(CardKnowledge.__table__.insert(), rows)
    repo.session.commit()
    loaded, statements = [], []
    def observed_load(session, row):
        loaded.append(row.name)
    def observed_sql(conn, cursor, sql, *args):
        statements.append(sql)
    event.listen(repo.session, 'loaded_as_persistent', observed_load)
    event.listen(repo.session.bind, 'before_cursor_execute', observed_sql)
    try:
        exact = repo.get_card_knowledge('\u00c9clair')
        assert exact.name == '\u00c9clair'
        assert len(statements) == 1 and 'mtg_card_name_casefold' not in statements[0]
        assert 'cardknowledge.name IN' in statements[0]
        repo.session.expunge_all()
        assert repo.get_card_knowledge('\u00e9clair').name == '\u00c9clair'
        assert repo.get_card_knowledge('Missing manual name') is None
        assert loaded == ['\u00c9clair', '\u00c9clair']
    finally:
        event.remove(repo.session, 'loaded_as_persistent', observed_load)
        event.remove(repo.session.bind, 'before_cursor_execute', observed_sql)


def test_memory_connection_registration_after_invalidation_and_table_recreation():
    engine = create_engine('sqlite:///:memory:', poolclass=StaticPool)
    try:
        for _ in range(2):
            SQLModel.metadata.create_all(engine, tables=[CardKnowledge.__table__, CardCache.__table__])
            with Session(engine) as session:
                repository = Repository(session)
                wanted = manual(repository, '\u00c9clair').id
                assert repository.get_card_knowledge('\u00e9clair').id == wanted
                session.invalidate()
    finally:
        engine.dispose()


@pytest.mark.parametrize('method', ['knowledge_single', 'knowledge_batch', 'knowledge_list', 'cache_single', 'cache_batch'])
def test_unicode_whitespace_lookup_is_read_only(repo, method):
    knowledge = manual(repo, '\u00c9clair')
    cache = cache_key(repo, '\u00c9clair')
    repo.session.refresh(knowledge); repo.session.refresh(cache)
    before = knowledge.model_dump(), cache.model_dump()
    wanted = cache.id if method.startswith('cache') else knowledge.id
    assert lookup(repo, method, '  \u00e9CLAIR\t').id == wanted
    repo.session.refresh(knowledge); repo.session.refresh(cache)
    assert (knowledge.model_dump(), cache.model_dump()) == before
    assert not repo.session.new and not repo.session.dirty


def test_preexisting_cache_fold_collision_keeps_lowercase_identity(repo):
    street = cache_key(repo, 'Stra\u00dfe', 'manual-fold-street')
    upper = cache_key(repo, 'STRASSE', 'manual-fold-upper')
    street_id, upper_id = street.id, upper.id
    result = repo.get_cached_cards_by_names(['stra\u00dfe', 'strasse'])
    assert result['stra\u00dfe'].id == street_id
    assert result['strasse'].id == upper_id
    assert len(repo.list_cards()) == 2
