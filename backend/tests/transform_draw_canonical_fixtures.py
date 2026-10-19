"""Finite canonical fixture poses; no cast, entry event or stock authority."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from game_state.state import MatchFactory, Zone
from rules_engine.card_faces import apply_transform_face
from tests.canonical_positive_fixtures import raw_card as positive_raw
from tests.day_night_apnap_canonical import raw_card as observer_raw


def raw_card(name):
    if name == "Norn's Inquisitor":
        path = Path(__file__).parent / 'fixtures/transform_draw_canonical/norns-inquisitor-scryfall-raw.json'
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == '3532ccffbb2549addfef0dcaf88f16925ae7c76d895ae822ef0c6bd44f506de0'
        return json.loads(data)
    if name == 'Corruption of Towashi':
        return observer_raw(name)
    if name not in ('Kumano Faces Kakkazan // Etching of Kumano',
                    'Delver of Secrets // Insectile Aberration',
                    'Bala Ged Recovery // Bala Ged Sanctuary'):
        raise KeyError(name)
    return positive_raw(name)


def permanent(card_id, name, *, face_index=None):
    raw = raw_card(name)
    materialized = MatchFactory.from_decks(
        [{**raw, 'quantity': 8, 'card_name': raw['name']}], [], seed=77)
    # A never-drawn sample has no inherited hand/zone-change history.
    template = next(card for card in materialized.cards.values() if card.zone == Zone.LIBRARY)
    if face_index is not None:
        apply_transform_face(template, face_index)
    return replace(template, id=card_id, owner=1, controller=1, zone=Zone.BATTLEFIELD,
                   instance_order=0, summoning_sick=True)
