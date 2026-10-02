from __future__ import annotations

import json

from card_data.display import select_display_image_uri
from card_data.fallback_cards import fallback_card_payload
from card_data.sync import ScryfallSyncService, needs_split_color_sync


def cached_json(value, expected_type):
    try:
        result = json.loads(value or '')
    except (TypeError, ValueError):
        return expected_type()
    return result if isinstance(result, expected_type) else expected_type()


def local_knowledge(repo, names):
    if not names or repo is None:
        return {}
    if hasattr(repo, 'get_card_knowledge_by_names'):
        return repo.get_card_knowledge_by_names(names)
    return {row.name.casefold(): row for row in repo.list_card_knowledge(names)} if hasattr(repo, 'list_card_knowledge') else {}


def _printed_stats_available(metadata):
    printed_types = str(metadata.get('type_line') or '').split(' — ', 1)[0].split(' // ', 1)[0].split()
    if 'Creature' in printed_types and any(metadata.get(key) is None for key in ('power', 'toughness')):
        return False
    if 'Planeswalker' in printed_types and metadata.get('loyalty') is None:
        return False
    return True


def ready_for_match(metadata):
    if not metadata.get('type_line') or not is_playable_deck_card(metadata) or not _printed_stats_available(metadata):
        return False
    if metadata.get('card_faces') and not metadata.get('layout'):
        return False
    if needs_split_color_sync(metadata):
        return False
    if metadata.get('layout') in {'modal_dfc', 'transform', 'adventure', 'split', 'reversible_card'}:
        faces = metadata.get('card_faces') or []
        return len(faces) >= 2 and all(isinstance(face, dict) and face.get('name') and face.get('type_line')
                                     and _printed_stats_available(face) for face in faces)
    return True


def is_playable_deck_card(metadata: dict) -> bool:
    layout = str(metadata.get("layout") or "").lower()
    type_line = str(metadata.get("type_line") or "").strip().lower()
    return layout not in {"art_series", "token", "double_faced_token", "emblem"} and type_line not in {"card", "emblem"} and not type_line.startswith("token ")


def hydrate_deck_cards(repo, deck: list[dict]) -> list[dict]:
    """Read local canonical data only; never fetch or write database records."""
    names = [str(item.get("card_name") or "") for item in deck]
    cached = repo.get_cached_cards_by_names(names) if repo is not None else {}
    knowledge = local_knowledge(repo, names)
    hydrated: list[dict] = []
    for item in deck:
        name = str(item.get("card_name") or "Card")
        out = dict(item)
        row = cached.get(name.lower())
        fallback = fallback_card_payload(name) or {}
        profile = ScryfallSyncService.canonical_local_profile(knowledge.get(name.casefold()), name)
        sources = []
        if fallback:
            sources.append('offline_seed')
        if profile:
            raw = profile['card_data']
            local = ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))
            local['card_faces'] = cached_json(local['card_faces_json'], list)
            local['colors'] = local['colors'].split(',') if local['colors'] else []
            fallback = local
            sources.append('local_knowledge')
        out.update({key: value for key, value in fallback.items() if value is not None})
        if row is not None:
            sources.append('cache')
            out["layout"] = getattr(row, "layout", "") or fallback.get("layout", "")
            cached_colors = str(getattr(row, "colors", "") or "")
            if cached_colors:
                out["colors"] = [
                    color.strip().upper()
                    for color in cached_colors.split(",")
                    if color.strip().upper() in {"W", "U", "B", "R", "G"}
                ]
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
            faces = cached_json(getattr(row, 'card_faces_json', ''), list)
            if faces and all(isinstance(face, dict) for face in faces):
                if fallback.get('card_faces') and (not getattr(row, 'layout', '') or needs_split_color_sync(row)):
                    art = {face.get('name'): face.get('image_uri') for face in faces}
                    out['card_faces'] = [{**face, 'image_uri': art.get(face.get('name')) or face.get('image_uri')}
                                         for face in fallback['card_faces']]
                else:
                    out["card_faces"] = faces
            has_face_art = any(face.get('image_uri') for face in out.get('card_faces') or [])
            out['image_uri'] = select_display_image_uri({
                'image_uri': getattr(row, 'image_uri', None) or (None if has_face_art else fallback.get('image_uri')),
                'card_faces': out.get('card_faces') or [],
            }, name=name, type_line=str(out.get('type_line') or ''))
        if out.get('layout') == 'split' and out.get('card_faces'):
            colors = {color for face in out['card_faces'] for color in (face.get('colors') or [])}
            if colors:
                out['colors'] = sorted(colors)
        if out.get('layout') in {'modal_dfc', 'transform', 'adventure', 'reversible_card'} and out.get('card_faces'):
            for key in ('oracle_text', 'mana_cost', 'type_line', 'power', 'toughness', 'loyalty'):
                current = out.get(key)
                if key in out['card_faces'][0] and (current is None or current == '' or isinstance(current, str) and ' // ' in current):
                    out[key] = out['card_faces'][0][key]
        if not out.get("image_uri"):
            out["image_uri"] = select_display_image_uri(out, name=name, type_line=str(out.get("type_line") or ""))
        out['card_data_sources'] = sources
        hydrated.append(out)
    return hydrated
