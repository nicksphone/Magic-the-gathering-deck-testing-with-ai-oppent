from __future__ import annotations

import copy
import json

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine

from knowledge.ingest import KnowledgeIngestor
from persistence.repository import Repository
from scripts.sync_all_card_knowledge import import_cards
from scripts.knowledge_gap_report import knowledge_report
from scripts.card_mechanics_inventory import inventory


@pytest.fixture
def repo():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield Repository(session)


@pytest.fixture
def bolt():
    return {"object": "card", "id": "printing-bolt", "oracle_id": "oracle-bolt", "name": "Lightning Bolt", "type_line": "Instant", "oracle_text": "Lightning Bolt deals 3 damage to any target.", "mana_cost": "{R}", "cmc": 1, "color_identity": ["R"], "keywords": [], "layout": "normal", "rulings_uri": "https://api.scryfall.com/cards/printing-bolt/rulings", "legalities": {"modern": "legal"}}


def test_sync_empty_rulings_is_verified_and_second_run_is_offline(repo, bolt):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=bolt if request.url.path.endswith("named") else {"object": "list", "data": [], "has_more": False})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        ingestor = KnowledgeIngestor(repo, client)
        assert ingestor.sync_name("Lightning Bolt") == "synced"
        assert ingestor.sync_name("Lightning Bolt") == "cached"
    assert len(requests) == 2
    row = repo.get_card_knowledge("Lightning Bolt")
    profile = json.loads(row.profiles_json)
    assert profile["card_data"] == bolt
    assert profile["rulings_verified"] is True
    assert profile["rulings"] == []
    assert row.play_value is None
    assert repo.get_cached_card_by_name("Lightning Bolt").oracle_text == bolt["oracle_text"]


def test_failed_rulings_does_not_claim_verification_or_write_cache(repo, bolt):
    def handle(request):
        return httpx.Response(200, json=bolt) if request.url.path.endswith("named") else httpx.Response(503)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            KnowledgeIngestor(repo, client).sync_name("Lightning Bolt")
    assert repo.list_card_knowledge() == []
    assert repo.list_cards() == []


def test_bulk_import_is_idempotent_and_does_not_claim_rulings_or_playability(repo, bolt):
    provenance = {"source": "scryfall", "updated_at": "2026-09-27"}
    first = import_cards(repo, [bolt], provenance)
    second = import_cards(repo, [bolt], provenance)
    assert first["added"] == 1
    assert second["unchanged"] == 1
    assert second["rulings_pending"] == 1
    assert repo.list_cards() == []
    profile = json.loads(repo.get_card_knowledge("Lightning Bolt").profiles_json)
    assert profile["rulings_verified"] is False
    assert profile["card_data"]["legalities"] == {"modern": "legal"}


def test_bulk_preserves_distinct_oracle_variants_with_same_printed_name(repo, bolt):
    variant = copy.deepcopy(bolt)
    variant["id"] = "other-printing"
    variant["oracle_id"] = "other-oracle"
    first = import_cards(repo, [bolt, variant], {"source": "scryfall"})
    second = import_cards(repo, [bolt, variant], {"source": "scryfall"})
    assert first["name_collisions"] == 1
    assert second["unchanged"] == 2
    assert len(repo.list_card_knowledge()) == 2
    assert {json.loads(row.profiles_json)["oracle_id"] for row in repo.list_card_knowledge()} == {"oracle-bolt", "other-oracle"}


def test_bulk_preserves_faces_and_verified_rulings_for_unchanged_card(repo, bolt):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"object": "list", "data": [], "has_more": False}))) as client:
        KnowledgeIngestor(repo, client).sync_payload(bolt)
    report = import_cards(repo, [bolt], {"source": "scryfall"})
    assert report["rulings_pending"] == 0
    assert json.loads(repo.get_card_knowledge("Lightning Bolt").profiles_json)["rulings_verified"] is True


def test_bulk_changed_card_marks_previous_rulings_unverified(repo, bolt):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"object": "list", "data": [], "has_more": False}))) as client:
        KnowledgeIngestor(repo, client).sync_payload(bolt)
    updated = {**bolt, "id": "new-printing"}
    report = import_cards(repo, [updated], {"source": "scryfall"})
    assert report["rulings_pending"] == 1
    assert json.loads(repo.get_card_knowledge("Lightning Bolt").profiles_json)["rulings_verified"] is False


def test_gap_report_distinguishes_missing_cards_and_pending_rulings(repo, bolt):
    import_cards(repo, [bolt], {"source": "scryfall"})
    report = knowledge_report(repo, ["Lightning Bolt", "Missing card"])
    assert report["missing_cards"] == ["Missing card"]
    assert report["rulings_pending"] == ["Lightning Bolt", "Missing card"]
    assert report["rules_support_certified"] is False


def test_search_follows_pages_and_obeys_limit(repo, bolt):
    second = {**bolt, "id": "second", "oracle_id": "second-oracle", "name": "Island", "type_line": "Basic Land - Island", "oracle_text": ""}
    fetched = []
    def handle(request):
        fetched.append(str(request.url))
        if request.url.path.endswith("search"):
            return httpx.Response(200, json={"object": "list", "data": [bolt], "has_more": True, "next_page": "https://api.scryfall.com/cards/search?page=2"}) if not request.url.params.get("page") else httpx.Response(200, json={"object": "list", "data": [second, second], "has_more": False})
        return httpx.Response(200, json={"object": "list", "data": [], "has_more": False})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        report = KnowledgeIngestor(repo, client).sync_search("f:standard", limit=2)
    assert report == {"synced": 2, "cached": 0, "errors": []}
    assert len(fetched) == 4


def test_knowledge_rejects_non_scryfall_rulings_urls(repo, bolt):
    raw = {**bolt, "rulings_uri": "https://example.com/private"}
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected external request"))) as client:
        with pytest.raises(ValueError, match="Scryfall API"):
            KnowledgeIngestor(repo, client).sync_payload(raw)
    assert repo.list_card_knowledge() == []


def test_bulk_retains_face_metadata_and_report_resolves_front_face(repo, bolt):
    raw = {**bolt, "name": "Delver of Secrets // Insectile Aberration", "layout": "transform", "card_faces": [
        {"name": "Delver of Secrets", "type_line": "Creature - Human Wizard", "power": "1", "toughness": "1"},
        {"name": "Insectile Aberration", "type_line": "Creature - Human Insect", "power": "3", "toughness": "2", "oracle_text": "Flying"},
    ]}
    imported = import_cards(repo, [raw], {"source": "scryfall"})
    assert imported["faces"] == 2
    profile = json.loads(repo.get_card_knowledge(raw["name"]).profiles_json)
    assert profile["card_data"]["card_faces"] == raw["card_faces"]
    report = knowledge_report(repo, ["Delver of Secrets"])
    assert report["missing_cards"] == []
    assert report["cards"][0]["face_count"] == 2


def test_report_prefers_verified_record_over_unverified_same_name_variant(repo, bolt):
    variant = {**bolt, "id": "variant", "oracle_id": "variant-oracle"}
    import_cards(repo, [bolt, variant], {"source": "scryfall"})
    rows = repo.list_card_knowledge()
    profile = json.loads(rows[1].profiles_json)
    profile["rulings_verified"] = True
    rows[1].profiles_json = json.dumps(profile)
    repo.session.add(rows[1])
    repo.session.commit()
    report = knowledge_report(repo, ["Lightning Bolt"])
    assert report["rulings_pending"] == []


def test_inventory_reports_gaps_without_claiming_coverage(repo, bolt):
    raw = {**bolt, "keywords": ["Suspend"]}
    import_cards(repo, [raw], {"source": "scryfall"})
    report = inventory(repo.list_card_knowledge())
    assert report["keywords"] == {"Suspend": 1}
    assert report["gap_candidates"][0]["keyword"] == "Suspend"
    assert report["rules_support_certified"] is False
