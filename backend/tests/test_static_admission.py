"""Verified Oracle clauses, not whole-card support or matchup certification."""
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.continuous import effective_combat_stats, has_keyword
from rules_engine.coverage import deck_pair_coverage, known_unsupported_mechanics
from tests.test_ai_recurring_engines import fixture, add
from tests.test_api_input_contracts import game, snapshot

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/static_admission.json').read_text())}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,resource,threshold,keyword', [
    ("Thieves' Guild Enforcer", 'graveyard', 8, 'deathtouch'),
    ('Guul Draz Vampire', 'life', 10, 'intimidate'),
])
def test_opponent_resources_are_live_controller_relative_and_snapshot_safe(seat, name, resource, threshold, keyword):
    from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
    state = fixture()
    source = add(state, name, seat, cards=ROWS)
    opponent = 3 - seat
    for active in [False, True, False, True]:
        if resource == 'life':
            state.players[opponent].life = threshold if active else threshold + 1
            state.players[seat].life = threshold
        else:
            while len(state.players[opponent].graveyard) < threshold:
                add(state, 'Swamp', opponent, Zone.GRAVEYARD,
                    cards={'Swamp': {'name': 'Swamp', 'type_line': 'Basic Land — Swamp', 'mana_cost': '',
                                     'oracle_text': '', 'power': None, 'toughness': None, 'keywords': [], 'colors': []}})
            card = state.cards[state.players[opponent].graveyard[-1]]
            card.is_token = not active
        before = serialize_match_snapshot(state)
        assert effective_combat_stats(state, source.id) == ((3, 2) if active else (1, 1))
        assert has_keyword(state, source.id, keyword) is active
        assert serialize_match_snapshot(state) == before
        restored = deserialize_match_snapshot(before)
        assert effective_combat_stats(restored, source.id) == ((3, 2) if active else (1, 1))
        assert has_keyword(restored, source.id, keyword) is active


@pytest.mark.parametrize('name', ['Thunderfoot Baloth', "Tyrant's Familiar"])
def test_unimplemented_static_clauses_are_visible_in_admission(name):
    row = ROWS[name]
    mechanics = known_unsupported_mechanics(row['oracle_text'], card_name=name)
    assert any('conditional static' in reason for reason in mechanics)
    report = deck_pair_coverage([dict(row, card_name=name)], [])
    card = report['known_unsupported_cards'][0]
    assert card['static_clause_gaps']
    assert all(item['clause'] and item['reasons'] for item in card['static_clause_gaps'])
    assert report['status'] == 'exploratory'


def test_supported_resource_clauses_do_not_warn():
    for name in ["Thieves' Guild Enforcer", 'Guul Draz Vampire']:
        assert known_unsupported_mechanics(ROWS[name]['oracle_text'], card_name=name) == []


@pytest.mark.parametrize('seat', [1, 2])
def test_control_change_rebinds_the_opponent_condition(seat):
    state = fixture()
    source = add(state, 'Guul Draz Vampire', seat, cards=ROWS)
    state.players[seat].life = 20
    state.players[3 - seat].life = 10
    assert effective_combat_stats(state, source.id) == (3, 2)
    state.players[seat].battlefield.remove(source.id)
    state.players[3 - seat].battlefield.append(source.id)
    source.controller = 3 - seat
    assert effective_combat_stats(state, source.id) == (1, 1)
    assert not has_keyword(state, source.id, 'intimidate')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('active', [False, True])
def test_ai_entry_projection_uses_opponent_life_without_mutation(seat, active):
    from ai.pending_effects import prospective_creature_stats, decision_projection_scope
    from game_state.serializers import serialize_match_snapshot
    state = fixture()
    source = add(state, 'Guul Draz Vampire', seat, Zone.HAND, cards=ROWS)
    state.players[3 - seat].life = 10 if active else 11
    before = serialize_match_snapshot(state)
    with decision_projection_scope(state, seat):
        for _ in range(2):
            assert prospective_creature_stats(state, source, seat) == ((3, 2) if active else (1, 1))
    assert serialize_match_snapshot(state) == before


def test_completeness_and_public_diagnostics_share_static_admission(game):
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    from card_data.service import CardService
    client, match = game
    row = ROWS['Thunderfoot Baloth']
    add(match.state, row['name'], cards=ROWS)
    before = snapshot(match)
    public = client.get(f'/matches/{match.state.id}/rules-diagnostics')
    assert public.status_code == 200
    gaps = public.json()['cards'][0]['printed_static_coverage_gaps']
    assert gaps
    assert snapshot(match) == before
    with Session(engine) as session:
        repo = Repository(session)
        repo.upsert_card({'scryfall_id': row['id'], 'name': row['name'], 'oracle_text': row['oracle_text'],
                         'mana_cost': row['mana_cost'], 'type_line': row['type_line'],
                         'power': row['power'], 'toughness': row['toughness']})
        report = CardService(repo).completeness_report([row['name']])['cards'][0]
        assert report['rules_coverage'] == 'known_unsupported'
        assert report['static_clause_gaps'] == gaps


def test_canonical_supported_static_corpus_has_no_new_static_gaps():
    from rules_engine.coverage import static_coverage_details
    rows = json.loads((Path(__file__).parent / 'fixtures/conditional_static.json').read_text())
    for row in rows:
        assert static_coverage_details(row['oracle_text'], card_name=row['name']) == [], row['name']


def test_triggered_activated_and_temporary_grammar_is_not_a_static_instruction():
    from rules_engine.coverage import static_coverage_details
    # Grammar fixtures are never production cards or deck additions.
    for text in ['Whenever a creature enters, it gets +1/+1 as long as you control it.',
                 '{G}: This creature gets +1/+1 as long as you control it.',
                 'Target creature gets +1/+1 until end of turn as long as it is attacking.']:
        assert static_coverage_details(text) == []


def test_unknown_second_face_keeps_face_provenance_and_deduplicates_reasons():
    row = ROWS['Thunderfoot Baloth']
    report = deck_pair_coverage([], [{'card_name': 'Face fixture', 'oracle_text': '', 'card_faces': [row, row]}])
    card = report['known_unsupported_cards'][0]
    assert card['deck'] == 'B'
    assert {item['face_index'] for item in card['static_clause_gaps']} == {0, 1}
    assert all(item['face_name'] == row['name'] for item in card['static_clause_gaps'])
    assert len(card['mechanics']) == len(set(card['mechanics']))


def test_http_preflight_exposes_static_gaps_without_mutating_match(game, monkeypatch):
    import main
    client, match = game
    row = ROWS['Thunderfoot Baloth']
    monkeypatch.setattr(main, '_hydrate_deck_cards', lambda repo, deck: [dict(row, **item) for item in deck])
    before = snapshot(match)
    deck = [{'card_name': row['name'], 'quantity': 60}]
    response = client.post('/simulate/batch/preflight', json={'deck_a': deck, 'deck_b': deck})
    assert response.status_code == 200, response.text
    cards = response.json()['known_unsupported_cards']
    assert {item['deck'] for item in cards} == {'A', 'B'}
    assert all(item['static_clause_gaps'] for item in cards)
    assert snapshot(match) == before
