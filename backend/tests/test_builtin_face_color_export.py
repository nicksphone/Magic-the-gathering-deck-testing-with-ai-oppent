"""Pinned all-119 exporter preservation and reviewed sixteen-face admission."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from scripts import export_builtin_oracle_seed as exporter

FIXTURE = Path(__file__).parent / 'fixtures/builtin_face_colors'
BEFORE = json.loads((FIXTURE / 'seed_before.json').read_text())
RAW = [json.loads(line) for line in (FIXTURE / 'canonical.jsonl').read_text().splitlines()]
ADMISSION = json.loads((FIXTURE / 'reviewed_admission.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
QUALIFIED119 = Path(__file__).parent / 'fixtures/mh3_seed_gap/seed119_before.json'
CLI_FIXTURE = Path(__file__).with_name('historical_seed_export_worker.py')


@pytest.fixture(autouse=True)
def historical119_export_cohort(monkeypatch):
    qualified = json.loads(QUALIFIED119.read_text())
    ledger = json.loads((Path(exporter.__file__).parents[1] / 'card_data/mh3_catalog_seed_provenance.json').read_text())
    assert sha(QUALIFIED119) == ledger['baseline_seed_sha256']
    assert set(qualified['cards']) == set(BEFORE['cards']) and len(qualified['cards']) == 119
    # These goldens exercise the original 119-card inputs, not the global 155-card inventory.
    monkeypatch.setattr(exporter, 'shipped_names', lambda: set(qualified['cards']))
    monkeypatch.setattr(exporter, 'DEFAULT_SEED', QUALIFIED119)


def cache(tmp_path, seed=None):
    db = tmp_path / 'owned.sqlite'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE cardcache(name TEXT,scryfall_id TEXT,oracle_text TEXT,mana_cost TEXT,type_line TEXT,layout TEXT,colors TEXT,power TEXT,toughness TEXT,card_faces_json TEXT,loyalty TEXT)')
        for card in (seed or BEFORE)['cards'].values():
            conn.execute('INSERT INTO cardcache VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                card['name'], card['scryfall_id'], card['oracle_text'], card['mana_cost'], card['type_line'],
                card['layout'], ','.join(card.get('colors', [])), card.get('power'), card.get('toughness'),
                json.dumps(card.get('card_faces', [])), None))
    return db


def kwargs(tmp_path, raws=None, admission=None):
    bulk = tmp_path / 'canonical.jsonl'
    bulk.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in (raws if raws is not None else RAW)))
    ledger = tmp_path / 'admission.json'
    ledger.write_text(json.dumps(admission if admission is not None else ADMISSION))
    return {'canonical_bulk': bulk, 'bulk_sha256': sha(bulk), 'semantic_admission': ledger,
            'admission_sha256': sha(ledger), 'preservation_seed': FIXTURE / 'seed_before.json'}


def test_golden_all119_only_sixteen_missing_colors_and_loyalty_nonloss(tmp_path):
    pin = json.loads((FIXTURE / 'provenance.json').read_text())
    assert all(sha(FIXTURE / name) == value for name, value in pin['files_sha256'].items())
    db = cache(tmp_path); before = sha(db); ledger = []
    result = exporter.export_seed(db, **kwargs(tmp_path), fact_ledger=ledger)
    assert sha(db) == before and len(result['cards']) == 119
    exporter._preserve_seed(result, BEFORE)
    expected = json.loads(exporter.DEFAULT_SEED.read_text())
    assert result == expected
    faces = [entry for entry in ledger if entry['fact_path'].startswith('card_faces')]
    assert len(faces) == 16 and sum(e['fact_kind'] == 'derived_rule_fact' for e in faces) == 6
    assert sum(e['fact_kind'] == 'canonical_explicit' for e in faces) == 10
    assert len(ledger) == 17
    assert result['cards']['Nissa, Ascended Animist']['loyalty'] == '7'
    for entry in faces:
        assert entry['cr_sha256'] == exporter.CR_SHA256 and entry['semantic_admission_sha256']
        if entry['fact_kind'] == 'derived_rule_fact':
            assert not entry['raw_colors_present'] and entry['derivation']['contract_version'] == exporter.DERIVATION_VERSION
    repeat = exporter.export_seed(db, **{**kwargs(tmp_path), 'preservation_seed': exporter.DEFAULT_SEED})
    assert repeat == expected


@pytest.mark.parametrize('fault', ['missing_printing', 'printing_name', 'face_order', 'face_oracle', 'duplicate_printing',
    'source_hash', 'admission_hash', 'no_admission', 'ambiguous_admission', 'unknown_symbol', 'empty_cost', 'missing_cost',
    'indicator', 'devoid', 'CDA', 'stale_oracle_hash', 'wrong_colors', 'CR_hash', 'existing_face_conflict',
    'existing_loyalty_conflict', 'root_fact_loss'])
def test_atomic_rejections_leave_sql_and_external_ledger_unchanged(tmp_path, fault):
    raws = deepcopy(RAW); admission = deepcopy(ADMISSION); seed = deepcopy(BEFORE)
    target = next(r for r in raws if r['name'].startswith('Imodane'))
    proof = next(e for e in admission if e['scryfall_id'] == target['id'] and e['face_index'] == 1)
    if fault == 'missing_printing': raws.remove(target)
    if fault == 'printing_name': target['name'] = RAW[0]['name']
    if fault == 'face_order': target['card_faces'].reverse()
    if fault == 'face_oracle': target['card_faces'][0]['oracle_text'] += '\n'
    if fault == 'duplicate_printing': raws.append(deepcopy(target))
    if fault == 'no_admission': admission = []
    if fault == 'ambiguous_admission': admission.append(deepcopy(proof))
    if fault == 'unknown_symbol': target['card_faces'][1]['mana_cost'] = '{4}{W/P}'
    if fault == 'empty_cost': target['card_faces'][1]['mana_cost'] = ''
    if fault == 'missing_cost': target['card_faces'][1].pop('mana_cost')
    if fault == 'indicator': target['card_faces'][1]['color_indicator'] = ['W']
    if fault == 'devoid': proof['derivation']['devoid_present'] = True
    if fault == 'CDA': proof['derivation']['unsupported_color_semantics'] = ['unadmitted color-defining clause']
    if fault == 'stale_oracle_hash': proof['face_oracle_sha256'] = '0' * 64
    if fault == 'wrong_colors': proof['colors'] = ['R']
    if fault == 'CR_hash': proof['derivation']['official_cr_sha256'] = '0' * 64
    if fault == 'existing_face_conflict': seed['cards']["Imodane's Recruiter"]['card_faces'][1]['colors'] = ['R']
    db = cache(tmp_path, seed); options = kwargs(tmp_path, raws, admission)
    if fault == 'source_hash': options['bulk_sha256'] = '0' * 64
    if fault == 'admission_hash': options['admission_sha256'] = '0' * 64
    with sqlite3.connect(db) as conn:
        if fault == 'existing_loyalty_conflict':
            conn.execute('UPDATE cardcache SET loyalty = ? WHERE name = ?', ('8', 'Nissa, Ascended Animist'))
        if fault == 'root_fact_loss':
            conn.execute('UPDATE cardcache SET power = NULL WHERE name = ?', ('Monastery Swiftspear',))
    before = sha(db); ledger = [{'unchanged': True}]
    with pytest.raises(ValueError): exporter.export_seed(db, **options, fact_ledger=ledger)
    assert sha(db) == before and ledger == [{'unchanged': True}]


def test_existing_loyalty_is_not_overwritten_by_old_named_allowlist(tmp_path):
    db = cache(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute('UPDATE cardcache SET loyalty = ? WHERE name = ?', ('99', 'The Wandering Emperor'))
    before = sha(db)
    with pytest.raises(ValueError, match='loyalty conflicts'): exporter.export_seed(db, **kwargs(tmp_path))
    assert sha(db) == before


def test_cli_atomic_failure_preserves_existing_payload_and_ledger(tmp_path):
    db = cache(tmp_path); options = kwargs(tmp_path, admission=[])
    output = tmp_path / 'output.json'; output.write_bytes(b'original output\n')
    ledger = tmp_path / 'output-ledger.json'; ledger.write_bytes(b'original ledger\n')
    before = sha(db)
    command = [sys.executable, str(CLI_FIXTURE), '--database', str(db), '--output', str(output),
               '--fact-ledger', str(ledger)]
    for key, value in options.items(): command += ['--' + key.replace('_', '-'), str(value)]
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode != 0 and 'admission' in run.stderr
    assert output.read_bytes() == b'original output\n' and ledger.read_bytes() == b'original ledger\n'
    assert sha(db) == before


def test_staging_failure_and_duplicate_destinations_publish_nothing(tmp_path):
    output = tmp_path / 'output.json'; output.write_bytes(b'original\n')
    with pytest.raises(OSError): exporter._write_outputs([(output, 'new\n'), (tmp_path / 'absent-dir/ledger.json', 'ledger\n')])
    assert output.read_bytes() == b'original\n'
    with pytest.raises(ValueError): exporter._write_outputs([(output, 'new\n'), (output, 'ledger\n')])
    assert output.read_bytes() == b'original\n'
    assert set(tmp_path.iterdir()) == {output}


@pytest.mark.parametrize('cost', ['', '{W/P}', '{W/U}', '{2/W}', '{C}', '{S}', '{X}', '{W}{UNKNOWN}', '{W}garbage'])
def test_unadmitted_cost_grammar_rejected_directly_not_masked_by_preservation(cost):
    raw = deepcopy(next(r for r in RAW if r['layout'] == 'adventure'))
    raw['card_faces'][1]['mana_cost'] = cost
    with pytest.raises(ValueError, match='cost/indicator semantics'):
        exporter._face_colors(raw, 1, ADMISSION)


def test_cli_success_publishes_complete_golden_and_distinct_external_fact_ledger(tmp_path):
    db = cache(tmp_path); options = kwargs(tmp_path)
    output = tmp_path / 'output.json'; ledger = tmp_path / 'output-ledger.json'
    command = [sys.executable, str(CLI_FIXTURE), '--database', str(db), '--output', str(output),
               '--fact-ledger', str(ledger)]
    for key, value in options.items(): command += ['--' + key.replace('_', '-'), str(value)]
    before = sha(db)
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(output.read_text()) == json.loads(exporter.DEFAULT_SEED.read_text())
    facts = json.loads(ledger.read_text())
    assert len(facts) == 17 and sum(f['fact_kind'] == 'derived_rule_fact' for f in facts) == 6
    assert all(f['fact_schema_version'] == 1 and f['preservation_seed_sha256'] == sha(FIXTURE / 'seed_before.json') for f in facts)
    assert sha(db) == before
