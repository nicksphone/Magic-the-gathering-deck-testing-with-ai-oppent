"""Finite official-print birth controls; protocol corruptions are not card facts."""
from copy import deepcopy
import hashlib
import json

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_copy_stack_characteristics as fixture


# Exact complete objects independently joined to the frozen public bulk invoice.
PRINTS = {
    "Bonecrusher Giant // Stomp": "d4d02d17fad14ea9b121cc0e98393366c358ad1cb304350b737a6cfbf695793b",
    "Valki, God of Lies // Tibalt, Cosmic Impostor": "d80ea2f2f24553eab6a38eed713e7db353ad3d366192e07ca9fdb68d418b574e",
    "Fire // Ice": "0ca740bbc3dc520898d7bdc9fdaf4b086e1da8d709db243e65c23482c4f8e6b8",
    "Negate": "90d37bb8ead523ea99cf40dff8eeb4187dd55f400a32ce4769c1001dc943b92c",
    "Spell Pierce": "ca07e889cb4b40d255d843a5c20f9882bb6391bc0b9fe24f7ecab903d4a0db9d",
    "Spell Snare": "2f0f4af22148e00a70f4aa492e7547287cc68529e8ca8fd0aad36c1c959cf174",
    "Disdainful Stroke": "21d28ec55e76e26b631c281c2920a40af831e813b783bc950c370f47cecfb591",
}
PARENTS = [
    ("Bonecrusher Giant // Stomp", 1),
    ("Valki, God of Lies // Tibalt, Cosmic Impostor", 1),
    ("Fire // Ice", 0),
]
COUNTERS = ["Negate", "Spell Pierce", "Spell Snare", "Disdainful Stroke"]
FIELDS = (
    "name", "mana_cost", "type_line", "types", "power", "toughness",
    "printed_power", "printed_toughness", "loyalty", "oracle_text", "keywords", "colors",
)


def _same(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key in expected:
            _same(actual[key], expected[key])
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for value, wanted in zip(actual, expected):
            _same(value, wanted)
    else:
        assert actual == expected


def _raw(name):
    raw = fixture.FACES.get(name) or fixture.SPLITS.get(name) or fixture.COUNTERS[name]
    _pinned(raw)
    return raw


def _pinned(raw):
    data = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(data).hexdigest() == PRINTS[raw["name"]]


def _image(raw):
    # All seven selected printings have this independently verified normal image.
    return (raw.get("image_uris") or raw["card_faces"][0]["image_uris"])["normal"]


def _faces(raw):
    return [
        {**deepcopy(face), **{key: face.get(key) for key in (
            "name", "mana_cost", "type_line", "oracle_text", "power", "toughness", "loyalty", "colors",
        )}, "image_uri": (face.get("image_uris") or {}).get("normal")}
        for face in raw.get("card_faces", [])
    ]


def _printed(raw, selected=None):
    """Independent finite RAW oracle, not a call to inference or normalization."""
    front = (raw.get("card_faces") or [{}])[0]
    modal = raw["layout"] == "modal_dfc"
    surface = raw["card_faces"][selected] if selected is not None else (front if modal else raw)
    kinds = (["Planeswalker"] if selected is not None and modal else
             ["Creature"] if modal or selected is None and raw["layout"] == "adventure" else ["Instant"])
    return {
        "name": surface["name"],
        "mana_cost": surface.get("mana_cost") or front.get("mana_cost", ""),
        "type_line": surface["type_line"],
        "types": kinds,
        "power": int(surface["power"]) if surface.get("power") is not None else None,
        "toughness": int(surface["toughness"]) if surface.get("toughness") is not None else None,
        "printed_power": surface.get("power"),
        "printed_toughness": surface.get("toughness"),
        "loyalty": int(surface["loyalty"]) if surface.get("loyalty") is not None else None,
        "oracle_text": surface.get("oracle_text") or front.get("oracle_text", ""),
        "keywords": [],
        "colors": deepcopy(surface.get("colors")),
    }


def _native(card, raw):
    expected = _printed(raw)
    physical = {**expected, "card_faces": _faces(raw), "layout": raw["layout"],
                "selected_face_index": None, "image_uri": _image(raw)}
    _same({key: getattr(card, key) for key in physical}, physical)
    _same(card.characteristic_record, {
        "version": 1, "physical": physical, "values": expected,
    })


def _row(row, raw, quantity):
    front = (raw.get("card_faces") or [{}])[0]
    faces = _faces(raw)
    normalized_keys = ("name", "mana_cost", "type_line", "oracle_text", "power",
                       "toughness", "loyalty", "colors", "image_uri")
    expected = {
        **deepcopy(raw), "card_name": raw["name"], "quantity": quantity,
        "scryfall_id": raw["id"], "image_uri": _image(raw),
        "oracle_text": raw.get("oracle_text") or front.get("oracle_text", ""),
        "mana_cost": raw.get("mana_cost") or front.get("mana_cost", ""),
        "power": raw.get("power") or front.get("power"),
        "toughness": raw.get("toughness") or front.get("toughness"),
        "loyalty": raw.get("loyalty") if raw.get("loyalty") is not None else front.get("loyalty"),
        "colors": raw.get("colors") or front.get("colors", []), "card_faces": faces,
        "legalities_json": json.dumps(raw.get("legalities", {})),
        "rulings_json": "[]",
        "card_faces_json": json.dumps([{key: face[key] for key in normalized_keys} for face in faces]),
    }
    _same(row, expected)


def _roundtrip(state):
    before = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(before)))
    _same(serialize_match_snapshot(restored), before)
    return restored


def _observe_normalizer(monkeypatch, name):
    genuine = ScryfallSyncService._normalize_payload
    calls = []

    def observe(cls, *args, **kwargs):
        raw = args[0]
        assert raw["name"] == name
        _pinned(raw)
        assert args[1] == _image(raw)
        before = deepcopy(raw)
        result = genuine(*args, **kwargs)
        _same(raw, before)
        calls.append(name)
        return result

    monkeypatch.setattr(ScryfallSyncService, "_normalize_payload", classmethod(observe))
    return calls


@pytest.mark.parametrize("name", list(PRINTS))
def test_selected_table_is_the_complete_pinned_official_object(name):
    _raw(name)


@pytest.mark.parametrize("name,face", PARENTS)
def test_actual_surviving_copy_birth_and_selected_snapshot(monkeypatch, name, face):
    raw = deepcopy(_raw(name))
    calls = _observe_normalizer(monkeypatch, name)
    genuine = MatchFactory.from_decks
    births = []

    def observe(cls, *args, **kwargs):
        assert kwargs == {"seed": 151}
        for deck in args:
            assert len(deck) == 1 and deck[0]["quantity"] == 60
            _row(deck[0], raw, 60)
        state = genuine(*args, **kwargs)
        assert set(state.cards) == {f"p{pid}-{i:03d}" for pid in (1, 2) for i in range(1, 61)}
        for card in state.cards.values():
            _native(card, raw)
        assert len(state.sideboard_facts["inventory"]) == 120
        _same(state.starting_decks, {1: args[0], 2: args[1]})
        births.append(deepcopy(state.sideboard_facts["inventory"]))
        return state

    monkeypatch.setattr(MatchFactory, "from_decks", classmethod(observe))
    state, source_id, copy_id = fixture.surviving_copy(name, face)
    assert calls == [name] and len(births) == 1
    _same(state.sideboard_facts["inventory"], births[0])
    source = state.cards[source_id]
    assert source.zone == Zone.GRAVEYARD and source.owner == source.controller == 1
    _native(source, raw)
    item = next(item for item in state.stack if item.id == copy_id)
    assert item.controller == 2 and item.source_card_id == source_id
    assert item.payload["__stack_copy_kind"] == "spell"
    copied = item.payload["__copied_card"]
    _same({key: copied[key] for key in FIELDS}, _printed(raw, face))
    assert copied["selected_face_index"] == face
    _same(copied["card_faces"], _faces(raw))
    _roundtrip(state)
    _same(_raw(name), raw)


@pytest.mark.parametrize("name", COUNTERS)
def test_actual_add_counter_uses_full_native_birth_without_stock_reseal(monkeypatch, name):
    parent, face = PARENTS[1] if name == "Disdainful Stroke" else PARENTS[0]
    state, _, _ = fixture.surviving_copy(parent, face)
    raw = deepcopy(_raw(name))
    inventory = deepcopy(state.sideboard_facts["inventory"])
    decks = deepcopy(state.starting_decks)
    rng = state.rng.getstate()
    calls = _observe_normalizer(monkeypatch, name)
    genuine = MatchFactory.from_decks
    births = []

    def observe(cls, *args, **kwargs):
        assert kwargs == {"seed": 0} and args[1] == []
        assert len(args[0]) == 1 and args[0][0]["quantity"] == 8
        _row(args[0][0], raw, 8)
        sample = genuine(*args, **kwargs)
        for card in sample.cards.values():
            _native(card, raw)
        births.append(sample)
        return sample

    monkeypatch.setattr(MatchFactory, "from_decks", classmethod(observe))
    card = fixture.add_counter(state, name)
    assert calls == [name] and len(births) == 1
    assert card.id == "counter" and card.owner == card.controller == 1
    assert card.zone == Zone.HAND and card.id in state.players[1].hand
    assert len(state.cards) == 121 and card.instance_order == 0
    _native(card, raw)
    _same(state.sideboard_facts["inventory"], inventory)
    _same(state.starting_decks, decks)
    assert state.rng.getstate() == rng
    restored = _roundtrip(state)
    _native(restored.cards[card.id], raw)
    _same(_raw(name), raw)


def test_real_unknown_counter_cast_invalidates_coverage_not_original_inventory():
    state, _, copy_id = fixture.surviving_copy()
    inventory = deepcopy(state.sideboard_facts["inventory"])
    decks = deepcopy(state.starting_decks)
    card = fixture.add_counter(state, "Negate")
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card.id,
        "targets": {"target_stack_id": copy_id, "pay_unless_counter": False},
    })
    assert resolve_top_of_stack(state)
    assert state.stack == []
    _same(state.sideboard_facts["inventory"], inventory)
    _same(state.starting_decks, decks)
    assert card.id not in state.sideboard_facts["inventory"]
    assert state.sideboard_facts["coverage_ok"] is False
    assert state.sideboard_facts["complete"] is False
    _roundtrip(state)


@pytest.mark.parametrize("field,value", [("keywords", ["Flying"]), ("power", 1)])
def test_protocol_coherent_printed_corruption_is_rejected(field, value):
    """Unwaived oracle mutation control, not an alternative Negate printing."""
    state, _, _ = fixture.surviving_copy()
    card = deepcopy(fixture.add_counter(state, "Negate"))
    setattr(card, field, deepcopy(value))
    card.characteristic_record["physical"][field] = deepcopy(value)
    card.characteristic_record["values"][field] = deepcopy(value)
    with pytest.raises(AssertionError):
        _native(card, _raw("Negate"))
