from __future__ import annotations

import httpx

from card_data.sync import ScryfallSyncService
from card_data.service import CardService


class _DummyRepo:
    def __init__(self, cached=None) -> None:
        self.cached = cached
        self.upsert_called = False

    def get_cached_card_by_name(self, name: str):
        del name
        return self.cached

    def upsert_card(self, payload):  # noqa: ANN001
        self.upsert_called = True
        return payload


class _CachedCard:
    def __init__(self) -> None:
        self.id = "cached-1"
        self.scryfall_id = "scryfall-1"
        self.name = "Cached Card"
        self.oracle_text = "Cached text"
        self.mana_cost = "{1}{U}"
        self.type_line = "Instant"
        self.colors = "U"
        self.power = None
        self.toughness = None
        self.image_uri = "/card-images/cached.png"
        self.legalities_json = "{}"
        self.card_faces_json = "[]"


class _BlankCachedCard:
    def __init__(self) -> None:
        self.id = "cached-2"
        self.scryfall_id = "scryfall-2"
        self.name = "Clarion Spirit"
        self.oracle_text = ""
        self.mana_cost = ""
        self.type_line = ""
        self.colors = ""
        self.power = None
        self.toughness = None
        self.image_uri = "/card-images/cached-blank.png"
        self.legalities_json = "{}"
        self.card_faces_json = "[]"
        self.rulings_json = "[]"


class _CompleteCachedCard(_BlankCachedCard):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Complete Card"
        self.oracle_text = "Draw a card."
        self.mana_cost = "{1}{U}"
        self.type_line = "Instant"
        self.image_uri = "/card-images/card-1.jpg"
        self.legalities_json = '{"modern":"legal"}'
        self.rulings_json = '[{"comment":"Test ruling"}]'


def test_extract_remote_image_uri_prefers_root_normal() -> None:
    service = ScryfallSyncService(_DummyRepo())
    raw = {"image_uris": {"normal": "https://img.example/root-normal.jpg", "png": "https://img.example/root.png"}}
    assert service._extract_remote_image_uri(raw) == "https://img.example/root-normal.jpg"


def test_extract_remote_image_uri_falls_back_to_face_images() -> None:
    service = ScryfallSyncService(_DummyRepo())
    raw = {
        "card_faces": [
            {"image_uris": {}},
            {"image_uris": {"png": "https://img.example/face2.png"}},
        ]
    }
    assert service._extract_remote_image_uri(raw) == "https://img.example/face2.png"


def test_sync_card_by_name_falls_back_to_cached_card_on_http_error(monkeypatch) -> None:
    repo = _DummyRepo(cached=_CachedCard())
    service = ScryfallSyncService(repo)

    def _boom(*args, **kwargs):  # noqa: ANN001
        request = httpx.Request("GET", "https://api.scryfall.com/cards/named")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr("card_data.sync.get_with_backoff", _boom)
    out = service.sync_card_by_name("Cached Card")

    assert out["name"] == "Cached Card"
    assert repo.upsert_called is False


def test_sync_card_by_name_merges_fallback_text_for_blank_cached_card(monkeypatch) -> None:
    repo = _DummyRepo(cached=_BlankCachedCard())
    service = ScryfallSyncService(repo)

    def _offline(*args, **kwargs):
        raise httpx.ConnectError("Declared offline transport", request=httpx.Request("GET", "https://api.scryfall.com/cards/named"))

    monkeypatch.setattr("card_data.sync.get_with_backoff", _offline)
    out = service.sync_card_by_name("Clarion Spirit")

    assert "second spell each turn" in out["oracle_text"]
    assert out["mana_cost"] == "{1}{W}"
    assert "Creature" in out["type_line"]


def test_completeness_report_identifies_cached_and_missing_card_data() -> None:
    complete = _CompleteCachedCard()
    fallback = _BlankCachedCard()

    class _ReportRepo:
        def get_cached_cards_by_names(self, names):  # noqa: ANN001
            del names
            return {"complete card": complete, "clarion spirit": fallback}

    report = CardService(_ReportRepo()).completeness_report(["Complete Card", "Clarion Spirit", "Unknown Card"])

    assert report["requested"] == 3
    assert report["missing"]["cached"] == 1
    assert report["missing"]["rulings"] == 2
    assert next(card for card in report["cards"] if card["name"] == "Clarion Spirit")["oracle_source"] == "fallback"
    assert next(card for card in report["cards"] if card["name"] == "Unknown Card")["oracle_source"] == "missing"


def test_completeness_report_warns_for_unsupported_bands_with_other() -> None:
    variant = _CompleteCachedCard()
    variant.name = "Old Fogey"
    variant.type_line = "Summon — Dinosaur"
    variant.oracle_text = "Phasing, fading 3, bands with other Dinosaurs, flanking"
    ordinary = _CompleteCachedCard()
    ordinary.name = "Benalish Hero"
    ordinary.type_line = "Creature — Human Soldier"
    ordinary.oracle_text = "Banding"

    class _ReportRepo:
        def get_cached_cards_by_names(self, names):  # noqa: ANN001
            del names
            return {"old fogey": variant, "benalish hero": ordinary}

    report = CardService(_ReportRepo()).completeness_report(["Old Fogey", "Benalish Hero"])
    assert report["complete"] == 2
    assert report["unsupported_count"] == 1
    assert report["cards"][0]["unsupported_mechanics"] == ["phasing", "bands with other"]
    assert report["cards"][1]["unsupported_mechanics"] == []
    assert report["cards"][0]["rules_coverage"] == "known_unsupported"
    assert report["cards"][1]["rules_coverage"] == "not_certified"


def test_cached_vanilla_creature_has_valid_empty_oracle_text() -> None:
    bear = _CompleteCachedCard()
    bear.name = "Grizzly Bears"
    bear.oracle_text = ""
    bear.type_line = "Creature — Bear"

    class _ReportRepo:
        def get_cached_cards_by_names(self, names):  # noqa: ANN001
            return {"grizzly bears": bear}

    report = CardService(_ReportRepo()).completeness_report(["Grizzly Bears"])
    assert report["complete"] == 1
    assert report["cards"][0]["oracle_source"] == "cache"
    assert report["cards"][0]["oracle"] is True


def test_completeness_report_warns_for_morph() -> None:
    card = _CompleteCachedCard()
    card.name = "Willbender"
    card.oracle_text = "Morph {1}{U}"

    class _ReportRepo:
        def get_cached_cards_by_names(self, names):  # noqa: ANN001
            del names
            return {"willbender": card}

    report = CardService(_ReportRepo()).completeness_report(["Willbender"])
    assert report["cards"][0]["unsupported_mechanics"] == ["morph"]
    assert report["cards"][0]["rules_coverage"] == "known_unsupported"
