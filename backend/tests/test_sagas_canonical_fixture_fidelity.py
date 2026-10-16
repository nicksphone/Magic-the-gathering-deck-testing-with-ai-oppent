"""Capture the original Saga tests' actual source births and consumer inputs."""
from copy import deepcopy
import hashlib
import json

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import Zone, _infer_keywords
from rules_engine.card_faces import FACE_FIELDS
from rules_engine.card_types import printed_card_types
from tests import test_sagas as original
from tests import sagas_canonical_fixtures as canonical
from tests.canonical_positive_fixtures import FIXTURES, PINS, SEED
from tests.day_night_apnap_canonical import DIRECTORY, PROVENANCE_SHA, SOURCES, raw_card as observer_raw


FABLE_CASES = (
    original.test_saga_transform_chapter_uses_the_source_permanents_back_face,
    original.test_transforming_saga_returns_under_chapter_controller_after_exile,
)


def capture_before_chapter(body, monkeypatch):
    captured = []
    births = []
    real_card = original.CardInstance

    class BeforeChapter(BaseException):
        pass

    def birth(*args, **kwargs):
        card = real_card(*args, **kwargs)
        if card.id == 'saga':
            births.append(deepcopy(card))
        return card

    def before_chapter(engine, state):
        captured.append(state)
        raise BeforeChapter

    with monkeypatch.context() as patch:
        patch.setattr(original, 'CardInstance', birth)
        patch.setattr(canonical, 'CardInstance', birth)
        patch.setattr(original.RulesEngine, '_advance_sagas', before_chapter)
        with pytest.raises(BeforeChapter):
            body()
    assert len(captured) == len(births) == 1
    return captured[0], births[0]


def assert_complete(card, raw, *, selected_face=0, factory=False):
    faces = (raw['card_faces'] if factory else
             ScryfallSyncService._normalize_faces(raw.get('card_faces') or []))
    surface = raw['card_faces'][0] if faces else raw
    assert card.name == surface['name']
    assert card.oracle_text == surface.get('oracle_text', '')
    assert card.mana_cost == surface.get('mana_cost', '')
    assert card.type_line == surface['type_line']
    assert card.types == printed_card_types(surface['type_line'])
    assert card.layout == raw['layout'] and card.card_faces == faces
    assert card.colors == surface.get('colors', [])
    assert card.keywords == _infer_keywords(surface.get('oracle_text', ''))
    assert card.selected_face_index == (selected_face if faces else None)
    for field in ('power', 'toughness', 'loyalty'):
        value = surface.get(field)
        assert getattr(card, field) == (int(value) if value is not None else None)
        if field != 'loyalty':
            assert getattr(card, 'printed_' + field) == value
    if faces:
        for field in FACE_FIELDS:
            assert card.printed_characteristics[field] == getattr(card, field)


@pytest.mark.parametrize('body', FABLE_CASES, ids=lambda body: body.__name__)
def test_actual_fable_source_is_complete_before_chapter_consumption(body, monkeypatch):
    state, _ = capture_before_chapter(body, monkeypatch)
    card = state.cards['saga']
    assert_complete(card, canonical.raw_card(canonical.FABLE))
    controller = 1 if body is FABLE_CASES[0] else 2
    assert card.id == 'saga' and card.owner == 1 and card.controller == controller
    assert card.zone == Zone.BATTLEFIELD and state.players[controller].battlefield[-1] in {'saga', 'corruption'}
    assert state.players[controller].battlefield.count(card.id) == 1
    assert card.counters == ({'__lore': 2, '+1/+1': 1} if controller == 1 else {'__lore': 2})
    if controller == 1:
        assert card.tapped and not card.summoning_sick and state.turn == 4
        assert state.players[1].battlefield[-2:] == ['saga', 'corruption']
    else:
        assert 'saga' not in state.players[1].battlefield
        assert state.active_player == state.priority_player == 2


@pytest.mark.parametrize('body', FABLE_CASES, ids=lambda body: body.__name__)
def test_actual_fable_is_born_from_canonical_facts_not_renamed_test_saga(body, monkeypatch):
    _, born = capture_before_chapter(body, monkeypatch)
    raw = canonical.raw_card(canonical.FABLE)
    cached = ScryfallSyncService._normalize_payload(raw, canonical.DISPLAY_IMAGE)
    assert born.name == raw['name']
    assert born.mana_cost == cached['mana_cost'] and born.oracle_text == cached['oracle_text']
    assert born.type_line == cached['type_line'] and born.layout == raw['layout']
    assert born.card_faces == ScryfallSyncService._normalize_faces(raw['card_faces'])
    assert born.id == 'saga' and born.owner == born.controller == 1
    assert born.zone == Zone.BATTLEFIELD and born.counters == {}


def test_actual_transform_observer_uses_the_complete_current_official_object(monkeypatch):
    state, _ = capture_before_chapter(FABLE_CASES[0], monkeypatch)
    card = state.cards['corruption']
    assert_complete(card, observer_raw('Corruption of Towashi'))
    assert card.id == 'corruption' and card.owner == card.controller == 1
    assert state.players[1].battlefield[-1] == card.id


def test_actual_kumano_deck_input_contains_the_entire_pinned_parent(monkeypatch):
    captured = []

    class BeforeFactory(BaseException):
        pass

    def before_factory(deck_a, deck_b, *args, **kwargs):
        captured.append(deepcopy((deck_a, deck_b, kwargs)))
        raise BeforeFactory

    monkeypatch.setattr(original.MatchFactory, 'from_decks', staticmethod(before_factory))
    with pytest.raises(BeforeFactory):
        original.test_double_faced_type_line_uses_front_face_before_transformation()
    assert len(captured) == 1
    raw = canonical.raw_card(canonical.KUMANO)
    expected = [{**raw, 'quantity': 1, 'card_name': raw['card_faces'][0]['name']}]
    assert captured[0] == (expected, expected, {'seed': 77})


def test_actual_kumano_factory_birth_materializes_the_printed_front(monkeypatch):
    states = []
    real_factory = original.MatchFactory.from_decks

    def capture(*args, **kwargs):
        state = real_factory(*args, **kwargs)
        states.append(state)
        return state

    monkeypatch.setattr(original.MatchFactory, 'from_decks', staticmethod(capture))
    original.test_double_faced_type_line_uses_front_face_before_transformation()
    assert len(states) == 1
    state = states[0]
    assert set(state.cards) == {'p1-001', 'p2-001'}
    for card in state.cards.values():
        assert card.name == 'Kumano Faces Kakkazan'
        assert_complete(card, canonical.raw_card(canonical.KUMANO), selected_face=None, factory=True)
        assert card.owner == card.controller == (1 if card.id.startswith('p1-') else 2)
        assert card.zone == Zone.HAND and state.players[card.owner].hand == [card.id]


def test_complete_seed_and_observer_provenance_remain_pinned():
    seed = (FIXTURES / SEED).read_bytes()
    assert hashlib.sha256(seed).hexdigest() == PINS[SEED]
    provenance = json.loads((FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == PINS[SEED] and provenance['oracle_modified'] is False
    for name in (canonical.FABLE, canonical.KUMANO):
        raw = canonical.raw_card(name)
        assert raw in list(map(json.loads, seed.splitlines()))
        assert raw['object'] == 'card' and len(raw['card_faces']) == 2
    data = (DIRECTORY / 'PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == PROVENANCE_SHA
    entry = next(row for row in json.loads(data)['new_cards'] if row['name'] == 'Corruption of Towashi')
    filename, pin = SOURCES[entry['name']]
    assert hashlib.sha256((DIRECTORY / filename).read_bytes()).hexdigest() == pin == entry['sha256']
    assert entry['full_unmodified_https_response'] is True and entry['source_url'].startswith('https://api.scryfall.com/')


def test_original_setups_do_not_alias_faces_or_mutate_the_pinned_seed(monkeypatch):
    first, _ = capture_before_chapter(FABLE_CASES[0], monkeypatch)
    second, _ = capture_before_chapter(FABLE_CASES[1], monkeypatch)
    left, right = first.cards['saga'], second.cards['saga']
    assert left.card_faces is not right.card_faces
    assert left.card_faces[0] is not right.card_faces[0]
    before = deepcopy((right.card_faces, canonical.raw_card(canonical.FABLE)))
    left.card_faces[0]['oracle_text'] = 'PROTOCOL MUTATION ONLY'
    assert (right.card_faces, canonical.raw_card(canonical.FABLE)) == before
