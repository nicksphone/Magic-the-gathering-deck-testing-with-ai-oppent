"""Actual named fixture inputs at original event/effect boundaries, not casts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

import tests.test_transform_draw as draw
import tests.test_transform_triggers as triggers
from game_state.state import Zone
from rules_engine.card_types import printed_card_types
from tests.canonical_positive_fixtures import raw_card as positive_raw
from tests.day_night_apnap_canonical import raw_card as observer_raw


KUMANO = 'Kumano Faces Kakkazan // Etching of Kumano'
DELVER = 'Delver of Secrets // Insectile Aberration'
BALA = 'Bala Ged Recovery // Bala Ged Sanctuary'
NORNS_SHA = '3532ccffbb2549addfef0dcaf88f16925ae7c76d895ae822ef0c6bd44f506de0'
ROOT = Path(__file__).parent / 'fixtures'
SUBJECTS = [
    (draw, draw.test_declining_transform_draw_allows_later_trigger_but_accepting_stops_it,
     'corruption', 'Corruption of Towashi', None),
    (triggers, triggers.test_norns_inquisitor_transform_trigger_uses_stack_and_survives_snapshot,
     'inquisitor', "Norn's Inquisitor", None),
    (draw, draw.test_entering_transformed_counts_but_modal_back_face_does_not,
     'etching', KUMANO, 1),
    (draw, draw.test_entering_transformed_counts_but_modal_back_face_does_not,
     'second-etching', KUMANO, 1),
    (draw, draw.test_entering_transformed_counts_but_modal_back_face_does_not,
     'modal', BALA, 1),
    (triggers, triggers.test_transform_trigger_requires_control_and_resulting_subtype,
     'delver', DELVER, 0),
]


def archived(name):
    if name == "Norn's Inquisitor":
        return json.loads((ROOT / 'transform_draw_canonical/norns-inquisitor-scryfall-raw.json').read_bytes())
    if name == 'Corruption of Towashi':
        return observer_raw(name)
    return positive_raw(name)


def capture(monkeypatch, module, body):
    records = {}
    real_event, real_effect = module.emit_event, module.resolve_effect

    def observe(state, boundary):
        for card_id in ('corruption', 'inquisitor', 'etching', 'second-etching', 'modal', 'delver'):
            if card_id in state.cards and card_id not in records:
                card = state.cards[card_id]
                records[card_id] = dict(before=deepcopy(vars(card)), actual=card, boundary=boundary)

    def event(state, kind, payload):
        observe(state, 'event:' + kind)
        return real_event(state, kind, payload)

    def effect(state, player, key, payload):
        observe(state, 'effect:' + key)
        return real_effect(state, player, key, payload)

    with monkeypatch.context() as patch:
        patch.setattr(module, 'emit_event', event)
        patch.setattr(module, 'resolve_effect', effect)
        body()
    return records


@pytest.mark.parametrize('module,body,card_id,name,index', SUBJECTS,
                         ids=['Corruption', 'Norns', 'Etching', 'SecondEtching', 'BalaGed', 'Delver'])
def test_actual_original_fixture_is_complete_before_real_event_or_effect(module, body, card_id, name, index, monkeypatch):
    record = capture(monkeypatch, module, body)[card_id]
    actual = record['before']
    raw = archived(name)
    face = raw if index is None else raw['card_faces'][index]
    assert record['boundary'].startswith(('event:', 'effect:'))
    assert actual['card_faces'] == raw.get('card_faces', []), 'Actual named fixture has reduced faces'
    for key in ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors'):
        assert actual[key] == face.get(key), 'Actual named fixture is not the complete canonical projection'
    assert actual['types'] == printed_card_types(face['type_line'])
    assert actual['layout'] == raw['layout'] and actual['selected_face_index'] == index
    for key in ('power', 'toughness', 'loyalty'):
        assert actual[key] == (int(face[key]) if face.get(key) is not None else None)
    assert actual['id'] == card_id and actual['owner'] == actual['controller'] == 1
    assert actual['zone'] == Zone.BATTLEFIELD


def test_actual_sibling_and_repeated_setup_faces_are_independent(monkeypatch):
    body = draw.test_entering_transformed_counts_but_modal_back_face_does_not
    first = capture(monkeypatch, draw, body)
    a, b = first['etching']['actual'], first['second-etching']['actual']
    before = deepcopy(b.card_faces)
    assert a is not b and a.card_faces is not b.card_faces
    assert all(left is not right for left, right in zip(a.card_faces, b.card_faces))
    a.card_faces[0]['oracle_text'] = 'Declared noncanonical independence sentinel'
    assert b.card_faces == before
    second = capture(monkeypatch, draw, body)
    assert second['etching']['actual'] is not a
    assert second['etching']['before']['card_faces'] == archived(KUMANO)['card_faces']


def test_full_official_rows_and_intake_provenance_are_pinned():
    path = ROOT / 'transform_draw_canonical'
    raw_bytes = (path / 'norns-inquisitor-scryfall-raw.json').read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == NORNS_SHA
    receipt = json.loads((path / 'PROVENANCE.json').read_bytes())
    raw = json.loads(raw_bytes)
    assert receipt['url'] == 'https://api.scryfall.com/cards/named?' + urlencode({'exact': "Norn's Inquisitor"})
    assert receipt['http_status'] == 200 and receipt['sha256'] == NORNS_SHA
    assert receipt['utc_started'] and receipt['utc_completed'] and receipt['response_headers_sha256']
    assert receipt['oracle_modified'] is False and raw['name'] == "Norn's Inquisitor"
    assert raw['object'] == 'card' and raw['id'] == receipt['scryfall_id']
    assert raw['oracle_id'] == receipt['oracle_id'] and raw['legalities']
    for name in ('Corruption of Towashi', KUMANO, DELVER, BALA):
        raw = archived(name)
        assert raw['object'] == 'card' and raw['id'] and raw['oracle_id']
        assert raw['rulings_uri'].startswith('https://api.scryfall.com/cards/')
