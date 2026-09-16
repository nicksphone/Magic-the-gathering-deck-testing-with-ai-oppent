from __future__ import annotations

import json

import pytest
from sqlmodel import Session, create_engine
from sqlmodel.sql.sqltypes import AutoString

from knowledge.models import CardKnowledge
from persistence.repository import Repository


@pytest.fixture(name="repo")
def repo_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    CardKnowledge.metadata.create_all(engine)
    with Session(engine) as session:
        yield Repository(session)


def _payload(**overrides):
    payload = {
        "name": "Lightning Bolt",
        "scryfall_id": "5f8293c0-e945-41a1-bf1c-3507b1205856",
        "oracle_source": "scryfall",
        "play_value": 8.5,
        "threat_level": 2,
        "answerable_by": ["counter"],
        "cast_windows": ["instant_window"],
        "etb_impact": 0.0,
        "profiles": {},
    }
    payload.update(overrides)
    return payload


def test_card_knowledge_round_trips_with_profiled_fields(repo) -> None:
    row = repo.upsert_card_knowledge(_payload())
    fetched = repo.get_card_knowledge("lightning bolt")
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.name == "Lightning Bolt"
    assert fetched.scryfall_id == "5f8293c0-e945-41a1-bf1c-3507b1205856"
    assert fetched.oracle_source == "scryfall"
    assert fetched.play_value == 8.5
    assert fetched.threat_level == 2
    assert json.loads(fetched.answerable_by_json) == ["counter"]
    assert json.loads(fetched.cast_windows_json) == ["instant_window"]
    assert fetched.etb_impact == 0.0
    assert json.loads(fetched.profiles_json) == {}


def test_upsert_updates_existing_row_by_normalized_name(repo) -> None:
    repo.upsert_card_knowledge(_payload())
    updated = repo.upsert_card_knowledge(
        _payload(play_value=4.0, threat_level=1, oracle_source="manual")
    )
    rows = repo.list_card_knowledge(names=["lightning bolt"])
    assert len(rows) == 1
    assert rows[0].id == updated.id
    assert rows[0].play_value == 4.0
    assert rows[0].threat_level == 1
    assert rows[0].oracle_source == "manual"


def test_profile_fields_default_to_none_until_profiled(repo) -> None:
    row = repo.upsert_card_knowledge(
        _payload(play_value=None, threat_level=None, answerable_by=[], cast_windows=[], etb_impact=None, profiles=None)
    )
    fetched = repo.get_card_knowledge(row.name)
    assert fetched is not None
    assert fetched.play_value is None
    assert fetched.threat_level is None
    assert json.loads(fetched.answerable_by_json) == []
    assert json.loads(fetched.cast_windows_json) == []
    assert fetched.etb_impact is None
    assert json.loads(fetched.profiles_json) == {}


def test_list_card_knowledge_filters_by_names(repo) -> None:
    repo.upsert_card_knowledge(_payload())
    repo.upsert_card_knowledge(_payload(name="Island", scryfall_id="island-1", oracle_source="scryfall"))
    repo.upsert_card_knowledge(_payload(name="Swamp", scryfall_id="swamp-1", oracle_source="scryfall"))
    rows = repo.list_card_knowledge(names=["island"])
    assert [row.name for row in rows] == ["Island"]
    assert repo.list_card_knowledge() is not None


def test_get_card_knowledge_miss_returns_none(repo) -> None:
    assert repo.get_card_knowledge("Card That Does Not Exist") is None
    assert repo.get_card_knowledge("") is None
