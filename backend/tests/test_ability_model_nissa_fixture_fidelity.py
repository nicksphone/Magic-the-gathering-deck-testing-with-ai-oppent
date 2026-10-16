"""Inspect Nissa from the original test at the real ability-model boundary."""
import hashlib
import json

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import Zone, _infer_keywords
from rules_engine.card_types import printed_card_types
from tests import canonical_positive_fixtures as canonical
from tests import test_ability_model as original


NAME = 'Nissa, Who Shakes the World'


def archived():
    data = (canonical.FIXTURES / canonical.SEED).read_bytes()
    assert hashlib.sha256(data).hexdigest() == canonical.PINS[canonical.SEED]
    rows = [row for row in map(json.loads, data.splitlines()) if row.get('name') == NAME]
    assert len(rows) == 1 and rows[0]['object'] == 'card'
    return rows[0]


def actual_input(monkeypatch):
    captured = []

    class BeforeSpec(BaseException):
        pass

    def capture(state, card, controller, *args, **kwargs):
        captured.append((state, card, controller, args, kwargs))
        raise BeforeSpec

    with monkeypatch.context() as patch:
        patch.setattr(original, 'build_ability_spec', capture)
        with pytest.raises(BeforeSpec):
            original.test_planeswalker_static_and_loyalty_text_is_not_cast_time_fallback()
    assert len(captured) == 1
    return captured[0]


def test_actual_original_nissa_input_keeps_the_entire_official_oracle(monkeypatch):
    state, card, controller, args, kwargs = actual_input(monkeypatch)
    raw = archived()
    assert card.oracle_text == raw['oracle_text']
    assert card.name == raw['name'] and card.id == 'nissa'
    assert card.owner == card.controller == controller == 1 and card.zone == Zone.HAND
    assert args == () and kwargs == {}
    assert card.id not in state.cards  # Preserve the original standalone source setup.


def test_actual_original_nissa_printed_fields_match_the_complete_projection(monkeypatch):
    _, card, _, _, _ = actual_input(monkeypatch)
    raw = archived()
    cached = ScryfallSyncService._normalize_payload(raw, canonical.CACHED_IMAGE_URI)
    expected = dict(name=raw['name'], oracle_text=raw['oracle_text'], mana_cost=cached['mana_cost'],
        type_line=cached['type_line'], types=printed_card_types(cached['type_line']),
        colors=raw['colors'], keywords=_infer_keywords(raw['oracle_text']),
        loyalty=int(raw['loyalty']), power=None, toughness=None,
        printed_power=None, printed_toughness=None, layout=raw['layout'],
        card_faces=json.loads(cached['card_faces_json']), image_uri=cached['image_uri'],
        selected_face_index=None)
    assert {field: getattr(card, field) for field in expected} == expected


def test_existing_seed_provenance_and_shared_loader_bind_the_complete_object():
    raw = archived()
    assert raw == canonical.raw_card(NAME)
    assert raw['uri'].startswith('https://api.scryfall.com/cards/')
    assert raw['id'] and raw['oracle_id'] and raw['object'] == 'card'
    assert raw['loyalty'] and raw['mana_cost'] and raw['type_line']
    provenance = json.loads((canonical.FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == canonical.PINS[canonical.SEED]
    assert provenance['oracle_modified'] is False
    assert provenance['response_statuses'] == [200, 200, 200]


def test_original_nissa_inputs_are_fresh_and_do_not_mutate_pinned_facts(monkeypatch):
    _, first, _, _, _ = actual_input(monkeypatch)
    _, second, _, _, _ = actual_input(monkeypatch)
    raw = archived()
    assert first is not second and first.oracle_text == second.oracle_text == raw['oracle_text']
    assert first.colors is not second.colors
    first.oracle_text = 'PROTOCOL MUTATION ONLY'
    first.colors.clear()
    assert second.oracle_text == archived()['oracle_text'] and second.colors == raw['colors']
    assert canonical.raw_card(NAME) == raw
