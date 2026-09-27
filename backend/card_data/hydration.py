from __future__ import annotations

import json

from card_data.display import select_display_image_uri
from card_data.fallback_cards import fallback_card_payload


def hydrate_deck_cards(repo, deck: list[dict]) -> list[dict]:
    """Attach cached/fallback metadata before constructing a game state."""
    names = [str(item.get("card_name") or "") for item in deck]
    cached = repo.get_cached_cards_by_names(names) if repo is not None else {}
    hydrated: list[dict] = []
    for item in deck:
        name = str(item.get("card_name") or "Card")
        out = dict(item)
        row = cached.get(name.lower())
        fallback = fallback_card_payload(name) or {}
        if row is not None:
            out["layout"] = getattr(row, "layout", "") or fallback.get("layout", "")
            fields = {
                key: (getattr(row, key, None) if getattr(row, key, None) is not None else fallback.get(key))
                if key in {"power", "toughness"} else getattr(row, key, None) or fallback.get(key)
                for key in ("oracle_text", "mana_cost", "type_line", "power", "toughness")
            }
            for key, value in fields.items():
                if value is not None:
                    out[key] = value
            loyalty = getattr(row, "loyalty", None)
            if loyalty is not None or fallback.get("loyalty") is not None:
                out["loyalty"] = loyalty if loyalty is not None else fallback.get("loyalty")
            faces_json = getattr(row, "card_faces_json", "") or ""
            if faces_json:
                try:
                    faces = json.loads(faces_json)
                except (TypeError, ValueError):
                    faces = []
                if isinstance(faces, list) and faces and all(isinstance(face, dict) for face in faces):
                    out["card_faces"] = faces
                    if out["layout"] in {"modal_dfc", "transform", "adventure", "reversible_card"}:
                        for key in ("oracle_text", "mana_cost", "type_line", "power", "toughness", "loyalty"):
                            if key in faces[0]:
                                out[key] = faces[0][key]
            out["image_uri"] = select_display_image_uri(row, name=name, type_line=str(out.get("type_line") or ""))
        elif fallback:
            out.update({key: value for key, value in fallback.items() if value is not None})
        if not out.get("image_uri"):
            out["image_uri"] = select_display_image_uri(out, name=name, type_line=str(out.get("type_line") or ""))
        hydrated.append(out)
    return hydrated
