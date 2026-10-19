from __future__ import annotations

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.heuristics import evaluate_board
from card_data.hydration import hydrate_deck_cards, ready_for_match
from decks.builtin_decks import BUILTIN_DECKS
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.continuous import effective_keywords
from rules_engine.engine import RulesEngine


def test_evaluate_board_rewards_evasive_keyword_creatures() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    upgraded = MatchFactory.from_decks(deck, deck)

    base_id = baseline.players[1].library.pop()
    baseline.players[1].battlefield.append(base_id)
    baseline.cards[base_id].zone = Zone.BATTLEFIELD
    baseline.cards[base_id].types = ["Creature"]
    baseline.cards[base_id].power = 2
    baseline.cards[base_id].toughness = 2
    baseline.cards[base_id].keywords = []

    upgrade_id = upgraded.players[1].library.pop()
    upgraded.players[1].battlefield.append(upgrade_id)
    upgraded.cards[upgrade_id].zone = Zone.BATTLEFIELD
    upgraded.cards[upgrade_id].types = ["Creature"]
    upgraded.cards[upgrade_id].power = 2
    upgraded.cards[upgrade_id].toughness = 2
    upgraded.cards[upgrade_id].keywords = ["Flying", "Lifelink"]

    assert evaluate_board(upgraded, 1) > evaluate_board(baseline, 1)


def test_ai_combat_uses_granted_keywords_from_static_effects() -> None:
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=11)
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    attacker_id = state.players[1].hand.pop()
    attacker = state.cards[attacker_id]
    attacker.name = "Small Deathtouch Creature"
    attacker.types = ["Creature"]
    attacker.zone = Zone.BATTLEFIELD
    attacker.type_line = "Creature — Insect"
    attacker.power = 1
    attacker.toughness = 1
    attacker.summoning_sick = False
    state.players[1].battlefield.append(attacker_id)

    grant_id = state.players[1].hand.pop()
    grant = state.cards[grant_id]
    grant.name = "Deathtouch Anthem"
    grant.types = ["Enchantment"]
    grant.zone = Zone.BATTLEFIELD
    grant.oracle_text = "Creatures you control have deathtouch."
    state.players[1].battlefield.append(grant_id)

    blocker_id = state.players[2].hand.pop()
    blocker = state.cards[blocker_id]
    blocker.name = "Large Blocker"
    blocker.types = ["Creature"]
    blocker.zone = Zone.BATTLEFIELD
    blocker.power = 3
    blocker.toughness = 3
    blocker.summoning_sick = False
    state.players[2].battlefield.append(blocker_id)

    chosen = AIAgent(difficulty="master", archetype="Midrange")._choose_attackers(
        state, [attacker_id], 1
    )

    assert attacker_id in chosen


def test_evaluate_board_penalizes_opponent_planeswalker_pressure() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    pressured = MatchFactory.from_decks(deck, deck)

    walker_id = pressured.players[2].library.pop()
    pressured.players[2].battlefield.append(walker_id)
    pressured.cards[walker_id].zone = Zone.BATTLEFIELD
    pressured.cards[walker_id].types = ["Planeswalker"]
    pressured.cards[walker_id].name = "Teferi, Hero of Dominaria"
    pressured.cards[walker_id].loyalty = 5

    assert evaluate_board(pressured, 1) < evaluate_board(baseline, 1)


def test_evaluate_board_reads_active_face_for_modal_permanents() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    face_a = MatchFactory.from_decks(deck, deck)
    face_b = MatchFactory.from_decks(deck, deck)

    card_a = face_a.players[1].library.pop()
    face_a.players[1].battlefield.append(card_a)
    face_a.cards[card_a].zone = Zone.BATTLEFIELD
    face_a.cards[card_a].name = "MDFC Shell"
    face_a.cards[card_a].types = ["Enchantment"]
    face_a.cards[card_a].selected_face_index = 0
    face_a.cards[card_a].card_faces = [
        {"name": "Front", "type_line": "Sorcery", "oracle_text": "Draw a card."},
        {"name": "Back", "type_line": "Enchantment", "oracle_text": "Creatures you control get +1/+1."},
    ]

    card_b = face_b.players[1].library.pop()
    face_b.players[1].battlefield.append(card_b)
    face_b.cards[card_b].zone = Zone.BATTLEFIELD
    face_b.cards[card_b].name = "MDFC Shell"
    face_b.cards[card_b].types = ["Enchantment"]
    face_b.cards[card_b].selected_face_index = 1
    face_b.cards[card_b].card_faces = [
        {"name": "Front", "type_line": "Sorcery", "oracle_text": "Draw a card."},
        {"name": "Back", "type_line": "Enchantment", "oracle_text": "Creatures you control get +1/+1."},
    ]

    assert evaluate_board(face_b, 1) > evaluate_board(face_a, 1)


def test_evaluate_board_rewards_trigger_engine_permanents() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    engine = MatchFactory.from_decks(deck, deck)

    base_id = baseline.players[1].library.pop()
    baseline.players[1].battlefield.append(base_id)
    baseline.cards[base_id].zone = Zone.BATTLEFIELD
    baseline.cards[base_id].types = ["Enchantment"]
    baseline.cards[base_id].name = "Vanilla Enchantment"
    baseline.cards[base_id].oracle_text = ""

    engine_id = engine.players[1].library.pop()
    engine.players[1].battlefield.append(engine_id)
    engine.cards[engine_id].zone = Zone.BATTLEFIELD
    engine.cards[engine_id].types = ["Enchantment"]
    engine.cards[engine_id].name = "Anointed Procession"
    engine.cards[engine_id].oracle_text = "Whenever a permanent enters the battlefield under your control, draw a card."

    assert evaluate_board(engine, 1) > evaluate_board(baseline, 1)


def test_evaluate_board_rewards_artifact_or_enchantment_engine_permanents() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    baseline = MatchFactory.from_decks(deck, deck)
    engine = MatchFactory.from_decks(deck, deck)

    base_id = baseline.players[1].library.pop()
    baseline.players[1].battlefield.append(base_id)
    baseline.cards[base_id].zone = Zone.BATTLEFIELD
    baseline.cards[base_id].types = ["Artifact"]
    baseline.cards[base_id].name = "Vanilla Artifact"
    baseline.cards[base_id].oracle_text = ""

    engine_id = engine.players[1].library.pop()
    engine.players[1].battlefield.append(engine_id)
    engine.cards[engine_id].zone = Zone.BATTLEFIELD
    engine.cards[engine_id].types = ["Artifact"]
    engine.cards[engine_id].name = "Engine Artifact"
    engine.cards[engine_id].oracle_text = "Whenever an artifact or enchantment enters the battlefield under your control, draw a card."

    assert evaluate_board(engine, 1) > evaluate_board(baseline, 1)


def _control_removal_position(seat):
    decks = []
    for name in ("Dimir Control", "Tempo"):
        rows = [{"quantity": int(q), "card_name": card} for q, card in
                (line.split(" ", 1) for line in BUILTIN_DECKS[name].strip().splitlines())]
        deck = hydrate_deck_cards(None, rows)
        assert sum(row["quantity"] for row in deck) == 60
        assert all(ready_for_match(row) for row in deck)
        decks.append(deck)
    if seat == 2:
        decks.reverse()
    state = MatchFactory.from_decks(*decks, seed=17)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn = 7
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].life = 8
    state.players[3-seat].life = 12
    # Controlled board seam, not a replayed legal episode; preserve canonical cards.
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()

    def place(name, owner, zone):
        card = next(card for card in state.cards.values() if card.owner == owner and card.name == name)
        getattr(state.players[owner], card.zone.value).remove(card.id)
        card.move_to_zone(zone)
        if zone == Zone.BATTLEFIELD:
            card.summoning_sick = False
        getattr(state.players[owner], zone.value).append(card.id)
        return card.id

    removal = place("Go for the Throat", seat, Zone.HAND)
    draw = place("Consider", seat, Zone.HAND)
    island = place("Island", seat, Zone.BATTLEFIELD)
    swamp = place("Swamp", seat, Zone.BATTLEFIELD)
    threat = place("Brazen Borrower", 3-seat, Zone.BATTLEFIELD)
    return state, removal, draw, island, swamp, threat


@pytest.mark.parametrize("seat", [1, 2])
def test_control_ai_prefers_removal_against_evasive_threat(seat) -> None:
    state, removal, draw, island, swamp, threat = _control_removal_position(seat)
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    assert "flying" in effective_keywords(state, threat)
    moves = rules.legal_moves(state, seat)
    assert {removal, draw}.issubset({move.get("card_id") for move in moves if move["type"] == "cast_spell"})
    checked_action(state, rules, seat, {"type": "cast_spell", "card_id": draw, "cost_choice": {"id": "base"}})

    action = complete_action(AIAgent(difficulty="master", archetype="Control").choose_action(state, moves, seat).action)
    assert action["type"] == "cast_spell"
    assert action["card_id"] == removal
    assert action["targets"]["target_card_id"] == threat
    announced = checked_action(state, rules, seat, action)
    assert announced.cards[removal].zone == Zone.STACK
    assert announced.cards[island].tapped and announced.cards[swamp].tapped
    assert announced.stack[-1].payload["mana_spent"] == 2
    restored = deserialize_match_snapshot(before)
    assert serialize_match_snapshot(checked_action(restored, rules, seat, action)) == serialize_match_snapshot(announced)
    for _ in range(2):
        announced = checked_action(announced, rules, announced.priority_player, {"type": "pass_priority"})
    assert announced.cards[threat].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("resource_gap", ["missing_black", "tapped_black", "one_island"])
def test_control_removal_requires_actual_payable_resources(seat, resource_gap):
    state, removal, draw, _, swamp, threat = _control_removal_position(seat)
    if resource_gap == "missing_black":
        # A second canonical Island supplies generic mana, never black mana.
        player = state.players[seat]
        replacement = next(cid for cid in player.library if state.cards[cid].name == "Island")
        player.library.remove(replacement)
        state.cards[replacement].move_to_zone(Zone.BATTLEFIELD)
        player.battlefield.append(replacement)
    if resource_gap == "tapped_black":
        state.cards[swamp].tapped = True
    else:
        state.players[seat].battlefield.remove(swamp)
        state.cards[swamp].move_to_zone(Zone.LIBRARY)
        state.players[seat].library.append(swamp)
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    moves = rules.legal_moves(state, seat)
    assert not any(move["type"] == "cast_spell" and move.get("card_id") == removal for move in moves)
    assert any(move["type"] == "cast_spell" and move.get("card_id") == draw for move in moves)
    with pytest.raises(ActionRejected):
        checked_action(state, rules, seat, {"type": "cast_spell", "card_id": removal,
            "cost_choice": {"id": "base"}, "targets": {"target_card_id": threat}})
    action = complete_action(AIAgent(difficulty="master", archetype="Control").choose_action(state, moves, seat).action)
    assert action.get("card_id") != removal
    checked_action(state, rules, seat, action)
    assert serialize_match_snapshot(state) == before
