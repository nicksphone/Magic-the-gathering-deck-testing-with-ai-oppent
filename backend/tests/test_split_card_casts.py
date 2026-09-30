"""Canonical Scryfall split-card casts use one half on the stack."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from effects.handlers import counter_spell
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.coverage import deck_pair_coverage
from rules_engine.colors import card_color_symbols
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.targeting import validate_cast_targets


CARDS = {row["name"]: row for row in json.loads((Path(__file__).parent / "fixtures/split_cards.json").read_text())}


def split_state(name: str):
    row = CARDS[name]
    deck = [{"quantity": 60, "card_name": name, **row, "oracle_text": row["card_faces"][0]["oracle_text"]}]
    state = MatchFactory.from_decks(deck, deck, seed=149)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    return state, state.players[1].hand[0]


def test_fire_half_uses_its_own_cost_and_restores_combined_identity() -> None:
    state, card_id = split_state("Fire // Ice")
    assert card_color_symbols(state.cards[card_id]) == {"R", "U"}
    state.players[1].mana_pool.update({"C": 1, "R": 1})
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "cast_spell" and move["card_id"] == card_id]
    assert [(move["card_name"], move["selected_face_index"], move["mana_cost"]) for move in moves] == [
        ("Fire", 0, "{1}{R}"),
    ]
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 0,
        "targets": {"target_distribution": {"2": 2}, "divide_total": 2},
    })
    assert (state.cards[card_id].name, state.cards[card_id].mana_cost, state.cards[card_id].types) == (
        "Fire", "{1}{R}", ["Instant"],
    )
    assert card_color_symbols(state.cards[card_id]) == {"R"}
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 18
    assert state.cards[card_id].zone == Zone.GRAVEYARD
    assert (state.cards[card_id].name, state.cards[card_id].mana_cost) == (
        "Fire // Ice", "{1}{R} // {1}{U}",
    )
    assert card_color_symbols(state.cards[card_id]) == {"R", "U"}


def test_ice_half_taps_target_and_draws_with_blue_mana() -> None:
    state, card_id = split_state("Fire // Ice")
    state.players[1].mana_pool.update({"C": 1, "U": 1})
    target = CardInstance("target-island", "Island", 2, 2, Zone.BATTLEFIELD, ["Land"], type_line="Basic Land — Island")
    state.cards[target.id] = target
    state.players[2].battlefield.append(target.id)
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "cast_spell" and move["card_id"] == card_id]
    assert [(move["card_name"], move["selected_face_index"], move["mana_cost"]) for move in moves] == [
        ("Ice", 1, "{1}{U}"),
    ]
    hand_before = len(state.players[1].hand)
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        "targets": {"target_card_id": target.id},
    })
    assert state.cards[card_id].name == "Ice"
    assert resolve_top_of_stack(state)
    assert target.id in state.players[2].battlefield and state.cards[target.id].tapped
    assert len(state.players[1].hand) == hand_before
    assert state.cards[card_id].zone == Zone.GRAVEYARD
    assert state.cards[card_id].name == "Fire // Ice"


def test_countered_normal_split_half_restores_combined_graveyard_identity() -> None:
    state, card_id = split_state("Fire // Ice")
    state.players[1].mana_pool.update({"C": 1, "R": 1})
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 0,
        "targets": {"target_distribution": {"2": 2}, "divide_total": 2},
    })
    counter_spell(state, 2, {"target_stack_id": state.stack[-1].id})
    assert state.cards[card_id].zone == Zone.GRAVEYARD
    assert (state.cards[card_id].name, state.cards[card_id].mana_cost) == (
        "Fire // Ice", "{1}{R} // {1}{U}",
    )
    assert state.players[2].life == 20


def test_opponent_turn_only_offers_instant_half() -> None:
    state, card_id = split_state("Incubation // Incongruity")
    assert set(state.cards[card_id].types) == {"Instant", "Sorcery"}
    state.active_player = 2
    state.players[1].mana_pool.update({"C": 1, "G": 1, "U": 1})
    target = CardInstance("target-creature", "Grizzly Bears", 2, 2, Zone.BATTLEFIELD,
                          ["Creature"], power=2, toughness=2)
    state.cards[target.id] = target
    state.players[2].battlefield.append(target.id)
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move["type"] == "cast_spell" and move["card_id"] == card_id]
    assert [(move["card_name"], move["selected_face_index"]) for move in moves] == [("Incongruity", 1)]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "cast_spell", "card_id": card_id, "selected_face_index": 0,
        })
    assert serialize_match_snapshot(state) == before


def test_fire_rejects_more_than_two_announced_recipients() -> None:
    state, card_id = split_state("Fire // Ice")
    state.players[1].mana_pool.update({"C": 1, "R": 1})
    target = CardInstance("third-target", "Grizzly Bears", 2, 2, Zone.BATTLEFIELD,
                          ["Creature"], power=2, toughness=2)
    state.cards[target.id] = target
    state.players[2].battlefield.append(target.id)
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move["type"] == "cast_spell" and move["card_id"] == card_id)
    targets = {"target_distribution": {"1": 1, "2": 1, target.id: 1}, "divide_total": 3}
    assert validate_cast_targets(move["target_hints"], targets) == (
        False, "Too many division targets selected (max 2).",
    )
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "cast_spell", "card_id": card_id, "selected_face_index": 0, "targets": targets,
        })
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize("stale_kind", ["missing_layout", "legacy_empty_colors"])
def test_match_hydration_backfills_stale_faces_from_local_canonical_data(monkeypatch, stale_kind) -> None:
    from card_data.sync import ScryfallSyncService
    from main import _hydrate_deck_cards

    raw = CARDS["Fire // Ice"]

    class FakeRepo:
        def __init__(self):
            faces = [{**face, "colors": []} for face in raw["card_faces"]] if stale_kind == "legacy_empty_colors" else raw["card_faces"]
            self.row = SimpleNamespace(
                name=raw["name"], scryfall_id=raw["id"], oracle_text="", mana_cost=raw["mana_cost"],
                type_line="Instant", layout="split" if stale_kind == "legacy_empty_colors" else "", image_uri="/card-images/old.svg", colors="R,U",
                card_faces_json=json.dumps(faces), power=None, toughness=None, loyalty=None,
            )
            self.upserts = 0

        def get_cached_cards_by_names(self, names):
            return {raw["name"].lower(): self.row} if raw["name"] in names else {}

        def get_cached_card_by_name(self, name):
            return self.row if name == raw["name"] else None

        def get_card_knowledge(self, name):
            return SimpleNamespace(
                oracle_source="scryfall", scryfall_id=raw["id"],
                profiles_json=json.dumps({"card_data": {**raw, "object": "card"}}),
            ) if name == raw["name"] else None

        def upsert_card(self, payload):
            self.upserts += 1
            for key, value in payload.items():
                setattr(self.row, key, value)
            return self.row

    def no_network(*args, **kwargs):
        raise AssertionError("Canonical local card data should avoid a network request")

    monkeypatch.setattr(ScryfallSyncService, "sync_card_by_name", no_network)
    repo = FakeRepo()
    deck = [{"quantity": 60, "card_name": raw["name"]}]
    first = _hydrate_deck_cards(repo, deck)
    second = _hydrate_deck_cards(repo, deck)
    assert first[0]["layout"] == second[0]["layout"] == "split"
    assert first[0]["card_faces"][1]["name"] == "Ice"
    assert first[0]["card_faces"][1]["colors"] is None
    assert repo.upserts == 1


def test_split_face_color_fallback_does_not_inherit_the_other_halfs_color():
    from card_data.sync import ScryfallSyncService
    state, card_id = split_state("Fire // Ice")
    state.cards[card_id].card_faces = ScryfallSyncService.__new__(ScryfallSyncService)._normalize_faces(
        state.cards[card_id].card_faces,
    )
    state.players[1].mana_pool.update({"C": 1, "U": 1})
    target = CardInstance("master", "Master of Waves", 2, 2, Zone.BATTLEFIELD, ["Creature"],
                          power=2, toughness=1, oracle_text="Protection from red")
    state.cards[target.id] = target
    state.players[2].battlefield.append(target.id)
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        "targets": {"target_card_id": target.id},
    })
    assert card_color_symbols(state.cards[card_id]) == {"U"}
    assert resolve_top_of_stack(state)
    assert state.cards[target.id].tapped
    assert card_color_symbols(state.cards[card_id]) == {"R", "U"}


def test_split_off_stack_colors_union_faces_when_top_level_metadata_is_missing():
    state, card_id = split_state("Fire // Ice")
    card = state.cards[card_id]
    card.colors = None
    card.card_faces = [{**card.card_faces[0], "colors": ["R"]}, {**card.card_faces[1], "colors": ["U"]}]
    assert card_color_symbols(card) == {"R", "U"}


@pytest.mark.parametrize("half,pool", [
    ("Fire", {"C": 1, "R": 1}),
    ("Ice", {"C": 1, "U": 1}),
])
def test_ai_materializes_a_castable_split_half(half: str, pool: dict[str, int]) -> None:
    state, card_id = split_state("Fire // Ice")
    state.players[1].mana_pool.update(pool)
    target = CardInstance("target-island", "Island", 2, 2, Zone.BATTLEFIELD,
                          ["Land"], type_line="Basic Land — Island")
    state.cards[target.id] = target
    state.players[2].battlefield.append(target.id)
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, 1)
                if move["type"] == "cast_spell" and move["card_id"] == card_id and move["card_name"] == half)
    action = AIAgent(difficulty="master", archetype="Tempo")._materialize_action(state, move, 1)
    assert action["selected_face_index"] == (0 if half == "Fire" else 1)
    state = checked_action(state, rules, 1, action)
    assert state.stack[-1].label == half


def test_preflight_warns_about_unimplemented_fuse() -> None:
    deck_a = [{"quantity": 4, "card_name": name, **CARDS[name]} for name in (
        "Toil // Trouble", "Commit // Memory",
    )]
    report = deck_pair_coverage(deck_a, [])
    assert [(entry["card_name"], entry["mechanics"]) for entry in report["known_unsupported_cards"]] == [
        ("Toil // Trouble", ["fuse"]),
    ]


def test_aftermath_half_cannot_be_cast_from_hand() -> None:
    state, card_id = split_state("Commit // Memory")
    state.players[1].mana_pool.update({"C": 6, "U": 2})
    moves = [move for move in RulesEngine().legal_moves(state, 1)
             if move["type"] == "cast_spell" and move["card_id"] == card_id]
    assert all(move["selected_face_index"] == 0 for move in moves)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        })
    assert serialize_match_snapshot(state) == before
