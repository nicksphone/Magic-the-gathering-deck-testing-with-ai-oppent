from __future__ import annotations

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot, serialize_match
from game_state.state import CardInstance, MatchFactory, Step, Zone, _infer_keywords
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.continuous import has_keyword
from rules_engine import combat


def _state():
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=81)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    for cid, owner, name, power, toughness, keywords in (
        ("hero", 1, "Benalish Hero", 1, 1, ["banding"]),
        ("angel", 1, "Serra Angel", 4, 4, ["flying", "vigilance"]),
        ("elf", 1, "Llanowar Elves", 1, 1, []),
        ("bears", 2, "Grizzly Bears", 2, 2, []),
    ):
        state.cards[cid] = CardInstance(
            id=cid, name=name, owner=owner, controller=owner, zone=Zone.BATTLEFIELD,
            types=["Creature"], power=power, toughness=toughness,
            keywords=keywords, summoning_sick=False,
        )
        state.players[owner].battlefield.append(cid)
    return state


def test_attack_band_survives_snapshot_and_propagates_block_to_flyer():
    state = _state()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "attack", "attackers": ["hero", "angel"], "bands": [["hero", "angel"]],
    })
    assert state.attack_bands == [["hero", "angel"]]
    assert serialize_match(state)["attack_bands"] == [["hero", "angel"]]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.attack_bands == [["hero", "angel"]]
    assert not combat._can_block_attacker(state, state.cards["angel"], state.cards["bears"])
    combat.declare_blockers(state, {"hero": ["bears"]})
    assert state.blocks == {"hero": ["bears"], "angel": ["bears"]}


@pytest.mark.parametrize("bands,targets", [
    ([["hero", "angel", "elf"]], {}),
    ([["angel", "elf"]], {}),
    ([["hero"]], {}),
    ([["hero", "angel"], ["hero", "elf"]], {}),
    ([["hero", "angel"]], {"hero": "player:2", "angel": "player:1"}),
])
def test_invalid_attack_bands_reject_without_mutation(bands, targets):
    state = _state()
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "attack", "attackers": ["hero", "angel", "elf"],
            "bands": bands, "attack_targets": targets,
        })
    assert serialize_match_snapshot(state) == before


def test_empty_attackers_cannot_create_band():
    state = _state()
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {"type": "attack", "attackers": [], "bands": [["hero", "angel"]]})


def test_band_persists_when_banding_lost_after_declaration():
    state = _state()
    state = checked_action(state, RulesEngine(), 1, {
        "type": "attack", "attackers": ["hero", "angel"], "bands": [["hero", "angel"]],
    })
    state.cards["hero"].keywords = []
    combat.declare_blockers(state, {"hero": ["bears"]})
    assert state.blocks["angel"] == ["bears"]


def test_oracle_inference_distinguishes_ordinary_banding_from_bands_with_other():
    assert "banding" in _infer_keywords("Banding (Any creatures with banding can attack in a band.)")
    assert "banding" not in _infer_keywords("Phasing, fading 3, bands with other Dinosaurs, flanking")

    hero = {"quantity": 60, "card_name": "Benalish Hero", "type_line": "Creature — Human Soldier", "oracle_text": "Banding", "power": 1, "toughness": 1}
    state = MatchFactory.from_decks([hero], [hero], seed=82)
    assert all("banding" in state.cards[cid].keywords for cid in state.players[1].library + state.players[1].hand)
    hero_id = state.players[1].hand.pop()
    state.players[1].battlefield.append(hero_id)
    state.cards[hero_id].zone = Zone.BATTLEFIELD
    assert has_keyword(state, hero_id, "banding")

    fogey = {"quantity": 60, "card_name": "Old Fogey", "type_line": "Summon — Dinosaur", "oracle_text": "Phasing, fading 3, bands with other Dinosaurs, flanking", "keywords": ["Banding"], "power": 7, "toughness": 7}
    state = MatchFactory.from_decks([fogey], [hero], seed=83)
    assert all("banding" not in state.cards[cid].keywords for cid in state.players[1].library + state.players[1].hand)
    fogey_id = state.players[1].hand.pop()
    state.players[1].battlefield.append(fogey_id)
    state.cards[fogey_id].zone = Zone.BATTLEFIELD
    assert not has_keyword(state, fogey_id, "banding")
