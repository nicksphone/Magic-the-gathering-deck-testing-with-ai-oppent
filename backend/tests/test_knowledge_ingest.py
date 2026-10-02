from __future__ import annotations

import copy
import json

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine

from knowledge.ingest import KnowledgeIngestor
from persistence.repository import Repository
from scripts.sync_all_card_knowledge import import_cards, backfill_tactical_tags, main as bulk_main
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
    assert {"burn", "removal"} <= set(profile["tactical_tags"])
    assert row.play_value is None
    assert repo.get_cached_card_by_name("Lightning Bolt").oracle_text == bolt["oracle_text"]

    profile.pop("tactical_tags")
    row.profiles_json = json.dumps(profile)
    repo.session.add(row)
    repo.session.commit()
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("cached tags fetched over network"))) as client:
        assert KnowledgeIngestor(repo, client).sync_name("Lightning Bolt") == "cached"
    assert "burn" in json.loads(repo.get_card_knowledge("Lightning Bolt").profiles_json)["tactical_tags"]


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
    assert {"burn", "removal"} <= set(json.loads(repo.get_card_knowledge("Lightning Bolt").profiles_json)["tactical_tags"])
    assert first["added"] == 1
    assert second["unchanged"] == 1
    assert second["rulings_pending"] == 1
    assert repo.list_cards() == []
    profile = json.loads(repo.get_card_knowledge("Lightning Bolt").profiles_json)
    assert profile["rulings_verified"] is False
    assert profile["card_data"]["legalities"] == {"modern": "legal"}


def test_offline_tag_backfill_preserves_canonical_and_verified_data(repo, bolt):
    import_cards(repo, [bolt], {"source": "scryfall", "updated_at": "2026-09-27"})
    row = repo.get_card_knowledge("Lightning Bolt")
    profile = json.loads(row.profiles_json)
    profile.pop("tactical_tags")
    profile["rulings_verified"] = True
    profile["rulings"] = []
    row.profiles_json = json.dumps(profile)
    row.play_value = 8.5
    repo.session.add(row)
    repo.upsert_card_knowledge({"name": "Swamp", "oracle_source": "manual"})
    repo.session.commit()

    assert backfill_tactical_tags(repo) == {"scanned": 2, "updated": 1, "unchanged": 0, "missing_canonical": 1}
    assert backfill_tactical_tags(repo) == {"scanned": 2, "updated": 0, "unchanged": 1, "missing_canonical": 1}
    after = repo.get_card_knowledge("Lightning Bolt")
    refreshed = json.loads(after.profiles_json)
    assert {"burn", "removal"} <= set(refreshed["tactical_tags"])
    assert refreshed["rulings_verified"] is True
    assert refreshed["rulings"] == []
    assert refreshed["card_data"] == bolt
    assert after.play_value == 8.5


def test_offline_tag_backfill_cli_does_not_download(monkeypatch, tmp_path, bolt):
    import sys
    from scripts import sync_all_card_knowledge as bulk

    db_path = tmp_path / "knowledge.sqlite3"
    out_path = tmp_path / "report.json"
    local_engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(local_engine)
    with Session(local_engine) as session:
        local_repo = Repository(session)
        import_cards(local_repo, [bolt], {"source": "scryfall", "updated_at": "2026-09-27"})
        row = local_repo.get_card_knowledge("Lightning Bolt")
        profile = json.loads(row.profiles_json)
        profile.pop("tactical_tags")
        row.profiles_json = json.dumps(profile)
        session.add(row)
        session.commit()

    monkeypatch.setattr(bulk, "download_bulk", lambda *args: pytest.fail("offline backfill downloaded data"))
    monkeypatch.setattr(sys, "argv", ["sync_all_card_knowledge", "--database", str(db_path), "--backfill-tags", "--out", str(out_path)])
    assert bulk_main() == 0
    assert json.loads(out_path.read_text())["updated"] == 1

    missing = tmp_path / "missing.sqlite3"
    monkeypatch.setattr(sys, "argv", ["sync_all_card_knowledge", "--database", str(missing), "--backfill-tags"])
    with pytest.raises(SystemExit):
        bulk_main()
    assert not missing.exists()


def test_bulk_cards_supply_offline_import_and_match_metadata(repo, bolt, monkeypatch):
    from decks.service import DeckService
    from main import _hydrate_deck_cards

    island = {
        **bolt, "id": "printing-island", "oracle_id": "oracle-island", "name": "Island",
        "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.",
        "mana_cost": "", "colors": [], "color_identity": ["U"],
    }
    import_cards(repo, [bolt, island], {"source": "scryfall", "updated_at": "2026-09-27"})
    def no_network(*args, **kwargs):
        pytest.fail("Offline bulk-backed import attempted a Scryfall request")
    monkeypatch.setattr("card_data.sync.get_with_backoff", no_network)

    imported = DeckService(repo).import_deck_text("Offline Burn", "4 Lightning Bolt\n56 Island")
    assert imported["deck_id"] is not None
    assert imported["resolved_mainboard_cards"][0]["card_metadata"]["oracle_text"] == bolt["oracle_text"]
    assert imported["mana_curve"]["1"] == 4
    assert imported["mana_curve"]["lands"] == 56
    hydrated = _hydrate_deck_cards(repo, imported["mainboard"])
    assert hydrated[0]["oracle_text"] == bolt["oracle_text"]
    assert repo.get_cached_card_by_name("Lightning Bolt").scryfall_id == bolt["id"]
    assert repo.get_cached_card_by_name("Island").scryfall_id == island["id"]
    assert json.loads(repo.get_cached_card_by_name("Lightning Bolt").rulings_json) == []


def test_bulk_only_cards_are_visible_to_completeness_and_suggestions(repo, bolt):
    from card_data.service import CardService

    island = {
        **bolt, "id": "printing-island", "oracle_id": "oracle-island", "name": "Island",
        "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.", "mana_cost": "",
    }
    bears = {
        **bolt, "id": "printing-bears", "oracle_id": "oracle-bears", "name": "Grizzly Bears",
        "type_line": "Creature — Bear", "oracle_text": "", "mana_cost": "{1}{G}", "power": "2", "toughness": "2",
    }
    import_cards(repo, [bolt, island, bears], {"source": "scryfall"})
    assert repo.list_cards() == []
    service = CardService(repo)
    report = service.completeness_report(["Lightning Bolt", "Island", "Grizzly Bears"])

    assert report["complete"] == 3
    assert report["missing"]["cached"] == 3
    assert report["missing"]["oracle"] == 0
    assert report["missing"]["mana_cost"] == 0
    assert report["missing"]["rulings"] == 3
    assert {card["oracle_source"] for card in report["cards"]} == {"knowledge"}
    assert service.suggest_name("Lightning Bol")["suggestion"] == "Lightning Bolt"
    assert repo.list_cards() == []


def test_verified_empty_rulings_are_not_reported_missing(repo, bolt):
    from card_data.service import CardService

    import_cards(repo, [bolt], {"source": "scryfall"})
    row = repo.get_card_knowledge("Lightning Bolt")
    profile = json.loads(row.profiles_json)
    profile.update({"rulings_verified": True, "rulings": []})
    row.profiles_json = json.dumps(profile)
    repo.session.add(row)
    repo.session.commit()

    report = CardService(repo).completeness_report(["Lightning Bolt"])
    assert report["missing"]["rulings"] == 0


def test_live_hydration_reads_bulk_faces_without_prior_deck_import_or_cache_write(repo, bolt, monkeypatch):
    from main import _hydrate_deck_cards

    delver = {
        **bolt, "id": "printing-delver", "oracle_id": "oracle-delver",
        "name": "Delver of Secrets // Insectile Aberration", "type_line": "Creature — Human Wizard // Creature — Human Insect",
        "layout": "transform", "mana_cost": "{U}",
        "card_faces": [
            {"name": "Delver of Secrets", "mana_cost": "{U}", "type_line": "Creature — Human Wizard", "power": "1", "toughness": "1", "colors": ["U"]},
            {"name": "Insectile Aberration", "type_line": "Creature — Human Insect", "power": "3", "toughness": "2", "oracle_text": "Flying"},
        ],
    }
    import_cards(repo, [delver], {"source": "scryfall"})
    monkeypatch.setattr("card_data.sync.get_with_backoff", lambda *args, **kwargs: pytest.fail("Network request"))
    cards = _hydrate_deck_cards(repo, [{"card_name": delver["name"], "quantity": 4}])
    assert [face["name"] for face in cards[0]["card_faces"]] == ["Delver of Secrets", "Insectile Aberration"]
    assert cards[0]["power"] == "1"
    assert cards[0]["colors"] == ["U"]
    assert cards[0]['card_faces'][1]['power'] == '3'
    assert repo.get_cached_card_by_name(delver['name']) is None


def test_unverified_manual_knowledge_is_not_materialized(repo, bolt):
    repo.upsert_card_knowledge({"name": "Lightning Bolt", "oracle_source": "manual", "profiles": {"card_data": bolt}})
    from card_data.sync import ScryfallSyncService

    assert ScryfallSyncService(repo).sync_card_from_local_knowledge("Lightning Bolt") is False
    assert repo.get_cached_card_by_name("Lightning Bolt") is None


def test_http_match_start_uses_bulk_only_cards_offline(tmp_path, bolt, monkeypatch):
    from fastapi.testclient import TestClient
    import main

    engine = create_engine(f"sqlite:///{tmp_path / 'cards.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    repo = Repository(session)
    island = {
        **bolt, "id": "printing-island", "oracle_id": "oracle-island", "name": "Island",
        "type_line": "Basic Land — Island", "oracle_text": "{T}: Add {U}.",
        "mana_cost": "", "colors": [], "color_identity": ["U"],
    }
    import_cards(repo, [bolt, island], {"source": "scryfall"})
    monkeypatch.setattr("card_data.sync.get_with_backoff", lambda *args, **kwargs: pytest.fail("Network request"))
    main.app.dependency_overrides[main.get_repo] = lambda: repo
    match_id = None
    try:
        with TestClient(main.app) as client:
            completeness = client.get("/cards/completeness", params=[("names", "Lightning Bolt"), ("names", "Island")])
            suggestion = client.get("/cards/suggest", params={"name": "Lightning Bol"})
            response = client.post("/matches/start", json={
                "deck_a": [{"quantity": 4, "card_name": "Lightning Bolt"}, {"quantity": 56, "card_name": "Island"}],
                "deck_b": [{"quantity": 60, "card_name": "Island"}],
                "controller_a": "human", "controller_b": "human", "mode": "human_vs_human", "seed": 51,
            })
        assert completeness.status_code == 200
        assert [card["name"] for card in completeness.json()["cards"]] == ["Lightning Bolt", "Island"]
        assert {card["oracle_source"] for card in completeness.json()["cards"]} == {"knowledge"}
        assert suggestion.status_code == 200
        assert suggestion.json()["suggestion"] == "Lightning Bolt"
        assert response.status_code == 200, response.text
        match_id = response.json()["id"]
        state = main.ACTIVE_MATCHES[match_id].state
        assert any(card.name == "Lightning Bolt" and card.oracle_text == bolt["oracle_text"] for card in state.cards.values())
        assert repo.get_cached_card_by_name('Lightning Bolt') is None
    finally:
        main.app.dependency_overrides.pop(main.get_repo, None)
        if match_id:
            main.ACTIVE_MATCHES.pop(match_id, None)
        session.close()


def test_bulk_preserves_distinct_oracle_variants_with_same_printed_name(repo, bolt):
    variant = copy.deepcopy(bolt)
    variant["id"] = "other-printing"
    variant["oracle_id"] = "other-oracle"
    first = import_cards(repo, [bolt, variant], {"source": "scryfall"})
    second = import_cards(repo, [bolt, variant], {"source": "scryfall"})
    assert first["name_collisions"] == 1
    assert second["unchanged"] == 2
    assert len(repo.list_card_knowledge()) == 2
    assert repo.list_card_knowledge_names() == ["Lightning Bolt"]
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
