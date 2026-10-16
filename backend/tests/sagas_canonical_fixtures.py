"""Complete pinned Saga facts, materialized using the existing face mapper."""
import json

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, Zone, _infer_keywords
from rules_engine.card_faces import apply_transform_face
from rules_engine.card_types import printed_card_types
from tests.canonical_positive_fixtures import raw_card


FABLE = 'Fable of the Mirror-Breaker // Reflection of Kiki-Jiki'
KUMANO = 'Kumano Faces Kakkazan // Etching of Kumano'
DISPLAY_IMAGE = 'fixture:sagas-canonical'  # Display only; avoids placeholder I/O.


def permanent(card_id, name, owner):
    cached = ScryfallSyncService._normalize_payload(raw_card(name), DISPLAY_IMAGE)
    number = lambda value: int(value) if value is not None else None
    card = CardInstance(
        card_id, cached['name'], owner, owner, Zone.BATTLEFIELD,
        types=printed_card_types(cached['type_line']), type_line=cached['type_line'],
        oracle_text=cached['oracle_text'], mana_cost=cached['mana_cost'],
        power=number(cached['power']), toughness=number(cached['toughness']),
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        loyalty=number(cached['loyalty']), colors=cached['colors'].split(',') if cached['colors'] else [],
        keywords=_infer_keywords(cached['oracle_text']), image_uri=cached['image_uri'],
        layout=cached['layout'], card_faces=json.loads(cached['card_faces_json']),
    )
    apply_transform_face(card, 0)
    return card
