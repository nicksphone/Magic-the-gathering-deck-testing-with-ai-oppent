from __future__ import annotations

import json
import hashlib
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


def canonical_hash(value) -> str:
    """Hash JSON facts independently of archive formatting/compression."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def validate_rulings_page(payload: dict, oracle_id: str) -> list[dict]:
    if not isinstance(oracle_id, str) or not oracle_id:
        raise ValueError("Rulings require an Oracle identity.")
    if payload.get("object") != "list" or not isinstance(payload.get("data"), list):
        raise ValueError("Invalid rulings response.")
    for ruling in payload["data"]:
        if (not isinstance(ruling, dict) or ruling.get("object") != "ruling"
                or ruling.get("oracle_id") != oracle_id
                or ruling.get("source") not in {"wotc", "scryfall"}
                or not isinstance(ruling.get("comment"), str)
                or not ruling.get("published_at")):
            raise ValueError("Invalid or mismatched canonical ruling.")
    if type(payload.get("has_more")) is not bool:
        raise ValueError("Rulings pagination status is missing.")
    return payload["data"]


class KnowledgeIngestor:
    """Persist canonical facts; ingestion does not certify gameplay support."""

    def __init__(self, repository: Repository, client: httpx.Client, interval: float = 0.12):
        self.repository = repository
        self.client = client
        if self.client.headers.get("User-Agent", "").startswith("python-httpx/"):
            self.client.headers["User-Agent"] = "MTGDeckTestingLab/0.1 (canonical knowledge ingest)"
        self.client.headers.setdefault("Accept", "application/json")
        self.interval = max(0.1, interval)
        self._last_request = 0.0
        self.normalizer = ScryfallSyncService(repository)

    def _get(self, url: str, params: dict | None = None) -> dict:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "api.scryfall.com":
            raise ValueError("Knowledge requests must use the Scryfall API.")
        # Scryfall's named/search endpoints now require 500ms spacing.
        interval = max(self.interval, 0.5 if parsed.path in {"/cards/named", "/cards/search"} else 0.1)
        time.sleep(max(0.0, interval - (time.monotonic() - self._last_request)))
        try:
            for attempt in range(3):
                response = get_with_backoff(self.client, url, params=params, timeout=30, retries=0)
                if response.status_code != 429 or attempt == 2:
                    break
                try:
                    retry_after = float(response.headers.get("Retry-After", "30"))
                except ValueError:
                    retry_after = 30.0
                # Current official policy blocks API access for 30s after 429.
                time.sleep(max(30.0, retry_after))
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
        rulings = list(validate_rulings_page(rulings_payload, raw["oracle_id"]))
        visited = {rulings_uri}
        while rulings_payload.get("has_more"):
            next_page = rulings_payload.get("next_page")
            if not isinstance(next_page, str) or next_page in visited or len(visited) >= 100:
                raise ValueError("Invalid or unbounded rulings pagination.")
            visited.add(next_page)
            rulings_payload = self._get(next_page)
            rulings.extend(validate_rulings_page(rulings_payload, raw["oracle_id"]))

        previous = self.repository.get_card_knowledge(raw["name"])
        profile = json.loads(previous.profiles_json) if previous else {}
        profile.update({
            "schema_version": SCHEMA_VERSION,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "oracle_id": raw["oracle_id"],
            "rulings_verified": True,
            "rulings": rulings,
            "rulings_provenance": {"source": "scryfall", "uri": rulings_uri,
                                   "fetched_at": datetime.now(timezone.utc).isoformat(),
                                   "sha256": canonical_hash(rulings), "complete": True},
            "card_data": raw,
            "card_data_sha256": canonical_hash(raw),
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
