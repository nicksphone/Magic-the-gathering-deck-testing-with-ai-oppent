"""Full printed loyalty admission and real wheel execution, not body projection."""
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body, compile_instruction
from rules_engine.engine import RulesEngine
from rules_engine.library_permissions import creature_types
from tests.test_legendary_channels import resolve_to_choice
from tests.test_wheel_draw import ROWS, canonical, setup


RAW = Path(__file__).parent / "fixtures/chandra_complete"


def full_card(state, file, seat, zone):
    raw = json.loads((RAW / file).read_text())
    sample = MatchFactory.from_decks([{**raw, "card_name": raw["name"], "quantity": 1}], [], seed=7)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


@pytest.mark.parametrize("seat", [1, 2])
def test_full_canonical_card_offers_every_printed_loyalty_ability(seat):
    state, source, _, _ = setup("Chandra Ablaze", seat, cast=False)
    source.loyalty = 7
    assert source.oracle_text == ROWS["Chandra Ablaze"]["oracle_text"]
    offered = RulesEngine().legal_moves(state, seat)
    assert {move["ability_index"] for move in offered
            if move["type"] == "activate_loyalty" and move["card_id"] == source.id} == {0, 1, 2}


@pytest.mark.parametrize("seat", [1, 2])
def test_actual_canonical_minus_two_discards_and_refills_both_players(seat):
    state, source, hands, action = setup("Chandra Ablaze", seat, cast=False)
    original_text = source.oracle_text
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, action))
    assert {pid: len(player.hand) for pid, player in state.players.items()} == {1: 3, 2: 3}
    assert state.discards_this_turn == {seat: 3, 3 - seat: 5}
    assert all(state.cards[card.id].zone.value == "graveyard"
               for cards in hands.values() for card in cards)
    assert state.cards[source.id].loyalty == 3
    assert state.cards[source.id].oracle_text == original_text


@pytest.mark.parametrize("index", [0, 1, 2])
def test_every_actual_printed_clause_requires_complete_compilation(index):
    text = ROWS["Chandra Ablaze"]["oracle_text"]
    body = text.splitlines()[index].split(": ", 1)[1]
    assert compile_instruction(body, "Chandra Ablaze") is not None


@pytest.mark.parametrize("index", [0, 1, 2])
def test_unknown_instruction_suffix_still_rejects_entire_surface(index):
    lines = ROWS["Chandra Ablaze"]["oracle_text"].splitlines()
    lines[index] += " An unrecognized instruction must not be discarded."
    assert compile_body("\n".join(lines), "Chandra Ablaze") is None


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("discard", ["red", "nonred", "empty"])
def test_conditional_damage_requires_actual_matching_discard(seat, discard):
    state, source, _, _ = setup("Chandra Ablaze", seat, sizes=(0, 0), cast=False)
    chosen = (full_card(state, "lightning-bolt.raw.json", seat, Zone.HAND)
              if discard == "red" else canonical(state, "Windfall", seat, Zone.HAND)
              if discard == "nonred" else None)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": 0,
        "targets": {"target_player": 3 - seat},
    }))
    if chosen is not None:
        assert state.pending_mechanic_choice["kind"] == "discard"
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), 3 - seat, {
                "type": "choose_mechanic", "card_ids": [chosen.id],
            })
        assert serialize_match_snapshot(state) == before
        state = deserialize_match_snapshot(before)
        state = checked_action(state, RulesEngine(), seat, {
            "type": "choose_mechanic", "card_ids": [chosen.id],
        })
        assert state.cards[chosen.id].zone == Zone.GRAVEYARD
    assert not state.pending_mechanic_choice
    assert state.players[3 - seat].life == (16 if discard == "red" else 20)
    assert state.cards[source.id].loyalty == 6


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("count", [0, 1, 2])
def test_deliberate_zero_one_or_two_free_casts_retain_resolution(seat, count):
    state, source, _, _ = setup("Chandra Ablaze", seat, cast=False)
    source.loyalty = 7
    state.players[seat].mana_pool = {color: 0 for color in "WUBRGC"}
    first = full_card(state, "dragon-fodder.raw.json", seat, Zone.GRAVEYARD)
    second = full_card(state, "lightning-bolt.raw.json", seat, Zone.GRAVEYARD)
    blue = canonical(state, "Windfall", seat, Zone.GRAVEYARD)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": 2,
    }))
    assert state.pending_mechanic_choice["kind"] == "effect_cast"
    offered = RulesEngine().legal_moves(state, seat)
    assert {move["card_id"] for move in offered if move["type"] == "cast_spell"} == {first.id, second.id}
    assert not any(move.get("card_id") == blue.id for move in offered)
    original_frame = state.pending_mechanic_choice["resolving_item"]
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            "type": "cast_spell", "card_id": blue.id, "from_graveyard": True,
        })
    assert serialize_match_snapshot(state) == before
    for index, card in enumerate([first, second][:count]):
        targets = {} if index == 0 else {"target_player": 3 - seat}
        state = checked_action(state, RulesEngine(), seat, {
            "type": "cast_spell", "card_id": card.id, "from_graveyard": True,
            "targets": targets,
        })
        if index == 0:
            assert state.pending_mechanic_choice["resolving_item"] == original_frame
            assert state.cards[first.id].zone == Zone.STACK
            state = deserialize_match_snapshot(serialize_match_snapshot(state))
    if count < 2:
        state = checked_action(state, RulesEngine(), seat, {
            "type": "choose_mechanic", "card_ids": ["decline"],
        })
    assert not state.pending_mechanic_choice
    state = resolve_to_choice(state)
    goblins = [state.cards[cid] for cid in state.players[seat].battlefield
               if state.cards[cid].is_token and "goblin" in creature_types(state.cards[cid], state)]
    assert len(goblins) == (2 if count else 0)
    assert state.players[3 - seat].life == (17 if count == 2 else 20)
    assert state.cards[second.id].zone == Zone.GRAVEYARD
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert all(value == 0 for value in state.players[seat].mana_pool.values())


@pytest.mark.parametrize("seat", [1, 2])
def test_red_discard_replaced_by_exile_still_satisfies_actual_condition(seat):
    state, source, _, _ = setup("Chandra Ablaze", seat, sizes=(0, 0), cast=False)
    red = full_card(state, "lightning-bolt.raw.json", seat, Zone.HAND)
    full_card(state, "../mass_exile_product/rest-in-peace.json", 3 - seat, Zone.BATTLEFIELD)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": 0,
        "targets": {"target_player": 3 - seat},
    }))
    state = checked_action(state, RulesEngine(), seat, {
        "type": "choose_mechanic", "card_ids": [red.id],
    })
    assert state.cards[red.id].zone == Zone.EXILE
    assert state.players[3 - seat].life == 16


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("mana", [0, 1])
def test_free_cast_waiver_does_not_waive_actual_noncreature_tax(seat, mana):
    state, source, _, _ = setup("Chandra Ablaze", seat, cast=False)
    source.loyalty = 7
    state.players[seat].mana_pool = {color: 0 for color in "WUBRGC"}
    state.players[seat].mana_pool["C"] = mana
    full_card(state, "thalia.raw.json", 3 - seat, Zone.BATTLEFIELD)
    spell = full_card(state, "dragon-fodder.raw.json", seat, Zone.GRAVEYARD)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": 2,
    }))
    cast = {"type": "cast_spell", "card_id": spell.id, "from_graveyard": True}
    if mana:
        state = checked_action(state, RulesEngine(), seat, cast)
        assert state.players[seat].mana_pool["C"] == 0
        state = resolve_to_choice(state)
        assert len([cid for cid in state.players[seat].battlefield if state.cards[cid].is_token]) == 2
    else:
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, cast)
        assert serialize_match_snapshot(state) == before
        state = checked_action(state, RulesEngine(), seat, {
            "type": "choose_mechanic", "card_ids": ["decline"],
        })
        assert state.cards[spell.id].zone == Zone.GRAVEYARD
        assert not any(state.cards[cid].is_token for cid in state.players[seat].battlefield)


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_actual_paid_stifle_counters_each_ability_without_refunding_loyalty(seat, index):
    state, source, _, _ = setup("Chandra Ablaze", seat, cast=False)
    source.loyalty = 7
    state.players[3 - seat].mana_pool["U"] = 1
    stifle = full_card(state, "stifle.raw.json", 3 - seat, Zone.HAND)
    before_hands = {pid: list(player.hand) for pid, player in state.players.items()}
    targets = {"target_player": 3 - seat} if index == 0 else {}
    state = checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": index,
        "targets": targets,
    })
    ability_id = state.stack[-1].id
    state = checked_action(state, RulesEngine(), seat, {"type": "pass_priority"})
    state = checked_action(state, RulesEngine(), 3 - seat, {
        "type": "cast_spell", "card_id": stifle.id,
        "targets": {"target_stack_id": ability_id},
    })
    state = resolve_to_choice(state)
    assert not state.stack and not state.pending_mechanic_choice
    assert state.players[3 - seat].life == 20
    assert state.players[3 - seat].mana_pool["U"] == 0
    assert list(state.players[seat].hand) == before_hands[seat]
    assert list(state.players[3 - seat].hand) == [cid for cid in before_hands[3 - seat] if cid != stifle.id]
    assert state.cards[source.id].loyalty == (8 if index == 0 else 5 if index == 1 else 0)
    assert state.cards[source.id].zone == (Zone.GRAVEYARD if index == 2 else Zone.BATTLEFIELD)


@pytest.mark.parametrize("seat", [1, 2])
def test_retained_cast_permission_rejects_trusted_reentry_protocol(seat):
    state, source, _, _ = setup("Chandra Ablaze", seat, cast=False)
    source.loyalty = 7
    spell = full_card(state, "dragon-fodder.raw.json", seat, Zone.GRAVEYARD)
    state = resolve_to_choice(checked_action(state, RulesEngine(), seat, {
        "type": "activate_loyalty", "card_id": source.id, "ability_index": 2,
    }))
    # Object-reference boundary only, not an HTTP-causal blink or response episode.
    state.players[seat].graveyard.remove(spell.id)
    state.cards[spell.id].move_to_zone(Zone.EXILE)
    state.cards[spell.id].move_to_zone(Zone.GRAVEYARD)
    state.players[seat].graveyard.append(spell.id)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, {
            "type": "cast_spell", "card_id": spell.id, "from_graveyard": True,
        })
    assert serialize_match_snapshot(state) == before
