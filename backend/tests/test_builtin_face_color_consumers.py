"""Actual factory/selected-face/view/restore parity for both seats; no engine certificate."""
from copy import deepcopy
import json
import pickle
from pathlib import Path
import pytest

from card_data.hydration import hydrate_deck_cards
from game_state.state import MatchFactory, Zone
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot, serialize_card_view
from rules_engine.card_faces import select_cast_face, apply_cast_face, apply_transform_face
from rules_engine.colors import card_color_symbols
from tests.generic_import_fixtures import client, repo

F = Path(__file__).parent / 'fixtures/builtin_face_colors'
ADMISSION = json.loads((F / 'reviewed_admission.json').read_text())
NAMES = sorted({e['requested_name'] for e in ADMISSION})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('entry', ADMISSION, ids=[e['face_name'] for e in ADMISSION])
def test_all16_actual_factory_selected_face_view_and_snapshot_restore(entry, seat):
    deck = [{'card_name': entry['requested_name'], 'quantity': 4}, {'card_name': 'Island', 'quantity': 56}]
    facts = hydrate_deck_cards(None, deck)
    assert facts[0]['scryfall_id'] == entry['scryfall_id']
    state = MatchFactory.from_decks(facts, facts, seed=716)
    card = next(c for c in state.cards.values() if c.owner == seat and c.card_faces)
    baseline = serialize_match_snapshot(state); original = pickle.dumps(state)
    face = select_cast_face(card, entry['face_index'])
    assert face.name == entry['face_name'] and sorted(card_color_symbols(face)) == entry['colors']
    # Apply existing face helpers only on a snapshot clone; this tests metadata,
    # not legality/admission or execution of every card's full effect clauses.
    clone = deserialize_match_snapshot(deepcopy(baseline)); selected = clone.cards[card.id]
    if selected.layout == 'transform':
        selected.zone = Zone.BATTLEFIELD
        apply_transform_face(selected, entry['face_index'])
    else:
        selected.zone = Zone.STACK
        apply_cast_face(selected, select_cast_face(selected, entry['face_index']))
    view = serialize_card_view(clone, card.id)
    assert view['colors'] == entry['colors'] and view['name'] == entry['face_name']
    assert view['selected_face_index'] == entry['face_index']
    assert selected.owner == selected.controller == seat and selected.id == card.id
    restored = deserialize_match_snapshot(serialize_match_snapshot(clone))
    assert serialize_card_view(restored, card.id)['colors'] == entry['colors']
    assert pickle.dumps(state) == original and serialize_match_snapshot(state) == baseline


@pytest.mark.parametrize('name', NAMES)
def test_actual_http_cold_seed_import_start_lazy_restore_preserves_face_facts(repo, client, name, monkeypatch):
    import main
    # Lazy GET restoration opens a session directly, outside get_repo overrides.
    monkeypatch.setattr(main, 'engine', repo.session.get_bind())
    deck = [{'card_name': name, 'quantity': 4}, {'card_name': 'Island', 'quantity': 56}]
    imported = client.post('/decks/import', json={'name': 'Face facts ' + name, 'source': 'user:face-audit',
                                                 'deck_text': '4 ' + name + '\n56 Island'})
    assert imported.status_code == 200, imported.text
    meta = imported.json()['resolved_mainboard_cards'][0]['card_metadata']
    expected = [e for e in ADMISSION if e['requested_name'] == name]
    assert [f['colors'] for f in meta['card_faces']] == [e['colors'] for e in expected]
    assert meta['scryfall_id'] == expected[0]['scryfall_id'] and meta['match_ready']
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'controller_a': 'human', 'controller_b': 'human', 'seed': 717})
    assert response.status_code == 200, response.text
    mid = response.json()['id']; match = main.ACTIVE_MATCHES[mid]
    root = serialize_match_snapshot(match.state)
    SQL = '\n'.join(repo.session.connection().connection.driver_connection.iterdump())
    for seat in [1, 2]:
        card = next(c for c in match.state.cards.values() if c.owner == seat and c.card_faces)
        assert [f['colors'] for f in card.card_faces] == [e['colors'] for e in expected]
        assert serialize_card_view(match.state, card.id)['colors'] == expected[0]['colors']
    first = client.get(f'/matches/{mid}')
    assert first.status_code == 200
    main.ACTIVE_MATCHES.clear()
    again = client.get(f'/matches/{mid}')
    assert again.status_code == 200 and again.json() == first.json()
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == root
    assert '\n'.join(repo.session.connection().connection.driver_connection.iterdump()) == SQL
    assert repo.list_cards() == []
