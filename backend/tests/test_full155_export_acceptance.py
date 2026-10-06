"""Lossless real CLI regeneration, not arbitrary canonical-update admission."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from scripts import export_builtin_oracle_seed as exporter
from tests.full155_export_fixtures import inputs, SEED_PATH, SEED, BASE, ADDED, FACE_RAW, sha

PRIOR = Path(__file__).parent / 'fixtures/full155_export_audit/approved17-ledger.json'


def command(db, output, ledger, options, prior=PRIOR):
    baseline = os.environ.get('MTG_EXPORTER_BASELINE_PATH')
    if baseline:
        code = 'import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_path(sys.argv.pop(1),run_name="__main__")'
        args = [sys.executable, '-c', code, str(Path(exporter.__file__).parent), baseline]
    else:
        args = [sys.executable, exporter.__file__]
    args += ['--database', str(db), '--output', str(output), '--fact-ledger', str(ledger)]
    for key, value in options.items():
        args += ['--' + key.replace('_', '-'), str(value)]
    if prior is not None and not baseline:
        args += ['--preservation-ledger', str(prior), '--preservation-ledger-sha256', sha(prior)]
    return args


@pytest.mark.parametrize('route', ['cache', 'knowledge'])
def test_actual_full155_cli_success_exact_shape_order17facts_and_idempotence(tmp_path, route):
    db, options = inputs(tmp_path, route)
    if route == 'knowledge':
        with sqlite3.connect(db) as conn:
            for raw in FACE_RAW:
                conn.execute('INSERT INTO cardknowledge VALUES (?,?,?,?)', (raw['name'], raw['id'], 'scryfall', json.dumps({'card_data': raw})))
        options.pop('canonical_bulk')
        options.pop('bulk_sha256')
    output = tmp_path / 'new.json'
    ledger = tmp_path / 'new-ledger.json'
    preserved = [db, SEED_PATH, PRIOR, options['semantic_admission']]
    if 'canonical_bulk' in options:
        preserved.append(options['canonical_bulk'])
    before = {str(p): sha(p) for p in preserved}
    run = subprocess.run(command(db, output, ledger, options), capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    result = json.loads(output.read_text())
    assert result == SEED and list(result['cards']) == list(SEED['cards'])
    assert output.read_bytes() == SEED_PATH.read_bytes()
    assert {n: result['cards'][n] for n in BASE['cards']} == BASE['cards']
    assert len(result['cards']) == 155 and len(ADDED) == 36
    assert json.loads(ledger.read_text()) == json.loads(PRIOR.read_text())
    assert ledger.read_bytes() == PRIOR.read_bytes()
    assert len(json.loads(ledger.read_text())) == 17
    assert {str(p): sha(p) for p in preserved} == before
    hashes = (sha(output), sha(ledger))
    again = subprocess.run(command(db, output, ledger, {**options, 'preservation_seed': output}, prior=ledger), capture_output=True, text=True, timeout=30)
    assert again.returncode == 0, again.stderr
    assert (sha(output), sha(ledger)) == hashes
    assert {str(p): sha(p) for p in preserved} == before


@pytest.mark.parametrize('route', ['cache', 'knowledge'])
@pytest.mark.parametrize('fault', ['cache_oracle_conflict', 'cache_power_absent', 'cache_ID_conflict',
    'raw_oracle_conflict', 'raw_unknown_field_loss', 'missing_added_printing', 'missing_printing',
    'missing_admission', 'bad_admission_hash', 'bulk_hash', 'ledger_hash', 'ledger_value',
    'ledger_raw_hash', 'ledger_duplicate', 'ledger_path'])
def test_conflicting_or_incomplete_facts_preserve_every_original_and_sql(tmp_path, route, fault):
    db, options = inputs(tmp_path, route, fault if fault in {'cache_oracle_conflict', 'missing_printing', 'missing_admission', 'bad_admission_hash'} else 'complete')
    raw_path = options['canonical_bulk']
    rows = [json.loads(line) for line in raw_path.read_text().splitlines()]
    target = next(row for row in rows if row['id'] == SEED['cards'][sorted(ADDED)[0]]['scryfall_id'])
    if fault == 'raw_oracle_conflict': target['oracle_text'] += '\n'
    if fault == 'raw_unknown_field_loss': target.pop('prices')
    if fault == 'missing_added_printing': rows.remove(target)
    raw_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    options['bulk_sha256'] = '0' * 64 if fault == 'bulk_hash' else sha(raw_path)
    with sqlite3.connect(db) as conn:
        if fault == 'cache_power_absent':
            conn.execute('UPDATE cardcache SET power = NULL WHERE name = ?', ('Monastery Swiftspear',))
        if fault == 'cache_ID_conflict':
            conn.execute('UPDATE cardcache SET scryfall_id = ? WHERE name = ?', (target['id'], 'Monastery Swiftspear'))
    prior = tmp_path / 'prior-ledger.json'
    facts = json.loads(PRIOR.read_text())
    if fault == 'ledger_value': facts[0]['colors'] = ['R'] if facts[0]['colors'] != ['R'] else ['W']
    if fault == 'ledger_raw_hash': facts[0]['raw_sha256'] = '0' * 64
    if fault == 'ledger_duplicate': facts.append(facts[0].copy())
    if fault == 'ledger_path': facts[0]['fact_path'] = 'unadmitted.raw.property'
    prior.write_text(json.dumps(facts))
    output = tmp_path / 'existing.json'; output.write_bytes(SEED_PATH.read_bytes())
    ledger = tmp_path / 'existing-ledger.json'; ledger.write_bytes(PRIOR.read_bytes())
    files = [db, output, ledger, prior, raw_path, SEED_PATH, options['semantic_admission']]
    before = {str(p): sha(p) for p in files}
    args = command(db, output, ledger, options, prior)
    if fault == 'ledger_hash': args[-1] = '0' * 64
    run = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert run.returncode != 0 and ('ValueError' in run.stderr or 'Error' in run.stderr)
    assert {str(p): sha(p) for p in files} == before
    output.unlink(); ledger.unlink()
    run = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert run.returncode != 0 and not output.exists() and not ledger.exists()
    assert sha(db) == before[str(db)] and sha(SEED_PATH) == before[str(SEED_PATH)]


def test_unsupported_prior_provenance_does_not_mutate_api_external_ledger(tmp_path):
    db, options = inputs(tmp_path)
    path = tmp_path / 'invalid-ledger.json'; path.write_text('{}')
    before = sha(db); ledger = [{'unchanged': True}]
    with pytest.raises(ValueError, match='Invalid preserved fact ledger'):
        exporter.export_seed(db, **options, preservation_ledger=path, preservation_ledger_sha256=sha(path), fact_ledger=ledger)
    assert sha(db) == before and ledger == [{'unchanged': True}]


def test_available_canonical_conflict_on_slim_existing_row_is_not_concealed(tmp_path):
    db, options = inputs(tmp_path)
    rows = [json.loads(line) for line in options['canonical_bulk'].read_text().splitlines()]
    target = next(row for row in rows if row['id'] == SEED['cards']['Nissa, Ascended Animist']['scryfall_id'])
    target['loyalty'] = '8'
    options['canonical_bulk'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    options['bulk_sha256'] = sha(options['canonical_bulk'])
    before = sha(db)
    with pytest.raises(ValueError, match='loyalty conflicts'):
        exporter.export_seed(db, **options)
    assert sha(db) == before


@pytest.mark.parametrize('destination', ['database', 'canonical_bulk', 'semantic_admission'])
@pytest.mark.parametrize('role', ['output', 'ledger'])
def test_cli_cannot_overwrite_database_or_canonical_inputs(tmp_path, destination, role):
    db, options = inputs(tmp_path)
    protected = db if destination == 'database' else options[destination]
    output = protected if role == 'output' else tmp_path / 'new.json'
    ledger = protected if role == 'ledger' else tmp_path / 'new-ledger.json'
    before = {str(p): sha(p) for p in (db, options['canonical_bulk'], options['semantic_admission'])}
    run = subprocess.run(command(db, output, ledger, options), capture_output=True, text=True, timeout=30)
    assert run.returncode != 0 and 'must not overwrite' in run.stderr
    assert {str(p): sha(p) for p in (db, options['canonical_bulk'], options['semantic_admission'])} == before


def test_unknown_nonraw_field_cannot_be_carried_without_canonical_availability(tmp_path):
    db, options = inputs(tmp_path)
    original = json.loads(SEED_PATH.read_text())
    # Genuine available field from the verified event packet; no fabricated canonical fact.
    raw = next(json.loads(line) for line in options['canonical_bulk'].read_text().splitlines()
               if json.loads(line)['id'] == SEED['cards'][sorted(ADDED)[0]]['id'])
    original['cards']['Monastery Swiftspear']['prices'] = raw['prices']
    path = tmp_path / 'conflicting-baseline.json'; path.write_text(json.dumps(original))
    with pytest.raises(ValueError, match='Missing exact canonical facts'):
        exporter.export_seed(db, **{**options, 'preservation_seed': path})


def test_legacy_unknown_layout_does_not_mask_non_normal_canonical_layout(tmp_path):
    db, options = inputs(tmp_path)
    rows = [json.loads(line) for line in options['canonical_bulk'].read_text().splitlines()]
    target = next(row for row in rows if row['id'] == SEED['cards']['Nissa, Who Shakes the World']['scryfall_id'])
    assert SEED['cards'][target['name']]['layout'] == ''
    target['layout'] = 'adventure'  # Deliberate corrupt input, never a canonical fixture.
    options['canonical_bulk'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    options['bulk_sha256'] = sha(options['canonical_bulk'])
    with pytest.raises(ValueError, match='canonical fact conflicts'):
        exporter.export_seed(db, **options)


def test_verified_bulk_does_not_conceal_conflicting_fullraw_knowledge_fields(tmp_path):
    db, options = inputs(tmp_path, 'knowledge')
    with sqlite3.connect(db) as conn:
        row = conn.execute('SELECT scryfall_id,profiles_json FROM cardknowledge LIMIT 1').fetchone()
        profile = json.loads(row[1]); profile['card_data'].pop('prices')
        conn.execute('UPDATE cardknowledge SET profiles_json = ? WHERE scryfall_id = ?', (json.dumps(profile), row[0]))
    before = sha(db)
    with pytest.raises(ValueError, match='Conflicting or ambiguous canonical sources'):
        exporter.export_seed(db, **options)
    assert sha(db) == before
