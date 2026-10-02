"""Canonical coverage gaps are evidence, never a blanket rules certificate."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.combat_constraints import combat_clause_coverage
from rules_engine.coverage import known_unsupported_mechanics, deck_pair_coverage, combat_coverage_details
from rules_engine.static_conditions import parse_static_condition, evaluate_static_condition
from tests.test_ai_recurring_engines import fixture, add as raw_add
from tests.test_conditional_combat import CARDS as SUPPORTED, add, lose
from tests.test_api_input_contracts import game, persist, snapshot

ROWS = {row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/combat_coverage.json').read_text())}
ROWS.update({row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/combat_temporary_costs.json').read_text())})
ROWS.update({row['name']: row for row in json.loads((Path(__file__).parent / 'fixtures/combat_payments_requirements.json').read_text())})


@pytest.mark.parametrize('name', ["Archangel of Tithes"])
def test_canonical_attack_taxes_are_not_silently_certified(name):
    rows = combat_clause_coverage(ROWS[name]['oracle_text'], name)
    assert any('unsupported combat payment' in row['reasons'] for row in rows)
    assert 'unsupported combat payment' in known_unsupported_mechanics(ROWS[name]['oracle_text'], card_name=name)
    report = deck_pair_coverage([{'card_name': name, 'oracle_text': ROWS[name]['oracle_text']}], [])
    assert report['known_unsupported_cards'][0]['card_name'] == name
    assert report['known_unsupported_cards'][0]['combat_clause_gaps'][0]['face_name'] == name
    assert report['status'] == 'exploratory'


@pytest.mark.parametrize('name', ['Stormtide Leviathan'])
def test_unimplemented_qualified_subject_is_visible(name):
    gaps = combat_clause_coverage(ROWS[name]['oracle_text'], name)
    assert gaps
    assert any('unsupported combat subject' in row['reasons'] for row in gaps)


def test_declaration_limit_coverage_now_uses_the_implemented_parser():
    assert not combat_clause_coverage(ROWS['Silent Arbiter']['oracle_text'], 'Silent Arbiter')


@pytest.mark.parametrize('name', list(SUPPORTED) + ['Goblin War Drums'])
def test_supported_clauses_and_keyword_reminder_text_do_not_add_false_warnings(name):
    row = (SUPPORTED | ROWS)[name]
    assert combat_clause_coverage(row['oracle_text'], name) == []


def test_faces_names_duplicates_trigger_and_granted_text_are_distinguished():
    faces = [ROWS["Archangel of Tithes"], ROWS["Archangel of Tithes"]]
    gaps = known_unsupported_mechanics('', faces)
    assert gaps.count('unsupported combat payment') == 1
    details = combat_coverage_details('', faces)
    assert {row['face_index'] for row in details} == {0, 1}
    # Explicit grammar fixtures, not cards or deck additions.
    assert combat_clause_coverage("Whenever this creature attacks, creatures can't block this turn.") == []
    assert combat_clause_coverage('Creatures gain "This creature can block any number of creatures."') == []
    assert combat_clause_coverage("As long as an unknown predicate, this creature can't attack.")
    assert combat_clause_coverage("This creature can't attack unless you control thirteen or more lands.")
    assert not combat_clause_coverage("CARDNAME can't attack alone.")
    assert not combat_clause_coverage("Named Source can't attack alone.", 'Named Source')


@pytest.mark.parametrize('condition', [
    "it's a human", "it is blue", 'enchanted creature is an artifact',
    'you control a red and white permanent', 'your opponents control a green permanent',
    'there are three or more cards in your graveyard', 'this aura has two or more counters on it',
    'you control seven or more lands', 'defending player controls an island',
    'there are five or more islands on the battlefield', 'it has five or more +1/+1 counters on it',
])
def test_recognition_and_live_predicate_evaluation_share_a_contract(condition):
    state = fixture()
    target = add(state, 'Slumbering Dragon')
    source = add(state, 'Bonds of Faith')
    before = serialize_match_snapshot(state)
    assert parse_static_condition(condition) is not None
    assert isinstance(evaluate_static_condition(state, source, target, condition), bool)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('player', [1, 2])
def test_live_diagnostics_exclude_private_zones_and_preserve_sqlite_state(game, player):
    import main
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    client, match = game
    creature = add(match.state, 'Slumbering Dragon', player)
    creature.counters['+1/+1'] = 4
    source = raw_add(match.state, "Archangel of Tithes", 3-player, cards=ROWS)
    secret = raw_add(match.state, 'Ghostly Prison', player, Zone.HAND, cards=ROWS)
    persist(match)
    before = snapshot(match)
    response = client.get(f'/matches/{match.state.id}/rules-diagnostics')
    assert response.status_code == 200
    data = response.json()
    assert data['revision'] == match.revision and data['status'] == 'exploratory'
    assert secret.id not in {row['card_id'] for row in data['cards']}
    target_view = next(row for row in data['cards'] if row['card_id'] == creature.id)
    assert target_view['active_combat_constraints'][0]['source_id'] == creature.id
    source_view = next(row for row in data['cards'] if row['card_id'] == source.id)
    assert source_view['printed_combat_coverage_gaps']
    assert snapshot(match) == before
    lose(match.state, creature)
    persist(match)
    expected = client.get(f'/matches/{match.state.id}/rules-diagnostics').json()
    assert next(row for row in expected['cards'] if row['card_id'] == creature.id)['printed_abilities_suppressed']
    match_id = match.state.id
    main.ACTIVE_MATCHES.pop(match_id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), match_id)
    assert client.get(f'/matches/{match_id}/rules-diagnostics').json() == expected
    assert client.get('/matches/does-not-exist/rules-diagnostics').status_code == 404


def test_http_preflight_reports_canonical_tax_from_name_only_deck(game, monkeypatch):
    import main
    from card_data.fallback_cards import fallback_card_payload
    client, match = game
    monkeypatch.setattr(main, '_hydrate_deck_cards', lambda repo, deck: [
        {**(ROWS.get(item['card_name']) or fallback_card_payload(item['card_name'])), **item}
        for item in deck])
    deck = [{'quantity': 4, 'card_name': "Archangel of Tithes"}, {'quantity': 56, 'card_name': 'Island'}]
    before = snapshot(match)
    response = client.post('/simulate/batch/preflight', json={'deck_a': deck, 'deck_b': deck})
    assert response.status_code == 200, response.text
    cards = response.json()['known_unsupported_cards']
    assert {row['deck'] for row in cards} == {'A', 'B'}
    assert all('unsupported combat payment' in row['mechanics'] for row in cards)
    assert all(row['combat_clause_gaps'] for row in cards)
    assert snapshot(match) == before


def test_cached_completeness_exposes_clause_provenance_without_sync(game, monkeypatch):
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from card_data.service import CardService
    from card_data.sync import ScryfallSyncService
    client, match = game
    row = ROWS["Archangel of Tithes"]
    monkeypatch.setattr(ScryfallSyncService, 'sync_card_by_name', lambda *a, **k: pytest.fail('Read report attempted sync'))
    with Session(engine) as session:
        repo = Repository(session)
        repo.upsert_card({'scryfall_id': row['id'], 'name': row['name'], 'oracle_text': row['oracle_text'],
                         'mana_cost': row['mana_cost'], 'type_line': row['type_line']})
        before = snapshot(match)
        card = CardService(repo).completeness_report(["Archangel of Tithes"])['cards'][0]
        assert card['rules_coverage'] == 'known_unsupported'
        assert 'unsupported combat payment' in card['unsupported_mechanics']
        assert card['combat_clause_gaps'][0]['face_name'] == "Archangel of Tithes"
        assert snapshot(match) == before
