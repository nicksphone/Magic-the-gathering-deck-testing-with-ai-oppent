"""Typed JSON admission; all rows are manual schema controls, not Oracle fixtures."""
from copy import deepcopy
import json

import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from knowledge.models import CardKnowledge
from persistence.models import CardCache
from persistence.repository import Repository
from scripts.card_mechanics_inventory import inventory
from scripts.knowledge_gap_report import knowledge_report


LIST_FIELDS = ['answerable_by', 'cast_windows']
INVALID_LISTS = [
    pytest.param('counter', id='string-container'),
    pytest.param({'counter': True}, id='object-container'),
    pytest.param(7, id='integer-container'),
    pytest.param(True, id='boolean-container'),
    pytest.param([None], id='null-element'),
    pytest.param([1], id='integer-element'),
    pytest.param([True], id='boolean-element'),
    pytest.param([{'future_effect': True}], id='object-element'),
    pytest.param([['counter']], id='list-element'),
    pytest.param(['counter', 1], id='mixed-elements'),
]


@pytest.fixture(params=['memory', 'file'])
def repo(request, tmp_path):
    url = 'sqlite:///:memory:' if request.param == 'memory' else 'sqlite:///' + str(tmp_path/'schema.sqlite')
    engine = create_engine(url, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine, tables=[CardKnowledge.__table__, CardCache.__table__])
    try:
        with Session(engine) as session:
            yield Repository(session)
    finally:
        engine.dispose()


def manual(**changes):
    return {'name': 'Manual JSON schema control', 'oracle_source': 'manual',
            'answerable_by': ['future_effect.v9'], 'cast_windows': ['future_window'],
            'profiles': {'future_metadata': {'nested': [1, None, True, {'key': 'value'}]}},
            **changes}


@pytest.mark.parametrize('field', LIST_FIELDS)
@pytest.mark.parametrize('invalid', INVALID_LISTS)
@pytest.mark.parametrize('existing', [False, True])
def test_required_list_of_strings_rejects_before_any_query_or_mutation(repo, field, invalid, existing):
    if existing:
        repo.upsert_card_knowledge(manual())
    before = [row.model_dump() for row in repo.list_card_knowledge()]
    statements = []
    def observed(connection, cursor, statement, *args):
        statements.append(statement)
    event.listen(repo.session.bind, 'before_cursor_execute', observed)
    try:
        with pytest.raises(ValueError):
            repo.upsert_card_knowledge(manual(**{field: deepcopy(invalid)}))
    finally:
        event.remove(repo.session.bind, 'before_cursor_execute', observed)
    assert statements == []
    assert not repo.session.new and not repo.session.dirty
    assert [row.model_dump() for row in repo.list_card_knowledge()] == before


@pytest.mark.parametrize('field', LIST_FIELDS)
@pytest.mark.parametrize('invalid', INVALID_LISTS)
def test_required_encoded_list_of_strings_is_admitted_by_model_only_if_valid(field, invalid):
    with pytest.raises(ValueError):
        CardKnowledge.model_validate({'name': 'Manual model JSON control',
            'oracle_source': 'manual', field+'_json': json.dumps(invalid)})


@pytest.mark.parametrize('field', ['answerable_by_json', 'cast_windows_json', 'profiles_json'])
@pytest.mark.parametrize('text', ['not JSON', '{'])
def test_required_json_storage_fields_reject_malformed_new_documents(field, text):
    with pytest.raises(ValueError):
        CardKnowledge.model_validate({'name': 'Manual malformed JSON control',
                                      'oracle_source': 'manual', field: text})


@pytest.mark.parametrize('field', LIST_FIELDS)
@pytest.mark.parametrize('invalid', ['counter', [1], {'counter': True}])
def test_required_invalid_payload_is_rejected_without_acquiring_connection(monkeypatch, field, invalid):
    with Session() as session:
        def forbidden(*args, **kwargs):
            raise AssertionError('Invalid typed payload reached SQL/connection/mutation')
        for method in ('connection', 'exec', 'add', 'commit'):
            monkeypatch.setattr(session, method, forbidden)
        repository = Repository(session)
        with pytest.raises(ValueError):
            repository.upsert_card_knowledge(manual(**{field: invalid}))
        assert not session.new and not session.dirty


@pytest.mark.parametrize('field', LIST_FIELDS)
@pytest.mark.parametrize('invalid', INVALID_LISTS)
def test_non_string_list_values_do_not_persist(repo, field, invalid):
    with pytest.raises(ValueError):
        repo.upsert_card_knowledge(manual(**{field: deepcopy(invalid)}))
    assert repo.get_card_knowledge('Manual JSON schema control') is None
    assert not repo.session.new and not repo.session.dirty


@pytest.mark.parametrize('field', LIST_FIELDS)
def test_bad_list_update_preserves_existing_typed_value(repo, field):
    first = repo.upsert_card_knowledge(manual())
    wanted = first.id
    before_text = getattr(first, field+'_json')
    with pytest.raises(ValueError):
        repo.upsert_card_knowledge(manual(**{field: [1]}))
    repo.session.refresh(first)
    assert first.id == wanted
    assert getattr(first, field+'_json') == before_text
    assert not repo.session.new and not repo.session.dirty


@pytest.mark.parametrize('values', [[], ['destroy_target', 'exile_target', 'counter'],
                                   ['future_effect.v9', '', 'future_effect.v9']])
def test_valid_lists_and_unknown_nested_metadata_round_trip_without_new_enums(repo, values):
    payload = manual(answerable_by=values, cast_windows=values)
    original = deepcopy(payload)
    row = repo.upsert_card_knowledge(payload)
    first_id = row.id
    assert json.loads(row.answerable_by_json) == values
    assert json.loads(row.cast_windows_json) == values
    assert json.loads(row.profiles_json) == original['profiles']
    assert payload == original
    again = repo.upsert_card_knowledge(payload)
    assert again.id == first_id
    repo.session.expire_all()
    fetched = repo.get_card_knowledge(original['name'])
    assert json.loads(fetched.answerable_by_json) == values
    assert json.loads(fetched.cast_windows_json) == values
    assert json.loads(fetched.profiles_json) == original['profiles']
    assert inventory([fetched])['cards'] == 0  # No canonical/gameplay assertion.
    report = knowledge_report(repo, [fetched.name])
    assert report['rulings_pending'] == [fetched.name]


@pytest.mark.parametrize('mode', ['omitted', 'empty', 'none'])
def test_existing_empty_and_none_default_compatibility(repo, mode):
    payload = {'name': 'Manual empty JSON control', 'oracle_source': 'manual'}
    if mode != 'omitted':
        payload.update(answerable_by=[] if mode == 'empty' else None,
                       cast_windows=[] if mode == 'empty' else None,
                       profiles={} if mode == 'empty' else None)
    row = repo.upsert_card_knowledge(payload)
    assert json.loads(row.answerable_by_json) == []
    assert json.loads(row.cast_windows_json) == []
    assert json.loads(row.profiles_json) == {}


@pytest.mark.parametrize('field', LIST_FIELDS)
@pytest.mark.parametrize('value', ['', {}, 0, False, ('future_effect',)])
def test_characterization_falsey_or_tuple_input_serializes_to_a_list(repo, field, value):
    # Input-coercion policy is unspecified; the persisted JSON shape is valid.
    row = repo.upsert_card_knowledge(manual(**{field: value}))
    expected = ['future_effect'] if isinstance(value, tuple) else []
    assert json.loads(getattr(row, field+'_json')) == expected


@pytest.mark.parametrize('profile', [['opaque'], 'opaque', 7, True])
def test_nonobject_profiles_remain_valid_json_blobs_without_rewrite(repo, profile):
    row = repo.upsert_card_knowledge(manual(profiles=profile))
    before = row.model_dump()
    assert json.loads(row.profiles_json) == profile
    repo.session.refresh(row)
    assert row.model_dump() == before
    assert not repo.session.new and not repo.session.dirty


@pytest.mark.parametrize('profile', [[], '', 0, False])
def test_characterization_falsey_profile_inputs_normalize_to_empty_object(repo, profile):
    row = repo.upsert_card_knowledge(manual(profiles=profile))
    assert json.loads(row.profiles_json) == {}


@pytest.mark.parametrize('field,text', [
    ('answerable_by_json', '{"legacy":true}'),
    ('answerable_by_json', '[1,null]'),
    ('cast_windows_json', '"legacy_window"'),
    ('cast_windows_json', 'invalid json'),
    ('profiles_json', '["legacy"]'),
    ('profiles_json', 'invalid json'),
])
def test_legacy_text_rows_remain_readable_without_rewrite(repo, field, text):
    legacy = CardKnowledge(name='Manual legacy JSON control', oracle_source='manual', **{field: text})
    repo.session.add(legacy); repo.session.commit(); repo.session.refresh(legacy)
    before = legacy.model_dump()
    repo.session.expunge_all()
    loaded = repo.get_card_knowledge(before['name'])
    assert loaded.model_dump() == before
    listed = repo.list_card_knowledge([before['name']])
    assert len(listed) == 1 and listed[0].model_dump() == before
    assert not repo.session.new and not repo.session.dirty


@pytest.mark.parametrize('field,text', [
    (field, text)
    for field in ('answerable_by_json', 'cast_windows_json')
    for text in (' \n [ "counter", "future_\u00e9ffect", "", "counter" ] \t',
                 r' [ "future_\u00e9ffect" ] ', ' [ ] \n')
] + [
    ('profiles_json', text) for text in (
        ' \n {"future": {"nested": [1, null, true, "\u00e9"]}} \t',
        '[1, "opaque", {"future":true}]', '"opaque"', ' true ',
        'false', 'null', '7.5', '[]', '{}', r'"\u00e9"',
    )
])
def test_valid_json_text_is_preserved_byte_for_byte_through_model_and_sqlite(repo, field, text):
    row = CardKnowledge.model_validate({'name': 'Manual exact JSON bytes control',
                                       'oracle_source': 'manual', field: text})
    assert getattr(row, field) == text
    repo.session.add(row); repo.session.commit(); repo.session.refresh(row)
    wanted = row.id
    repo.session.expunge_all()
    stored = repo.get_card_knowledge('Manual exact JSON bytes control')
    assert stored.id == wanted
    assert getattr(stored, field).encode('utf-8') == text.encode('utf-8')


@pytest.mark.parametrize('field,text', [('answerable_by_json', '[1]'),
                                      ('cast_windows_json', '"legacy"'),
                                      ('profiles_json', 'not JSON')])
def test_direct_orm_assignment_bypass_remains_legacy_compatible(repo, field, text):
    row = repo.upsert_card_knowledge(manual())
    setattr(row, field, text)
    repo.session.add(row); repo.session.commit(); repo.session.refresh(row)
    before = row.model_dump()
    repo.session.expunge_all()
    assert repo.get_card_knowledge(before['name']).model_dump() == before
