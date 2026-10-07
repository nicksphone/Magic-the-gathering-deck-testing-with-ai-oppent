"""Context-aware diagnostics, never a whole-card execution certificate."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.service import CardService
from game_state.serializers import serialize_match_snapshot
from rules_engine.coverage import deck_pair_coverage, known_unsupported_mechanics
from rules_engine.suspend import instruction
from tests.suspend_readiness_fixtures import ReadonlyCanonicalRows
from tests.test_suspend_lifecycle import CARDS, DIRECTORY, setup

NAMES = ['Rift Bolt', 'Ancestral Vision', 'Errant Ephemeron']


def metadata(name):
    return hydrate_deck_cards(ReadonlyCanonicalRows([name]), [{'card_name': name, 'quantity': 1}])[0]


def gaps(row):
    return known_unsupported_mechanics(row['oracle_text'], row.get('card_faces'),
                                      card_name=row['card_name'], canonical_context=row)


def test_canonical_intake_bytes_preserved():
    intake = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert len(intake['cards']) == 7
    for row in intake['cards']:
        raw = (DIRECTORY / row['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['sha256']
        canonical = json.loads(raw)
        assert canonical['id'] == row['scryfall_id'] and canonical['name'] == row['name']


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_context_admission_preserves_legacy_warning_and_root(name, seat):
    row = metadata(name)
    before = deepcopy(row)
    state, cid = setup(seat, name)
    snap = serialize_match_snapshot(state)
    assert instruction(state.cards[cid]) is not None and ready_for_match(row)
    legacy = known_unsupported_mechanics(row['oracle_text'], card_name=name)
    assert 'suspend' in legacy
    assert gaps(row) == [gap for gap in legacy if gap != 'suspend']
    assert row == before and serialize_match_snapshot(state) == snap
    pair = deck_pair_coverage([row] if seat == 1 else [], [row] if seat == 2 else [])
    assert pair == {'status': 'exploratory', 'known_unsupported_cards': []}


@pytest.mark.parametrize('name', NAMES + ['Aeon Chronicler'])
@pytest.mark.parametrize('seat', [1, 2])
def test_actual_inprocess_preflight_matches_hydrated_helper(name, seat, record_property):
    import main
    repo = ReadonlyCanonicalRows([name, 'Errant Ephemeron'])
    original = deepcopy(repo.raw)
    deck = [{'card_name': name, 'quantity': 1}]
    # Put the canonical row in either reported seat; no lifespan or SQL startup.
    control = [{'card_name': 'Errant Ephemeron', 'quantity': 1}]
    decks = [deck, control] if seat == 1 else [control, deck]
    expected = deck_pair_coverage(*(hydrate_deck_cards(repo, d) for d in decks))
    overrides = dict(main.app.dependency_overrides)
    active = dict(main.ACTIVE_MATCHES)
    main.app.dependency_overrides[main.get_repo] = lambda: repo
    try:
        client = TestClient(main.app)
        try:
            response = client.post('/simulate/batch/preflight', json={
                'deck_a': decks[0], 'deck_b': decks[1], 'sandbox': True})
        finally:
            client.close()
        assert response.status_code == 200, response.text
        assert response.json() == expected
        record_property('actual_preflight', json.dumps({'seat': seat, 'name': name, 'response': response.json()}))
        assert expected['status'] == 'exploratory'
        assert bool(expected['known_unsupported_cards']) == (name == 'Aeon Chronicler')
        report = CardService(repo).completeness_report([name])['cards'][0]
        record_property('actual_completeness', json.dumps(report))
        assert report['match_ready']
        assert ('suspend' in report['unsupported_mechanics']) == (name == 'Aeon Chronicler')
        assert report['rules_coverage'] == ('known_unsupported' if name == 'Aeon Chronicler' else 'not_certified')
        assert repo.raw == original and dict(main.ACTIVE_MATCHES) == active
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(overrides)


@pytest.mark.parametrize('field,value', [
    ('layout', None), ('layout', 'unknown'), ('layout', 'adventure'),
    ('card_data_sources', []), ('card_data_sources', ['unknown']),
    ('card_data_sources', 'cache'), ('type_line', ''), ('mana_cost', []),
    ('card_data_sources', [[]]), ('layout', []),
    ('card_faces', [{'name': 'unverified face'}]),
])
def test_partial_unknown_diagnostic_context_retains_warning(field, value):
    row = metadata('Rift Bolt')
    row[field] = value  # Malformed diagnostic context, not a fabricated card fixture.
    before = deepcopy(row)
    assert 'suspend' in gaps(row)
    assert row == before


@pytest.mark.parametrize('field', ['layout', 'type_line', 'card_data_sources'])
def test_missing_required_context_retains_warning(field):
    row = metadata('Rift Bolt')
    row.pop(field)
    assert 'suspend' in gaps(row)


@pytest.mark.parametrize('context', [None, {}, [], 'cache'])
def test_legacy_and_invalid_context_are_conservative(context):
    row = metadata('Rift Bolt')
    assert 'suspend' in known_unsupported_mechanics(row['oracle_text'], card_name=row['card_name'],
                                                 canonical_context=context)


def test_borrowed_context_or_faces_cannot_clear_warning():
    row = metadata('Rift Bolt')
    assert 'suspend' in known_unsupported_mechanics(CARDS['Aeon Chronicler']['oracle_text'],
                                                 card_name='Aeon Chronicler', canonical_context=row)
    assert 'suspend' in known_unsupported_mechanics(row['oracle_text'], [CARDS['Aeon Chronicler']],
                                                 card_name=row['card_name'], canonical_context=row)
    assert 'suspend' in known_unsupported_mechanics(row['oracle_text'], card_name='Ancestral Vision',
                                                 canonical_context=row)


@pytest.mark.parametrize('layout', ['', 'normal'])
def test_explicit_admitted_layout_and_source(layout):
    row = metadata('Rift Bolt')
    row['layout'] = layout
    for source in ['cache', 'local_knowledge', 'offline_seed']:
        row['card_data_sources'] = [source]
        assert 'suspend' not in gaps(row)


def test_full_canonical_variable_and_additional_body_stays_unsupported():
    row = metadata('Aeon Chronicler')
    assert 'suspend' in gaps(row)
    assert gaps(row) == known_unsupported_mechanics(row['oracle_text'], card_name=row['card_name'])


def test_no_normal_mana_cost_is_not_an_unknown_suspend_cost():
    row = metadata('Ancestral Vision')
    assert CARDS['Ancestral Vision']['mana_cost'] == ''
    assert 'mana_cost' not in row
    assert 'suspend' not in gaps(row)


@pytest.mark.parametrize('name', ['Soul-Scar Mage', 'Searing Blaze'])
def test_other_canonical_warning_families_unchanged(name):
    root = Path(__file__).resolve().parents[1]
    row = json.loads((root / 'card_data/builtin_oracle_seed.json').read_text())['cards'][name]
    row = {**row, 'card_name': name, 'card_data_sources': ['offline_seed']}
    legacy = known_unsupported_mechanics(row['oracle_text'], card_name=name)
    assert legacy and gaps(row) == legacy


@pytest.mark.parametrize('surface', [
    'Suspend 0-{R}', 'Suspend X-{X}{R}', 'Suspend 1-Pay 2 life',
    'Suspend 1-{Q}', 'Suspend 1-{R}\nSuspend 2-{U}',
    'Suspend 1-{R}\nWhenever a time counter is removed from this card while it\'s exiled, draw a card.',
])
def test_runtime_surface_negative_diagnostics(surface):
    row = metadata('Rift Bolt')
    # Adversarial diagnostic strings only; not new canonical Oracle/card rows.
    row['oracle_text'] = 'Rift Bolt deals 3 damage to any target.\n' + surface
    assert 'suspend' in gaps(row)


@pytest.mark.parametrize('body', ['', 'Flying'])
def test_bounded_creature_body_diagnostics(body):
    row = metadata('Errant Ephemeron')
    printed = row['oracle_text'].splitlines()[-1]
    row['oracle_text'] = '\n'.join(filter(None, [body, printed]))
    assert 'suspend' not in gaps(row)
    row['power'] = None
    assert 'suspend' in gaps(row)


def test_remaining_body_and_other_markers_never_suppressed():
    row = metadata('Rift Bolt')
    # Diagnostic unknown body combines two actual unchanged canonical clauses.
    row['oracle_text'] += '\n' + CARDS['Aeon Chronicler']['oracle_text'].splitlines()[-1]
    assert 'suspend' in gaps(row)
    row = metadata('Errant Ephemeron')
    row['oracle_text'] += '\n' + CARDS['Aeon Chronicler']['oracle_text'].splitlines()[0]
    assert 'suspend' in gaps(row)
