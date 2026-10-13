from __future__ import annotations

try:
    from . import _bootstrap
except ImportError:
    import _bootstrap

import argparse
import json
from collections import Counter
from pathlib import Path
import stat
from urllib.parse import urlsplit

from sqlmodel import Session

from persistence.db import engine, init_db
from persistence.repository import Repository
from scripts.oracle_corpus_report import collect_corpus


def _oracle_blank(raw: dict, requested_name: str) -> bool | None:
    faces = raw.get('card_faces', [])
    if faces:
        selected = faces if requested_name.casefold() == str(raw.get('name', '')).casefold() else [
            face for face in faces if isinstance(face.get('name'), str)
            and face['name'].casefold() == requested_name.casefold()]
        if not selected:
            return None
        texts = [face.get('oracle_text') for face in selected]
    elif raw.get('layout') in {'transform', 'modal_dfc', 'split', 'flip', 'meld', 'double_faced_token'}:
        return None
    else:
        texts = [raw.get('oracle_text')]
    if any(isinstance(text, str) and text.strip() for text in texts):
        return False
    return True if all(isinstance(text, str) for text in texts) else None


def _image_status(image_uri: object, *, cache_dir: Path | None) -> tuple[bool | None, str]:
    from card_data.placeholders import CACHE_ROUTE_PREFIX, local_image_available

    if cache_dir is None:
        return None, 'unavailable'
    if image_uri is None or image_uri == '':
        return False, 'missing'
    if not isinstance(image_uri, str):
        return None, 'unavailable'
    try:
        parsed = urlsplit(image_uri)
        if parsed.scheme in {'http', 'https'} and parsed.netloc:
            return False, 'remote'
        prefix = CACHE_ROUTE_PREFIX + '/'
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
                or '%' in image_uri or not image_uri.startswith(prefix)):
            return None, 'unavailable'
        filename = image_uri[len(prefix):]
        if not filename or filename in {'.', '..'} or Path(filename).name != filename or '\\' in filename:
            return None, 'unavailable'
        root = Path(cache_dir)
        if not root.is_absolute() or root != root.resolve() or root.is_symlink():
            return None, 'unavailable'
        target = root / filename
        try:
            mode = target.lstat().st_mode
        except FileNotFoundError:
            return False, 'missing'
        if not stat.S_ISREG(mode):
            return None, 'unavailable'
        if not local_image_available(image_uri, cache_dir=root):
            return False, 'missing'
        placeholder = filename.startswith('placeholder-') or filename == 'generic-token-creature.svg'
        return True, 'placeholder' if placeholder else 'local'
    except (OSError, ValueError, TypeError):
        return None, 'unavailable'


def knowledge_report(repo: Repository, names: list[str], *, image_cache_dir: Path | None = None) -> dict:
    rows = repo.list_card_knowledge()
    lookup = {}
    totals = Counter()
    for row in rows:
        profile = json.loads(row.profiles_json)
        if not isinstance(profile, dict):
            raise ValueError('Knowledge profile must be an object')
        raw = profile.get("card_data", {})
        if (not isinstance(raw, dict) or not isinstance(raw.get('card_faces', []), list)
                or any(not isinstance(face, dict) for face in raw.get('card_faces', []))
                or not isinstance(profile.get('rulings', []), list)):
            raise ValueError('Invalid knowledge coverage container')
        totals["rows"] += 1
        totals["canonical_payloads"] += int(row.oracle_source == "scryfall" and bool(raw.get("oracle_id")))
        totals["rulings_verified"] += int(profile.get("rulings_verified") is True)
        aliases = [row.name, raw.get("name", "")]
        aliases.extend(face.get("name", "") for face in raw.get("card_faces", []))
        for alias in aliases:
            if isinstance(alias, str) and alias:
                key = alias.casefold()
                previous = lookup.get(key)
                rank = (profile.get("rulings_verified") is True, row.name.casefold() == key)
                previous_rank = (previous[1].get("rulings_verified") is True, previous[0].name.casefold() == key) if previous else (-1, -1)
                if rank > previous_rank:
                    lookup[key] = (row, profile)
    cards = []
    totals['cached_rows'] = len(repo.list_cards())
    cached = repo.get_cached_cards_by_names(names)
    for name in sorted(set(names), key=str.casefold):
        match = lookup.get(name.casefold())
        row, profile = match if match else (None, {})
        raw = profile.get("card_data", {})
        cache = cached.get(name.strip().lower())
        image_uri = cache.image_uri if cache else None
        local_image, image_status = _image_status(image_uri, cache_dir=image_cache_dir)
        if cache and (name.strip().casefold() != cache.name.strip().casefold()
                      or cache.card_faces_json not in (None, '', '[]')):
            try:
                cache_faces = json.loads(cache.card_faces_json)
                if not isinstance(cache_faces, list) or any(not isinstance(face, dict) for face in cache_faces):
                    raise ValueError('Invalid cached face container')
                faces = [face for face in cache_faces if isinstance(face.get('name'), str)
                         and face['name'].casefold() == name.strip().casefold()]
                if len(faces) == 1:
                    local_image, image_status = _image_status(faces[0].get('image_uri'), cache_dir=image_cache_dir)
                elif faces or name.strip().casefold() != cache.name.strip().casefold():
                    local_image, image_status = None, 'unavailable'
            except (ValueError, TypeError):
                local_image, image_status = None, 'unavailable'
        cards.append({
            "name": name,
            "canonical": bool(row and row.oracle_source == "scryfall" and raw.get("oracle_id")),
            "rulings_verified": profile.get("rulings_verified") is True,
            "rulings_count": len(profile.get("rulings", [])),
            "face_count": len(raw.get("card_faces", [])),
            'knowledge_present': row is not None,
            'oracle_source': row.oracle_source if row else None,
            'cached': cache is not None,
            'cache_oracle_text_blank': (not cache.oracle_text.strip()
                if cache and isinstance(cache.oracle_text, str) else None),
            'oracle_text_blank': _oracle_blank(raw, name),
            'local_image': local_image,
            'image_status': image_status,
        })
    coverage = {
        'knowledge_present': sum(card['knowledge_present'] for card in cards),
        'cached': sum(card['cached'] for card in cards),
        'oracle_text_blank': sum(card['oracle_text_blank'] is True for card in cards),
        'oracle_text_unavailable': sum(card['oracle_text_blank'] is None for card in cards),
        'local_image': sum(card['local_image'] is True for card in cards),
        'placeholder_image': sum(card['image_status'] == 'placeholder' for card in cards),
        'local_image_unavailable': sum(card['local_image'] is None for card in cards),
    }
    return {"database": dict(totals), "requested_cards": len(cards), "missing_cards": [card["name"] for card in cards if not card["canonical"]], "rulings_pending": [card["name"] for card in cards if not card["rulings_verified"]], "cards": cards, "rules_support_certified": False, 'coverage': coverage}


def main() -> int:
    parser = argparse.ArgumentParser(description="Report canonical knowledge coverage, separately from rules support")
    parser.add_argument("--require-rulings", action="store_true")
    parser.add_argument("--out", type=Path)
    from card_data.placeholders import CACHE_DIR
    parser.add_argument('--image-cache-dir', type=Path, default=CACHE_DIR,
                        help='Read-only local image cache to inspect; never downloads or repairs media')
    args = parser.parse_args()
    init_db()
    with Session(engine) as session:
        repo = Repository(session)
        names = [item["name"] for item in collect_corpus().values()]
        for deck in repo.list_decks():
            for board in (deck.mainboard_json, deck.sideboard_json):
                names.extend(item["card_name"] for item in json.loads(board) if item.get("card_name"))
        report = knowledge_report(repo, names, image_cache_dir=args.image_cache_dir)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return int(bool(report["missing_cards"]) or (args.require_rulings and bool(report["rulings_pending"])))


if __name__ == "__main__":
    raise SystemExit(main())
