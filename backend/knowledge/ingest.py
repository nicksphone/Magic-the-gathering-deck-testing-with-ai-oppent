from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from card_data.http_utils import get_with_backoff
from card_data.sync import ScryfallSyncService
from card_data.tactical import canonical_tactical_tags
from persistence.repository import Repository

SCHEMA_VERSION = 1
API = "https://api.scryfall.com"


class KnowledgeIngestor:
    """Persist canonical facts; ingestion does not certify gameplay support."""

    def __init__(self, repository: Repository, client: httpx.Client, interval: float = 0.12):
        self.repository = repository
        self.client = client
        self.interval = max(0.1, interval)
        self._last_request = 0.0
        self.normalizer = ScryfallSyncService(repository)

    def _get(self, url: str, params: dict | None = None) -> dict:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "api.scryfall.com":
            raise ValueError("Knowledge requests must use the Scryfall API.")
        time.sleep(max(0.0, self.interval - (time.monotonic() - self._last_request)))
        try:
            response = get_with_backoff(self.client, url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Expected a Scryfall object.")
            return result
        finally:
            self._last_request = time.monotonic()

    def cached(self, name: str):
        row = self.repository.get_card_knowledge(name)
        if row is None:
            cached_card = self.repository.get_cached_card_by_name(name)
            row = self.repository.get_card_knowledge(cached_card.name) if cached_card else None
        if row is None or row.oracle_source != "scryfall":
            return None
        profile = json.loads(row.profiles_json)
        if profile.get("schema_version") != SCHEMA_VERSION or not profile.get("rulings_verified"):
            return None
        if "tactical_tags" not in profile and isinstance(profile.get("card_data"), dict):
            profile.update(canonical_tactical_tags(profile["card_data"]))
            row.profiles_json = json.dumps(profile, sort_keys=True)
            self.repository.session.add(row)
            self.repository.session.commit()
        return row

    def sync_name(self, name: str, force: bool = False) -> str:
        existing = self.cached(name)
        if existing is not None and not force:
            return "cached"
        raw = self._get(f"{API}/cards/named", {"exact": name})
        self.sync_payload(raw)
        return "synced"

    def sync_payload(self, raw: dict) -> None:
        if raw.get("object") != "card" or not all(raw.get(key) for key in ("id", "oracle_id", "name", "type_line")):
            raise ValueError("Incomplete canonical card payload.")
        rulings_uri = raw.get("rulings_uri")
        if not rulings_uri:
            raise ValueError("Canonical card has no rulings endpoint.")
        rulings_payload = self._get(rulings_uri)
        if rulings_payload.get("object") != "list" or not isinstance(rulings_payload.get("data"), list):
            raise ValueError("Invalid rulings response.")
        rulings = list(rulings_payload["data"])
        while rulings_payload.get("has_more"):
            rulings_payload = self._get(rulings_payload["next_page"])
            rulings.extend(rulings_payload["data"])

        previous = self.repository.get_card_knowledge(raw["name"])
        profile = json.loads(previous.profiles_json) if previous else {}
        profile.update({
            "schema_version": SCHEMA_VERSION,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "oracle_id": raw["oracle_id"],
            "rulings_verified": True,
            "rulings": rulings,
            "card_data": raw,
            "facts": {
                "mana_value": raw.get("cmc"),
                "color_identity": raw.get("color_identity", []),
                "keywords": raw.get("keywords", []),
                "layout": raw.get("layout"),
                "face_count": len(raw.get("card_faces", [])),
            },
        })
        profile.update(canonical_tactical_tags(raw))
        # Both tables represent one verified fetch; never leave a half-written
        # knowledge/cache pair if validation or the database write fails.
        payload = self.normalizer._normalize_payload(
            raw, self.normalizer._extract_remote_image_uri(raw), rulings,
        )
        from sqlmodel import select
        from knowledge.models import CardKnowledge
        from persistence.models import CardCache

        session = self.repository.session
        try:
            cache = session.exec(select(CardCache).where(CardCache.scryfall_id == raw["id"])).first()
            if cache is None:
                cache = CardCache(**payload)
            else:
                # Preserve downloaded art while refreshing canonical metadata.
                if cache.image_uri and cache.image_uri.startswith("/card-images/"):
                    payload["image_uri"] = cache.image_uri
                for key, value in payload.items():
                    setattr(cache, key, value)
            knowledge = previous or CardKnowledge(name=raw["name"])
            knowledge.scryfall_id = raw["id"]
            knowledge.oracle_source = "scryfall"
            knowledge.profiles_json = json.dumps(profile, sort_keys=True)
            knowledge.updated_at = datetime.now(timezone.utc)
            session.add(cache)
            session.add(knowledge)
            session.commit()
        except Exception:
            session.rollback()
            raise

    def sync_search(self, query: str, limit: int, force: bool = False) -> dict:
        report = {"synced": 0, "cached": 0, "errors": []}
        if limit < 1:
            raise ValueError("Search limit must be positive.")
        page = self._get(f"{API}/cards/search", {"q": query, "unique": "cards", "order": "name"})
        seen = 0
        while True:
            for raw in page["data"]:
                if seen >= limit:
                    return report
                seen += 1
                try:
                    if not force and self.cached(raw["name"]):
                        report["cached"] += 1
                    else:
                        self.sync_payload(raw)
                        report["synced"] += 1
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    report["errors"].append({"name": raw.get("name"), "error": str(exc)})
            if not page.get("has_more") or seen >= limit:
                return report
            page = self._get(page["next_page"])
