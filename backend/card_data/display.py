from __future__ import annotations

import json
from typing import Any

from card_data.placeholders import CACHE_ROUTE_PREFIX, ensure_placeholder_image, local_image_available


def select_display_image_uri(card: Any, *, name: str, type_line: str = "", token: bool = False) -> str:
    image_uri = _get_attr_or_key(card, "image_uri")
    if _available_image_uri(image_uri):
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
            if _available_image_uri(face_image_uri):
                return str(face_image_uri)

    return ensure_placeholder_image(name=name, type_line=type_line, token=token)


def _available_image_uri(image_uri: Any) -> bool:
    return bool(image_uri and (not str(image_uri).startswith(CACHE_ROUTE_PREFIX + "/")
                              or local_image_available(str(image_uri))))


def _get_attr_or_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
