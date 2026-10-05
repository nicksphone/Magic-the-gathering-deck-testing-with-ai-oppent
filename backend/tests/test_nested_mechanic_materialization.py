"""Materialization contract boundaries; isolated fixtures, no live writes."""
import copy
import json
import sqlite3

import pytest

from knowledge.mechanic_metadata import mechanic_metadata, SCHEMA_VERSION, EXTRACTOR_VERSION
from scripts import corpus_knowledge_readiness as c
from tests.test_corpus_knowledge_readiness import sources


def case(raw, archive_sha):
    sha = c.canonical_hash(raw)
    provenance = {'source': 'scryfall', 'archive_sha256': archive_sha, 'record_sha256': sha,
                  'annotation': 'preserve this exact existing provenance'}
    profile = {'card_data': raw, 'card_data_sha256': sha, 'oracle_id': raw['oracle_id'],
               'card_data_provenance': provenance, 'rulings': [], 'rulings_verified': True,
               'rulings_provenance': {'annotation': 'preserve existing ruling receipt'},
               'tactical_tags': ['existing_version_surface'], 'other_annotation': {'keep': True}}
    original = {'id': 1, 'name': raw['name'], 'scryfall_id': raw['id'], 'profiles_json': json.dumps(profile)}
    after = {**profile, 'mechanic_metadata': mechanic_metadata(raw)}
    patch = {'id': 1, 'name': raw['name'], 'scryfall_id': raw['id'],
             'before_profile_sha256': c.canonical_hash(profile), 'after_profile_sha256': c.canonical_hash(after), 'profile': after}
    manifest = {'cards': {'source': 'scryfall'}, 'tags': 'preserve_existing', 'rulings': None,
                'mechanics': {'schema_version': SCHEMA_VERSION, 'extractor_version': EXTRACTOR_VERSION},
                'retained_card_source_provenance': [provenance]}
    return original, profile, patch, manifest


def test_exact_nested_only_delta_preserves_every_other_profile_field(sources):
    _, raw, args = sources
    original, before, patch, manifest = case(raw, args.cards_sha256)
    accepted = c.validate_profile_patch(original, patch, manifest)
    assert {k: v for k, v in accepted.items() if k != 'mechanic_metadata'} == before
    metadata = accepted['mechanic_metadata']
    assert metadata == mechanic_metadata(raw)
    assert metadata['provenance']['input_sha256'] == c.canonical_hash(raw)
    assert all(v['execution_support'] == 'unknown' for v in metadata['coverage'].values())
    assert metadata['learned_quality']['status'] == 'not_assessed'
    assert metadata['unsupported_semantics']


def test_prepare_materialization_also_replaces_provenance_not_nested_only(sources):
    database, raw, args = sources
    args.rulings = args.rulings_sha256 = args.rulings_manifest = None
    args.materialize_mechanics_version = EXTRACTOR_VERSION
    with sqlite3.connect(database) as conn:
        profile = json.loads(conn.execute('SELECT profiles_json FROM cardknowledge').fetchone()[0])
        profile['card_data_provenance'] = {'source': 'scryfall', 'archive_sha256': args.cards_sha256,
                                          'record_sha256': c.canonical_hash(raw), 'annotation': 'do not drop'}
        profile['card_data_sha256'] = c.canonical_hash(raw)
        conn.execute('UPDATE cardknowledge SET profiles_json=?', (json.dumps(profile),))
    with c.closing(c.readonly(database)) as source:
        c.prepare(source, args)
    import gzip
    with gzip.open(args.out, 'rt') as stream:
        next(stream)
        prepared = json.loads(next(stream))['profile']
    assert prepared['card_data'] == profile['card_data']
    assert prepared['card_data_provenance'] != profile['card_data_provenance']
    assert 'annotation' not in prepared['card_data_provenance']


@pytest.mark.parametrize('section', ['coverage', 'learned_quality', 'evidence'])
def test_importer_recomputes_exact_extractor_content(sources, section):
    _, raw, args = sources
    original, _, patch, manifest = case(raw, args.cards_sha256)
    forged = copy.deepcopy(patch)
    if section == 'coverage':
        family = next(iter(forged['profile']['mechanic_metadata']['coverage']))
        forged['profile']['mechanic_metadata']['coverage'][family]['execution_support'] = 'supported'
    else:
        forged['profile']['mechanic_metadata'][section] = {'forged': True}
    forged['after_profile_sha256'] = c.canonical_hash(forged['profile'])
    assert c.mechanic_status(forged['profile'], c.canonical_hash(raw)) == 'current_input_version_not_semantics'
    with pytest.raises(ValueError, match='pinned extractor output'):
        c.validate_profile_patch(original, forged, manifest)


@pytest.mark.parametrize('field', ['tactical_tags', 'card_data', 'other_annotation'])
def test_shared_validator_rejects_non_owned_changes(sources, field):
    _, raw, args = sources
    original, _, patch, manifest = case(raw, args.cards_sha256)
    patch['profile'][field] = {'changed': True}
    patch['after_profile_sha256'] = c.canonical_hash(patch['profile'])
    with pytest.raises(ValueError):
        c.validate_profile_patch(original, patch, manifest)


@pytest.mark.parametrize('limit,version,reason', [(501, EXTRACTOR_VERSION, 'bounded'), (1, 'wrong-version', 'version mismatch')])
def test_existing_materialization_limit_and_version_pin(sources, limit, version, reason):
    database, _, args = sources
    args.limit = limit
    args.materialize_mechanics_version = version
    with c.closing(c.readonly(database)) as source:
        with pytest.raises(ValueError, match=reason):
            c.prepare(source, args)
