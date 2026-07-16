from __future__ import annotations

import json
from typing import Any

from card_data.placeholders import ensure_placeholder_image


def select_display_image_uri(card: Any, *, name: str, type_line: str = "", token: bool = False) -> str:
    image_uri = _get_attr_or_key(card, "image_uri")
    if image_uri:
        return str(image_uri)

    card_faces = _get_attr_or_key(card, "card_faces")
    if card_faces is None:
        card_faces_json = _get_attr_or_key(card, "card_faces_json")
        if isinstance(card_faces_json, str) and card_faces_json.strip():
            try:
                card_faces = json.loads(card_faces_json)
            except Exception:
                card_faces = []
    if isinstance(card_faces, list):
        for face in card_faces:
            if not isinstance(face, dict):
                continue
            face_image_uri = face.get("image_uri")
            if face_image_uri:
                return str(face_image_uri)

    return ensure_placeholder_image(name=name, type_line=type_line, token=token)


def _get_attr_or_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
