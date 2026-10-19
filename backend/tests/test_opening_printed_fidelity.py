"""Complete opening-card facts at the actual helper's native birth boundary."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.copiable_values import values
from tests import test_opening_hand as opening


FIXTURES = Path(__file__).parent / "fixtures"
PROVENANCE_SHA = "722c22921d540592f3ed00af2aa2ee5be7465ee5b51c5c310dc5f78502cd06cf"
# Paths, container hashes, row locations, complete-object hashes, and field counts.
SOURCES = {
    "Gemstone Caverns": (
        "hand_entry_bookkeeping/canonical.jsonl",
        "99a897459c994dedb916a59104c0023cab4e9d96aac274d60fd3f7603c44cfc0",
        1,
        "83578fec264f8bf40afc6fef586e880e2e9744312340da286649237356e749aa", 65,
    ),
    "Leyline of Anticipation": (
        "global_flash_timing_audit/leyline-of-anticipation.json",
        "ef29f3f72a77d201848b0cabbf33824d25e076e8bd5b9f6ba3fc1ac7656c5455",
        None,
        "a97ecfefa77554abb02425ec07a17766529f974795c65e59901db6533d264e83", 62,
    ),
    "Leyline of Sanctity": (
        "browser_inline26/canonical.jsonl",
        "3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd",
        19,
        "fd5bb6b6f9f5c8c0471710b95306aab8be57ba233b6210d8f22754ae822961b5", 64,
    ),
    "Leyline of Transformation": (
        "opening_printed_fidelity/leyline-of-transformation.json",
        "2a436abce7873c5459d92f6bed4a49cef100607418d20abbb008ff8f8ecff487",
        None,
        "4dccede11af8dd7f430e8c1ab94a18ebce29d02fb0b601771260d3fdd5d0fae3", 65,
    ),
    "Leyline of Vitality": (
        "opening_printed_fidelity/leyline-of-vitality.json",
        "374c3658c858ad9ac9425458cdbe4b4019160682c4e81550d8ca957f6cf45921",
        None,
        "c43fe7ca448be9288a210c036493547559d8dd65679cd48332f5a91bdf3e7c52", 63,
    ),
    "Leyline of the Void": (
        "hand_entry_bookkeeping/canonical.jsonl",
        "99a897459c994dedb916a59104c0023cab4e9d96aac274d60fd3f7603c44cfc0",
        4,
        "27e6e1e44435b5daad9bf8c336024793947ee9e74de9b21c71289446afb17bec", 65,
    ),
}


def _raw(name):
    relative, file_sha, line, row_sha, fields = SOURCES[name]
    encoded = (FIXTURES / relative).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == file_sha
    raw = json.loads(encoded.splitlines()[line - 1] if line is not None else encoded)
    assert raw["object"] == "card" and raw["name"] == name and len(raw) == fields
    digest = hashlib.sha256(json.dumps(
        raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert digest == row_sha
    if relative.startswith("opening_printed_fidelity/"):
        encoded = (FIXTURES / "opening_printed_fidelity/PROVENANCE.json").read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == PROVENANCE_SHA
        proof = json.loads(encoded)[name]
        assert proof["body_sha256"] == file_sha and proof["http_status"] == 200
        assert proof["curl_exit"] == 0 and proof["fields"] == fields
        assert (raw["id"], raw["oracle_id"]) == (proof["id"], proof["oracle_id"])
    return raw


def _facts(raw):
    # These six normal noncreature prints have no innate keywords.
    assert raw["layout"] == "normal" and raw["keywords"] == []
    assert all(raw.get(key) is None for key in ("power", "toughness", "loyalty"))
    return {
        "name": raw["name"], "mana_cost": raw["mana_cost"],
        "type_line": raw["type_line"], "oracle_text": raw["oracle_text"],
        "types": [kind for kind in ("Enchantment", "Land")
                  if kind in raw["type_line"].split()],
        "power": None, "toughness": None, "loyalty": None,
        "printed_power": raw.get("power"), "printed_toughness": raw.get("toughness"),
        "keywords": deepcopy(raw["keywords"]), "colors": deepcopy(raw["colors"]),
        "layout": raw["layout"], "card_faces": deepcopy(raw.get("card_faces", [])),
        "selected_face_index": None,
    }


def _assert_printed(card, facts):
    assert {key: getattr(card, key) for key in facts} == facts
    record = card.characteristic_record
    assert type(record) is dict and type(record["version"]) is int and record["version"] == 1
    assert set(record) == {"version", "physical", "values"}
    assert type(record["physical"]) is dict and set(record["physical"]) == set(facts) | {"image_uri"}
    assert {key: record["physical"][key] for key in facts} == facts
    copiable = {key: value for key, value in facts.items()
                if key not in {"layout", "card_faces", "selected_face_index"}}
    assert record["values"] == copiable and values(card) == copiable
    # Art is display metadata, not a new printing/artwork requirement.
    assert record["physical"]["image_uri"] == card.image_uri


@pytest.mark.parametrize("name", tuple(SOURCES))
@pytest.mark.parametrize("seat", (1, 2))
def test_actual_add_opening_retains_full_print_before_native_capture(monkeypatch, name, seat):
    raw = _raw(name)
    facts = _facts(raw)
    state = opening.opening_game(starter=seat)
    rows_before = deepcopy(opening.CARDS)
    before = deepcopy(serialize_match_snapshot(state))
    expected_id = f"opening-{seat}-{len(state.cards)}"
    births = []
    original = CardInstance.__post_init__

    def observed(card):
        if card.id == expected_id:
            births.append({key: deepcopy(getattr(card, key)) for key in facts})
        return original(card)

    monkeypatch.setattr(CardInstance, "__post_init__", observed)
    card_id = opening.add_opening(state, name, seat)

    assert births == [facts], "OPENING_PRINTED_FACTS_LOST_BEFORE_NATIVE_CAPTURE"
    assert card_id == expected_id and set(state.cards) == set(before["cards"]) | {card_id}
    card = state.cards[card_id]
    _assert_printed(card, facts)
    assert (card.owner, card.controller, card.zone) == (seat, seat, Zone.HAND)
    assert state.players[seat].hand.count(card_id) == 1
    assert card.colors is not opening.CARDS[name]["colors"]
    assert opening.CARDS == rows_before
    after = deepcopy(serialize_match_snapshot(state))
    stripped = deepcopy(after)
    del stripped["cards"][card_id]
    stripped["players"][str(seat)]["hand"].remove(card_id)
    assert stripped == before
    restored = deserialize_match_snapshot(json.loads(json.dumps(after)))
    _assert_printed(restored.cards[card_id], facts)
    assert serialize_match_snapshot(restored) == after
